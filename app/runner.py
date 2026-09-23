import time
from pathlib import Path

from app.config import (
    LATTES_DELAY_SECONDS,
    OUTPUT_DIR,
    REFERENCE_YEAR,
)
from app.lattes import collect_lattes
from app.metrics import evaluate_professors
from app.qualis import QualisDB


ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = ROOT / "input" / "professores.txt"

YEAR_OUTPUT_DIR = (
    ROOT
    / OUTPUT_DIR
    / str(REFERENCE_YEAR)
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

    print(
        f"URLs encontradas: {len(urls)}"
    )
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

            data = collect_lattes(
                url
            )

            if not data:
                print(
                    "  ERRO: nenhum dado retornado."
                )
                continue

            name = data.get(
                "name",
                "Nome não identificado",
            )

            publications = data.get(
                "publications",
                [],
            )

            print(
                f"  Professor: {name}"
            )

            print(
                f"  Publicações coletadas: "
                f"{len(publications)}"
            )

            lattes_data.append(
                data
            )

        except Exception as exc:

            print(
                f"  ERRO: {exc}"
            )

        if index < len(urls):

            time.sleep(
                LATTES_DELAY_SECONDS
            )

    print()
    print(
        f"Lattes coletados com sucesso: "
        f"{len(lattes_data)}/{len(urls)}"
    )

    return lattes_data


def run_evaluation():
    """
    Executa o fluxo completo:

        input/professores.txt
        -> Lattes
        -> métricas
    """

    lattes_data = collect_all_lattes()

    if not lattes_data:
        raise RuntimeError(
            "Nenhum Lattes foi coletado."
        )

    print()
    print("=" * 70)
    print("AVALIAÇÃO")
    print("=" * 70)
    print()

    resultado = evaluate_professors(
        lattes_data=lattes_data,
        qualis_db=QualisDB(),
    )

    professors = resultado[
        "professors"
    ]

    for professor in sorted(
        professors
    ):

        dados = professors[
            professor
        ]

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

    print(
        f"Pendências: "
        f"{len(resultado['pending'])}"
    )

    return resultado


if __name__ == "__main__":
    run_evaluation()
