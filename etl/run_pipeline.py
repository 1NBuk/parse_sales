import os
import subprocess
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
PARSERS_DIR = os.path.join(BASE_DIR, "..", "parsers")
PYTHON_EXEC = r"C:\Users\User\PycharmProjects\parse_sales\venv\Scripts\python.exe"

def run_all_parsers():
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
    print(f"Парсеры завершены: {datetime.now()}")

    print("Загрузка данных в Google Drive")
    subprocess.run(
        [PYTHON_EXEC, os.path.join(BASE_DIR, "upload_to_gdrive.py")],
        check=True
    )
    print(f"ETL pipeline завершён: {datetime.now()}")
