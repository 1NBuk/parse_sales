import time
import pandas as pd
import re
from datetime import datetime
from rapidfuzz import fuzz
from urllib.parse import quote

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

products = [
    "Яйцо куриное Окское С0 10шт",
    "Батон Коломенский Нарезной 200г",
    "Молоко Простоквашино отборное пастеризованное",
    "Сахар песок белый 1кг",
    "Соль пищевая 1кг",
    "Крупа гречневая ядрица 900г",
    "Масло Олейна подсолнечное 1л",
    "Масло Брест-Литовск сливочное 180г",
    "Бедро куриное Петелинка",
    "Чай Greenfield Golden Ceylon 100г",
    "Картофель",
    "Лук репчатый",
    "Морковь",
    "Капуста белокочанная",
    "Яблоки"
]


def create_driver():
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-infobars")

    prefs = {
        "profile.default_content_setting_values.geolocation": 2,
        "profile.default_content_setting_values.notifications": 2
    }
    options.add_experimental_option("prefs", prefs)

    return uc.Chrome(options=options)


def close_popups_fast(driver):
    try:
        selectors_to_try = [
            "button.popup__close",
            "div.flocktory-widget-overlay",
            "div.modal button",
            "[aria-label='Close']",
            ".close-btn"
        ]

        for selector in selectors_to_try:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    try:
                        driver.execute_script("arguments[0].click();", element)
                    except:
                        pass
            except:
                pass
    except:
        pass


def search_product_fast(driver, product_name):
    try:
        clean_query = re.sub(r'[%&?=]', '', product_name)
        encoded_query = quote(clean_query, safe='')
        search_url = f"https://lenta.com/search/{encoded_query}/"

        print(f"Переходим: {search_url}")
        driver.get(search_url)

        time.sleep(3)
        close_popups_fast(driver)

        try:
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "lu-product-card"))
            )
            print("Карточки загружены")
        except:
            try:
                results_title = driver.find_elements(By.XPATH, "//h1[contains(text(), 'Результаты по запросу')]")
                if results_title:
                    print("Страница результатов загружена")
                else:
                    no_results = driver.find_elements(By.XPATH,
                                                      "//*[contains(text(), 'ничего не найдено') or contains(text(), 'Не найдено')]")
                    if no_results:
                        print("Ничего не найдено")
                        return []
                    else:
                        print("Не удалось определить статус загрузки")
                        return []
            except:
                print("Ошибка при проверке результатов")
                return []

        cards = driver.find_elements(By.CSS_SELECTOR, "lu-product-card")
        print(f"Найдено карточек: {len(cards)}")

        results = []

        for card in cards[:15]:
            try:
                name_element = card.find_element(By.CSS_SELECTOR, "span.card-name_content")
                name = name_element.text.strip()

                unit = None
                try:
                    unit_element = card.find_element(By.CSS_SELECTOR, "p.card-name_package")
                    unit = unit_element.text.strip()
                except:
                    unit_match = re.search(r'(\d+[.,]?\d*\s*(?:кг|г|л|мл|шт|мг|таб|пач|уп|упак))', name, re.IGNORECASE)
                    if unit_match:
                        unit = unit_match.group(1)

                if not unit:
                    unit = "1000г"

                price = None
                price_patterns = [
                    r'(\d+[.,]\d+)\s*₽',
                    r'(\d+)\s*₽',
                ]

                card_text = card.text
                for pattern in price_patterns:
                    match = re.search(pattern, card_text, re.IGNORECASE)
                    if match:
                        price = match.group(1)
                        break

                if not price:
                    price_selectors = [
                        "span.main-price",
                        ".product-price",
                        ".price-and-buttons",
                        "[data-loyalty-price]"
                    ]
                    for selector in price_selectors:
                        try:
                            price_elem = card.find_element(By.CSS_SELECTOR, selector)
                            price_text = price_elem.text.strip()
                            price_match = re.search(r'(\d+[.,]\d+|\d+)', price_text)
                            if price_match:
                                price = price_match.group(0)
                                break
                        except:
                            continue

                if name:
                    results.append({
                        "name": name,
                        "price": price,
                        "unit": unit
                    })

            except Exception as e:
                continue

        print(f"Обработано: {len(results)} товаров")
        return results

    except Exception as e:
        print(f"Ошибка при поиске: {str(e)}")
        return []


