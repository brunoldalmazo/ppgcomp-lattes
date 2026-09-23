from pathlib import Path
from bs4 import BeautifulSoup

from app.lattes import (
    extract_journal_articles,
    extract_conference_papers,
)
from app.qualis import QualisDB


PROFESSORES = {
    "Bruno Lopes Dalmazo",
    "Eduardo Nunes Borges",
    "Rodrigo Andrade de Bem",
    "Paulo Lilles Jorge Drews Junior",
}


ALIAS = {
    "Bruno Lopes Dalmazo": [
        "DALMAZO, BRUNO",
        "DALMAZO, BRUNO L.",
    ],
    "Eduardo Nunes Borges": [
        "BORGES, EDUARDO",
        "BORGES, EDUARDO N.",
    ],
    "Rodrigo Andrade de Bem": [
        "DE BEM, RODRIGO",
        "DE BEM, RODRIGO A.",
    ],
    "Paulo Lilles Jorge Drews Junior": [
        "DREWS-JR, PAULO",
        "DREWS-JR, PAULO L. J.",
        "DREWS JUNIOR, PAULO",
    ],
}


def encontrar_professores(autores):

    autores = autores.upper()

    encontrados = []

    for professor, aliases in ALIAS.items():

        for alias in aliases:

            if alias in autores:
                encontrados.append(professor)
                break

    return encontrados


qualis = QualisDB()

publicacoes = {}
processados = set()


for arquivo in Path("output/raw").glob("*.html"):

    soup = BeautifulSoup(
        arquivo.read_text(encoding="utf-8"),
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

    if nome in processados:
        continue

    processados.add(nome)

    artigos = (
        extract_journal_articles(soup)
        + extract_conference_papers(soup)
    )

    for artigo in artigos:

        if artigo["year"] < 2023 or artigo["year"] > 2026:
            continue

        chave = (
            artigo["year"],
            artigo["title"].strip().lower(),
        )

        if chave not in publicacoes:
            publicacoes[chave] = artigo


print()
print("=== PUBLICAÇÕES COM COAUTORIA ENTRE PROFESSORES ===")
print()


for chave, artigo in sorted(
    publicacoes.items(),
    key=lambda x: (x[1]["year"], x[1]["title"]),
):

    professores = encontrar_professores(
        artigo["authors"]
    )

    if len(professores) < 2:
        continue

    resultado_qualis = qualis.lookup(
        issn=artigo["issn"],
        title=artigo["venue"],
        publication_type=artigo["type"],
    )

    if resultado_qualis:

        estrato = resultado_qualis["qualis"]
        pontos = resultado_qualis["points"]

    else:

        estrato = "NÃO ENCONTRADO"
        pontos = None

    if pontos is not None:

        pontos_individuais = (
            pontos / len(professores)
        )

        pontos_texto = (
            f"{pontos_individuais:.4f}"
        )

    else:

        pontos_individuais = None
        pontos_texto = "-"


    print(
        artigo["year"],
        "|",
        artigo["type"],
    )

    print(
        "Título:",
        artigo["title"],
    )

    print(
        "Veículo:",
        artigo["venue"],
    )

    print(
        "Qualis:",
        estrato,
        "| Pontos:",
        pontos if pontos is not None else "-",
    )

    print(
        "Professores avaliados:",
        ", ".join(professores),
    )

    print(
        "N:",
        len(professores),
        "| Pontos por professor:",
        pontos_texto,
    )

    print("-" * 80)
