import os
import sys
import subprocess
from datetime import datetime, date
from concurrent.futures import ProcessPoolExecutor, as_completed
import time
import random

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

PARSERS_DIR = os.path.join(REPO_ROOT, "etl", "parsers")
RAW_DIR = os.path.join(REPO_ROOT, "data", "raw")
PROCESSED_DIR = os.path.join(REPO_ROOT, "data", "processed")
LOG_FILE = os.path.join(REPO_ROOT, "pipeline.log")

PYTHON_EXEC = sys.executable

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

from transformer.transform import transform_all
from etl.upload_to_postgres import upload


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = f"[{timestamp}] {message}"

    print(text)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")

def check_last_run():
    LAST_RUN_FILE = os.path.join(os.path.dirname(__file__), "last_run.txt")
    today = date.today().isoformat()

    if os.path.exists(LAST_RUN_FILE):
        with open(LAST_RUN_FILE, "r", encoding="utf-8") as f:
            last_run = f.read().strip()

        # Если файл пустой или содержит неверную дату — переписываем
        if last_run == today:
            print("Pipeline уже запускался сегодня. Выход.")
            sys.exit()
        else:
            print(f"[INFO] last_run.txt содержит: '{last_run}', переписываем.")

    with open(LAST_RUN_FILE, "w", encoding="utf-8") as f:
        f.write(today)

def run_parser(parser, retries=3):

    parser_path = os.path.join(PARSERS_DIR, parser)

    # случайная задержка перед запуском
    delay = random.uniform(2, 6)
    log(f"{parser} стартует через {delay:.2f} сек")
    time.sleep(delay)

    for attempt in range(1, retries + 1):

        result = subprocess.run(
            [PYTHON_EXEC, parser_path],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            return parser, result

        if "403" in result.stderr or "403" in result.stdout:

            log(f"⚠ {parser} получил 403. Попытка {attempt}/{retries}")

            if attempt < retries:
                time.sleep(15)
                continue

        return parser, result

    return parser, result

def run_all_parsers():

    errors = []

    parser_files = sorted(
        f for f in os.listdir(PARSERS_DIR)
        if f.endswith("_parser.py")
    )

    if not parser_files:
        log("⚠ Парсеры не найдены")
        return errors

    log(f"Найдено парсеров: {len(parser_files)}")

    with ProcessPoolExecutor(max_workers=4) as executor:

        futures = {
            executor.submit(run_parser, parser): parser
            for parser in parser_files
        }

        for future in as_completed(futures):

            parser, result = future.result()

            log("===================================")
            log(f"Результат парсера: {parser}")
            log("===================================")

            if result.stdout:
                print(result.stdout)

            if result.returncode != 0:
                log(f"⚠ Ошибка в {parser}")
                log(result.stderr)
                errors.append(parser)
            else:
                log(f"✓ Парсер завершён: {parser}")

    return errors


# --------------------------------------------------
# Upload CSV
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
# Главный pipeline
# --------------------------------------------------

def main():
    check_last_run()
    log("===================================")
    log("Запуск ETL pipeline")
    log("===================================")

    # 1. PARSING
    errors = run_all_parsers()

    if errors:
        log("⚠ Некоторые парсеры завершились с ошибками:")
        for e in errors:
            log(f"- {e}")

    # 2. TRANSFORM
    log("Запуск transform шага")

    try:

        transform_all()

        log("✓ Transform завершён")

    except Exception as e:

        log(f"⚠ Ошибка transform: {e}")
        return

    # 3. LOAD
    log("Загрузка данных в PostgreSQL")

    upload_processed_files()

    log("===================================")
    log("ETL pipeline завершён")
    log("===================================")


# --------------------------------------------------

if __name__ == "__main__":
    main()