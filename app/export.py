import json
from datetime import date, datetime

from app.config import (
    OUTPUT_DIR,
    REFERENCE_YEAR,
    MIN_SCORE,
    LATTES_UPDATE_LIMIT_DAYS,
    QUALIS_AREA,
    QUALIS_FILE,
    WEIGHTS,
)


def make_json_safe(value):
    """
    Converte recursivamente estruturas Python para
    estruturas compatíveis com JSON.
    """

    if isinstance(value, dict):
        return {
            str(key): make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            make_json_safe(item)
            for item in value
        ]

    if isinstance(value, (date, datetime)):
        return value.isoformat()

    return value


def export_json(
    resultado,
    lattes_data=None,
    start_year=None,
    end_year=None,
):
    """
    Salva o resultado da avaliação em JSON.

    Além do resultado da avaliação, pode armazenar
    os dados completos coletados dos Lattes.

    Estrutura principal:

        output/
        └── ANO/
            └── dados.json

    O campo "lattes_data" contém todas as publicações
    coletadas, independentemente do período avaliado.
    Isso permite recalcular posteriormente períodos
    diferentes sem precisar coletar os Lattes novamente.
    """

    year_output_dir = (
        OUTPUT_DIR
        / str(REFERENCE_YEAR)
    )

    year_output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        year_output_dir
        / "dados.json"
    )

    data = {
        "configuracao": {
            "reference_year": REFERENCE_YEAR,
            "min_score": MIN_SCORE,
            "lattes_update_limit_days": (
                LATTES_UPDATE_LIMIT_DAYS
            ),
            "qualis_area": QUALIS_AREA,
            "qualis_file": str(
                QUALIS_FILE
            ),
            "weights": WEIGHTS,
            "evaluation_start_year": (
                start_year
            ),
            "evaluation_end_year": (
                end_year
            ),
        },
        "lattes_data": (
            lattes_data
            if lattes_data is not None
            else []
        ),
        "professors": resultado[
            "professors"
        ],
        "publications": resultado[
            "publications"
        ],
        "coauthorships": resultado[
            "coauthorships"
        ],
        "pending": resultado[
            "pending"
        ],
        "publication_index": resultado[
            "publication_index"
        ],
    }

    safe_data = make_json_safe(
        data
    )

    output_file.write_text(
        json.dumps(
            safe_data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return output_file
