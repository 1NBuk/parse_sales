import time
import pandas as pd
from datetime import datetime
import re
import os
import sys
import json
import random
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.insert(0, BASE_DIR)

try:
    from etl.driver_utils import create_driver
except ImportError:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "driver_utils",
        os.path.join(os.path.dirname(__file__), "driver_utils.py")
    )
    driver_utils = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver_utils)
    create_driver = driver_utils.create_driver

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from rapidfuzz import fuzz


def human_delay(min_seconds=0.5, max_seconds=1.5):
    """Случайная задержка для имитации человека"""
    time.sleep(random.uniform(min_seconds, max_seconds))


if len(sys.argv) > 1:
    try:
        products = json.loads(sys.argv[1])
    except:
        products = [sys.argv[1]]
else:
    products = [
        "Яйцо куриное Окское С1 10шт",
        "Батон Коломенский Нарезной 200г",
        "Молоко Простоквашино отборное пастеризованное 3.4-4.5",
        "Сахар кусковой белый 1кг",
        "Соль пищевая 1кг",
        "Крупа гречневая Мистраль 900г",
        "Масло Олейна подсолнечное 1л",
        "Масло Брест-Литовск сливочное 82,5 180г",
        "Филе грудки цыпленка Петелинка",
        "Чай Greenfield Golden Ceylon 100г",
        "Картофель белый, вес",
        "Лук репчатый",
        "Социальный товар Морковь",
        "Капуста белокочанная",
        "Яблоки сезонные"
    ]

results = []
today = datetime.today().strftime("%Y-%m-%d")


def accept_cookies(driver):
    """Принимаем cookies, если появляется баннер."""
    try:
        human_delay(1, 2)

        # Пробуем найти кнопку "Согласен"
        try:
            cookie_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Согласен')]"))
            )
            cookie_button.click()
            print("Cookies приняты", file=sys.stderr)
            human_delay(1, 2)
            return True
        except:
            pass

        # Пробуем другие селекторы
        try:
            buttons = driver.find_elements(By.CSS_SELECTOR, "div[class*='acceptCookieAlert'] button")
            if buttons:
                buttons[0].click()
                print("Cookies приняты", file=sys.stderr)
                human_delay(1, 2)
                return True
        except:
            pass

    except Exception as e:
        print(f"Ошибка при принятии cookies: {e}", file=sys.stderr)

    return False


def clear_search_box_forced(driver):
    """Гарантированная очистка поля поиска с множественными способами."""
    try:
        # Находим поле поиска
        search_box = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input#search"))
        )

        # Кликаем для фокуса
        search_box.click()
        human_delay(0.3, 0.5)

        # Способ 1: Ctrl+A + Delete
        search_box.send_keys(Keys.CONTROL + "a")
        human_delay(0.1, 0.2)
        search_box.send_keys(Keys.DELETE)
        human_delay(0.1, 0.2)

        # Способ 2: Очистка через clear()
        search_box.clear()
        human_delay(0.1, 0.2)

        # Способ 3: Очистка через JavaScript
        driver.execute_script("arguments[0].value = '';", search_box)
        human_delay(0.2, 0.3)

        # Способ 4: Отправляем пустую строку
        search_box.send_keys("")
        human_delay(0.1, 0.2)

        # Проверяем результат
        current_value = search_box.get_attribute("value")
        if current_value and len(current_value) > 0:
            print(f"  Предупреждение: поле не очистилось полностью. Значение: '{current_value}'", file=sys.stderr)
            # Пробуем ещё раз через JS
            driver.execute_script("arguments[0].value = ''; arguments[0].dispatchEvent(new Event('input'));",
                                  search_box)
            human_delay(0.3, 0.5)

        return search_box

    except Exception as e:
        print(f"Ошибка при очистке поиска: {e}", file=sys.stderr)
        return None


def extract_price_v2(card, driver):
    """Извлечение цены из карточки Ашана."""
    selectors = [
        "[class*='price']",
        "[class*='Price']",
        "div[class*='price']",
        "span[class*='price']"
    ]

    for sel in selectors:
        try:
            elements = card.find_elements(By.CSS_SELECTOR, sel)
            for elem in elements:
                text = elem.text.strip()
                match = re.search(r"(\d+[.,]?\d*)\s?[₽руб]", text)
                if match:
                    price_str = match.group(1).replace(",", ".")
                    return float(price_str)
                match = re.search(r"(\d+[.,]\d{2})", text)
                if match:
                    price_str = match.group(1).replace(",", ".")
                    if float(price_str) < 10000:
                        return float(price_str)
        except:
            continue

    return None


