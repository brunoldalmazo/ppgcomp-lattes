import re
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


STUDENTS_FILE = (
    ROOT
    / "input"
    / "alunos.txt"
)


def normalize_name(name):
    value = str(
        name or ""
    ).strip()

    if not value:
        return ""

    value = unicodedata.normalize(
        "NFKD",
        value,
    )

    value = "".join(
        char
        for char in value
        if not unicodedata.combining(
            char
        )
    )

    value = value.lower()

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def normalize_author_name(name):
    value = str(
        name or ""
    ).strip()

    if not value:
        return ""

    if "," in value:
        parts = [
            part.strip()
            for part in value.split(
                ",",
                1,
            )
        ]

        if len(parts) == 2:
            surname = parts[0]
            given = parts[1]

            value = (
                given
                + " "
                + surname
            )

    return normalize_name(
        value
    )


def load_students():
    if not STUDENTS_FILE.exists():
        return {}

    students = {}

    try:
        lines = STUDENTS_FILE.read_text(
            encoding="utf-8"
        ).splitlines()
    except OSError:
        return {}

    for line in lines:
        original = line.strip()

        if not original:
            continue

        normalized = normalize_name(
            original
        )

        if not normalized:
            continue

        students.setdefault(
            normalized,
            original,
        )

    return students


def split_authors(authors):
    if isinstance(
        authors,
        list,
    ):
        values = authors
    else:
        values = str(
            authors or ""
        ).split(";")

    return [
        str(author).strip()
        for author in values
        if str(author).strip()
    ]


def find_student_authors(
    publication,
    students=None,
):
    if students is None:
        students = load_students()

    if not students:
        return []

    authors = split_authors(
        publication.get(
            "authors",
            "",
        )
    )

    matches = []

    for author in authors:
        normalized_author = (
            normalize_author_name(
                author
            )
        )

        if not normalized_author:
            continue

        student_name = students.get(
            normalized_author
        )

        if student_name:
            matches.append(
                student_name
            )

    return list(
        dict.fromkeys(
            matches
        )
    )


def has_student_author(
    publication,
    students=None,
):
    return bool(
        find_student_authors(
            publication,
            students=students,
        )
    )
