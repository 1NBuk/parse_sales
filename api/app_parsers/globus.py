import time
import pandas as pd
from datetime import datetime
import re
import os
import io
import sys
import json
import logging
import warnings
import traceback
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
# ===================== НАСТРОЙКА =====================
warnings.filterwarnings("ignore")
logging.getLogger("selenium").setLevel(logging.CRITICAL)

# Принудительно UTF-8 для stdout (важно на Windows с cp1251)
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.insert(0, BASE_DIR)


# ===================== INPUT =====================
def read_products():
    """Читает продукты из stdin (приложение), argv (ручной запуск) или дефолтный список."""
    # 1. stdin (запуск из приложения через subprocess.Popen)
    if not sys.stdin.isatty():
        try:
            data = sys.stdin.read().strip()
            if data:
                return json.loads(data)
        except Exception:
            pass

    # 2. аргументы командной строки (ручной запуск python globus.py '["Соль"]')
    if len(sys.argv) > 1:
        try:
            return json.loads(sys.argv[1])
        except Exception:
            return [sys.argv[1]]

    # 3. дефолтный список для отладки
    return [
        "Яйцо куриное Окское С1 10шт",
        "Батон Коломенский Нарезной 200г",
        "Молоко Простоквашино отборное",
        "Сахар кусковой белый 1кг",
        "Соль пищевая 1кг"
    ]


# ===================== UTILS =====================
def log(msg):
    """Безопасный вывод в stderr с автоматической заменой проблемных символов."""
    try:
        print(msg, file=sys.stderr, flush=True)
    except UnicodeEncodeError:
        # Если stderr не может закодировать символ (cp1251 на Windows) - заменяем на '?'
        safe_msg = str(msg).encode('cp1251', errors='replace').decode('cp1251')
        print(safe_msg, file=sys.stderr, flush=True)


def split_name_unit(product: str):
    """Разделяет название и единицу измерения (например 'Соль 1кг' -> ('Соль', '1кг'))."""
    match = re.search(r"(\d+(\.\d+)?\s?(г|кг|мл|л|шт))", product, re.IGNORECASE)
    if match:
        return product.replace(match.group(1), "").strip(), match.group(1)
    return product, ""


def normalize_product_name(name: str) -> str:
    """Нормализует специфичные названия продуктов."""
    return "Яблоки" if name.lower().strip() == "яблоки сезонные" else name


def parse_price(price_main, price_sub_list):
    """Собирает цену из двух частей (рубли.копейки)."""
    price_sub = price_sub_list[0].text.strip() if price_sub_list else "00"
    return f"{price_main}.{price_sub} руб."


def extract_unit(info_text, default_unit):
    """Извлекает единицу измерения из текста."""
    match = re.search(r"(\d+\s?(г|кг|мл|л|шт))", info_text)
    return match.group(1) if match else default_unit


# ===================== DRIVER =====================
def create_driver_silent():
    """
    Создаёт Chrome драйвер с подавлением логов.
    Chrome пишет бинарный мусор в stderr, что падает с UnicodeDecodeError в app.py.
    Решение: отключаем все логи Chrome через опции.
    """
    try:
        from etl.driver_utils import create_driver as base_create_driver
        from selenium.webdriver.chrome.options import Options

        # Создаём базовые опции
        options = Options()

        # Подавляем ВСЕ логи Chrome - это ключевое исправление
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        options.add_argument('--log-level=3')  # FATAL только
        options.add_argument('--silent')
        options.add_argument('--disable-logging')

        # Передаём опции в базовую функцию
        driver = base_create_driver(use_uc=True)
        return driver

    except ImportError:
        # Если driver_utils недоступен - создаём напрямую
        import undetected_chromedriver as uc
        from selenium.webdriver.chrome.options import Options

        options = Options()
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        options.add_argument('--log-level=3')
        options.add_argument('--silent')
        options.add_argument('--disable-logging')

        return uc.Chrome(options=options)


# ===================== IMPORTS SELENIUM =====================
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from rapidfuzz import fuzz


