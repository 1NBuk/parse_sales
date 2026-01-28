import os
import subprocess
from datetime import datetime
from transformer.transform import transform_all
from etl.upload_to_gdrive import upload

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARSERS_DIR = os.path.join(REPO_ROOT, "etl", "parsers")
PYTHON_EXEC = "python3"


def run_all_parsers():
    errors = []

    parser_files = sorted(
        f for f in os.listdir(PARSERS_DIR)
        if f.endswith("_parser.py")
    )

    for parser in parser_files:
        parser_path = os.path.join(PARSERS_DIR, parser)
        print("\n==========================")
        print(f"Запуск парсера: {parser}")
        print("==========================")

        result = subprocess.run(
            [PYTHON_EXEC, parser_path],
            capture_output=True,
            text=True
        )

        print(result.stdout)

        if result.returncode != 0:
            print(f"Ошибка в {parser}:")
            print(result.stderr)
            errors.append(parser)

    if errors:
        print("\nПарсеры с ошибками:", ", ".join(errors))


if __name__ == "__main__":
    print(f"Запуск ETL pipeline: {datetime.now()}")

    run_all_parsers()

    print("Запуск transform шага")
    transform_all()

    print("Загрузка данных")
    upload()

    print(f"ETL pipeline завершён: {datetime.now()}")