def scroll_page_slowly(driver):
    """Медленная прокрутка страницы для имитации человека."""
    try:
        driver.execute_script("window.scrollBy(0, 300);")
        human_delay(0.5, 1)
        driver.execute_script("window.scrollBy(0, 300);")
        human_delay(0.3, 0.8)
    except:
        pass


def check_for_blocking_page(driver):
    """Проверяем, не заблокировали ли нас."""
    try:
        page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        if "что-то пошло не так" in page_text or "обновить страницу" in page_text:
            print("Обнаружена страница блокировки!", file=sys.stderr)
            return True
        return False
    except:
        return False


def wait_for_search_results(driver, timeout=25):
    """Ожидание загрузки результатов поиска."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, "[data-testid='productCard-container']")
            )
        )
        return True
    except TimeoutException:
        return False


def main():
    driver = create_driver(use_uc=True)

    try:
        print("Загрузка сайта...", file=sys.stderr)
        driver.get("https://www.auchan.ru")
        human_delay(3, 5)

        # Принимаем cookies
        accept_cookies(driver)
        human_delay(2, 3)

        for idx, product in enumerate(products):
            print(f"\n{'=' * 50}", file=sys.stderr)
            print(f"Обработка {idx + 1}/{len(products)}: {product}", file=sys.stderr)
            print(f"{'=' * 50}", file=sys.stderr)

            name_only, unit_default = split_name_unit(product)

            if not unit_default:
                unit_default = "1 кг"

            try:
                # Проверяем блокировку
                if check_for_blocking_page(driver):
                    print("Сайт заблокировал запросы. Перезапустите парсер позже.", file=sys.stderr)
                    break

                # === ГАРАНТИРОВАННАЯ ОЧИСТКА ПЕРЕД ПОИСКОМ ===
                print("Очищаем поле поиска...", file=sys.stderr)
                search_box = clear_search_box_forced(driver)

                if not search_box:
                    print("Не удалось получить поле поиска", file=sys.stderr)
                    results.append({
                        "store": "Ашан",
                        "product": product,
                        "unit": unit_default,
                        "price": None,
                        "date": today
                    })
                    human_delay(5, 8)
                    continue

                # Проверяем, что поле действительно пустое
                current_value = search_box.get_attribute("value")
                if current_value:
                    print(f"  Поле содержит: '{current_value}'. Очищаем принудительно...", file=sys.stderr)
                    driver.execute_script("arguments[0].value = '';", search_box)
                    human_delay(0.3, 0.5)

                print("  Поле очищено", file=sys.stderr)
                human_delay(0.5, 1)

                # === ВВОД ЗАПРОСА ===
                print(f"Вводим запрос: {product}", file=sys.stderr)
                for char in product:
                    search_box.send_keys(char)
                    human_delay(0.05, 0.15)

                human_delay(0.5, 1)
                search_box.send_keys(Keys.ENTER)
                print("Нажали Enter", file=sys.stderr)

                # Большая задержка после поиска
                human_delay(3, 5)

                # Медленно прокручиваем страницу
                scroll_page_slowly(driver)

                # Ждём загрузки результатов
                if not wait_for_search_results(driver):
                    print(f"Таймаут загрузки результатов для '{product}'", file=sys.stderr)

                    if check_for_blocking_page(driver):
                        print("Обнаружена блокировка!", file=sys.stderr)
                        break

                    results.append({
                        "store": "Ашан",
                        "product": product,
                        "unit": unit_default,
                        "price": None,
                        "date": today
                    })
                    human_delay(5, 8)
                    continue

                print("Результаты загружены", file=sys.stderr)
                human_delay(1, 2)

                # Находим карточки
                cards = driver.find_elements(By.CSS_SELECTOR, "[data-testid='productCard-container']")
                print(f"Найдено карточек: {len(cards)}", file=sys.stderr)

                if not cards:
                    print(f"Карточки не найдены для '{product}'", file=sys.stderr)
                    results.append({
                        "store": "Ашан",
                        "product": product,
                        "unit": unit_default,
                        "price": None,
                        "date": today
                    })
                    human_delay(5, 8)
                    continue

                # Поиск лучшего совпадения
                best_index = None
                best_score = -1
                best_title = ""

                for i in range(min(len(cards), 5)):
                    try:
                        cards = driver.find_elements(By.CSS_SELECTOR, "[data-testid='productCard-container']")
                        if i >= len(cards):
                            break

                        card = cards[i]

                        # Поиск названия
                        title = ""
                        try:
                            name_elem = card.find_element(By.CSS_SELECTOR, "[class*='productCardContentPanel_name']")
                            title = name_elem.text.strip()
                        except:
                            try:
                                links = card.find_elements(By.TAG_NAME, "a")
                                for link in links:
                                    href = link.get_attribute("href")
                                    if href and "/product/" in href:
                                        title = link.get_attribute("title") or link.text.strip()
                                        if title:
                                            break
                            except:
                                continue

                        if not title:
                            continue

                        score = fuzz.token_sort_ratio(name_only.lower(), title.lower())
                        print(f"  Карточка {i + 1}: '{title[:50]}...' score={score}", file=sys.stderr)

                        if score > best_score:
                            best_score = score
                            best_index = i
                            best_title = title

                    except Exception as e:
                        print(f"Ошибка при анализе карточки {i}: {e}", file=sys.stderr)
                        continue

                if best_index is None or best_score < 30:
                    print(f"Товар не найден (лучший score={best_score})", file=sys.stderr)
                    results.append({
                        "store": "Ашан",
                        "product": product,
                        "unit": unit_default,
                        "price": None,
                        "date": today
                    })
                    human_delay(5, 8)
                    continue

                # Получаем лучшую карточку
                cards = driver.find_elements(By.CSS_SELECTOR, "[data-testid='productCard-container']")
                if best_index >= len(cards):
                    print("Индекс карточки вне диапазона", file=sys.stderr)
                    results.append({
                        "store": "Ашан",
                        "product": product,
                        "unit": unit_default,
                        "price": None,
                        "date": today
                    })
                    human_delay(5, 8)
                    continue

                best_card = cards[best_index]

                # Прокручиваем к карточке
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", best_card)
                human_delay(0.5, 1)

                # Извлекаем цену
                price = extract_price_v2(best_card, driver)

                # Извлекаем единицу измерения
                card_text = best_card.text
                match_unit = re.search(r"(\d+\s?(г|кг|мл|л|шт))", card_text, re.IGNORECASE)

                if not match_unit:
                    match_unit = re.search(r"(\d+[.,]?\d*\s?(г|кг|мл|л|шт))", best_title, re.IGNORECASE)

                unit_site = match_unit.group(1) if match_unit else unit_default

                results.append({
                    "store": "Ашан",
                    "product": product,
                    "unit": unit_site,
                    "price": price,
                    "date": today
                })

                print(f"✓ Найден: {best_title[:60]}...", file=sys.stderr)
                print(f"✓ Цена: {price} ₽, {unit_site} (score={best_score})", file=sys.stderr)

                # === ОЧИСТКА ПОСЛЕ ОБРАБОТКИ ===
                print("Очищаем поле поиска после обработки...", file=sys.stderr)
                clear_search_box_forced(driver)

                # Большая задержка между товарами
                delay = random.uniform(5, 10)
                print(f"Пауза {delay:.1f} секунд перед следующим товаром...", file=sys.stderr)
                time.sleep(delay)

            except Exception as e:
                print(f"✗ Ошибка при обработке '{product}': {e}", file=sys.stderr)
                import traceback
                traceback.print_exc()
                results.append({
                    "store": "Ашан",
                    "product": product,
                    "unit": unit_default,
                    "price": None,
                    "date": today
                })
                try:
                    clear_search_box_forced(driver)
                except:
                    pass

                human_delay(8, 12)

        # Вывод статистики
        print(f"\n{'=' * 50}", file=sys.stderr)
        successful = sum(1 for r in results if r['price'] is not None)
        print(f"Обработано товаров: {len(results)}", file=sys.stderr)
        print(f"Успешно найдено: {successful}", file=sys.stderr)
        print(f"Не найдено: {len(results) - successful}", file=sys.stderr)
        print(f"{'=' * 50}", file=sys.stderr)

    except Exception as e:
        print(f"Критическая ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
    finally:
        print("\nЗавершение работы...", file=sys.stderr)
        human_delay(2, 3)
        driver.quit()

    # Сохранение результатов
    if results:
        df = pd.DataFrame(results)
        data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw"))
        os.makedirs(data_dir, exist_ok=True)
        file_path = os.path.join(data_dir, "auchan_prices.csv")
        df.to_csv(file_path, index=False, encoding="utf-8-sig")

        print(f"\nСохранено {len(df)} записей в {file_path}", file=sys.stderr)
        print(json.dumps(results, ensure_ascii=False))
    else:
        print("Нет результатов для сохранения", file=sys.stderr)


def split_name_unit(product):
    match = re.search(r"(\d+(\.\d+)?\s?(г|кг|мл|л|шт))", product, re.IGNORECASE)
    if match:
        return product.replace(match.group(1), "").strip(), match.group(1)
    return product, ""


if __name__ == "__main__":
    main()