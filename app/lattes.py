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


TECHNICAL_SECTION_TYPES = {
    "Patente": "patent",
    "Programa de computador": "software",
    "Programa de computador registrado": "software",
    "Desenho industrial": "industrial_design",
    "Desenho industrial registrado": "industrial_design",
}


TECHNICAL_IGNORED_SECTIONS = {
    "Programas de computador sem registro",
    "Programa de Computador sem registro de patente",
    "Produtos tecnológicos",
    "Processos ou técnicas",
    "Trabalhos técnicos",
    "Demais tipos de produção técnica",
}


def normalize_section_header(text):
    """
    Remove o sufixo "Ordenar por ..." do texto de cabeçalho.
    """

    return re.sub(
        r"Ordenar por.*$",
        "",
        text or "",
        flags=re.IGNORECASE,
    ).strip()


def parse_technical_date(value):
    date = parse_date(value)

    if date:
        return date.isoformat()

    return None


def parse_technical_item(raw, section_type, section_header):
    """
    Interpreta o texto de um item de produção técnica.

    section_type: patent | software | industrial_design
    """

    if not raw:
        return None

    item = {
        "type": section_type,
        "patent_kind": None,
        "status": None,
        "title": None,
        "year": None,
        "authors": None,
        "country": None,
        "registry_number": None,
        "registry_institution": None,
        "deposit_date": None,
        "grant_date": None,
        "source_section": section_header,
        "raw": raw,
    }

    head = re.match(
        r"^(.*?)\s+\.\s+(.*?)\.\s+(\d{4})",
        raw,
        flags=re.DOTALL,
    )

    if head:
        item["authors"] = normalize_space(
            head.group(1)
        )
        item["title"] = normalize_space(
            head.group(2)
        )
        item["year"] = int(head.group(3))

    registry_match = re.search(
        r"Número do registro:\s*([^,\s]+)",
        raw,
    )

    if registry_match:
        item["registry_number"] = registry_match.group(
            1
        ).strip()

    institution_match = re.search(
        r"Instituição de registro:\s*([^.]+)",
        raw,
    )

    if institution_match:
        item["registry_institution"] = (
            normalize_space(
                institution_match.group(1)
            )
        )

    country_match = re.search(
        r",\s*([^,.]+?)\.\s*Patente:",
        raw,
    )

    if country_match:
        item["country"] = normalize_space(
            country_match.group(1)
        )

    deposit_match = re.search(
        r"Depósito:\s*(\d{2}/\d{2}/\d{4})",
        raw,
    )

    if deposit_match:
        item["deposit_date"] = parse_technical_date(
            deposit_match.group(1)
        )

    grant_match = re.search(
        r"Concessão:\s*(\d{2}/\d{2}/\d{4})",
        raw,
    )

    if grant_match:
        item["grant_date"] = parse_technical_date(
            grant_match.group(1)
        )

    patent_kind_match = re.search(
        r"Patente:\s*([^.]+?)\.",
        raw,
    )

    if section_type == "patent" and patent_kind_match:

        kind = normalize_space(
            patent_kind_match.group(1)
        ).lower()

        if "modelo de utilidade" in kind:
            item["patent_kind"] = "utility_model"

        elif "inovação" in kind:
            item["patent_kind"] = "invention"

    # -------------------------------------------------
    # Classificação de status
    # -------------------------------------------------

    if section_type == "patent":

        if item["grant_date"] or re.search(
            r"Concessão:",
            raw,
        ):
            item["status"] = "granted"

        elif item["deposit_date"] or re.search(
            r"Depósito:",
            raw,
        ):
            item["status"] = "deposited"

    else:

        if item["registry_number"]:
            item["status"] = "registered"

    # -------------------------------------------------
    # Ano do evento (D3):
    # concessão, se concedida; senão o ano do texto
    # (depósito para patentes; registro para
    # software e desenho industrial).
    # -------------------------------------------------

    if (
        item["status"] == "granted"
        and item["grant_date"]
    ):

        try:
            item["year"] = int(
                item["grant_date"][:4]
            )
        except (TypeError, ValueError):
            pass

    return item


def extract_technical_production(soup):
    """
    Extrai patentes, programas de computador registrados e
    desenhos industriais registrados.

    Usa o texto do cabeçalho (div.inst_back / div.cita-artigos)
    e coleta os div.layout-cell-11 irmãos seguintes até o próximo
    cabeçalho, na ordem do documento.

    A plataforma Lattes renderiza cada bloco duas vezes no HTML
    (headers e itens duplicados em containers gêmeos), então clones
    exatos (texto raw idêntico) são descartados dentro do mesmo
    currículo. Duplicatas entre CVs são mantidas: são elas que
    alimentam a divisão de pontos entre professores (D1) e o merge
    de status entre ocorrências (D2).
    """

    items = []
    seen_raw = set()

    headers = soup.select(
        "div.inst_back, div.cita-artigos"
    )

    for header in headers:

        header_text = normalize_space(
            header.get_text(" ", strip=True)
        )

        header_text = normalize_section_header(
            header_text
        )

        if header_text in TECHNICAL_IGNORED_SECTIONS:
            continue

        section_type = TECHNICAL_SECTION_TYPES.get(
            header_text
        )

        if not section_type:
            continue

        sibling = header.find_next_sibling()

        while sibling:

            classes = sibling.get("class") or []

            if (
                sibling.name == "div"
                and (
                    "inst_back" in classes
                    or "cita-artigos" in classes
                )
            ):
                break

            if (
                sibling.name == "div"
                and classes
                == [
                    "layout-cell",
                    "layout-cell-11",
                ]
            ):
                raw = normalize_space(
                    sibling.get_text(
                        " ",
                        strip=True,
                    )
                )

                parsed = parse_technical_item(
                    raw,
                    section_type,
                    header_text,
                )

                if parsed and raw not in seen_raw:
                    seen_raw.add(raw)
                    items.append(parsed)

            sibling = sibling.find_next_sibling()

    return items


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

        technical_production = (
            extract_technical_production(
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
            "Itens de produção técnica encontrados: "
            f"{len(technical_production)}"
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
            "technical_production": technical_production,
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

            technical_production = (
                extract_technical_production(
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
                "Itens de produção técnica encontrados: "
                f"{len(technical_production)}"
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
                "technical_production": technical_production,
                "html_path": str(
                    html_path
                ),
                "text": text,
            }

        finally:

            browser.close()
