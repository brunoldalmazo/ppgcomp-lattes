"""
Dry-run da especificação de produção técnica (Fase 0).

Lê os HTMLs já salvos em output/raw/ (sem rede, sem novo scrape),
extrai patentes, programas de computador registrados e desenhos
industriais registrados e imprime um relatório de verificação.

Não altera dados.json nem nenhum dado de produção.

Uso:

    python3 scripts/dry_run_producao_tecnica.py
"""

import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(ROOT),
)

from bs4 import BeautifulSoup

from app.lattes import (
    extract_name,
    extract_technical_production,
)
from app.metrics import technical_key


RAW_DIR = ROOT / "output" / "raw"

EXPECTED = {
    "patents": 25,
    "patents_invention": 19,
    "patents_utility_model": 6,
    # D2 aprovada: melhor status vence. A patente BR1020240245865
    # aparece como depositada em alguns CVs e concedida
    # (Concessão: 21/10/2025) em outros => concedida.
    # Números originais de referência (5/20) não aplicavam o merge D2.
    "patents_granted": 6,
    "patents_deposited": 19,
    "software_registered": 132,
    "industrial_design_registered": 10,
}


def load_items():
    """
    Extrai a produção técnica de todos os HTMLs salvos.

    Retorna (registros_por_professor, todos_os_itens).
    """

    professor_items = {}
    all_items = []

    html_files = sorted(RAW_DIR.glob("*.html"))

    if not html_files:
        raise RuntimeError(
            f"Nenhum HTML encontrado em {RAW_DIR}"
        )

    for html_path in html_files:

        soup = BeautifulSoup(
            html_path.read_text(encoding="utf-8"),
            "lxml",
        )

        name = extract_name(soup) or html_path.name

        items = extract_technical_production(soup)

        professor_items[name] = items
        all_items.extend(items)

    return professor_items, all_items


