import sys
import os
sys.stdout.reconfigure(encoding="utf-8")
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.insert(0, BASE_DIR)

import time
import pandas as pd
import re
import urllib.parse
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from rapidfuzz import fuzz

# Импортируем webdriver-manager для автоматического управления драйверами
from webdriver_manager.chrome import ChromeDriverManager

products = [
    "Яйцо куриное Окское отборное С1 10шт",
    "Яйцо куриное Окское С1",
    "Батон Коломенский Нарезной 200г",
    "Молоко Простоквашино отборное пастеризованное 3.4-4.5%",
    "Сахар кусковой белый 1кг",
    "Соль пищевая 1кг",
    "Крупа гречневая Мистраль 900г",
    "Масло Олейна подсолнечное 1л",
    "Масло Брест-Литовск сливочное 82,5% 180г",
    "Филе грудки цыпленка Петелинка",
    "Чай Greenfield Kenyan Sunrise чёрный байховый 100г",
    "Картофель",
    "Лук репчатый",
    "Морковь отечественная",
    "Капуста белокочанная",
    "Яблоки сезонные"
]

results = []


def split_name_unit(product):
    match = re.search(r"(\d+(\.\d+)?\s?(г|кг|мл|л|шт))", product, re.IGNORECASE)
    if match:
        unit = match.group(1)
        name = product.replace(unit, "").strip()
    else:
        unit = ""
        name = product
    return name, unit


# Получаем текущую дату
today = datetime.today().strftime("%Y-%m-%d")


def setup_driver():
    """Настройка драйвера с автоматической установкой правильной версии ChromeDriver"""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # Автоматическая загрузка и установка правильной версии ChromeDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # Маскируем Selenium для обхода детекции
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        """
    })

    return driver


# ===== Перекресток =====
driver = setup_driver()

try:
    # "Прогреваем" сайт - заходим на главную страницу
    driver.get("https://www.perekrestok.ru")
    time.sleep(3)

    for product in products:
        name_only, unit_default = split_name_unit(product)
        encoded_query = urllib.parse.quote(name_only)
        url = f"https://www.perekrestok.ru/cat/search?search={encoded_query}"

        print(f"\nИщу: {name_only}")

        try:
            driver.get(url)
            time.sleep(3)  # Даем время на загрузку

            # Проверяем, есть ли результаты поиска
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".product-card"))
                )
            except:
                print(f"  Перекресток — {name_only} — товары не найдены")
                results.append({
                    "store": "Перекресток",
                    "product": name_only,
                    "unit": unit_default or "1000 гр",
                    "price": None,
                    "date": today
                })
                time.sleep(2)
                continue

            cards = driver.find_elements(By.CSS_SELECTOR, ".product-card")

            selected_card = None
            max_score = 0
            price = None
            unit_from_site = unit_default or "1000 гр"

            # Проходим по всем карточкам и выбираем по максимальному score
            for card in cards:
                try:
                    title_elem = card.find_element(By.CSS_SELECTOR, ".product-card__title")
                    title_text = title_elem.text.strip().lower()
                    score = fuzz.token_sort_ratio(name_only.lower(), title_text)

                    if score > max_score:
                        max_score = score
                        selected_card = card
                except Exception as e:
                    continue

            if selected_card and max_score > 50:  # фильтр по минимальному сходству
                # Получаем цену
                price_selectors = [
                    ".price-new",
                    ".product-card-price__current",
                    ".product-card-price__discount",
                    ".product-card__price",
                    ".product-card__price--current"
                ]

                for selector in price_selectors:
                    try:
                        elem = selected_card.find_element(By.CSS_SELECTOR, selector)
                        text = elem.text.strip()
                        if text:
                            # Очищаем текст от лишних символов
                            price = re.sub(r'[^\d\.,]', '', text)
                            break
                    except:
                        continue

                # Если не нашли цену в основных селекторах, ищем любую цену
                if not price:
                    try:
                        price_elements = selected_card.find_elements(By.CSS_SELECTOR,
                                                                     "[class*='price'], [class*='Price']")
                        for elem in price_elements:
                            text = elem.text.strip()
                            if text and any(char.isdigit() for char in text):
                                price = re.sub(r'[^\d\.,]', '', text)
                                break
                    except:
                        pass

                # Получаем unit
                try:
                    unit_elem = selected_card.find_element(By.CSS_SELECTOR, ".product-card__size")
                    if unit_elem.text.strip():
                        unit_from_site = unit_elem.text.strip()
                except:
                    # Пробуем другие селекторы для unit
                    unit_selectors = [
                        ".product-card__weight",
                        ".product-card__quantity",
                        ".product-card__volume"
                    ]
                    for selector in unit_selectors:
                        try:
                            unit_elem = selected_card.find_element(By.CSS_SELECTOR, selector)
                            if unit_elem.text.strip():
                                unit_from_site = unit_elem.text.strip()
                                break
                        except:
                            continue

                if price:
                    # Форматируем цену
                    try:
                        price_num = float(price.replace(',', '.'))
                        price = f"{price_num:.2f} ₽"
                    except:
                        price = f"{price} ₽"

                    print(f"Перекресток — {name_only} — {price} — {unit_from_site} (сходство: {max_score}%)")
                else:
                    print(f"Перекресток — {name_only} — цена не найдена (сходство: {max_score}%)")
                    price = None
            else:
                print(f"  ✗ Перекресток — {name_only} — подходящий товар не найден (лучшее сходство: {max_score}%)")
                price = None

            results.append({
                "store": "Перекресток",
                "product": name_only,
                "unit": unit_from_site,
                "price": price,
                "date": today
            })

        except Exception as e:
            print(f"  ✗ Перекресток — {name_only} — ошибка при поиске: {str(e)}")
            results.append({
                "store": "Перекресток",
                "product": name_only,
                "unit": unit_default or "1000 гр",
                "price": None,
                "date": today
            })

        time.sleep(1.5)  # Увеличил задержку для избежания блокировки

finally:
    driver.quit()

# ===== Сохраняем CSV =====
df = pd.DataFrame(results)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw"))
os.makedirs(BASE_DIR, exist_ok=True)
file_path = os.path.join(BASE_DIR, "perekrestok_prices.csv")
df.to_csv(file_path, index=False, encoding="utf-8-sig")
print(f"\nСохранено {len(df)} записей в {file_path}")

# Выводим статистику
found_count = df[df['price'].notna()].shape[0]
print(f"Найдено цен: {found_count} из {len(df)}")