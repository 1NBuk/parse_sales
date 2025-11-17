import time
import pandas as pd
from datetime import datetime
from rapidfuzz import fuzz

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==========================================================
# СПИСОК ПРОДУКТОВ
# ==========================================================
products = [
    "Яйцо куриное Окское отборное С0 10шт",
    "Батон Коломенский Нарезной 200г",
    "Молоко Простоквашино отборное пастеризованное 3.4-4.5%",
    "Сахар песок белый 1кг",
    "Соль пищевая 1кг",
    "Крупа гречневая ядрица 900г",
    "Масло Олейна подсолнечное 1л",
    "Масло Брест-Литовск сливочное 82,5% 180г",
    "Бедро куриное Петелинка",
    "Чай Greenfield Golden Ceylon 100г",
    "Картофель",
    "Лук репчатый",
    "Морковь",
    "Капуста белокочанная",
    "Яблоки"
]

# ==========================================================
# ЗАПУСК UNDETECTED CHROMEDRIVER
# ==========================================================
options = uc.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")

driver = uc.Chrome(options=options)


# ==========================================================
# ФУНКЦИЯ: ВВЕСТИ ЗАПРОС В ПОИСК ЛЕНТЫ
# ==========================================================
def search_lenta(query):
    driver.get("https://lenta.com/")

    # ждём поле поиска
    search_input = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input.header-search__input"))
    )

    # вводим запрос
    search_input.clear()
    search_input.send_keys(query)
    time.sleep(0.5)
    search_input.send_keys(Keys.ENTER)

    # ждём загрузку результатов
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.sku-card-small"))
        )
    except:
        return []

    time.sleep(1)

    cards = driver.find_elements(By.CSS_SELECTOR, "div.sku-card-small")
    results = []

    for card in cards:
        try:
            name = card.find_element(By.CSS_SELECTOR, ".sku-card-small__title").text.strip()
        except:
            continue

        # Цена
        try:
            whole = card.find_element(By.CSS_SELECTOR, ".price__integer").text.strip()
            frac = card.find_element(By.CSS_SELECTOR, ".price__decimal").text.strip()
            price = f"{whole}.{frac}"
        except:
            price = None

        # Ссылка
        try:
            link = card.find_element(By.TAG_NAME, "a").get_attribute("href")
        except:
            link = None

        results.append({"name": name, "price": price, "link": link})

    return results


# ==========================================================
# ОСНОВНОЙ ЦИКЛ
# ==========================================================
results_final = []
today = datetime.today().strftime("%Y-%m-%d")

for product in products:
    print(f"\n🔎 Ищем: {product}")

    items = search_lenta(product)

    if not items:
        print("❌ Не найдено")
        results_final.append({
            "store": "Лента",
            "product": product,
            "found_name": None,
            "price": None,
            "link": None,
            "date": today
        })
        continue

    # выбираем самый похожий товар
    best = None
    best_score = 0

    for item in items:
        score = fuzz.token_set_ratio(product, item["name"])
        if score > best_score:
            best_score = score
            best = item

    print(f"➡ Лучший товар: {best['name']} — {best['price']} ₽ (score {best_score})")

    results_final.append({
        "store": "Лента",
        "product": product,
        "found_name": best["name"],
        "price": best["price"],
        "link": best["link"],
        "date": today
    })

    time.sleep(1)

driver.quit()

# ==========================================================
# СОХРАНЕНИЕ РЕЗУЛЬТАТА
# ==========================================================
df = pd.DataFrame(results_final)
df.to_csv("lenta_prices.csv", index=False, encoding="utf-8-sig")

print("\n💾 Результат сохранён в lenta_prices.csv")