def clean_price(price_text):
    if not price_text:
        return None

    try:
        cleaned = re.sub(r'[^\d.,]', '', str(price_text))
        cleaned = cleaned.replace(',', '.')
        if '.' in cleaned:
            parts = cleaned.split('.')
            if len(parts) > 1:
                cleaned = parts[0] + '.' + ''.join(parts[1:])

        if cleaned and cleaned.replace('.', '').isdigit():
            return float(cleaned)
        return None
    except:
        return None


def find_best_match(product_name, items):
    if not items:
        return None, 0

    best_match = None
    best_score = 0

    for item in items:
        if not item['name']:
            continue

        scores = [
            fuzz.token_set_ratio(product_name.lower(), item['name'].lower()),
            fuzz.partial_ratio(product_name.lower(), item['name'].lower()),
        ]

        current_score = max(scores)

        if item['price']:
            current_score += 10

        if current_score > best_score:
            best_score = current_score
            best_match = item

    return best_match, best_score


def main():
    results_final = []
    today = datetime.today().strftime("%Y-%m-%d")

    print("Запуск парсера Ленты...")
    print(f"Всего товаров: {len(products)}")

    driver = create_driver()

    try:
        for i, product in enumerate(products, 1):
            print(f"\n==================================================")
            print(f"Поиск {i}/{len(products)}: {product}")
            print(f"==================================================")

            start_time = time.time()
            items = search_product_fast(driver, product)
            search_time = time.time() - start_time

            if items:
                print(f"Найдено: {len(items)} товаров (время: {search_time:.1f}с)")

                for j, item in enumerate(items[:3], 1):
                    price_display = item['price'] if item['price'] else 'нет цены'
                    print(f"   {j}. {item['name']} - {price_display} - {item['unit']}")

                best_match, score = find_best_match(product, items)

                if best_match and score >= 50:
                    clean_price_value = clean_price(best_match['price'])

                    print(f"ВЫБРАНО: {best_match['name']}")
                    print(f"   Цена: {clean_price_value}")
                    print(f"   Unit: {best_match['unit']}")
                    print(f"   Схожесть: {score:.1f}%")

                    results_final.append({
                        "store": "Лента",
                        "product": product,
                        "unit": best_match["unit"],
                        "price": clean_price_value,
                        "date": today
                    })
                else:
                    print(f"Нет подходящего товара (схожесть: {score:.1f}%)")
                    results_final.append({
                        "store": "Лента",
                        "product": product,
                        "unit": "1000г",
                        "price": None,
                        "date": today
                    })
            else:
                print("Товары не найдены")
                results_final.append({
                    "store": "Лента",
                    "product": product,
                    "unit": "1000г",
                    "price": None,
                    "date": today
                })

            if i < len(products):
                time.sleep(1)

    except Exception as e:
        print(f"Критическая ошибка: {str(e)}")

    finally:
        print("\nЗакрываем браузер...")
        driver.quit()

    print(f"\n==================================================")
    print("Сохраняем результаты...")

    df = pd.DataFrame(results_final)
    df.to_csv("lenta_prices.csv", index=False, encoding="utf-8-sig")

    found_count = len([x for x in results_final if x['price'] is not None])
    print(f"РЕЗУЛЬТАТЫ:")
    print(f"   Найдено: {found_count}/{len(products)}")
    print(f"   Не найдено: {len(products) - found_count}")
    print(f"   Файл: lenta_prices.csv")
    print("Готово!")


if __name__ == "__main__":
    main()