from pathlib import Path
import json
import logging
import threading

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_file,
)

from app.metrics import evaluate_professors
from app.qualis import QualisDB
from app.export import make_json_safe
from app.export_excel import export_excel
from app.qualis_overrides import (
    VALID_QUALIS,
    get_override,
    get_vehicle_override,
    remove_override,
    remove_vehicle_override,
    set_override,
    set_vehicle_override,
)
from app.publication_flags import (
    get_student_manual_flag,
    set_student_flag,
)
from app.students import find_student_authors


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent

DATA_FILE = ROOT / "output" / "2026" / "dados.json"

app = Flask(__name__)

QUALIS_DB = QualisDB()

# Cache da avaliação por processo.
# A chave considera os parâmetros e a versão do dados.json.
_EVALUATION_CACHE = {}
_EVALUATION_CACHE_LOCK = threading.RLock()

# Cache dos dados brutos carregados do JSON.
# A assinatura permite detectar atualizações do arquivo.
_DATA_CACHE = None
_DATA_CACHE_SIGNATURE = None
_DATA_CACHE_LOCK = threading.RLock()


def clear_evaluation_cache():
    """Invalida os resultados de avaliação em memória."""
    with _EVALUATION_CACHE_LOCK:
        _EVALUATION_CACHE.clear()


def get_data_signature():
    """Identifica alterações no arquivo de dados."""
    stat = DATA_FILE.stat()
    return stat.st_mtime_ns, stat.st_size


def get_cached_evaluation(
    lattes_data,
    start_year,
    end_year,
    min_score,
    data_signature,
):
    """
    Retorna uma avaliação em cache ou calcula uma nova.

    O bloqueio evita que várias requisições simultâneas
    recalcularem a mesma avaliação no mesmo processo.
    """
    cache_key = (
        data_signature,
        start_year,
        end_year,
        float(min_score),
    )

    with _EVALUATION_CACHE_LOCK:
        cached = _EVALUATION_CACHE.get(cache_key)

        if cached is not None:
            logger.info(
                "Avaliação recuperada do cache: %s",
                cache_key,
            )
            return cached

        logger.info(
            "Calculando avaliação: %s",
            cache_key,
        )

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

        resultado = make_json_safe(resultado)

        # Não guardar o resultado se o arquivo mudou durante
        # o cálculo. A próxima requisição fará novo cálculo.
        try:
            current_signature = get_data_signature()
        except OSError:
            current_signature = None

        if current_signature == data_signature:
            _EVALUATION_CACHE.clear()
            _EVALUATION_CACHE[cache_key] = resultado

        return resultado


def load_data():
    """
    Carrega dados.json e mantém o conteúdo em memória.

    Se o arquivo mudar, uma nova versão será carregada.
    O bloqueio evita leituras redundantes em requisições
    simultâneas no mesmo processo.
    """
    global _DATA_CACHE, _DATA_CACHE_SIGNATURE

    with _DATA_CACHE_LOCK:
        while True:
            signature_before = get_data_signature()

            if (
                _DATA_CACHE is not None
                and _DATA_CACHE_SIGNATURE == signature_before
            ):
                return _DATA_CACHE

            with DATA_FILE.open("r", encoding="utf-8") as file:
                data = json.load(file)

            # Confere se o arquivo não foi atualizado durante
            # a leitura. Se mudou, repete usando a nova versão.
            signature_after = get_data_signature()

            if signature_before != signature_after:
                continue

            _DATA_CACHE = data
            _DATA_CACHE_SIGNATURE = signature_after

            logger.info(
                "Dados carregados em memória: %s",
                DATA_FILE,
            )

            return _DATA_CACHE


def get_default_period(data):
    config = data.get("configuracao", {})

    start_year = config.get("evaluation_start_year")
    end_year = config.get("evaluation_end_year")

    if start_year is None:
        end_year = config.get("reference_year", 2026)
        start_year = end_year - 3

    return int(start_year), int(end_year)


def get_default_min_score(data):
    config = data.get("configuracao", {})
    return float(config.get("min_score", 4.0))


def normalize_doi(doi):
    value = str(doi or "").strip().lower()

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

    return value.rstrip(".,;:)]}>")


