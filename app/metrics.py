from collections import defaultdict
import re

from app.config import (
    MIN_SCORE,
    WEIGHTS,
)
from app.qualis import QualisDB
from app.qualis_overrides import (
    get_override,
    load_overrides,
)
from app.publication_flags import (
    get_student_flag,
)


def normalize_title(title):
    return " ".join(
        str(title or "").strip().lower().split()
    )


def normalize_doi(doi):
    value = str(doi or "").strip().lower()

    if not value:
        return ""

    value = re.sub(
        r"^\s*https?://(?:dx\.)?doi\.org/",
        "",
        value,
    )

    value = re.sub(
        r"^\s*doi:\s*",
        "",
        value,
    )

    return value.rstrip(
        ".,;:)]}>"
    )


def publication_key(publication):
    doi = normalize_doi(
        publication.get("doi")
    )

    if doi:
        return (
            "doi",
            doi,
        )

    return (
        "title",
        publication.get("year"),
        normalize_title(
            publication.get("title")
        ),
    )


def deduplicate_publications(publications):
    result = []
    seen = set()

    for publication in publications:

        key = publication_key(
            publication
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(
            publication
        )

    return result


def normalize_lattes_data(lattes_data):
    if not isinstance(
        lattes_data,
        list,
    ):
        raise TypeError(
            "lattes_data deve ser uma lista de registros de Lattes."
        )

    result = {}

    for item in lattes_data:

        name = str(
            item.get("name") or ""
        ).strip()

        if not name:
            continue

        result[name] = item

    return result


def build_publication_index(
    professor_publications
):
    index = defaultdict(list)

    for (
        professor,
        publications,
    ) in professor_publications.items():

        for publication in publications:

            key = publication_key(
                publication
            )

            if professor not in index[key]:
                index[key].append(
                    professor
                )

    return index


def lookup_publication_qualis(
    publication,
    qualis_db,
):
    return qualis_db.lookup(
        issn=publication.get(
            "issn",
            "",
        ),
        title=publication.get(
            "venue",
            "",
        ),
        publication_type=publication.get(
            "type",
            "",
        ),
    )


def build_doi_qualis_index(
    professor_publications,
    qualis_db,
):
    doi_qualis = {}

    for publications in (
        professor_publications.values()
    ):

        for publication in publications:

            doi = normalize_doi(
                publication.get(
                    "doi"
                )
            )

            if (
                not doi
                or doi in doi_qualis
            ):
                continue

            qualis_result = (
                lookup_publication_qualis(
                    publication,
                    qualis_db,
                )
            )

            if qualis_result is not None:

                doi_qualis[doi] = (
                    qualis_result
                )

    return doi_qualis


def enrich_publication(
    publication,
    evaluated_professors,
    publication_index,
    qualis_db,
    doi_qualis=None,
    overrides=None,
):
    key = publication_key(
        publication
    )

    evaluated_coauthors = sorted(
        professor
        for professor in (
            publication_index.get(
                key,
                []
            )
        )
        if professor in evaluated_professors
    )

    doi = normalize_doi(
        publication.get(
            "doi"
        )
    )

    qualis_result = None

    if (
        doi
        and doi_qualis
    ):
        qualis_result = (
            doi_qualis.get(
                doi
            )
        )

    if qualis_result is None:

        qualis_result = (
            lookup_publication_qualis(
                publication,
                qualis_db,
            )
        )

    # -------------------------------------------------
    # Qualis oficial
    # -------------------------------------------------

    if qualis_result is None:

        official_qualis = None
        official_points = 0.0
        qualis_title = ""
        qualis_tipo = ""
        qualis_tipo_norm = ""
        qualis_issn = ""
        qualis_fonte = ""
        qualis_periodo = ""
        qualis_matched_by = ""

    else:

        official_qualis = (
            qualis_result.get(
                "qualis"
            )
        )

        official_points = (
            qualis_result.get(
                "points"
            )
            or 0.0
        )

        qualis_title = (
            qualis_result.get(
                "titulo",
                "",
            )
        )

        qualis_tipo = (
            qualis_result.get(
                "tipo",
                "",
            )
        )

        qualis_tipo_norm = (
            qualis_result.get(
                "tipo_norm",
                "",
            )
        )

        qualis_issn = (
            qualis_result.get(
                "issn",
                "",
            )
        )

        qualis_fonte = (
            qualis_result.get(
                "fonte",
                "",
            )
        )

        qualis_periodo = (
            qualis_result.get(
                "periodo",
                "",
            )
        )

        qualis_matched_by = (
            qualis_result.get(
                "matched_by",
                "",
            )
        )

    # -------------------------------------------------
    # Qualis manual
    # -------------------------------------------------

    override = get_override(
        publication,
        overrides=overrides,
    )

    manual_qualis = None
    manual_note = ""

    if override:

        manual_qualis = (
            override.get(
                "qualis"
            )
        )

        manual_note = (
            override.get(
                "note",
                "",
            )
        )

    # -------------------------------------------------
    # Qualis aplicado
    # -------------------------------------------------

    if manual_qualis:

        applied_qualis = (
            manual_qualis
        )

        applied_points = (
            WEIGHTS.get(
                manual_qualis,
                0.0,
            )
        )

        qualis_source = (
            "manual"
        )

    else:

        applied_qualis = (
            official_qualis
        )

        applied_points = (
            official_points
        )

        qualis_source = (
            "automatic"
            if official_qualis
            else ""
        )

    evaluated_coauthor_count = len(
        evaluated_coauthors
    )

    if (
        applied_points > 0
        and evaluated_coauthor_count > 0
    ):

        individual_points = (
            applied_points
            / evaluated_coauthor_count
        )

    else:

        individual_points = 0.0

    # -------------------------------------------------
    # Marcação manual de aluno
    # -------------------------------------------------

    student_author = get_student_flag(
        publication
    )

    enriched = dict(
        publication
    )

    enriched.update(
        {
            # Qualis oficial
            "qualis": applied_qualis,
            "qualis_official": (
                official_qualis
            ),
            "qualis_official_points": (
                official_points
            ),

            # Qualis manual
            "qualis_manual": (
                manual_qualis
            ),
            "qualis_manual_note": (
                manual_note
            ),

            # Qualis aplicado
            "qualis_applied": (
                applied_qualis
            ),
            "qualis_applied_points": (
                applied_points
            ),
            "qualis_source": (
                qualis_source
            ),

            # Dados do registro Qualis
            "qualis_title": (
                qualis_title
            ),
            "qualis_tipo": (
                qualis_tipo
            ),
            "qualis_tipo_norm": (
                qualis_tipo_norm
            ),
            "qualis_issn": (
                qualis_issn
            ),
            "qualis_fonte": (
                qualis_fonte
            ),
            "qualis_periodo": (
                qualis_periodo
            ),
            "qualis_matched_by": (
                qualis_matched_by
            ),

            # Coautoria
            "evaluated_professors": (
                evaluated_coauthors
            ),
            "evaluated_coauthor_count": (
                evaluated_coauthor_count
            ),

            # Pontuação individual
            "individual_points": (
                individual_points
            ),

            # Marcação de aluno
            "student_author": (
                student_author
            ),
        }
    )

    return enriched


def evaluate_professors(
    lattes_data,
    qualis_db=None,
    start_year=None,
    end_year=None,
    min_score=None,
):
    if qualis_db is None:

        qualis_db = QualisDB()

    if min_score is None:

        min_score = MIN_SCORE

    if (
        start_year is not None
        and end_year is not None
        and start_year > end_year
    ):

        raise ValueError(
            "start_year não pode ser maior que end_year."
        )

    professor_data = (
        normalize_lattes_data(
            lattes_data
        )
    )

    evaluated_professors = set(
        professor_data.keys()
    )

    professor_publications = {}

    for (
        professor,
        data,
    ) in professor_data.items():

        publications = data.get(
            "publications",
            [],
        )

        if (
            start_year is not None
            and end_year is not None
        ):

            publications = [
                publication
                for publication in publications
                if (
                    start_year
                    <= publication.get(
                        "year",
                        0,
                    )
                    <= end_year
                )
            ]

        publications = (
            deduplicate_publications(
                publications
            )
        )

        professor_publications[
            professor
        ] = publications

    publication_index = (
        build_publication_index(
            professor_publications
        )
    )

    doi_qualis = (
        build_doi_qualis_index(
            professor_publications,
            qualis_db,
        )
    )

    overrides = load_overrides()

    enriched_by_key = {}

    for publications in (
        professor_publications.values()
    ):

        for publication in publications:

            key = publication_key(
                publication
            )

            if key in enriched_by_key:
                continue

            enriched_by_key[key] = (
                enrich_publication(
                    publication=publication,
                    evaluated_professors=(
                        evaluated_professors
                    ),
                    publication_index=(
                        publication_index
                    ),
                    qualis_db=qualis_db,
                    doi_qualis=doi_qualis,
                    overrides=overrides,
                )
            )

    publications = list(
        enriched_by_key.values()
    )

    professors = {}

    coauthorships = (
        defaultdict(list)
    )

    pending = []

    for professor in sorted(
        evaluated_professors
    ):

        data = professor_data[
            professor
        ]

        own_publications = (
            professor_publications[
                professor
            ]
        )

        counts = {
            qualis: 0
            for qualis in WEIGHTS
        }

        points = {
            qualis: 0.0
            for qualis in WEIGHTS
        }

        total = 0.0

        coauthored_count = 0

        for publication in (
            own_publications
        ):

            key = publication_key(
                publication
            )

            enriched = (
                enriched_by_key[
                    key
                ]
            )

            qualis = enriched.get(
                "qualis_applied"
            )

            individual_points = (
                enriched.get(
                    "individual_points",
                    0.0,
                )
            )

            evaluated_coauthors = (
                enriched.get(
                    "evaluated_professors",
                    [],
                )
            )

            if qualis in counts:

                counts[qualis] += 1

                points[qualis] += (
                    individual_points
                )

                total += (
                    individual_points
                )

            if len(
                evaluated_coauthors
            ) > 1:

                coauthored_count += 1

                coauthorships[
                    professor
                ].append(
                    enriched
                )

            if not qualis:

                pending.append(
                    {
                        "professor": (
                            professor
                        ),
                        "year": (
                            publication.get(
                                "year"
                            )
                        ),
                        "type": (
                            publication.get(
                                "type"
                            )
                        ),
                        "title": (
                            publication.get(
                                "title"
                            )
                        ),
                        "venue": (
                            publication.get(
                                "venue"
                            )
                        ),
                        "issn": (
                            publication.get(
                                "issn"
                            )
                        ),
                        "doi": (
                            publication.get(
                                "doi"
                            )
                        ),
                        "pendencia": (
                            "Qualis não encontrado"
                        ),
                    }
                )

        professors[
            professor
        ] = {
            "professor": professor,
            "lattes_url": data.get(
                "lattes_url"
            ),
            "lattes_update": data.get(
                "last_update",
                data.get(
                    "lattes_update",
                    "",
                ),
            ),
            "lattes_update_date": data.get(
                "last_update_date"
            ),
            "publications": len(
                own_publications
            ),
            "coauthored_publications": (
                coauthored_count
            ),
            "total": total,
            "status": (
                "ATENDE"
                if total >= min_score
                else "NÃO ATENDE"
            ),
            "counts": counts,
            "points": points,
        }

    return {
        "start_year": start_year,
        "end_year": end_year,
        "min_score": min_score,
        "professors": professors,
        "publications": publications,
        "coauthorships": dict(
            coauthorships
        ),
        "pending": pending,
        "publication_index": dict(
            publication_index
        ),
    }
