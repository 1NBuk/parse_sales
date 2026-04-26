import os
import sys
import subprocess
import time
import random
from datetime import datetime, date
from concurrent.futures import ProcessPoolExecutor, as_completed

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

PARSERS_DIR = os.path.join(REPO_ROOT, "etl", "parsers")
RAW_DIR = os.path.join(REPO_ROOT, "data", "raw")
PROCESSED_DIR = os.path.join(REPO_ROOT, "data", "processed")
LOG_FILE = os.path.join(REPO_ROOT, "pipeline.log")
LAST_RUN_FILE = os.path.join(REPO_ROOT, "last_run.txt")

PYTHON_EXEC = sys.executable

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)
os.environ["PYTHONIOENCODING"] = "utf-8"

from transformer.transform import transform_all
from etl.upload_to_postgres import upload

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = f"[{timestamp}] {message}"
    print(text)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")

def already_ran_today():
    today = date.today().isoformat()
    if os.path.exists(LAST_RUN_FILE):
        try:
            with open(LAST_RUN_FILE, "r", encoding="utf-8") as f:
                last_run = f.read().strip()
            if last_run == today:
                log("Pipeline уже запускался сегодня. Выход.")
                return True
        except Exception as e:
            log(f"Ошибка чтения last_run.txt: {e}")
    return False

def mark_run_success():
    try:
        with open(LAST_RUN_FILE, "w", encoding="utf-8") as f:
            f.write(date.today().isoformat())
    except Exception as e:
        log(f"Ошибка записи last_run.txt: {e}")

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
        if "403" in (result.stdout + result.stderr):
            if attempt < retries:
                time.sleep(15)
                continue
        return parser_file, False, result.stderr or "Unknown error"
    return parser_file, False, "Unknown error"

def run_all_parsers():
    parser_files = sorted(f for f in os.listdir(PARSERS_DIR) if f.endswith("_parser.py"))
    log(f"Найдено парсеров: {len(parser_files)}")
    errors = []
    with ProcessPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(run_parser, parser) for parser in parser_files]
        for future in as_completed(futures):
            parser, success, output = future.result()
            log(f"Результат парсера: {parser}")
            if output:
                log(output)
            if success:
                log(f"Парсер завершён: {parser}")
            else:
                log(f"Ошибка в {parser}")
                errors.append(parser)
    return errors

def upload_processed_files():
    files = [f for f in os.listdir(PROCESSED_DIR) if f.endswith(".csv")]
    if not files:
        log("Нет файлов для загрузки")
        return
    for file_name in files:
        csv_file = os.path.join(PROCESSED_DIR, file_name)
        try:
            upload(csv_file)
            log(f"Загружен файл: {file_name}")
        except Exception as e:
            log(f"Ошибка загрузки {file_name}: {e}")

def run_ml():
    log("Запуск ML обучения")

    result = subprocess.run(
        [PYTHON_EXEC, os.path.join(REPO_ROOT, "ml", "price_model.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore"
    )

    log(result.stdout)

    if result.returncode != 0:
        log("Ошибка ML обучения")
        log(result.stderr)
    else:
        log("ML обучение завершено")

def main():
    if already_ran_today():
        return
    log("Запуск ETL pipeline")
    try:
        errors = run_all_parsers()
        if errors:
            log("Некоторые парсеры завершились с ошибками:")
            for e in errors:
                log(f"- {e}")
        log("Запуск transform шага")
        transform_all()
        log("Transform завершён")
        log("Загрузка данных в PostgreSQL")
        upload_processed_files()
        log("Запуск ML шага")
        run_ml()
        log("ETL pipeline завершён")
        mark_run_success()
    except Exception as e:
        log(f"Критическая ошибка pipeline: {e}")

if __name__ == "__main__":
    main()