# driver_utils.py
import random
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def create_driver(use_uc=False, headless=False, disable_bot_detection=True, random_user_agent=False):
    """
    Создает драйвер с настройками для обхода обнаружения и поддержкой прокси
    """
    try:
        proxy_url = os.getenv("PROXY_URL")
        if proxy_url and not proxy_url.startswith("http"):
            proxy_url = f"http://{proxy_url}"
        if proxy_url:
            print(f"Используется прокси: {proxy_url}")

        if use_uc:
            # Используем undetected_chromedriver
            import undetected_chromedriver as uc
            print("Используется undetected_chromedriver")

            # Настройки для UC
            options = uc.ChromeOptions()

            # Базовые настройки
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-gpu")
            options.add_argument("start-maximized")
            options.add_argument("--disable-infobars")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-browser-side-navigation")

            # Случайный User-Agent
            if random_user_agent:
                user_agents = [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ]
                options.add_argument(f"user-agent={random.choice(user_agents)}")

            # 🔧 ПРОКСИ ДЛЯ UC
            if proxy_url:
                options.add_argument(f'--proxy-server={proxy_url}')

            # Режим headless
            if headless:
                options.add_argument("--headless")

            # Инициализация UC
            driver = uc.Chrome(
                options=options,
                use_subprocess=True,
                driver_executable_path=None,
                browser_executable_path=None,
                version_main=None,
                suppress_welcome=True
            )

        else:
            # Используем обычный Selenium Chrome
            print("Используется обычный Selenium Chrome")

            options = Options()

            # Базовые настройки для обхода обнаружения
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)

            # Дополнительные настройки
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-gpu")
            options.add_argument("start-maximized")
            options.add_argument("--disable-infobars")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-browser-side-navigation")

            # Случайный User-Agent
            if random_user_agent:
                user_agents = [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ]
                options.add_argument(f"user-agent={random.choice(user_agents)}")

            # 🔧 ПРОКСИ ДЛЯ ОБЫЧНОГО CHROME
            if proxy_url:
                options.add_argument(f'--proxy-server={proxy_url}')

            # Режим headless
            if headless:
                options.add_argument('--headless')

            # Инициализация драйвера
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

        print("Драйвер успешно создан")
        return driver

    except Exception as e:
        print(f"Ошибка при создании драйвера: {e}")

        # Попытка создать драйвер с минимальными настройками
        try:
            options = Options()
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")

            # Минимальный прокси
            proxy_url = os.getenv('PROXY_URL')
            if proxy_url:
                options.add_argument(f'--proxy-server={proxy_url}')

            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            print("Драйвер создан с минимальными настройками")
            return driver
        except Exception as e2:
            print(f"Критическая ошибка: {e2}")
            raise