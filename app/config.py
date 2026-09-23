import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent

REFERENCE_YEAR = int(os.getenv("REFERENCE_YEAR", "2026"))
PERIOD_YEARS = int(os.getenv("PERIOD_YEARS", "4"))
PERIOD_START = REFERENCE_YEAR - PERIOD_YEARS + 1

MIN_SCORE = float(os.getenv("MIN_SCORE", "4.0"))

LATTES_UPDATE_LIMIT_DAYS = int(
    os.getenv("LATTES_UPDATE_LIMIT_DAYS", "365")
)

QUALIS_AREA = os.getenv("QUALIS_AREA", "Computação")

QUALIS_FILE = ROOT / os.getenv(
    "QUALIS_FILE",
    "qualis/qualis.csv"
)

OUTPUT_DIR = ROOT / os.getenv(
    "OUTPUT_DIR",
    "output"
)

HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

LATTES_DELAY_SECONDS = float(
    os.getenv("LATTES_DELAY_SECONDS", "3")
)

WEIGHTS = {
    "A1": 1.000,
    "A2": 0.875,
    "A3": 0.750,
    "A4": 0.625,
    "B1": 0.500,
    "B2": 0.375,
    "B3": 0.250,
    "B4": 0.125,
    "C": 0.000,
}