def find_publication(data, doi=None, title=None, year=None):
    publications = []

    for lattes in data.get("lattes_data", []):
        for publication in lattes.get("publications", []):
            publications.append(publication)

    requested_doi = normalize_doi(doi)

    if requested_doi:
        for publication in publications:
            publication_doi = normalize_doi(
                publication.get("doi")
            )

            if (
                publication_doi
                and publication_doi == requested_doi
            ):
                return publication

    requested_title = " ".join(
        str(title or "").strip().lower().split()
    )
    requested_year = str(year or "").strip()

    if requested_title:
        for publication in publications:
            publication_title = " ".join(
                str(publication.get("title", ""))
                .strip()
                .lower()
                .split()
            )

            publication_year = str(
                publication.get("year", "")
            ).strip()

            if (
                publication_title == requested_title
                and (
                    not requested_year
                    or publication_year == requested_year
                )
            ):
                return publication

    return None


def get_publication_student_authors(publication):
    """
    Usa os nomes de alunos pré-processados quando disponíveis.
    Mantém o método antigo como alternativa para registros
    que ainda não tenham sido pré-processados.
    """
    if publication.get("_student_authors_precomputed") is True:
        cached_authors = publication.get(
            "_student_authors_cached"
        )

        if isinstance(cached_authors, list):
            return cached_authors

    return find_student_authors(publication)


@app.route("/")
def index():
    data = load_data()

    return render_template(
        "index.html",
        data=data,
    )


@app.route("/api/avaliacao")
def api_avaliacao():
    try:
        data = load_data()

        default_start, default_end = get_default_period(data)
        default_min_score = get_default_min_score(data)

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
            return jsonify({
                "erro": (
                    "O ano inicial não pode "
                    "ser maior que o ano final."
                )
            }), 400

        if min_score < 0:
            return jsonify({
                "erro": "A pontuação mínima não pode ser negativa."
            }), 400

        lattes_data = data.get("lattes_data", [])

        if not lattes_data:
            return jsonify({
                "erro": (
                    "Nenhum dado bruto de Lattes "
                    "foi encontrado no JSON."
                )
            }), 500

        data_signature = get_data_signature()

        resultado = get_cached_evaluation(
            lattes_data=lattes_data,
            start_year=start_year,
            end_year=end_year,
            min_score=min_score,
            data_signature=data_signature,
        )

        return jsonify(resultado)

    except Exception:
        logger.exception("Erro ao processar a avaliação")
        return jsonify({
            "erro": "Erro interno ao calcular a avaliação."
        }), 500


@app.route("/api/export/excel", methods=["POST"])
def api_export_excel():
    data = load_data()
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        payload = {}

    default_start, default_end = get_default_period(data)
    default_min_score = get_default_min_score(data)

    start_year = payload.get("start_year", default_start)
    end_year = payload.get("end_year", default_end)
    min_score = payload.get("min_score", default_min_score)

    try:
        start_year = int(start_year)
        end_year = int(end_year)
        min_score = float(min_score)
    except (TypeError, ValueError):
        return jsonify({
            "erro": "Parâmetros de avaliação inválidos."
        }), 400

    if start_year > end_year:
        return jsonify({
            "erro": (
                "O ano inicial não pode "
                "ser maior que o ano final."
            )
        }), 400

    if min_score < 0:
        return jsonify({
            "erro": "A pontuação mínima não pode ser negativa."
        }), 400

    lattes_data = data.get("lattes_data", [])

    if not lattes_data:
        return jsonify({
            "erro": (
                "Nenhum dado bruto de Lattes "
                "foi encontrado no JSON."
            )
        }), 500

    # Mantém o comportamento original do Excel:
    # recalcula a avaliação ao solicitar a exportação.
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
        output_file = export_excel(resultado=resultado)
    except Exception as exc:
        logger.exception("Erro ao gerar arquivo Excel")
        return jsonify({
            "erro": f"Erro ao gerar Excel: {exc}"
        }), 500

    return send_file(
        output_file,
        as_attachment=True,
        download_name=(
            f"avaliacao_ppgcomp_{start_year}_{end_year}.xlsx"
        ),
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )


