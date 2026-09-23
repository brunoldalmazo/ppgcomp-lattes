from pathlib import Path

from bs4 import BeautifulSoup

from app.config import OUTPUT_DIR
from app.lattes import (
    extract_name,
    extract_update_date,
    extract_journal_articles,
    extract_conference_papers,
    parse_date,
)
from app.metrics import evaluate_professors
from app.qualis import QualisDB


def load_saved_lattes():
    raw_dir = OUTPUT_DIR / "raw"

    html_files = sorted(raw_dir.glob("*.html"))

    if not html_files:
        print("Nenhum HTML encontrado em:", raw_dir)
        return []

    lattes_data = []

    for html_path in html_files:
        print(f"Lendo: {html_path.name}")

        html = html_path.read_text(
            encoding="utf-8"
        )

        soup = BeautifulSoup(
            html,
            "lxml",
        )

        text = soup.get_text(
            " ",
            strip=True,
        )

        name = extract_name(soup)
        update_date = extract_update_date(text)

        journal_publications = (
            extract_journal_articles(soup)
        )

        conference_publications = (
            extract_conference_papers(soup)
        )

        publications = (
            journal_publications
            + conference_publications
        )

        lattes_data.append(
            {
                "url": "",
                "name": name,
                "last_update": update_date,
                "last_update_date": (
                    parse_date(update_date)
                    if update_date
                    else None
                ),
                "publications": publications,
                "html_path": str(html_path),
                "text": text,
            }
        )

        print(
            f"  Nome: {name or '[não encontrado]'}"
        )
        print(
            f"  Atualização: "
            f"{update_date or '[não encontrada]'}"
        )
        print(
            f"  Periódicos: "
            f"{len(journal_publications)}"
        )
        print(
            f"  Congressos: "
            f"{len(conference_publications)}"
        )
        print(
            f"  Total: {len(publications)}"
        )
        print()

    return lattes_data


def main():
    print("=" * 70)
    print("DIAGNÓSTICO DE PENDÊNCIAS — HTMLs SALVOS")
    print("=" * 70)
    print()

    lattes_data = load_saved_lattes()

    if not lattes_data:
        return

    qualis_db = QualisDB()

    result = evaluate_professors(
        lattes_data=lattes_data,
        qualis_db=qualis_db,
    )

    pending = result["pending"]

    print()
    print("=" * 70)
    print(f"TOTAL DE PENDÊNCIAS: {len(pending)}")
    print("=" * 70)
    print()

    if not pending:
        print("Nenhuma pendência.")
        return

    # ------------------------------------------------------------
    # Pendências por tipo
    # ------------------------------------------------------------

    print("PENDÊNCIAS POR TIPO")
    print("-" * 70)

    by_type = {}

    for item in pending:
        reason = (
            item.get("reason")
            or item.get("tipo")
            or item.get("type")
            or "SEM TIPO"
        )

        by_type[reason] = (
            by_type.get(reason, 0) + 1
        )

    for reason, count in sorted(
        by_type.items(),
        key=lambda x: (-x[1], x[0]),
    ):
        print(
            f"{count:4d} | {reason}"
        )

    print()

    # ------------------------------------------------------------
    # Todas as pendências
    # ------------------------------------------------------------

    print("DETALHAMENTO")
    print("-" * 70)

    for i, item in enumerate(
        pending,
        start=1,
    ):

        print(
            f"[{i}]"
        )

        for key, value in item.items():
            print(
                f"    {key}: {value}"
            )

        print()

    # ------------------------------------------------------------
    # Agrupamento por publicação
    # ------------------------------------------------------------

    print("=" * 70)
    print("AGRUPAMENTO POR PUBLICAÇÃO")
    print("=" * 70)
    print()

    grouped = {}

    for item in pending:

        year = item.get("year", "")
        title = item.get("title", "")

        key = (
            year,
            str(title).strip().lower(),
        )

        grouped.setdefault(
            key,
            [],
        ).append(item)

    print(
        f"Pendências individuais: {len(pending)}"
    )
    print(
        f"Publicações distintas com pendência: "
        f"{len(grouped)}"
    )
    print()

    for i, (
        (year, title),
        items,
    ) in enumerate(
        sorted(grouped.items()),
        start=1,
    ):

        print(
            f"[{i}] {year} | {title}"
        )

        for item in items:

            professor = (
                item.get("professor")
                or item.get("name")
                or ""
            )

            reason = (
                item.get("reason")
                or item.get("tipo")
                or item.get("type")
                or ""
            )

            venue = (
                item.get("venue")
                or ""
            )

            issn = (
                item.get("issn")
                or ""
            )

            print(
                f"    Professor: {professor}"
            )
            print(
                f"    Tipo: {reason}"
            )
            print(
                f"    Venue: {venue}"
            )
            print(
                f"    ISSN: {issn}"
            )

        print()


if __name__ == "__main__":
    main()
