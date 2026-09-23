from pathlib import Path

from bs4 import BeautifulSoup

from app.lattes import (
    extract_journal_articles,
    extract_conference_papers,
)


PROFESSORES = {
    "Bruno Lopes Dalmazo",
    "Eduardo Nunes Borges",
    "Rodrigo Andrade de Bem",
    "Paulo Lilles Jorge Drews Junior",
}


dados = {}


for arquivo in Path("output/raw").glob("*.html"):

    soup = BeautifulSoup(
        arquivo.read_text(
            encoding="utf-8"
        ),
        "lxml",
    )

    elemento = soup.select_one("h2.nome")

    if not elemento:
        continue

    nome = elemento.get_text(
        " ",
        strip=True,
    )

    if nome not in PROFESSORES:
        continue

    if nome in dados:
        continue

    publicacoes = (
        extract_journal_articles(soup)
        + extract_conference_papers(soup)
    )

    publicacoes = [
        p
        for p in publicacoes
        if 2023 <= p.get("year", 0) <= 2026
    ]

    dados[nome] = publicacoes


# ============================================================
# CONTAGEM BRUTA
# ============================================================

print()
print("=" * 80)
print("CONTAGEM BRUTA POR LATTES")
print("=" * 80)
print()

for professor in sorted(dados):

    print(
        f"{professor}: "
        f"{len(dados[professor])} publicações"
    )


# ============================================================
# DUPLICAÇÕES INTERNAS
# ============================================================

print()
print("=" * 80)
print("DUPLICAÇÕES DENTRO DO MESMO LATTES")
print("=" * 80)
print()

for professor in sorted(dados):

    vistos = {}
    duplicados = []

    for pub in dados[professor]:

        chave = (
            pub.get("year"),
            pub.get("title", "").strip().lower(),
        )

        if chave in vistos:

            duplicados.append({
                "year": pub.get("year"),
                "title": pub.get("title"),
            })

        else:

            vistos[chave] = pub

    if duplicados:

        print()
        print(professor)

        for pub in duplicados:

            print(
                f"  {pub['year']} | "
                f"{pub['title']}"
            )


# ============================================================
# PUBLICAÇÕES COMPARTILHADAS
# ============================================================

por_chave = {}


for professor, publicacoes in dados.items():

    # Remove duplicações internas do próprio Lattes
    vistos_professor = set()

    for pub in publicacoes:

        chave = (
            pub.get("year"),
            pub.get("title", "").strip().lower(),
        )

        if chave in vistos_professor:
            continue

        vistos_professor.add(chave)

        if chave not in por_chave:

            por_chave[chave] = {
                "title": pub.get("title"),
                "year": pub.get("year"),
                "professores": set(),
            }

        por_chave[chave]["professores"].add(
            professor
        )


# ============================================================
# LISTAGEM DAS COAUTORIAS
# ============================================================

print()
print("=" * 80)
print("PUBLICAÇÕES PRESENTES EM MAIS DE UM LATTES")
print("=" * 80)
print()

contagem_coautoria = {
    professor: 0
    for professor in PROFESSORES
}


total_compartilhadas = 0


for item in sorted(
    por_chave.values(),
    key=lambda x: (
        x["year"],
        x["title"],
    ),
):

    professores = sorted(
        item["professores"]
    )

    if len(professores) <= 1:
        continue

    total_compartilhadas += 1

    for professor in professores:
        contagem_coautoria[professor] += 1

    print()
    print(
        f"{item['year']} | "
        f"{item['title']}"
    )

    print(
        "  Professores:",
        ", ".join(professores),
    )


# ============================================================
# RESUMO
# ============================================================

print()
print("=" * 80)
print("RESUMO DE COAUTORIA")
print("=" * 80)
print()

print(
    f"Total de publicações compartilhadas: "
    f"{total_compartilhadas}"
)

print()

for professor in sorted(contagem_coautoria):

    print(
        f"{professor}: "
        f"{contagem_coautoria[professor]} coautorias"
    )

print()
