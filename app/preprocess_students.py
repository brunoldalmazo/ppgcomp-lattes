import json
import shutil
from datetime import datetime
from pathlib import Path

from app.students import find_student_authors, load_students


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_ROOT / "output" / "2026" / "dados.json"


def main():
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Arquivo nao encontrado: {DATA_FILE}"
        )

    with DATA_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    lattes_data = data.get("lattes_data")

    if not isinstance(lattes_data, list) or not lattes_data:
        raise ValueError(
            "O JSON nao contem uma lista valida de lattes_data."
        )

    students = load_students()
    cache = {}
    total = 0
    matched = 0

    for professor in lattes_data:
        for publication in professor.get("publications", []):
            total += 1
            authors = str(publication.get("authors", "") or "")

            if authors not in cache:
                cache[authors] = find_student_authors(
                    publication,
                    students=students,
                )

            matches = cache[authors]

            publication["_student_authors_precomputed"] = True
            publication["_student_authors_cached"] = matches

            if matches:
                matched += 1

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = DATA_FILE.with_name(
        f"dados.json.backup-{timestamp}"
    )

    shutil.copy2(DATA_FILE, backup)

    temporary_file = DATA_FILE.with_suffix(".json.tmp")

    try:
        with temporary_file.open("w", encoding="utf-8") as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2,
            )
            file.write("\n")

        temporary_file.replace(DATA_FILE)

    except Exception:
        if temporary_file.exists():
            temporary_file.unlink()
        raise

    print("Pre-processamento concluido.")
    print(f"Backup: {backup}")
    print(f"Curriculos: {len(lattes_data)}")
    print(f"Alunos cadastrados: {len(students)}")
    print(f"Publicacoes processadas: {total}")
    print(f"Listas de autores distintas: {len(cache)}")
    print(f"Registros com alunos identificados: {matched}")
    print("Resultados da avaliacao preservados no JSON.")


if __name__ == "__main__":
    main()
