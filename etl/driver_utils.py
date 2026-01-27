import os
import time
import undetected_chromedriver as uc
from selenium.common.exceptions import TimeoutException, WebDriverException


def create_driver(use_uc=True):
    """
    Создаёт драйвер Chrome/UC с оптимальными опциями для CI и локального запуска.
    use_uc=True — использовать undetected_chromedriver.
    """
    is_ci = os.getenv("GITHUB_ACTIONS") == "true"

    if use_uc:
        options = uc.ChromeOptions()
    else:
        from selenium.webdriver.chrome.options import Options
        options = Options()

    # Общие опции для стабильной работы в headless/CI
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")

    # Headless только в CI
    if is_ci or use_uc:
        options.add_argument("--headless=new")

    # Пользовательский user-agent
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Создание драйвера
    if use_uc:
        driver = uc.Chrome(options=options)
    else:
        from selenium import webdriver
        driver = webdriver.Chrome(options=options)

    # Таймауты
    driver.set_page_load_timeout(150)  # Максимальное время загрузки страницы
    driver.implicitly_wait(10)  # Ожидание элементов

    return driver


def safe_get(driver, url, retries=3, wait_after_load=5):
    """
    Безопасный метод для driver.get с повторными попытками и задержкой после загрузки.
    """
    for attempt in range(1, retries + 1):
        try:
            driver.get(url)
            time.sleep(wait_after_load)  # Ждём подгрузки JS/контента
            return
        except (TimeoutException, WebDriverException) as e:
            print(f"[warn] Попытка {attempt} не удалась: {e}")
            if attempt == retries:
                raise
            time.sleep(5)  # Подождать перед повторной попыткой
