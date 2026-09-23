from pathlib import Path
import json

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_file,
)

from app.metrics import evaluate_professors
from app.qualis import QualisDB
from app.export import (
    make_json_safe,
)

from app.export_excel import (
    export_excel,
)
from app.qualis_overrides import (
    VALID_QUALIS,
    get_override,
    remove_override,
    set_override,
)
from app.publication_flags import (
    get_student_flag,
    set_student_flag,
)


ROOT = Path(__file__).resolve().parent.parent


DATA_FILE = (
    ROOT
    / "output"
    / "2026"
    / "dados.json"
)


app = Flask(__name__)


QUALIS_DB = QualisDB()


def load_data():
    with DATA_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def get_default_period(data):
    config = data.get(
        "configuracao",
        {},
    )

    start_year = config.get(
        "evaluation_start_year"
    )

    end_year = config.get(
        "evaluation_end_year"
    )

    if start_year is None:
        end_year = config.get(
            "reference_year",
            2026,
        )

        start_year = (
            end_year - 3
        )

    return (
        int(start_year),
        int(end_year),
    )


def get_default_min_score(data):
    config = data.get(
        "configuracao",
        {},
    )

    return float(
        config.get(
            "min_score",
            4.0,
        )
    )


def normalize_doi(doi):
    value = str(
        doi or ""
    ).strip().lower()

    if not value:
        return ""

    prefixes = [
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi:",
    ]

    for prefix in prefixes:
        if value.startswith(prefix):
            value = value[len(prefix):]
            break

    return value.rstrip(
        ".,;:)]}>"
    )


def find_publication(
    data,
    doi=None,
    title=None,
    year=None,
):
    publications = []

    for lattes in data.get(
        "lattes_data",
        [],
    ):
        for publication in lattes.get(
            "publications",
            [],
        ):
            publications.append(
                publication
            )

    requested_doi = normalize_doi(
        doi
    )

    if requested_doi:
        for publication in publications:
            publication_doi = (
                normalize_doi(
                    publication.get(
                        "doi"
                    )
                )
            )

            if (
                publication_doi
                and publication_doi
                == requested_doi
            ):
                return publication

    requested_title = " ".join(
        str(
            title or ""
        )
        .strip()
        .lower()
        .split()
    )

    requested_year = str(
        year or ""
    ).strip()

    if requested_title:
        for publication in publications:
            publication_title = (
                " ".join(
                    str(
                        publication.get(
                            "title",
                            "",
                        )
                    )
                    .strip()
                    .lower()
                    .split()
                )
            )

            publication_year = str(
                publication.get(
                    "year",
                    "",
                )
            ).strip()

            if (
                publication_title
                == requested_title
                and (
                    not requested_year
                    or publication_year
                    == requested_year
                )
            ):
                return publication

    return None


@app.route("/")
def index():
    data = load_data()

    return render_template(
        "index.html",
        data=data,
    )


@app.route("/api/avaliacao")
def api_avaliacao():
    data = load_data()

    default_start, default_end = (
        get_default_period(data)
    )

    default_min_score = (
        get_default_min_score(data)
    )

    start_year = request.args.get(
        "start_year",
        default_start,
        type=int,
    )

    end_year = request.args.get(
        "end_year",
        default_end,
        type=int,
    )

    min_score = request.args.get(
        "min_score",
        default_min_score,
        type=float,
    )

    if start_year > end_year:
        return jsonify(
            {
                "erro": (
                    "O ano inicial não pode "
                    "ser maior que o ano final."
                )
            }
        ), 400

    if min_score < 0:
        return jsonify(
            {
                "erro": (
                    "A pontuação mínima não pode "
                    "ser negativa."
                )
            }
        ), 400

    lattes_data = data.get(
        "lattes_data",
        [],
    )

    if not lattes_data:
        return jsonify(
            {
                "erro": (
                    "Nenhum dado bruto de Lattes "
                    "foi encontrado no JSON."
                )
            }
        ), 500

    resultado = evaluate_professors(
        lattes_data=lattes_data,
        qualis_db=QUALIS_DB,
        start_year=start_year,
        end_year=end_year,
        min_score=min_score,
    )

    resultado["configuracao"] = {
        "start_year": start_year,
        "end_year": end_year,
        "min_score": min_score,
    }

    return jsonify(
        make_json_safe(resultado)
    )


@app.route(
    "/api/export/excel",
    methods=["POST"],
)
def api_export_excel():
    data = load_data()

    payload = request.get_json(
        silent=True
    )

    if not isinstance(
        payload,
        dict,
    ):
        payload = {}

    default_start, default_end = (
        get_default_period(data)
    )

    default_min_score = (
        get_default_min_score(data)
    )

    start_year = payload.get(
        "start_year",
        default_start,
    )

    end_year = payload.get(
        "end_year",
        default_end,
    )

    min_score = payload.get(
        "min_score",
        default_min_score,
    )

    try:
        start_year = int(
            start_year
        )

        end_year = int(
            end_year
        )

        min_score = float(
            min_score
        )

    except (
        TypeError,
        ValueError,
    ):
        return jsonify(
            {
                "erro": (
                    "Parâmetros de avaliação inválidos."
                )
            }
        ), 400

    if start_year > end_year:
        return jsonify(
            {
                "erro": (
                    "O ano inicial não pode "
                    "ser maior que o ano final."
                )
            }
        ), 400

    if min_score < 0:
        return jsonify(
            {
                "erro": (
                    "A pontuação mínima não pode "
                    "ser negativa."
                )
            }
        ), 400

    lattes_data = data.get(
        "lattes_data",
        [],
    )

    if not lattes_data:
        return jsonify(
            {
                "erro": (
                    "Nenhum dado bruto de Lattes "
                    "foi encontrado no JSON."
                )
            }
        ), 500

    resultado = evaluate_professors(
        lattes_data=lattes_data,
        qualis_db=QUALIS_DB,
        start_year=start_year,
        end_year=end_year,
        min_score=min_score,
    )

    resultado["configuracao"] = {
        "start_year": start_year,
        "end_year": end_year,
        "min_score": min_score,
    }

    try:
        output_file = export_excel(
            resultado=resultado,
        )

    except Exception as exc:
        return jsonify(
            {
                "erro": (
                    "Erro ao gerar Excel: "
                    f"{exc}"
                )
            }
        ), 500

    return send_file(
        output_file,
        as_attachment=True,
        download_name=(
            f"avaliacao_ppgcomp_"
            f"{start_year}_{end_year}.xlsx"
        ),
        mimetype=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        ),
    )


