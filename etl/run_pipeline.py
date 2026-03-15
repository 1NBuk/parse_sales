import os
import sys
import subprocess
import time
import random
from datetime import datetime, date
from concurrent.futures import ProcessPoolExecutor, as_completed

# --------------------------------------------------
# PATHS
# --------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

PARSERS_DIR = os.path.join(REPO_ROOT, "etl", "parsers")
RAW_DIR = os.path.join(REPO_ROOT, "data", "raw")
PROCESSED_DIR = os.path.join(REPO_ROOT, "data", "processed")
LOG_FILE = os.path.join(REPO_ROOT, "pipeline.log")

PYTHON_EXEC = sys.executable

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

os.environ["PYTHONIOENCODING"] = "utf-8"

from transformer.transform import transform_all
from etl.upload_to_postgres import upload

# --------------------------------------------------
# LOGGING
# --------------------------------------------------

def log(message):

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = f"[{timestamp}] {message}"

    print(text)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")


# --------------------------------------------------
# CHECK LAST RUN
# --------------------------------------------------

def check_last_run():

    LAST_RUN_FILE = os.path.join(os.path.dirname(__file__), "last_run.txt")
    today = date.today().isoformat()

    if os.path.exists(LAST_RUN_FILE):

        with open(LAST_RUN_FILE, "r", encoding="utf-8") as f:
            last_run = f.read().strip()

        if last_run == today:
            log("Pipeline уже запускался сегодня. Выход.")
            sys.exit()

    with open(LAST_RUN_FILE, "w", encoding="utf-8") as f:
        f.write(today)


# --------------------------------------------------
# RUN SINGLE PARSER
# --------------------------------------------------

def run_parser(parser_file, retries=3):

    parser_path = os.path.join(PARSERS_DIR, parser_file)

    delay = random.uniform(2, 6)
    time.sleep(delay)

    for attempt in range(1, retries + 1):

        result = subprocess.run(
            [PYTHON_EXEC, parser_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )

        if result.returncode == 0:
            return parser_file, True, result.stdout

        if "403" in result.stdout or "403" in result.stderr:

            if attempt < retries:
                time.sleep(15)
                continue

        return parser_file, False, result.stderr

    return parser_file, False, "Unknown error"


# --------------------------------------------------
# RUN ALL PARSERS (PARALLEL)
# --------------------------------------------------

def run_all_parsers():

    parser_files = sorted(
        f for f in os.listdir(PARSERS_DIR)
        if f.endswith("_parser.py")
    )

    log(f"Найдено парсеров: {len(parser_files)}")

    errors = []

    with ProcessPoolExecutor(max_workers=4) as executor:

        futures = [
            executor.submit(run_parser, parser)
            for parser in parser_files
        ]

        for future in as_completed(futures):

            parser, success, output = future.result()

            log("===================================")
            log(f"Результат парсера: {parser}")
            log("===================================")

            if output:
                log(output)

            if success:
                log(f"✓ Парсер завершён: {parser}")
            else:
                log(f"⚠ Ошибка в {parser}")
                errors.append(parser)

    return errors


# --------------------------------------------------
# UPLOAD CSV
# --------------------------------------------------

def upload_processed_files():

    files = [
        f for f in os.listdir(PROCESSED_DIR)
        if f.endswith(".csv")
    ]

    if not files:
        log("⚠ Нет файлов для загрузки")
        return

    for file_name in files:

        csv_file = os.path.join(PROCESSED_DIR, file_name)

        try:

            upload(csv_file)

            log(f"✓ Загружен файл: {file_name}")

        except Exception as e:

            log(f"⚠ Ошибка загрузки {file_name}: {e}")


# --------------------------------------------------
# MAIN PIPELINE
# --------------------------------------------------

def main():

    check_last_run()

    log("===================================")
    log("Запуск ETL pipeline")
    log("===================================")

    # PARSING
    errors = run_all_parsers()

    if errors:

        log("⚠ Некоторые парсеры завершились с ошибками:")

        for e in errors:
            log(f"- {e}")

    # TRANSFORM

    log("Запуск transform шага")

    try:

        transform_all()

        log("✓ Transform завершён")

    except Exception as e:

        log(f"⚠ Ошибка transform: {e}")
        return

    # UPLOAD

    log("Загрузка данных в PostgreSQL")

    upload_processed_files()

    log("===================================")
    log("ETL pipeline завершён")
    log("===================================")


# --------------------------------------------------

if __name__ == "__main__":
    main()