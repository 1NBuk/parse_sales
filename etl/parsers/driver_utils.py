import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import undetected_chromedriver as uc


def create_driver(use_uc=False):
    """
    Создает драйвер для работы.

    Args:
        use_uc (bool): Использовать undetected_chromedriver (для сложных сайтов)
    """
    options = Options()

    # Проверяем, запущено ли на GitHub Actions
    is_ci = os.getenv('GITHUB_ACTIONS') == 'true'

    if is_ci:
        options.add_argument("--headless=new")  # Headless режим для CI
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.binary_location = "/usr/bin/google-chrome-stable"
    else:
        # Для локального запуска
        options.add_argument("--start-maximized")

    options.add_argument("--disable-blink-features=AutomationControlled")

    if use_uc:
        # Используем undetected_chromedriver
        return uc.Chrome(
            options=options,
            version_main=None,  # Автоопределение версии
            headless=is_ci,  # Headless только на CI
        )
    else:
        # Используем обычный Selenium
        service = Service()
        return webdriver.Chrome(service=service, options=options)