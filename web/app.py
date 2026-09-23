from pathlib import Path
import json

from flask import Flask, render_template


ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "output" / "2026" / "dados.json"

app = Flask(__name__)


def load_data():
    with DATA_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


@app.route("/")
def index():
    data = load_data()

    return render_template(
        "index.html",
        data=data,
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
    )
