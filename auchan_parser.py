import time
import pandas as pd
from datetime import datetime
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from rapidfuzz import fuzz
import undetected_chromedriver as uc

# -------------------------------------------------------------
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

results = []
today = datetime.today().strftime("%Y-%m-%d")

# -------------------------------------------------------------
def split_name_unit(product):
    match = re.search(r"(\d+(\.\d+)?\s?(г|кг|мл|л|шт))", product, re.IGNORECASE)
    if match:
        return product.replace(match.group(1), "").strip(), match.group(1)
    return product, ""  # если нет веса, unit_default будет пустым

# -------------------------------------------------------------
def extract_price(card, driver):
    """Надёжный поиск цены через CSS и JS fallback."""
    selectors = [
        ".digi-product-price-variant_actual",
        ".digi-product__price .digi-product-price-variant_actual",
    ]
    for sel in selectors:
        try:
            elem = card.find_element(By.CSS_SELECTOR, sel)
            raw = elem.text.strip()
            m = re.search(r"(\d+[.,]?\d*)", raw)
            if m:
                return m.group(1).replace(",", ".") + " ₽"
        except:
            pass

    # fallback через JS
    try:
        js = driver.execute_script("""
            let el = arguments[0].querySelector(".digi-product-price-variant_actual");
            return el ? el.textContent : null;
        """, card)
        if js:
            m = re.search(r"(\d+[.,]?\d*)", js)
            if m:
                return m.group(1).replace(",", ".") + " ₽"
    except:
        pass

    return None

# -------------------------------------------------------------
options = uc.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
driver = uc.Chrome(options=options)

driver.get("https://www.auchan.ru")
time.sleep(3)

# -------------------------------------------------------------
# MAIN LOOP
# -------------------------------------------------------------
for product in products:
    name_only, unit_default = split_name_unit(product)

    # если unit_default пустой, ставим "1 кг"
    if not unit_default:
        unit_default = "1 кг"

    try:
        # поиск
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input#search"))
        )
        search_box.clear()
        search_box.send_keys(product)
        search_box.send_keys(Keys.ENTER)

        # загрузка карточек
        WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR,
                                                 "div.digi-product, div.product-card"))
        )

        time.sleep(1.5)  # даём пересобрать DOM

        # -------- 1️⃣ Находим ВСЕ карточки — имена используем только как TEXT --------
        cards = driver.find_elements(By.CSS_SELECTOR, "div.digi-product, div.product-card")

        best_index = None
        best_score = -1

        # -------- 2️⃣ оцениваем SCORE по названию --------
        for idx in range(len(cards)):

            # каждый раз получаем карточку заново → нет stale element
            cards = driver.find_elements(By.CSS_SELECTOR, "div.digi-product, div.product-card")
            card = cards[idx]

            title = ""
            for sel in [
                "a.digi-product__label",
                ".digi-product__label",
                "a.product-card__title",
            ]:
                try:
                    title = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                    break
                except:
                    continue

            if not title:
                continue

            score = fuzz.token_sort_ratio(name_only.lower(), title.lower())

            if score > best_score:
                best_score = score
                best_index = idx

        # -------- 3️⃣ если нет совпадений --------
        if best_index is None or best_score < 25:
            print(f"⚠️ Ашан — {product} — товар не найден (score={best_score})")
            results.append({"store": "Ашан", "product": product, "unit": unit_default, "price": None, "date": today})
            continue

        # -------- 4️⃣ снова получаем ЛУЧШУЮ карточку — заново! --------
        cards = driver.find_elements(By.CSS_SELECTOR, "div.digi-product, div.product-card")
        best_card = cards[best_index]

        # -------- 5️⃣ цена --------
        price = extract_price(best_card, driver)

        # -------- 6️⃣ единица измерения --------
        card_text = best_card.text
        match_unit = re.search(r"(\d+\s?(г|кг|мл|л|шт))", card_text)
        unit_site = match_unit.group(1) if match_unit else unit_default  # если нет на сайте, используем unit_default

        results.append({
            "store": "Ашан",
            "product": product,
            "unit": unit_site,
            "price": price,
            "date": today
        })

        print(f"✅ Ашан — {product} — {price} — {unit_site} (score={best_score})")

    except Exception as e:
        print(f"❌ Ошибка при обработке '{product}': {e}")
        results.append({"store": "Ашан", "product": product, "unit": unit_default, "price": None, "date": today})

    time.sleep(2)

driver.quit()

# SAVE
df = pd.DataFrame(results)
df.to_csv("auchan_prices.csv", index=False, encoding="utf-8-sig")
print("\n💾 Сохранено!")
