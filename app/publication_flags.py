import json
import os
from pathlib import Path
from urllib import request as urlrequest
from urllib.error import URLError, HTTPError


ROOT = Path(__file__).resolve().parent.parent


FLAGS_FILE = (
    ROOT
    / "output"
    / "publication_flags.json"
)

GIST_ID = os.getenv("GIST_ID", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GIST_FILENAME = "publication_flags.json"


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
    # Tenta carregar do Gist primeiro
    if GIST_ID:
        gist_data = load_from_gist()
        if gist_data is not None and isinstance(gist_data, dict):
            return gist_data

    # Fallback para arquivo local
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


def save_flags(flags):
    # Tenta salvar no Gist primeiro
    if GIST_ID:
        save_to_gist(flags)

    # Sempre mantém cópia local para fallback
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


def save_to_gist(flags):
    if not GIST_ID or not GITHUB_TOKEN:
        return False

    content = json.dumps(flags, ensure_ascii=False, indent=2)
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
