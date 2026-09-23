import json
from datetime import date, datetime

from app.config import (
    OUTPUT_DIR,
    PERIOD_START,
    PERIOD_YEARS,
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


def export_json(resultado):
    """
    Salva o resultado da avaliação em JSON no diretório anual.

    Estrutura:
        output/
        └── ANO/
            └── dados.json
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
            "period_years": PERIOD_YEARS,
            "period_start": PERIOD_START,
            "min_score": MIN_SCORE,
            "lattes_update_limit_days": (
                LATTES_UPDATE_LIMIT_DAYS
            ),
            "qualis_area": QUALIS_AREA,
            "qualis_file": str(
                QUALIS_FILE
            ),
            "weights": WEIGHTS,
        },
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
