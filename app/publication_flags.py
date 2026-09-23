import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


FLAGS_FILE = (
    ROOT
    / "output"
    / "publication_flags.json"
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


def get_student_flag(
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
        return False

    return bool(
        value.get(
            "student_author",
            False,
        )
    )


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
        )
    }

    save_flags(
        flags
    )

    return flags[key]
