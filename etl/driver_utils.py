import os
import time
import undetected_chromedriver as uc

from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

def create_driver(use_uc=True):
    """
    Создаёт Chrome-драйвер:
    - use_uc=True: undetected_chromedriver
    - use_uc=False: обычный Selenium Chrome
    Настройки оптимизированы для CI (GitHub Actions) и стабильной работы headless.
    """
    is_ci = os.getenv("GITHUB_ACTIONS") == "true"

    # --- Общие настройки Chrome ---
    chrome_args = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--window-size=1920,1080",
        "--disable-extensions",
        "--disable-blink-features=AutomationControlled",
        "--disable-features=VizDisplayCompositor",
        "--remote-debugging-port=9222",
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    if is_ci:
        chrome_args.append("--headless=new")

    if use_uc:
        # --- undetected_chromedriver ---
        options = uc.ChromeOptions()
        for arg in chrome_args:
            options.add_argument(arg)

        caps = DesiredCapabilities.CHROME.copy()
        caps["pageLoadStrategy"] = "eager"  # быстрее открывает страницы

        driver = uc.Chrome(options=options, desired_capabilities=caps, service=Service())
    else:
        # --- обычный Selenium Chrome ---
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service as ChromeService

        options = Options()
        for arg in chrome_args:
            options.add_argument(arg)

        # Для Selenium 4+ больше не используем desired_capabilities напрямую
        options.set_capability("pageLoadStrategy", "eager")

        driver = webdriver.Chrome(service=ChromeService(), options=options)

    # --- Таймауты ---
    driver.set_page_load_timeout(180)  # max время ожидания загрузки страницы
    driver.implicitly_wait(20)          # implicit wait для поиска элементов
    return driver


def safe_get(driver, url, retries=3, delay=5):
    """
    Безопасный driver.get() с повторными попытками.
    retries: число попыток
    delay: задержка после открытия страницы
    """
    for attempt in range(1, retries + 1):
        try:
            driver.get(url)
            time.sleep(delay)
            return
        except Exception as e:
            print(f"⚠ Попытка {attempt}/{retries}: ошибка при открытии {url}: {e}")
            if attempt == retries:
                raise
            time.sleep(delay + 2)
