import os
import time
import undetected_chromedriver as uc
from selenium.webdriver.chrome.service import Service

def create_driver(use_uc=True):
    """
    Создает Chrome-драйвер.

    use_uc: True — используем undetected_chromedriver
            False — обычный selenium.Chrome
    """
    is_ci = os.getenv("GITHUB_ACTIONS") == "true"

    if use_uc:
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-extensions")
        options.add_argument("--remote-debugging-port=9222")
        if is_ci:
            options.add_argument("--headless=new")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        driver = uc.Chrome(options=options, service=Service())
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
        driver = webdriver.Chrome(options=options, service=ChromeService())

    driver.set_page_load_timeout(180)
    driver.implicitly_wait(15)
    return driver


def safe_get(driver, url, retries=3, delay=5):
    """
    Безопасный вызов driver.get() с повторными попытками
    """
    for attempt in range(retries):
        try:
            driver.get(url)
            time.sleep(delay)
            return
        except Exception as e:
            print(f"⚠ Ошибка при открытии {url}: {e}")
            if attempt == retries - 1:
                raise
            time.sleep(delay + 2)
