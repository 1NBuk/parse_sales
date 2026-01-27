import os
import time
import undetected_chromedriver as uc
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

def create_driver(use_uc=True):
    """
    Создаёт Chrome-драйвер (обычный или undetected_chromedriver),
    с настройками для CI (GitHub Actions) и стабильной работы headless.
    """
    is_ci = os.getenv("GITHUB_ACTIONS") == "true"

    # --- Настройки Chrome ---
    if use_uc:
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-features=VizDisplayCompositor")  # стабильность headless
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--remote-debugging-port=9222")
        if is_ci:
            options.add_argument("--headless=new")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        caps = DesiredCapabilities.CHROME.copy()
        caps["pageLoadStrategy"] = "eager"  # быстрее открывает страницы

        driver = uc.Chrome(options=options, desired_capabilities=caps, service=Service())
    else:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service as ChromeService
        from selenium.webdriver.chrome.options import Options

        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        if is_ci:
            options.add_argument("--headless=new")

        caps = DesiredCapabilities.CHROME.copy()
        caps["pageLoadStrategy"] = "eager"

        driver = webdriver.Chrome(options=options, desired_capabilities=caps, service=ChromeService())

    # --- Таймауты ---
    driver.set_page_load_timeout(180)  # max время ожидания загрузки страницы
    driver.implicitly_wait(20)          # implicit wait для поиска элементов
    return driver


def safe_get(driver, url, retries=3, delay=5):
    """
    Безопасный driver.get() с повторными попытками.
    retry: число попыток
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
