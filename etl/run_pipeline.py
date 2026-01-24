import os
import subprocess
from datetime import datetime

from etl.upload_to_gdrive import upload

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARSERS_DIR = os.path.join(REPO_ROOT, "etl", "parsers")  # <-- внутри etl
PYTHON_EXEC = "python3"

def run_all_parsers():
    if not os.path.exists(PARSERS_DIR):
        raise FileNotFoundError(f"Папка с парсерами не найдена: {PARSERS_DIR}")

    parser_files = [f for f in os.listdir(PARSERS_DIR) if f.endswith("_parser.py")]

    for parser in parser_files:
        parser_path = os.path.join(PARSERS_DIR, parser)
        print("\n==========================")
        print(f"Запуск парсера: {parser}")
        print("==========================")
        result = subprocess.run([PYTHON_EXEC, parser_path], capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            print(f"Ошибка при запуске {parser}: {result.stderr}")

if __name__ == "__main__":
    print(f"Запуск ETL pipeline: {datetime.now()}")
    run_all_parsers()
    print(f"ETL pipeline завершён: {datetime.now()}")
    upload()
