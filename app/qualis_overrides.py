import json
import os
import re
import unicodedata
from pathlib import Path
from urllib import request as urlrequest
from urllib.error import URLError, HTTPError


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

GIST_ID = os.getenv("GIST_ID", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GIST_FILENAME = "qualis_overrides.json"


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


def normalize_vehicle_text(value):
    """
    Normaliza o nome de um veículo para gerar
    uma chave estável para override manual.
    """

    value = str(
        value or ""
    ).strip().lower()

    if not value:
        return ""

    value = unicodedata.normalize(
        "NFKD",
        value
    )

    value = "".join(
        char
        for char in value
        if not unicodedata.combining(char)
    )

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value
    )

    return " ".join(
        value.split()
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


def vehicle_key(publication):
    """
    Gera um identificador estável para o veículo
    de uma publicação.

    Para periódicos, o ISSN é preferencial.

    Para conferências/eventos, uma sigla explícita
    no final do nome é usada como identificador
    principal do veículo.

    Exemplos:

        International Conference on Computational
        Science and Its Applications - ICCSA

        Computational Science and Its Applications
        - ICCSA

    tornam-se o mesmo veículo:

        event:iccsa
    """

    venue = (
        publication.get("venue")
        or publication.get("journal")
        or publication.get("conference")
        or ""
    )

    publication_type = str(
        publication.get(
            "type",
            ""
        )
    ).strip().lower()

    issn = str(
        publication.get(
            "issn",
            ""
        ) or ""
    ).strip()

    issn_normalized = re.sub(
        r"[^0-9x]",
        "",
        issn.lower()
    )

    if publication_type in {
        "journal",
        "periódico",
        "periodico",
    } and issn_normalized:

        return (
            "journal_issn:"
            + issn_normalized
        )

    normalized = normalize_vehicle_text(
        venue
    )

    if not normalized:
        return ""

    if publication_type in {
        "journal",
        "periódico",
        "periodico",
    }:

        return (
            "journal_title:"
            + normalized
        )

    # Para eventos, procura uma sigla explícita
    # no final do nome:
    #
    #   "... - ICCSA"
    #   "... (ICCSA)"
    #
    # A sigla passa a identificar o veículo.
    venue_text = str(
        venue or ""
    ).strip()

    acronym_match = re.search(
        r"(?:[-–—]\s*|\(\s*)([A-Za-z][A-Za-z0-9]{1,14})\s*\)?\s*$",
        venue_text,
    )

    if acronym_match:

        acronym = (
            acronym_match.group(1)
            .strip()
            .lower()
        )

        return (
            "event:"
            + acronym
        )

    return (
        "event:"
        + normalized
    )


def _normalize_storage(data):
    """
    Converte o formato antigo de overrides para o
    novo formato estruturado.

    Formato antigo:

    {
        "doi:...": {...},
        "title:...": {...}
    }

    Novo formato:

    {
        "publications": {...},
        "vehicles": {...}
    }
    """

    if not isinstance(
        data,
        dict,
    ):
        return {
            "publications": {},
            "vehicles": {},
        }

    if (
        "publications" in data
        or "vehicles" in data
    ):

        publications = data.get(
            "publications",
            {}
        )

        vehicles = data.get(
            "vehicles",
            {}
        )

        if not isinstance(
            publications,
            dict,
        ):
            publications = {}

        if not isinstance(
            vehicles,
            dict,
        ):
            vehicles = {}

        return {
            "publications": publications,
            "vehicles": vehicles,
        }

    publications = {}

    for key, value in data.items():

        if isinstance(
            value,
            dict,
        ):

            publications[key] = value

    return {
        "publications": publications,
        "vehicles": {},
    }


def load_overrides():
    """
    Carrega os ajustes manuais existentes.

    Tenta primeiro o Gist configurado (variáveis GIST_ID e
    GITHUB_TOKEN). Se não houver Gist ou falhar na leitura,
    cai de volta para o arquivo local em
    output/qualis_overrides.json.

    Também mantém compatibilidade com o formato
    antigo de arquivo.
    """

    # Tenta carregar do Gist primeiro
    if GIST_ID:
        gist_data = load_from_gist()
        if gist_data is not None:
            return _normalize_storage(gist_data)

    # Fallback para arquivo local
    if not OVERRIDES_FILE.exists():
        return {
            "publications": {},
            "vehicles": {},
        }

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

        return {
            "publications": {},
            "vehicles": {},
        }

    return _normalize_storage(
        data
    )


def save_overrides(
    overrides
):
    """
    Salva os ajustes manuais.
    """

    normalized = _normalize_storage(
        overrides
    )

    OVERRIDES_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OVERRIDES_FILE.write_text(
        json.dumps(
            normalized,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    save_to_gist(normalized)


def _gist_headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "scraper-lattes",
    }

    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    return headers


def load_from_gist():
    if not GIST_ID:
        return None

    url = f"https://api.github.com/gists/{GIST_ID}"
    req = urlrequest.Request(url, headers=_gist_headers())

    try:
        with urlrequest.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (URLError, HTTPError, OSError):
        return None

    files = data.get("files", {})
    content = None

    for fdata in files.values():
        if fdata.get("filename") == GIST_FILENAME:
            content = fdata.get("content")
            break

    if content is None and files:
        content = next(iter(files.values())).get("content")

    if content is None:
        return None

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


def save_to_gist(overrides):
    if not GIST_ID or not GITHUB_TOKEN:
        return False

    content = json.dumps(overrides, ensure_ascii=False, indent=2)
    payload = {
        "files": {
            GIST_FILENAME: {
                "content": content,
            }
        }
    }

    url = f"https://api.github.com/gists/{GIST_ID}"
    req = urlrequest.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            **_gist_headers(),
            "Content-Type": "application/json",
        },
        method="PATCH",
    )

    try:
        with urlrequest.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except (URLError, HTTPError, OSError):
        return False


