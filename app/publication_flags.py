import json
import logging
from pathlib import Path

from app.gist_storage import load_json as load_gist_json
from app.gist_storage import save_json as save_gist_json


logger = logging.getLogger(__name__)


ROOT = Path(__file__).resolve().parent.parent


FLAGS_FILENAME = "publication_flags.json"


FLAGS_FILE = (
    ROOT
    / "output"
    / FLAGS_FILENAME
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


def publication_key(publication):
    doi = normalize_doi(
        publication.get("doi")
    )

    if doi:
        return (
            "doi:" + doi
        )

    year = publication.get(
        "year"
    )

    title = " ".join(
        str(
            publication.get(
                "title",
                ""
            )
        )
        .strip()
        .lower()
        .split()
    )

    return (
        f"title:{year}:{title}"
    )


def load_flags():
    """
    Carrega as flags manuais.

    Quando o Gist está configurado, ele é a fonte de verdade.
    Se o Gist estiver indisponível, recorre ao arquivo local.
    """

    gist_data = load_gist_json(
        FLAGS_FILENAME
    )

    if isinstance(
        gist_data,
        dict,
    ):
        return gist_data

    if not FLAGS_FILE.exists():
        return {}

    try:
        data = json.loads(
            FLAGS_FILE.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return {}

    if not isinstance(
        data,
        dict,
    ):
        return {}

    return data


def _write_local_flags(flags):
    """Grava as flags no arquivo local."""

    FLAGS_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    FLAGS_FILE.write_text(
        json.dumps(
            flags,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def save_flags(flags):
    """
    Salva as flags.

    O arquivo local é sempre atualizado (serve de cache/fallback) e
    o Gist é atualizado em seguida, quando configurado.

    Uma falha isolada no Gist não interrompe a requisição; só há erro
    quando nenhum dos dois destinos consegue gravar.
    """

    if not isinstance(
        flags,
        dict,
    ):
        raise ValueError(
            "As flags devem ser um objeto JSON."
        )

    local_saved = True

    try:
        _write_local_flags(
            flags
        )
    except OSError:
        local_saved = False

        logger.exception(
            "Falha ao gravar flags localmente em %s",
            FLAGS_FILE,
        )

    gist_saved = save_gist_json(
        FLAGS_FILENAME,
        flags,
    )

    if not local_saved and not gist_saved:
        raise RuntimeError(
            "Não foi possível salvar as flags de aluno "
            "no arquivo local nem no Gist."
        )


def get_student_manual_flag(
    publication,
    flags=None,
):
    if flags is None:
        flags = load_flags()

    key = publication_key(
        publication
    )

    value = flags.get(
        key
    )

    if not isinstance(
        value,
        dict,
    ):
        return None

    if "student_author_manual" in value:
        return bool(
            value.get(
                "student_author_manual"
            )
        )

    if "student_author" in value:
        return bool(
            value.get(
                "student_author"
            )
        )

    return None


def get_student_flag(
    publication,
    flags=None,
):
    manual_flag = get_student_manual_flag(
        publication=publication,
        flags=flags,
    )

    if manual_flag is None:
        return False

    return manual_flag


def set_student_flag(
    publication,
    student_author,
):
    flags = load_flags()

    key = publication_key(
        publication
    )

    flags[key] = {
        "student_author": bool(
            student_author
        ),
        "student_author_manual": bool(
            student_author
        ),
    }

    save_flags(
        flags
    )

    return flags[key]
