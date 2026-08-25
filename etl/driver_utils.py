# driver_utils.py
import os
import random
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def create_driver(use_uc=False, headless=None, disable_bot_detection=True, random_user_agent=False):
    """
    Создает драйвер с настройками для обхода обнаружения
    """
    if headless is None:
        headless = os.environ.get("SELENIUM_HEADLESS", "0") == "1"

    try:
        if use_uc:
            # Используем undetected_chromedriver
            import undetected_chromedriver as uc
            print("Используется undetected_chromedriver")

            options = uc.ChromeOptions()

            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-gpu")
            options.add_argument("start-maximized")
            options.add_argument("--disable-infobars")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-browser-side-navigation")

            if random_user_agent:
                user_agents = [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ]
                options.add_argument(f"user-agent={random.choice(user_agents)}")

            if headless:
                options.add_argument("--headless")

            driver = uc.Chrome(
                options=options,
                use_subprocess=True,
                version_main=147
            )

        else:
            print("Используется обычный Selenium Chrome")

            options = Options()
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-gpu")
            options.add_argument("start-maximized")
            options.add_argument("--disable-infobars")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-browser-side-navigation")

            chrome_bin = os.environ.get("CHROME_BIN")
            if chrome_bin:
                options.binary_location = chrome_bin

            if random_user_agent:
                user_agents = [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ]
                options.add_argument(f"user-agent={random.choice(user_agents)}")

            if headless:
                options.add_argument("--headless=new")

            chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
            if chromedriver_path:
                service = Service(chromedriver_path)
            else:
                service = Service(ChromeDriverManager().install())

            driver = webdriver.Chrome(service=service, options=options)

        # Размер окна (только если не headless)
        if not headless:
            width = random.randint(1200, 1920)
            height = random.randint(800, 1080)
            driver.set_window_size(width, height)

        # Выполняем скрипты для скрытия автоматизации
        if not use_uc:  # UC уже делает это автоматически
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        return driver

    except Exception as e:
        print(f"Ошибка при создании драйвера: {e}")

        # Попытка создать драйвер с минимальными настройками
        try:
            options = Options()
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--no-sandbox")

            chrome_bin = os.environ.get("CHROME_BIN")
            if chrome_bin:
                options.binary_location = chrome_bin

            if headless:
                options.add_argument("--headless=new")

            chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
            if chromedriver_path:
                service = Service(chromedriver_path)
            else:
                service = Service(ChromeDriverManager().install())

            driver = webdriver.Chrome(service=service, options=options)
            return driver
        except Exception as e2:
            print(f"Критическая ошибка: {e2}")
            raise