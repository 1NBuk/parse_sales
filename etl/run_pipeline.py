import os
import sys
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
import subprocess
from datetime import datetime, date
from transformer.transform import transform_all
from etl.upload_to_postgres import upload

today = date.today().isoformat()
LAST_RUN_FILE = os.path.join(os.path.dirname(__file__), "last_run.txt")

if os.path.exists(LAST_RUN_FILE):
    with open(LAST_RUN_FILE) as f:
        last_run = f.read().strip()
    if last_run == today:
        print("Pipeline уже запускался сегодня. Выход.")
        exit()

with open(LAST_RUN_FILE, "w") as f:
    f.write(today)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARSERS_DIR = os.path.join(REPO_ROOT, "etl", "parsers")

RAW_DIR = os.path.join(REPO_ROOT, "data", "raw")
PROCESSED_DIR = os.path.join(REPO_ROOT, "data", "processed")

LOG_FILE = os.path.join(REPO_ROOT, "pipeline.log")

# Python из текущего окружения (venv)
PYTHON_EXEC = os.sys.executable

# Создаем папки если их нет
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)


# --------------------------------------------------
# Логирование
# --------------------------------------------------

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = f"[{timestamp}] {message}"
    print(text)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")


# --------------------------------------------------
# Запуск всех парсеров
# --------------------------------------------------

def run_all_parsers():
    errors = []

    parser_files = sorted(
        f for f in os.listdir(PARSERS_DIR)
        if f.endswith("_parser.py")
    )

    if not parser_files:
        log("⚠ Парсеры не найдены")
        return errors

    for parser in parser_files:
        parser_path = os.path.join(PARSERS_DIR, parser)

        log("===================================")
        log(f"Запуск парсера: {parser}")
        log("===================================")

        result = subprocess.run(
            [PYTHON_EXEC, parser_path],
            capture_output=True,
            text=True
        )

        if result.stdout:
            print(result.stdout)

        if result.returncode != 0:
            log(f"⚠ Ошибка в {parser}")
            log(result.stderr)
            errors.append(parser)
        else:
            log(f"✓ Парсер завершен: {parser}")

    return errors


# --------------------------------------------------
# Главный pipeline
# --------------------------------------------------

def main():

    log("===================================")
    log("Запуск ETL pipeline")
    log("===================================")

    # 1. Парсинг
    errors = run_all_parsers()

    if errors:
        log("Pipeline остановлен из-за ошибок:")
        for e in errors:
            log(f"- {e}")

    # 2. Transform
    log("Запуск transform шага")

    try:
        transform_all()
        log("✓ Transform завершён")
    except Exception as e:
        log(f"⚠ Ошибка transform: {e}")
        return
    # 3. Загрузка в PostgreSQL
    log("Загрузка данных в PostgreSQL")
    for file_name in os.listdir(PROCESSED_DIR):
        if file_name.endswith(".csv"):
            csv_file = os.path.join(PROCESSED_DIR, file_name)
            upload(csv_file)
    log("===================================")
    log("ETL pipeline завершён")
    log("===================================")


# --------------------------------------------------

if __name__ == "__main__":
    main()
