import hashlib
import re
import time
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from .config import (
    HEADLESS,
    LATTES_DELAY_SECONDS,
    OUTPUT_DIR,
)


def normalize_space(text):
    if not text:
        return ""

    return re.sub(r"\s+", " ", text).strip()


def extract_name(soup):
    element = soup.select_one("h2.nome")

    if element:
        return normalize_space(
            element.get_text(" ", strip=True)
        )

    return ""


def extract_update_date(text):
    patterns = [
        r"Última atualização do currículo.*?(\d{2}/\d{2}/\d{4})",
        r"Atualização do currículo.*?(\d{2}/\d{2}/\d{4})",
        r"Data da última atualização.*?(\d{2}/\d{2}/\d{4})",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        if match:
            return match.group(1)

    match = re.search(
        r"atualiza.{0,100}?(\d{2}/\d{2}/\d{4})",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if match:
        return match.group(1)

    return ""


def parse_date(value):
    if not value:
        return None

    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(
                value,
                fmt,
            ).date()
        except ValueError:
            pass

    return None


def save_html(url, html):
    raw_dir = OUTPUT_DIR / "raw"

    raw_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    identifier = hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()[:16]

    html_path = raw_dir / f"{identifier}.html"

    html_path.write_text(
        html,
        encoding="utf-8",
    )

    return html_path


def extract_journal_articles(soup):

    bloco = soup.select_one(
        "#artigos-completos"
    )

    if not bloco:
        return []

    itens = bloco.select(
        ".layout-cell-11"
    )

    publications = []

    for item in itens:

        ano_el = item.select_one(
            '[data-tipo-ordenacao="ano"]'
        )

        ano_text = (
            ano_el.get_text(strip=True)
            if ano_el
            else ""
        )

        try:
            year = int(ano_text)
        except ValueError:
            year = None

        if not year:
            continue

        autor_el = item.select_one(
            '[data-tipo-ordenacao="autor"]'
        )

        primeiro_autor = (
            autor_el.get_text(strip=True)
            if autor_el
            else ""
        )

        doi_el = item.select_one(
            "a.icone-doi"
        )

        doi = (
            doi_el.get("href", "")
            if doi_el
            else ""
        )

        issn_el = item.select_one(
            "img[data-issn]"
        )

        issn = (
            issn_el.get("data-issn", "")
            if issn_el
            else ""
        )

        if not issn:
            citado_el = item.select_one(
                "span.citado[cvuri]"
            )

            if citado_el:
                cvuri = citado_el.get(
                    "cvuri",
                    ""
                )

                match_issn = re.search(
                    r"[?&]issn=(\d{8})",
                    cvuri,
                )

                if match_issn:
                    issn = match_issn.group(1)

        transform = item.select_one(
            "span.transform"
        )

        if not transform:
            continue

        text = transform.get_text(
            " ",
            strip=True,
        )

        prefix = (
            primeiro_autor
            + " "
            + ano_text
        )

        if text.startswith(prefix):
            text = text[len(prefix):].strip()

        match = re.match(
            r"^(.*?)\s+\.\s+(.*?)\.\s+(.+?),\s*v\.",
            text,
            flags=re.DOTALL,
        )

        if not match:
            continue

        authors = normalize_space(
            match.group(1)
        )

        title = normalize_space(
            match.group(2)
        )

        venue = normalize_space(
            match.group(3)
        )

        publications.append(
            {
                "year": year,
                "type": "journal",
                "title": title,
                "authors": authors,
                "venue": venue,
                "issn": issn,
                "doi": doi,
            }
        )

    return publications


def extract_conference_papers(soup):

    anchor = soup.select_one(
        'a[name="TrabalhosPublicadosAnaisCongresso"]'
    )

    if not anchor:
        return []

    cabecalho = anchor.find_parent(
        "div",
        class_="cita-artigos",
    )

    if not cabecalho:
        return []

    publications = []

    el = cabecalho.find_next_sibling()

    while el:

        if (
            el.name == "div"
            and "cita-artigos" in el.get("class", [])
        ):
            break

        if (
            el.name == "div"
            and el.get("class") == [
                "layout-cell",
                "layout-cell-11",
            ]
        ):

            text = normalize_space(
                el.get_text(
                    " ",
                    strip=True,
                )
            )

            doi_el = el.select_one(
                "a.icone-doi"
            )

            doi = (
                doi_el.get("href", "")
                if doi_el
                else ""
            )

            match = re.match(
                r"^(.*?)\s+\.\s+(.*?)\.\s+In:\s+(.*?),\s*(\d{4}),\s*(.*?)(?:\.|$)",
                text,
                flags=re.DOTALL,
            )

            if match:

                authors = normalize_space(
                    match.group(1)
                )

                title = normalize_space(
                    match.group(2)
                )

                venue = normalize_space(
                    match.group(3)
                )

                year = int(
                    match.group(4)
                )

                publications.append(
                    {
                        "year": year,
                        "type": "conference",
                        "title": title,
                        "authors": authors,
                        "venue": venue,
                        "issn": "",
                        "doi": doi,
                    }
                )

        el = el.find_next_sibling()

    return publications


def collect_lattes(url):

    raw_dir = OUTPUT_DIR / "raw"

    raw_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    identifier = hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()[:16]

    html_path = raw_dir / f"{identifier}.html"

    if html_path.exists():

        print(
            f"Usando HTML salvo: {html_path}"
        )

        html = html_path.read_text(
            encoding="utf-8"
        )

        soup = BeautifulSoup(
            html,
            "lxml",
        )

        text = soup.get_text(
            "\n",
            strip=True,
        )

        name = extract_name(
            soup
        )

        update_date = extract_update_date(
            text
        )

        journal_publications = (
            extract_journal_articles(
                soup
            )
        )

        conference_publications = (
            extract_conference_papers(
                soup
            )
        )

        publications = (
            journal_publications
            + conference_publications
        )

        print(
            f"Nome encontrado: "
            f"{name or '[não encontrado]'}"
        )

        print(
            "Última atualização: "
            f"{update_date or '[não encontrada]'}"
        )

        print(
            "Artigos de periódico encontrados: "
            f"{len(journal_publications)}"
        )

        print(
            "Trabalhos de congresso encontrados: "
            f"{len(conference_publications)}"
        )

        print(
            "Total de publicações encontradas: "
            f"{len(publications)}"
        )

        return {
            "url": url,
            "name": name,
            "last_update": update_date,
            "last_update_date": (
                parse_date(update_date)
                if update_date
                else None
            ),
            "publications": publications,
            "html_path": str(
                html_path
            ),
            "text": text,
        }

    print(
        f"Acessando Lattes: {url}"
    )

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=HEADLESS
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1000,
            }
        )

        try:

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=120000,
            )

            page.wait_for_timeout(
                5000
            )

            body_text = page.locator(
                "body"
            ).inner_text()

            if "Código de segurança" in body_text:

                print()
                print("=" * 60)
                print(
                    "CAPTCHA DO LATTES DETECTADO"
                )
                print(
                    "Resolva o CAPTCHA na janela do navegador."
                )
                print(
                    "Depois volte ao terminal e pressione ENTER."
                )
                print("=" * 60)
                print()

                input(
                    "Pressione ENTER após resolver o CAPTCHA... "
                )

                page.wait_for_timeout(
                    3000
                )

            html = page.content()

            text = page.locator(
                "body"
            ).inner_text()

            html_path = save_html(
                url,
                html,
            )

            soup = BeautifulSoup(
                html,
                "lxml",
            )

            name = extract_name(
                soup
            )

            update_date = extract_update_date(
                text
            )

            journal_publications = (
                extract_journal_articles(
                    soup
                )
            )

            conference_publications = (
                extract_conference_papers(
                    soup
                )
            )

            publications = (
                journal_publications
                + conference_publications
            )

            print(
                f"Nome encontrado: "
                f"{name or '[não encontrado]'}"
            )

            print(
                "Última atualização: "
                f"{update_date or '[não encontrada]'}"
            )

            print(
                "Artigos de periódico encontrados: "
                f"{len(journal_publications)}"
            )

            print(
                "Trabalhos de congresso encontrados: "
                f"{len(conference_publications)}"
            )

            print(
                "Total de publicações encontradas: "
                f"{len(publications)}"
            )

            print(
                f"HTML salvo em: {html_path}"
            )

            time.sleep(
                LATTES_DELAY_SECONDS
            )

            return {
                "url": url,
                "name": name,
                "last_update": update_date,
                "last_update_date": (
                    parse_date(update_date)
                    if update_date
                    else None
                ),
                "publications": publications,
                "html_path": str(
                    html_path
                ),
                "text": text,
            }

        finally:

            browser.close()
