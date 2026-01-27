import os
import time
import undetected_chromedriver as uc
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities


def create_driver(use_uc=True):
    """
    use_uc оставлен для обратной совместимости со всеми парсерами
    Фактически всегда используется undetected_chromedriver
    """

    is_ci = os.getenv("GITHUB_ACTIONS") == "true"

    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    if is_ci:
        options.add_argument("--headless=new")

    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    caps = DesiredCapabilities.CHROME.copy()
    caps["pageLoadStrategy"] = "eager"

    driver = uc.Chrome(
        options=options,
        desired_capabilities=caps
    )

    driver.set_page_load_timeout(90 if is_ci else 60)
    driver.implicitly_wait(15)

    return driver


def safe_get(driver, url, retries=3):
    for attempt in range(retries):
        try:
            driver.get(url)
            time.sleep(3)
            return
        except Exception as e:
            if attempt == retries - 1:
                raise e
            time.sleep(5)