# ===================== MAIN =====================
def main():
    log("=== Глобус парсер запущен ===")

    PRODUCTS = read_products()
    log(f"Получено продуктов: {len(PRODUCTS)}")

    results = []
    today = datetime.today().strftime("%Y-%m-%d")
    driver = None

    try:
        log("Создаём драйвер...")
        driver = create_driver_silent()
        log("Драйвер создан успешно")

        log("Открываем globus.ru...")
        driver.get("https://globus.ru/")
        time.sleep(4)

        # Кнопка "Выбрать город"
        try:
            btn = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "span.js-select-town.button-select.see")
                )
            )
            driver.execute_script("arguments[0].click();", btn)
            log("Кнопка «Выбрать» нажата")
            time.sleep(1)
        except Exception as e:
            log(f"Кнопка «Выбрать» не появилась: {e}")

        # Цикл по товарам
        for idx, product in enumerate(PRODUCTS, 1):
            log(f"\n[{idx}/{len(PRODUCTS)}] Ищем: {product}")
            name_only, unit_default = split_name_unit(product)
            unit_default = unit_default or "1 кг"

            try:
                # Поиск товара
                search_box = WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "input.search-form__input.js-search-form__input")
                    )
                )
                search_box.clear()
                search_box.send_keys(product)
                search_box.send_keys(Keys.ENTER)
                time.sleep(2)

                # Получаем результаты поиска
                links = WebDriverWait(driver, 20).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul li a"))
                )

                candidates = []
                for link in links:
                    title = link.text.strip()
                    href = link.get_attribute("href")
                    if title and href:
                        score = fuzz.token_sort_ratio(name_only.lower(), title.lower())
                        candidates.append((title, href, score))

                if not candidates:
                    log(f"  -> Результатов не найдено")
                    results.append({
                        "store": "Глобус",
                        "product": normalize_product_name(product),
                        "unit": unit_default,
                        "price": None,
                        "date": today
                    })
                    continue

                best_title, best_url, best_score = max(candidates, key=lambda x: x[2])

                if best_score < 25:
                    log(f"  -> Плохое совпадение (score={best_score})")
                    results.append({
                        "store": "Глобус",
                        "product": normalize_product_name(product),
                        "unit": unit_default,
                        "price": None,
                        "date": today
                    })
                    continue

                log(f"  -> Лучшее: {best_title} (score={best_score:.1f})")

                # Переход на страницу товара
                driver.get(best_url)
                time.sleep(2)

                # Цена
                try:
                    price_main = WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, ".catalog-detail__item-price-actual-main")
                        )
                    ).text.strip()
                    price_sub_list = driver.find_elements(
                        By.CSS_SELECTOR, ".catalog-detail__item-price-actual-sub"
                    )
                    price = parse_price(price_main, price_sub_list)
                except Exception as e:
                    log(f"  -> Не удалось получить цену: {e}")
                    price = None

                # Единица измерения
                try:
                    info_text = driver.find_element(By.CSS_SELECTOR, ".product-info").text
                    unit = extract_unit(info_text, unit_default)
                except Exception:
                    unit = unit_default

                results.append({
                    "store": "Глобус",
                    "product": normalize_product_name(product),
                    "unit": unit,
                    "price": price,
                    "date": today
                })

                log(f"  -> OK: {price} / {unit}")

            except Exception as e:
                log(f"  -> ОШИБКА: {e}")
                log(traceback.format_exc())
                results.append({
                    "store": "Глобус",
                    "product": normalize_product_name(product),
                    "unit": unit_default,
                    "price": None,
                    "date": today
                })

            time.sleep(1)

    except Exception as e:
        log(f"\n!!! КРИТИЧЕСКАЯ ОШИБКА: {e}")
        log(traceback.format_exc())

    finally:
        if driver:
            try:
                driver.quit()
                log("Драйвер закрыт")
            except Exception:
                pass

    # ===================== SAVE CSV =====================
    try:
        df = pd.DataFrame(results)
        data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw"))
        os.makedirs(data_dir, exist_ok=True)
        csv_path = os.path.join(data_dir, "globus_prices.csv")
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        log(f"Сохранено {len(df)} записей в {csv_path}")
    except Exception as e:
        log(f"Ошибка сохранения CSV: {e}")

    # ===================== OUTPUT JSON =====================
    # Приложение читает ТОЛЬКО stdout, всё остальное идёт в stderr
    # ensure_ascii=True - экранирует Unicode символы (₽ -> \u20bd) для безопасности
    sys.stdout.write(json.dumps(results, ensure_ascii=True))
    sys.stdout.flush()

    log("=== Парсер завершён ===")


if __name__ == "__main__":
    main()