import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import undetected_chromedriver as uc


def create_driver(use_uc=False):
    options = Options()
    is_ci = os.getenv('GITHUB_ACTIONS') == 'true'

    if is_ci:
        # Добавить больше опций для стабильности
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--disable-extensions")
        options.add_argument("--proxy-server='direct://'")
        options.add_argument("--proxy-bypass-list=*")
        options.add_argument("--disable-accelerated-2d-canvas")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Экспериментальные опции для избежания детекта
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_experimental_option("prefs", {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
        })

        options.binary_location = "/usr/bin/google-chrome-stable"
    else:
        options.add_argument("--start-maximized")

    if use_uc:
        try:
            # Для UC драйвера
            driver = uc.Chrome(
                options=options,
                version_main=None,
                headless=is_ci,
                service_args=['--verbose', '--log-path=/tmp/chromedriver.log']
            )
        except Exception as e:
            print(f"UC Chrome failed: {e}, falling back to regular Chrome")
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            service = Service(log_path='/tmp/chromedriver.log')
            driver = webdriver.Chrome(service=service, options=options)
    else:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        service = Service(log_path='/tmp/chromedriver.log')
        driver = webdriver.Chrome(service=service, options=options)

    # Увеличить таймауты для CI
    if is_ci:
        driver.set_page_load_timeout(90)
        driver.implicitly_wait(20)
    else:
        driver.set_page_load_timeout(60)
        driver.implicitly_wait(10)

    return driver
