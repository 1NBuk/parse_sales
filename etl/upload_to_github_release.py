import os
import requests
from datetime import datetime

# ===== НАСТРОЙКИ =====

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_OWNER = "1NBuk"
REPO_NAME = "parse_sales"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LOCAL_FILE = os.path.join(
    BASE_DIR, "..", "data", "processed", "clean_prices.csv"
)

# =====================


def get_headers():
    if not GITHUB_TOKEN:
        raise RuntimeError("Переменная окружения GITHUB_TOKEN не задана")

    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }


def create_release(tag, name):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases"

    payload = {
        "tag_name": tag,
        "name": name,
        "draft": False,
        "prerelease": False
    }

    response = requests.post(
        url,
        headers=get_headers(),
        json=payload
    )

    if response.status_code not in (201, 422):
        raise RuntimeError(
            f"Ошибка создания релиза: {response.status_code} {response.text}"
        )

    if response.status_code == 422:
        # релиз уже существует
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/tags/{tag}"
        response = requests.get(url, headers=get_headers())

    return response.json()


def upload_asset(upload_url, filepath, filename):
    upload_url = upload_url.split("{")[0]

    headers = get_headers()
    headers["Content-Type"] = "text/csv"

    with open(filepath, "rb") as f:
        response = requests.post(
            upload_url,
            headers=headers,
            params={"name": filename},
            data=f
        )

    if response.status_code != 201:
        raise RuntimeError(
            f"Ошибка загрузки файла: {response.status_code} {response.text}"
        )


def upload():
    if not os.path.exists(LOCAL_FILE):
        raise FileNotFoundError(f"Файл не найден: {LOCAL_FILE}")

    date_str = datetime.now().strftime("%Y-%m-%d")
    tag = f"prices-{date_str}"
    release_name = f"Цены продуктов — {date_str}"
    filename = f"clean_prices_{date_str}.csv"

    release = create_release(tag, release_name)
    upload_asset(release["upload_url"], LOCAL_FILE, filename)

    print(f"Файл {filename} загружен в GitHub Release {tag}")


if __name__ == "__main__":
    upload()
