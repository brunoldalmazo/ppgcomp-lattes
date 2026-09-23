import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


OVERRIDES_FILE = (
    ROOT
    / "output"
    / "qualis_overrides.json"
)


VALID_QUALIS = {
    "A1",
    "A2",
    "A3",
    "A4",
    "A5",
    "A6",
    "A7",
    "A8",
}


def normalize_doi(doi):
    """
    Normaliza DOI para uso como identificador.
    """

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

            value = value[
                len(prefix):
            ]

            break

    return value.rstrip(
        ".,;:)]}>"
    )


def publication_key(publication):
    """
    Gera um identificador estável para uma publicação.

    DOI é preferencial.

    Quando não existe DOI, utiliza:
        ano + título normalizado
    """

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


def load_overrides():
    """
    Carrega os ajustes manuais existentes.

    Retorna um dicionário vazio caso o arquivo
    ainda não exista.
    """

    if not OVERRIDES_FILE.exists():
        return {}

    try:

        data = json.loads(
            OVERRIDES_FILE.read_text(
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


def save_overrides(
    overrides
):
    """
    Salva os ajustes manuais.
    """

    OVERRIDES_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OVERRIDES_FILE.write_text(
        json.dumps(
            overrides,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def get_override(
    publication,
    overrides=None,
):
    """
    Retorna o Qualis manual de uma publicação,
    se existir.
    """

    if overrides is None:
        overrides = load_overrides()

    key = publication_key(
        publication
    )

    value = overrides.get(
        key
    )

    if not isinstance(
        value,
        dict,
    ):

        return None

    qualis = str(
        value.get(
            "qualis",
            ""
        )
    ).strip().upper()

    if qualis not in VALID_QUALIS:
        return None

    return value


def set_override(
    publication,
    qualis,
    note="",
):
    """
    Cria ou substitui um ajuste manual.

    Apenas A1-A8 são aceitos.
    """

    qualis = str(
        qualis or ""
    ).strip().upper()

    if qualis not in VALID_QUALIS:

        raise ValueError(
            "Qualis manual inválido. "
            "Use somente A1, A2, A3, A4, "
            "A5, A6, A7 ou A8."
        )

    overrides = load_overrides()

    key = publication_key(
        publication
    )

    overrides[key] = {
        "qualis": qualis,
        "note": str(
            note or ""
        ).strip(),
    }

    save_overrides(
        overrides
    )

    return overrides[key]


def remove_override(
    publication
):
    """
    Remove o ajuste manual de uma publicação.

    Após a remoção, a classificação automática
    volta a ser utilizada.
    """

    overrides = load_overrides()

    key = publication_key(
        publication
    )

    removed = (
        key in overrides
    )

    if removed:

        del overrides[key]

        save_overrides(
            overrides
        )

    return removed