def build_report():
    (
        professor_items,
        all_items,
    ) = load_items()

    lines = []

    def out(text=""):
        lines.append(text)

    # -------------------------------------------------
    # Contagens globais por categoria
    # -------------------------------------------------

    global_counts = Counter(
        (item["type"], item["status"])
        for item in all_items
    )

    out("=" * 70)
    out("DRY-RUN — PRODUÇÃO TÉCNICA")
    out("=" * 70)
    out()
    out(f"HTMLs processados: {len(professor_items)}")
    out(
        "Itens extraídos (com repetição entre CVs): "
        f"{len(all_items)}"
    )
    out()
    out("Contagens globais (itens extraídos, sem dedup):")

    for (item_type, status), count in sorted(
        global_counts.items()
    ):
        out(f"  {item_type:20s} {status or '-':12s} {count}")

    # -------------------------------------------------
    # Deduplicação global (por número de registro /
    # fallback título+ano) e resolução D2
    # -------------------------------------------------

    occurrences = defaultdict(list)

    for item in all_items:
        occurrences[technical_key(item)].append(item)

    unique_items = []

    for key, item_occurrences in occurrences.items():
        merged = dict(item_occurrences[0])

        # D2: patente conta uma vez, com o melhor status
        has_grant = any(
            occurrence.get("grant_date")
            or occurrence.get("status") == "granted"
            for occurrence in item_occurrences
        )

        if merged.get("type") == "patent" and has_grant:
            merged["status"] = "granted"

            for occurrence in item_occurrences:
                if occurrence.get("grant_date"):
                    merged["grant_date"] = occurrence[
                        "grant_date"
                    ]
                    merged["year"] = int(
                        occurrence["grant_date"][:4]
                    )
                    break

        unique_items.append(merged)

    unique_counts = Counter(
        (item["type"], item["status"])
        for item in unique_items
    )

    out()
    out("Contagens globais (itens únicos, com dedup):")

    for (item_type, status), count in sorted(
        unique_counts.items()
    ):
        out(f"  {item_type:20s} {status or '-':12s} {count}")

    patents = [
        item
        for item in unique_items
        if item["type"] == "patent"
    ]

    patents_invention = sum(
        1
        for item in patents
        if item.get("patent_kind") == "invention"
    )
    patents_utility = sum(
        1
        for item in patents
        if item.get("patent_kind") == "utility_model"
    )
    patents_granted = sum(
        1
        for item in patents
        if item.get("status") == "granted"
    )
    patents_deposited = sum(
        1
        for item in patents
        if item.get("status") == "deposited"
    )
    software_registered = unique_counts.get(
        ("software", "registered"),
        0,
    )
    industrial_design = unique_counts.get(
        ("industrial_design", "registered"),
        0,
    )

    out()
    out("Patentes (dedup, D2):")
    out(f"  Total: {len(patents)}")
    out(f"  Invenção: {patents_invention}")
    out(f"  Modelo de utilidade: {patents_utility}")
    out(f"  Concedidas: {patents_granted}")
    out(f"  Depositadas: {patents_deposited}")
    out()
    out(f"Software registrado: {software_registered}")
    out(
        "Desenho industrial registrado: "
        f"{industrial_design}"
    )

    # -------------------------------------------------
    # Duplicados removidos
    # -------------------------------------------------

    duplicates = {
        key: occurrences_list
        for key, occurrences_list in occurrences.items()
        if len(occurrences_list) > 1
    }

    out()
    out(f"Chaves duplicadas: {len(duplicates)}")

    for key, occurrences_list in sorted(
        duplicates.items(),
        key=lambda pair: str(pair[0]),
    ):
        titles = {
            occurrence.get("title")
            for occurrence in occurrences_list
        }
        title = " / ".join(
            str(title) for title in titles
        )[:70]

        out(
            f"  {key[0]}:{key[1][:32]} "
            f"({len(occurrences_list)} ocorrências) — "
            f"{title}"
        )

    # -------------------------------------------------
    # Contagem por professor
    # -------------------------------------------------

    out()
    out("Contagem por professor (itens únicos listados):")

    for professor, items in sorted(
        professor_items.items()
    ):
        keys = {
            technical_key(item) for item in items
        }

        patents_count = sum(
            1
            for item in items
            if item["type"] == "patent"
        )
        software_count = sum(
            1
            for item in items
            if item["type"] == "software"
        )
        design_count = sum(
            1
            for item in items
            if item["type"] == "industrial_design"
        )

        out(
            f"  {professor}: "
            f"{len(keys)} únicos "
            f"(patentes {patents_count}, "
            f"software {software_count}, "
            f"DI {design_count})"
        )

    # -------------------------------------------------
    # Itens não parseados
    # -------------------------------------------------

    unparsed_registry = [
        item
        for item in all_items
        if "Número do registro" in (item.get("raw") or "")
        and not item.get("registry_number")
    ]

    no_year = [
        item
        for item in all_items
        if not item.get("year")
    ]

    no_status = [
        item
        for item in all_items
        if not item.get("status")
    ]

    out()
    out(
        "Itens com 'Número do registro' não parseado: "
        f"{len(unparsed_registry)}"
    )

    for item in unparsed_registry:
        out(f"  {item.get('raw', '')[:120]}")

    out()
    out(f"Itens sem ano: {len(no_year)}")

    for item in no_year:
        out(f"  {item.get('raw', '')[:120]}")

    out()
    out(f"Itens sem status: {len(no_status)}")

    for item in no_status:
        out(f"  {item.get('raw', '')[:120]}")

    # -------------------------------------------------
    # Comparação com os números de referência
    # -------------------------------------------------

    found = {
        "patents": len(patents),
        "patents_invention": patents_invention,
        "patents_utility_model": patents_utility,
        "patents_granted": patents_granted,
        "patents_deposited": patents_deposited,
        "software_registered": software_registered,
        "industrial_design_registered": industrial_design,
    }

    out()
    out("=" * 70)
    out("COMPARAÇÃO COM OS NÚMEROS DE REFERÊNCIA")
    out("=" * 70)
    out()
    out(f"{'Métrica':35s} {'esperado':>10s} {'obtido':>10s}")

    divergences = []

    for metric, expected in EXPECTED.items():
        obtained = found[metric]
        mark = "OK" if obtained == expected else "DIVERGE"

        if obtained != expected:
            divergences.append(metric)

        out(
            f"{metric:35s} {expected:10d} {obtained:10d} "
            f"{mark}"
        )

    out()

    if divergences:
        out(
            "ATENÇÃO: divergências encontradas em: "
            f"{', '.join(divergences)}"
        )
        out(
            "Não continuar para a Fase 1 sem explicar "
            "as diferenças."
        )
    else:
        out("Todos os números de referência batem.")

    report = "\n".join(lines)

    return report, divergences


def main():
    report, divergences = build_report()

    print(report)

    return 1 if divergences else 0


if __name__ == "__main__":
    sys.exit(main())
