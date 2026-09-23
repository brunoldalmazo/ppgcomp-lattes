import re
import unicodedata
from pathlib import Path

import pandas as pd

from .config import QUALIS_FILE


QUALIS_POINTS = {
    "A1": 1.000,
    "A2": 0.875,
    "A3": 0.750,
    "A4": 0.625,
    "A5": 0.500,
    "A6": 0.375,
    "A7": 0.250,
    "A8": 0.125,
}


QUALIS_CONVERSION = {
    "B1": "A5",
    "B2": "A6",
    "B3": "A7",
    "B4": "A8",
}


def normalize_text(value):
    if value is None:
        return ""

    value = str(value).strip().lower()

    value = unicodedata.normalize(
        "NFKD",
        value,
    )

    value = "".join(
        char
        for char in value
        if not unicodedata.combining(char)
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def normalize_issn(value):
    if value is None:
        return ""

    value = str(value).strip().upper()

    return re.sub(
        r"[^0-9X]",
        "",
        value,
    )


def normalize_tipo(value):
    value = normalize_text(value)

    if value in {
        "article",
        "journal",
        "periodico",
        "periodico cientifico",
        "journal article",
    }:
        return "journal"

    if value in {
        "conference",
        "evento",
        "conferencia",
        "conference/event",
        "conference event",
        "anais",
    }:
        return "conference"

    if "period" in value:
        return "journal"

    if (
        "confer" in value
        or "evento" in value
        or "anais" in value
    ):
        return "conference"

    return value


def normalize_conference_title(value):
    value = normalize_text(
        value
    )

    value = re.sub(
        r"\b\d{4}\b",
        " ",
        value,
    )

    value = re.sub(
        r"\b\d+(?:st|nd|rd|th)\b",
        " ",
        value,
    )

    value = re.sub(
        r"\b\d+(?:st|nd|rd|th)?\b",
        " ",
        value,
    )

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def compact_text(value):
    return re.sub(
        r"[^a-z0-9]",
        "",
        normalize_text(value),
    )


def extract_parenthetical_acronyms(value):
    if not value:
        return set()

    identifiers = set()

    for match in re.findall(
        r"\(([^()]{1,30})\)",
        value,
    ):
        candidate = normalize_text(
            match
        )

        compact = compact_text(
            candidate
        )

        if (
            compact
            and re.fullmatch(
                r"[a-z][a-z0-9-]{1,19}",
                compact,
            )
        ):
            identifiers.add(
                compact
            )

    return identifiers


def extract_explicit_acronym(value):
    if not value:
        return set()

    identifiers = set()

    for match in re.findall(
        r"\b[A-Z][A-Z0-9-]{1,19}\b",
        value,
    ):
        candidate = compact_text(
            match
        )

        if candidate:
            identifiers.add(
                candidate
            )

    return identifiers


def extract_leading_acronym(value):
    if not value:
        return set()

    matches = re.findall(
        r"^\s*([A-Z][A-Z0-9-]{1,19})\b",
        value,
    )

    identifiers = set()

    for match in matches:
        candidate = compact_text(
            match
        )

        if candidate:
            identifiers.add(
                candidate
            )

    return identifiers


def event_identifiers(title):
    title_norm = normalize_text(
        title
    )

    identifiers = set()

    identifiers.update(
        extract_parenthetical_acronyms(
            title_norm
        )
    )

    identifiers.update(
        extract_explicit_acronym(
            title
        )
    )

    identifiers.add(
        title_norm
    )

    identifiers.add(
        compact_text(title_norm)
    )

    return {
        value
        for value in identifiers
        if value
    }


def conference_title_tokens(value):
    normalized = normalize_conference_title(
        value
    )

    tokens = normalized.split()

    stopwords = {
        "a",
        "an",
        "and",
        "as",
        "at",
        "conferencia",
        "conference",
        "de",
        "do",
        "da",
        "das",
        "dos",
        "em",
        "for",
        "international",
        "na",
        "no",
        "on",
        "of",
        "os",
        "the",
        "um",
        "uma",
        "with",
    }

    return {
        token
        for token in tokens
        if len(token) >= 3
        and token not in stopwords
    }


def normalize_qualis(value):
    qualis = (
        str(value or "")
        .strip()
        .upper()
    )

    if qualis in QUALIS_POINTS:
        return qualis

    return QUALIS_CONVERSION.get(
        qualis,
        "",
    )


def read_qualis_file(path):
    path = Path(path)

    df = pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
    )

    df.columns = [
        normalize_text(column)
        for column in df.columns
    ]

    rename_map = {}

    for column in df.columns:
        if column == "issn":
            rename_map[column] = "issn"
        elif column == "titulo":
            rename_map[column] = "titulo"
        elif column == "qualis":
            rename_map[column] = "qualis"
        elif column == "tipo":
            rename_map[column] = "tipo"
        elif column == "fonte":
            rename_map[column] = "fonte"
        elif column == "periodo":
            rename_map[column] = "periodo"

    df = df.rename(
        columns=rename_map
    )

    required = {
        "titulo",
        "qualis",
        "tipo",
        "fonte",
        "periodo",
    }

    for column in required:
        if column not in df.columns:
            df[column] = ""

    if "issn" not in df.columns:
        df["issn"] = ""

    df["issn_norm"] = df["issn"].apply(
        normalize_issn
    )

    df["titulo_norm"] = df["titulo"].apply(
        normalize_text
    )

    df["titulo_conference_norm"] = (
        df["titulo"].apply(
            normalize_conference_title
        )
    )

    df["tipo_norm"] = df["tipo"].apply(
        normalize_tipo
    )

    df["qualis_original"] = (
        df["qualis"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df["qualis_norm"] = df[
        "qualis_original"
    ].apply(
        normalize_qualis
    )

    df["periodo_norm"] = (
        df["periodo"]
        .astype(str)
        .str.strip()
    )

    return df


class QualisDB:

    def __init__(
        self,
        qualis_file=None,
        conference_file=None,
    ):
        self.qualis_file = (
            Path(qualis_file)
            if qualis_file
            else Path(QUALIS_FILE)
        )

        self.df_journals_all = (
            read_qualis_file(
                self.qualis_file
            )
        )

        if conference_file:
            self.conference_file = (
                Path(conference_file)
            )
        else:
            self.conference_file = (
                self.qualis_file.parent
                / "qualis_conferencias.csv"
            )

        if self.conference_file.exists():
            self.df_conferences_all = (
                read_qualis_file(
                    self.conference_file
                )
            )
        else:
            self.df_conferences_all = (
                pd.DataFrame(
                    columns=self.df_journals_all.columns
                )
            )

        self.df = pd.concat(
            [
                self.df_journals_all,
                self.df_conferences_all,
            ],
            ignore_index=True,
        )

        self.df_journals = (
            self.df_journals_all[
                (
                    self.df_journals_all[
                        "tipo_norm"
                    ] == "journal"
                )
                & (
                    self.df_journals_all[
                        "qualis_norm"
                    ].isin(QUALIS_POINTS)
                )
            ].copy()
        )

        self.df_conferences = (
            self.df_conferences_all[
                (
                    self.df_conferences_all[
                        "tipo_norm"
                    ] == "conference"
                )
                & (
                    self.df_conferences_all[
                        "qualis_norm"
                    ].isin(QUALIS_POINTS)
                )
            ].copy()
        )

        self.journal_by_issn = {}
        self.journal_by_title = {}

        self.conference_by_title = {}
        self.conference_by_identifier = {}

        for _, row in (
            self.df_journals.iterrows()
        ):
            issn = row["issn_norm"]

            if issn:
                self.journal_by_issn[
                    issn
                ] = row

            title = row["titulo_norm"]

            if title:
                self.journal_by_title[
                    title
                ] = row

        for _, row in (
            self.df_conferences.iterrows()
        ):
            title = row[
                "titulo_conference_norm"
            ]

            if title:
                self.conference_by_title[
                    title
                ] = row

            identifiers = (
                event_identifiers(
                    row["titulo"]
                )
            )

            for identifier in identifiers:
                if identifier in {
                    title,
                    compact_text(title),
                }:
                    continue

                self.conference_by_identifier.setdefault(
                    identifier,
                    [],
                ).append(
                    row
                )

        self.conference_identifier_count = sum(
            len(values)
            for values in (
                self.conference_by_identifier.values()
            )
        )

    def _result(
        self,
        row,
        match_type,
    ):
        if row is None:
            return {
                "qualis": None,
                "points": 0.0,
                "match_type": match_type,
                "titulo": None,
                "issn": "",
                "fonte": "",
                "periodo": "",
            }

        qualis = row[
            "qualis_norm"
        ]

        if qualis not in QUALIS_POINTS:
            return {
                "qualis": None,
                "points": 0.0,
                "match_type": match_type,
                "titulo": row["titulo"],
                "issn": row["issn"],
                "fonte": row["fonte"],
                "periodo": row["periodo"],
            }

        return {
            "qualis": qualis,
            "points": QUALIS_POINTS[qualis],
            "match_type": match_type,
            "titulo": row["titulo"],
            "issn": row["issn"],
            "fonte": row["fonte"],
            "periodo": row["periodo"],
        }

    def lookup_journal(
        self,
        title="",
        issn="",
    ):
        issn_norm = normalize_issn(
            issn
        )

        if issn_norm:
            row = (
                self.journal_by_issn.get(
                    issn_norm
                )
            )

            if row is not None:
                return self._result(
                    row,
                    "issn_exact",
                )

        title_norm = normalize_text(
            title
        )

        if title_norm:
            row = (
                self.journal_by_title.get(
                    title_norm
                )
            )

            if row is not None:
                return self._result(
                    row,
                    "title_exact",
                )

        return self._result(
            None,
            "not_found",
        )

    def lookup_conference(
        self,
        title="",
    ):
        title_norm = (
            normalize_conference_title(
                title
            )
        )

        row = (
            self.conference_by_title.get(
                title_norm
            )
        )

        if row is not None:
            return self._result(
                row,
                "title_exact",
            )

        query_tokens = conference_title_tokens(
            title
        )

        if query_tokens:
            scored_matches = []

            for key, candidate in (
                self.conference_by_title.items()
            ):
                candidate_tokens = (
                    conference_title_tokens(
                        key
                    )
                )

                if query_tokens.issubset(
                    candidate_tokens
                ):
                    extra_tokens = (
                        candidate_tokens
                        - query_tokens
                    )

                    scored_matches.append(
                        (
                            len(extra_tokens),
                            candidate,
                        )
                    )

            if scored_matches:
                best_extra_count = min(
                    score[0]
                    for score in scored_matches
                )

                best_matches = [
                    candidate
                    for extra_count, candidate
                    in scored_matches
                    if extra_count
                    == best_extra_count
                ]

                unique_matches = {}

                for candidate in best_matches:
                    identifier = (
                        candidate["titulo"]
                    )

                    unique_matches[
                        identifier
                    ] = candidate

                if len(unique_matches) == 1:
                    return self._result(
                        next(
                            iter(
                                unique_matches.values()
                            )
                        ),
                        "title_tokens",
                    )

        identifiers = (
            extract_parenthetical_acronyms(
                title
            )
        )

        for identifier in identifiers:
            candidates = (
                self.conference_by_identifier.get(
                    identifier,
                    [],
                )
            )

            if len(candidates) == 1:
                return self._result(
                    candidates[0],
                    "acronym_exact",
                )

        leading_identifiers = (
            extract_leading_acronym(
                title
            )
        )

        for identifier in (
            leading_identifiers
        ):
            candidates = (
                self.conference_by_identifier.get(
                    identifier,
                    [],
                )
            )

            if len(candidates) == 1:
                return self._result(
                    candidates[0],
                    "leading_acronym",
                )

        matches = []

        for key, candidate in (
            self.conference_by_title.items()
        ):
            if not key:
                continue

            if (
                title_norm in key
                or key in title_norm
            ):
                matches.append(
                    candidate
                )

        if len(matches) == 1:
            return self._result(
                matches[0],
                "title_partial",
            )

        return self._result(
            None,
            "not_found",
        )

    def lookup(
        self,
        title="",
        issn="",
        publication_type="",
    ):
        tipo = normalize_tipo(
            publication_type
        )

        if tipo == "journal":
            return self.lookup_journal(
                title=title,
                issn=issn,
            )

        if tipo == "conference":
            return self.lookup_conference(
                title=title,
            )

        if issn:
            result = self.lookup_journal(
                title=title,
                issn=issn,
            )

            if result["qualis"] is not None:
                return result

        return self.lookup_conference(
            title=title,
        )