def get_override(
    publication,
    overrides=None,
):
    """
    Retorna o override manual específico da
    publicação, se existir.
    """

    if overrides is None:
        overrides = load_overrides()

    overrides = _normalize_storage(
        overrides
    )

    key = publication_key(
        publication
    )

    value = overrides[
        "publications"
    ].get(key)

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


def get_vehicle_override(
    publication,
    overrides=None,
):
    """
    Retorna o override manual do veículo,
    se existir.
    """

    if overrides is None:
        overrides = load_overrides()

    overrides = _normalize_storage(
        overrides
    )

    key = vehicle_key(
        publication
    )

    if not key:
        return None

    value = overrides[
        "vehicles"
    ].get(key)

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
    Cria ou substitui um ajuste manual
    específico de uma publicação.

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

    overrides[
        "publications"
    ][key] = {
        "qualis": qualis,
        "note": str(
            note or ""
        ).strip(),
    }

    save_overrides(
        overrides
    )

    return overrides[
        "publications"
    ][key]


def set_vehicle_override(
    publication,
    qualis,
    note="",
):
    """
    Cria ou substitui um ajuste manual
    para todo o veículo da publicação.

    Todas as publicações do mesmo veículo
    passarão a utilizar esta classificação,
    salvo quando existir um override específico
    da publicação.
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

    key = vehicle_key(
        publication
    )

    if not key:

        raise ValueError(
            "Não foi possível identificar "
            "o veículo da publicação."
        )

    overrides[
        "vehicles"
    ][key] = {
        "qualis": qualis,
        "note": str(
            note or ""
        ).strip(),
    }

    save_overrides(
        overrides
    )

    return overrides[
        "vehicles"
    ][key]


def remove_override(
    publication
):
    """
    Remove o ajuste manual específico
    de uma publicação.
    """

    overrides = load_overrides()

    key = publication_key(
        publication
    )

    removed = (
        key in overrides[
            "publications"
        ]
    )

    if removed:

        del overrides[
            "publications"
        ][key]

        save_overrides(
            overrides
        )

    return removed


def remove_vehicle_override(
    publication
):
    """
    Remove o ajuste manual do veículo.

    Após a remoção, as publicações daquele veículo
    voltam a utilizar a classificação automática,
    exceto aquelas com override específico.
    """

    overrides = load_overrides()

    key = vehicle_key(
        publication
    )

    if not key:
        return False

    removed = (
        key in overrides[
            "vehicles"
        ]
    )

    if removed:

        del overrides[
            "vehicles"
        ][key]

        save_overrides(
            overrides
        )

    return removed