@app.route(
    "/api/qualis/override",
    methods=["POST"],
)
def api_set_qualis_override():
    data = load_data()

    payload = request.get_json(
        silent=True
    )

    if not isinstance(
        payload,
        dict,
    ):
        return jsonify(
            {
                "erro": (
                    "JSON inválido."
                )
            }
        ), 400

    qualis = str(
        payload.get(
            "qualis",
            "",
        )
    ).strip().upper()

    if qualis not in VALID_QUALIS:
        return jsonify(
            {
                "erro": (
                    "Qualis inválido. "
                    "Use A1, A2, A3, A4, "
                    "A5, A6, A7 ou A8."
                )
            }
        ), 400

    publication = find_publication(
        data=data,
        doi=payload.get(
            "doi"
        ),
        title=payload.get(
            "title"
        ),
        year=payload.get(
            "year"
        ),
    )

    if publication is None:
        return jsonify(
            {
                "erro": (
                    "Publicação não encontrada."
                )
            }
        ), 404

    note = str(
        payload.get(
            "note",
            "",
        )
    ).strip()

    override = set_override(
        publication=publication,
        qualis=qualis,
        note=note,
    )

    return jsonify(
        {
            "ok": True,
            "mensagem": (
                "Classificação manual salva."
            ),
            "doi": publication.get(
                "doi"
            ),
            "title": publication.get(
                "title"
            ),
            "qualis_official": publication.get(
                "qualis"
            ),
            "qualis_manual": override[
                "qualis"
            ],
            "note": override[
                "note"
            ],
        }
    )


@app.route(
    "/api/qualis/override",
    methods=["DELETE"],
)
def api_remove_qualis_override():
    data = load_data()

    payload = request.get_json(
        silent=True
    )

    if not isinstance(
        payload,
        dict,
    ):
        payload = {}

    publication = find_publication(
        data=data,
        doi=payload.get(
            "doi"
        ),
        title=payload.get(
            "title"
        ),
        year=payload.get(
            "year"
        ),
    )

    if publication is None:
        return jsonify(
            {
                "erro": (
                    "Publicação não encontrada."
                )
            }
        ), 404

    removed = remove_override(
        publication
    )

    return jsonify(
        {
            "ok": True,
            "removed": removed,
            "mensagem": (
                "Classificação automática "
                "restaurada."
                if removed
                else
                "Nenhum override manual "
                "estava cadastrado."
            ),
        }
    )


@app.route(
    "/api/qualis/override",
    methods=["GET"],
)
def api_get_qualis_override():
    data = load_data()

    publication = find_publication(
        data=data,
        doi=request.args.get(
            "doi"
        ),
        title=request.args.get(
            "title"
        ),
        year=request.args.get(
            "year"
        ),
    )

    if publication is None:
        return jsonify(
            {
                "erro": (
                    "Publicação não encontrada."
                )
            }
        ), 404

    override = get_override(
        publication
    )

    return jsonify(
        {
            "ok": True,
            "qualis_official": publication.get(
                "qualis"
            ),
            "override": override,
        }
    )


@app.route(
    "/api/publication/student-author",
    methods=["GET"],
)
def api_get_student_author():
    data = load_data()

    publication = find_publication(
        data=data,
        doi=request.args.get(
            "doi"
        ),
        title=request.args.get(
            "title"
        ),
        year=request.args.get(
            "year"
        ),
    )

    if publication is None:
        return jsonify(
            {
                "erro": (
                    "Publicação não encontrada."
                )
            }
        ), 404

    return jsonify(
        {
            "ok": True,
            "student_author": (
                get_student_flag(
                    publication
                )
            ),
        }
    )


@app.route(
    "/api/publication/student-author",
    methods=["POST"],
)
def api_set_student_author():
    data = load_data()

    payload = request.get_json(
        silent=True
    )

    if not isinstance(
        payload,
        dict,
    ):
        return jsonify(
            {
                "erro": (
                    "JSON inválido."
                )
            }
        ), 400

    publication = find_publication(
        data=data,
        doi=payload.get(
            "doi"
        ),
        title=payload.get(
            "title"
        ),
        year=payload.get(
            "year"
        ),
    )

    if publication is None:
        return jsonify(
            {
                "erro": (
                    "Publicação não encontrada."
                )
            }
        ), 404

    student_author = bool(
        payload.get(
            "student_author",
            False,
        )
    )

    flag = set_student_flag(
        publication=publication,
        student_author=student_author,
    )

    return jsonify(
        {
            "ok": True,
            "student_author": flag[
                "student_author"
            ],
        }
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
    )
