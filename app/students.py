
import re
import unicodedata
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

STUDENTS_FILE = ROOT / "input" / "alunos.txt"

# Partículas comuns em sobrenomes.
NAME_PARTICLES = {
    "de", "da", "do", "das", "dos", "e",
    "van", "von", "del", "la", "le",
}


@lru_cache(maxsize=50000)
def normalize_name(name):
    value = str(name or "").strip()

    if not value:
        return ""

    value = unicodedata.normalize("NFKD", value)

    value = "".join(
        char
        for char in value
        if not unicodedata.combining(char)
    )

    value = value.lower()
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def normalize_author_name(name):
    value = str(name or "").strip()

    if not value:
        return ""

    if "," in value:
        parts = [
            part.strip()
            for part in value.split(",", 1)
        ]

        if len(parts) == 2:
            surname = parts[0]
            given = parts[1]
            value = given + " " + surname

    return normalize_name(value)


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

        normalized = normalize_name(original)

        if normalized:
            students.setdefault(normalized, original)

    return students


def split_authors(authors):
    if isinstance(authors, list):
        values = authors
    else:
        values = str(authors or "").split(";")

    return [
        str(author).strip()
        for author in values
        if str(author).strip()
    ]


@lru_cache(maxsize=50000)
def name_tokens(name):
    return normalize_name(name).replace(",", " ").split()


@lru_cache(maxsize=50000)
def significant_tokens(name):
    return [
        token
        for token in name_tokens(name)
        if token not in NAME_PARTICLES
    ]


def token_matches(abbreviated, full):
    """
    Aceita nomes completos e iniciais:
    'denner' corresponde a 'Denner';
    'd.' corresponde a 'Denner'.
    """
    abbreviated = normalize_name(abbreviated).rstrip(".")
    full = normalize_name(full)

    if not abbreviated or not full:
        return False

    if len(abbreviated) == 1:
        return full.startswith(abbreviated)

    return full.startswith(abbreviated)


def ordered_name_match(abbreviated_tokens, full_tokens):
    """
    Verifica se os nomes abreviados aparecem na mesma ordem
    entre os nomes completos, permitindo partículas omitidas.
    """
    if not abbreviated_tokens or not full_tokens:
        return False

    position = 0

    for abbreviated in abbreviated_tokens:
        abbreviated = abbreviated.rstrip(".")

        if not abbreviated or abbreviated in NAME_PARTICLES:
            continue

        found = False

        while position < len(full_tokens):
            full = full_tokens[position]
            position += 1

            if token_matches(abbreviated, full):
                found = True
                break

        if not found:
            return False

    return True


def abbreviated_author_matches_student(author, student):
    """
    Compara autores no formato 'SOBRENOME, NOME(S)' com
    nomes completos de alunos.

    Exemplo:
    'ALMEIDA, G. P.' -> 'Gustavo Pereira de Almeida'

    Se houver vários alunos compatíveis, todos são aceitos.
    """
    author = str(author or "").strip()

    if "," not in author:
        return False

    surname_part, given_part = [
        part.strip()
        for part in author.split(",", 1)
    ]

    surname_tokens = significant_tokens(surname_part)
    given_tokens = name_tokens(given_part)

    student_tokens = name_tokens(student)
    student_significant = significant_tokens(student)

    if not surname_tokens or not given_tokens:
        return False

    if not student_significant:
        return False

    # O último sobrenome significativo precisa coincidir.
    if surname_tokens[-1] != student_significant[-1]:
        return False

    # Se o autor informou mais de um componente do sobrenome,
    # exige que eles também apareçam no nome do aluno, na ordem.
    if len(surname_tokens) > 1:
        if not ordered_name_match(
            surname_tokens,
            student_significant,
        ):
            return False

    # Remove partículas dos nomes próprios.
    student_given_tokens = [
        token
        for token in student_tokens
        if token not in NAME_PARTICLES
        and token not in student_significant[-1:]
    ]

    given_tokens = [
        token
        for token in given_tokens
        if token not in NAME_PARTICLES
    ]

    # Os nomes informados devem corresponder, na ordem,
    # a nomes do aluno. Iniciais também são aceitas.
    return ordered_name_match(
        given_tokens,
        student_given_tokens,
    )


def find_student_authors(publication, students=None):
    if students is None:
        students = load_students()

    if not students:
        return []

    authors = split_authors(
        publication.get("authors", "")
    )

    matches = []

    for author in authors:
        normalized_author = normalize_author_name(author)

        if not normalized_author:
            continue

        # Primeira etapa: correspondência exata.
        student_name = students.get(normalized_author)

        if student_name:
            matches.append(student_name)
            continue

        # Segunda etapa: correspondência com nomes abreviados.
        # Aceita todos os alunos compatíveis, inclusive quando
        # mais de um aluno corresponde ao mesmo autor.
        for student_name in students.values():
            if abbreviated_author_matches_student(
                author,
                student_name,
            ):
                matches.append(student_name)

    return list(dict.fromkeys(matches))


def has_student_author(publication, students=None):
    return bool(
        find_student_authors(
            publication,
            students=students,
        )
    )
