import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import undetected_chromedriver as uc


def create_driver(use_uc=False):
    from selenium.webdriver.chrome.options import Options
    import undetected_chromedriver as uc
    import os
    options = Options()
    is_ci = os.getenv('GITHUB_ACTIONS') == 'true'

    if is_ci:
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
            (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
        options.binary_location = "/usr/bin/google-chrome-stable"
    else:
        options.add_argument("--start-maximized")

    if use_uc:
        return uc.Chrome(options=options, version_main=None, headless=is_ci)
    else:
        from selenium.webdriver.chrome.service import Service
        from selenium import webdriver
        service = Service()
        return webdriver.Chrome(service=service, options=options)
