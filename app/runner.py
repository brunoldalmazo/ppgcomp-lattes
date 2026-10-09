import time
from pathlib import Path

from app.config import (
    LATTES_DELAY_SECONDS,
    OUTPUT_DIR,
    REFERENCE_YEAR,
    PERIOD_YEARS,
)
from app.lattes import collect_lattes
from app.metrics import evaluate_professors
from app.qualis import QualisDB
from app.export import export_json
from app.export_excel import export_excel
from app.students import find_student_authors, load_students


ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = ROOT / "input" / "professores.txt"

YEAR_OUTPUT_DIR = (
    ROOT
    / OUTPUT_DIR
    / str(REFERENCE_YEAR)
)

PERIOD_START = (
    REFERENCE_YEAR
    - PERIOD_YEARS
    + 1
)


def load_lattes_urls():
    """
    Lê as URLs do arquivo input/professores.txt.

    Uma URL por linha.
    Linhas vazias e comentários são ignorados.
    """

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {INPUT_FILE}"
        )

    urls = []

    for line in INPUT_FILE.read_text(
        encoding="utf-8"
    ).splitlines():

        url = line.strip()

        if not url:
            continue

        if url.startswith("#"):
            continue

        urls.append(url)

    return urls


def collect_all_lattes():
    """
    Coleta todos os Lattes definidos em professores.txt.
    """

    urls = load_lattes_urls()

    if not urls:
        raise ValueError(
            "Nenhuma URL de Lattes foi encontrada em "
            "input/professores.txt"
        )

    print()
    print("=" * 70)
    print("COLETA DOS LATTES")
    print("=" * 70)
    print()

    print(f"URLs encontradas: {len(urls)}")
    print()

    lattes_data = []

    for index, url in enumerate(
        urls,
        start=1,
    ):

        print(
            f"[{index}/{len(urls)}] "
            f"Coletando: {url}"
        )

        try:
            data = collect_lattes(url)

            if not data:
                print("  ERRO: nenhum dado retornado.")
                continue

            name = data.get(
                "name",
                "Nome não identificado",
            )

            publications = data.get(
                "publications",
                [],
            )

            print(f"  Professor: {name}")
            print(
                f"  Publicações coletadas: "
                f"{len(publications)}"
            )

            lattes_data.append(data)

        except Exception as exc:
            print(f"  ERRO: {exc}")

        if index < len(urls):
            time.sleep(LATTES_DELAY_SECONDS)

    print()
    print(
        f"Lattes coletados com sucesso: "
        f"{len(lattes_data)}/{len(urls)}"
    )

    return lattes_data


def preprocess_student_authors(lattes_data):
    """
    Identifica autores alunos localmente e salva os resultados
    nas publicações brutas, que serão persistidas no dados.json.

    Listas de autores idênticas são processadas apenas uma vez.
    """

    print()
    print("=" * 70)
    print("PRÉ-PROCESSAMENTO DE AUTORES ALUNOS")
    print("=" * 70)

    students = load_students()
    author_matches_cache = {}
    total_publications = 0

    for professor in lattes_data:
        for publication in professor.get("publications", []):
            total_publications += 1

            authors = str(
                publication.get("authors", "") or ""
            )

            if authors not in author_matches_cache:
                author_matches_cache[authors] = (
                    find_student_authors(
                        publication,
                        students=students,
                    )
                )

            publication["_student_authors_precomputed"] = True
            publication["_student_authors_cached"] = (
                author_matches_cache[authors]
            )

    matched_publications = sum(
        bool(publication["_student_authors_cached"])
        for professor in lattes_data
        for publication in professor.get("publications", [])
    )

    print(f"Alunos cadastrados: {len(students)}")
    print(f"Currículos processados: {len(lattes_data)}")
    print(f"Registros de publicações: {total_publications}")
    print(
        f"Listas de autores distintas: "
        f"{len(author_matches_cache)}"
    )
    print(
        f"Registros com alunos identificados: "
        f"{matched_publications}"
    )


def run_evaluation():
    """
    Executa o fluxo completo:

        input/professores.txt
        -> coleta dos Lattes
        -> pré-processamento local dos autores alunos
        -> avaliação
        -> dados.json
        -> avaliacao_ppgcomp_YYYY.xlsx
    """

    lattes_data = collect_all_lattes()

    if not lattes_data:
        raise RuntimeError(
            "Nenhum Lattes foi coletado."
        )

    preprocess_student_authors(lattes_data)

    print()
    print("=" * 70)
    print("AVALIAÇÃO")
    print("=" * 70)
    print()

    resultado = evaluate_professors(
        lattes_data=lattes_data,
        qualis_db=QualisDB(),
        start_year=PERIOD_START,
        end_year=REFERENCE_YEAR,
    )

    professors = resultado["professors"]

    for professor in sorted(professors):
        dados = professors[professor]

        print(
            f"{professor}: "
            f"{dados['total']:.4f} pontos | "
            f"{dados['status']} | "
            f"{dados['publications']} publicações | "
            f"{dados['coauthored_publications']} coautorias"
        )

    print()
    print(
        f"Publicações distintas: "
        f"{len(resultado['publications'])}"
    )

    print(f"Pendências: {len(resultado['pending'])}")

    output_file = export_json(
        resultado=resultado,
        lattes_data=lattes_data,
        start_year=PERIOD_START,
        end_year=REFERENCE_YEAR,
    )

    excel_file = export_excel(
        resultado=resultado
    )

    print()
    print(f"JSON salvo em: {output_file}")
    print(f"Excel salvo em: {excel_file}")

    return resultado


if __name__ == "__main__":
    run_evaluation()