@app.route("/api/qualis/override", methods=["POST"])
def api_set_qualis_override():
    data = load_data()
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({"erro": "JSON inválido."}), 400

    qualis = str(payload.get("qualis", "")).strip().upper()

    if qualis not in VALID_QUALIS:
        return jsonify({
            "erro": (
                "Qualis inválido. Use A1, A2, A3, A4, "
                "A5, A6, A7 ou A8."
            )
        }), 400

    scope = str(
        payload.get("scope", "publication")
    ).strip().lower()

    if scope not in {"publication", "vehicle"}:
        return jsonify({
            "erro": "Escopo inválido. Use publication ou vehicle."
        }), 400

    publication = find_publication(
        data=data,
        doi=payload.get("doi"),
        title=payload.get("title"),
        year=payload.get("year"),
    )

    if publication is None:
        return jsonify({
            "erro": "Publicação não encontrada."
        }), 404

    note = str(payload.get("note", "")).strip()

    if scope == "vehicle":
        try:
            override = set_vehicle_override(
                publication=publication,
                qualis=qualis,
                note=note,
            )
        except ValueError as exc:
            return jsonify({"erro": str(exc)}), 400

        clear_evaluation_cache()

        return jsonify({
            "ok": True,
            "mensagem": "Classificação manual do veículo salva.",
            "scope": "vehicle",
            "title": publication.get("title"),
            "venue": publication.get("venue"),
            "qualis_manual": override["qualis"],
            "note": override["note"],
        })

    override = set_override(
        publication=publication,
        qualis=qualis,
        note=note,
    )

    clear_evaluation_cache()

    return jsonify({
        "ok": True,
        "mensagem": "Classificação manual salva.",
        "scope": "publication",
        "doi": publication.get("doi"),
        "title": publication.get("title"),
        "qualis_official": publication.get("qualis"),
        "qualis_manual": override["qualis"],
        "note": override["note"],
    })


@app.route("/api/qualis/override", methods=["DELETE"])
def api_remove_qualis_override():
    data = load_data()
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        payload = {}

    scope = str(
        payload.get("scope", "publication")
    ).strip().lower()

    if scope not in {"publication", "vehicle"}:
        return jsonify({
            "erro": "Escopo inválido. Use publication ou vehicle."
        }), 400

    publication = find_publication(
        data=data,
        doi=payload.get("doi"),
        title=payload.get("title"),
        year=payload.get("year"),
    )

    if publication is None:
        return jsonify({
            "erro": "Publicação não encontrada."
        }), 404

    if scope == "vehicle":
        removed = remove_vehicle_override(publication)
    else:
        removed = remove_override(publication)

    if removed:
        clear_evaluation_cache()

    if scope == "vehicle":
        message = (
            "Classificação automática do veículo restaurada."
            if removed
            else "Nenhum override manual do veículo estava cadastrado."
        )
    else:
        message = (
            "Classificação automática restaurada."
            if removed
            else "Nenhum override manual estava cadastrado."
        )

    return jsonify({
        "ok": True,
        "removed": removed,
        "scope": scope,
        "mensagem": message,
    })


@app.route("/api/qualis/override", methods=["GET"])
def api_get_qualis_override():
    data = load_data()

    publication = find_publication(
        data=data,
        doi=request.args.get("doi"),
        title=request.args.get("title"),
        year=request.args.get("year"),
    )

    if publication is None:
        return jsonify({
            "erro": "Publicação não encontrada."
        }), 404

    publication_override = get_override(publication)
    vehicle_override = get_vehicle_override(publication)

    return jsonify({
        "ok": True,
        "qualis_official": publication.get("qualis"),
        "publication_override": publication_override,
        "vehicle_override": vehicle_override,
        "override": publication_override or vehicle_override,
    })


@app.route("/api/publication/student-author", methods=["GET"])
def api_get_student_author():
    data = load_data()

    publication = find_publication(
        data=data,
        doi=request.args.get("doi"),
        title=request.args.get("title"),
        year=request.args.get("year"),
    )

    if publication is None:
        return jsonify({
            "erro": "Publicação não encontrada."
        }), 404

    student_authors = get_publication_student_authors(
        publication
    )
    student_author_auto = bool(student_authors)

    student_author_manual = get_student_manual_flag(
        publication
    )

    if student_author_manual is None:
        student_author = student_author_auto
    else:
        student_author = bool(student_author_manual)

    return jsonify({
        "ok": True,
        "student_author": student_author,
        "student_author_auto": student_author_auto,
        "student_author_manual": student_author_manual,
        "student_authors": student_authors,
    })


@app.route("/api/publication/student-author", methods=["POST"])
def api_set_student_author():
    data = load_data()
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({"erro": "JSON inválido."}), 400

    publication = find_publication(
        data=data,
        doi=payload.get("doi"),
        title=payload.get("title"),
        year=payload.get("year"),
    )

    if publication is None:
        return jsonify({
            "erro": "Publicação não encontrada."
        }), 404

    student_author = bool(
        payload.get("student_author", False)
    )

    flag = set_student_flag(
        publication=publication,
        student_author=student_author,
    )

    student_authors = get_publication_student_authors(
        publication
    )

    clear_evaluation_cache()

    return jsonify({
        "ok": True,
        "student_author": flag["student_author"],
        "student_author_auto": bool(student_authors),
        "student_author_manual": flag["student_author_manual"],
        "student_authors": student_authors,
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
    )
