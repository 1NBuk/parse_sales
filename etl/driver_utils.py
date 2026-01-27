import os
import time
import undetected_chromedriver as uc
from selenium.webdriver.chrome.service import Service

def create_driver():
    is_ci = os.getenv("GITHUB_ACTIONS") == "true"

    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--remote-debugging-port=9222")

    # Headless для CI
    if is_ci:
        options.add_argument("--headless=new")

    # Браузер будет использовать User-Agent
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Настройки таймаутов
    driver = uc.Chrome(options=options, service=Service())
    driver.set_page_load_timeout(180)   # увеличил таймаут
    driver.implicitly_wait(15)

    return driver

def safe_get(driver, url, retries=3, delay=5):
    for attempt in range(retries):
        try:
            driver.get(url)
            time.sleep(delay)  # ждем прогрузки JS
            return
        except Exception as e:
            print(f"⚠ Ошибка при открытии {url}: {e}")
            if attempt == retries - 1:
                raise
            time.sleep(delay + 2)
