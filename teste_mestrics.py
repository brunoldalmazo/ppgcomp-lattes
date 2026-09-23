from pathlib import Path

from bs4 import BeautifulSoup

from app.lattes import (
    extract_journal_articles,
    extract_conference_papers,
)
from app.metrics import evaluate_professors
from app.qualis import QualisDB


PROFESSORES = {
    "Bruno Lopes Dalmazo",
    "Eduardo Nunes Borges",
    "Rodrigo Andrade de Bem",
    "Paulo Lilles Jorge Drews Junior",
}


lattes_data = []


processados = set()


for arquivo in Path("output/raw").glob("*.html"):

    soup = BeautifulSoup(
        arquivo.read_text(
            encoding="utf-8"
        ),
        "lxml",
    )

    elemento = soup.select_one(
        "h2.nome"
    )

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

    publicacoes = (
        extract_journal_articles(soup)
        + extract_conference_papers(soup)
    )

    lattes_data.append({
        "name": nome,
        "last_update": "",
        "last_update_date": None,
        "publications": publicacoes,
    })


resultado = evaluate_professors(
    lattes_data=lattes_data,
    qualis_db=QualisDB(),
    professor_names=PROFESSORES,
)


print()
print("=" * 70)
print("RESUMO DA AVALIAÇÃO")
print("=" * 70)
print()


for professor, dados in resultado[
    "professors"
].items():

    print(
        professor
    )

    print(
        "  Total:",
        f"{dados['total']:.4f}",
    )

    print(
        "  Status:",
        dados["status"],
    )

    print(
        "  Publicações:",
        dados["publications"],
    )

    print(
        "  Coautorias:",
        dados["coauthored_publications"],
    )

    print(
        "  Estratos:"
    )

    for estrato in [
        "A1",
        "A2",
        "A3",
        "A4",
        "B1",
        "B2",
        "B3",
        "B4",
        "C",
    ]:

        count = dados[
            "counts"
        ][estrato]

        points = dados[
            "points"
        ][estrato]

        if count > 0:

            print(
                f"    {estrato}: "
                f"{count} "
                f"({points:.4f} pontos)"
            )

    print(
        "-" * 70
    )


print()
print(
    "Total de publicações:",
    len(
        resultado["publications"]
    ),
)

print(
    "Total de pendências:",
    len(
        resultado["pending"]
    ),
)
