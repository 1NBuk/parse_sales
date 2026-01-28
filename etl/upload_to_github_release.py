import os
import requests
from datetime import datetime

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_OWNER = "1NBuk"
REPO_NAME = "parse_sales"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_FILE = os.path.join(BASE_DIR, "..", "data", "processed", "clean_prices.csv")


def get_headers():
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN не задан")
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }


def create_release(tag, name):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases"
    payload = {"tag_name": tag, "name": name, "draft": False, "prerelease": False}

    response = requests.post(url, headers=get_headers(), json=payload)
    if response.status_code == 201:
        return response.json()
    if response.status_code == 422:
        # релиз уже есть
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/tags/{tag}"
        response = requests.get(url, headers=get_headers())
        return response.json()
    raise RuntimeError(f"Ошибка создания релиза: {response.status_code} {response.text}")


def delete_existing_asset(upload_url, filename):
    """Удаляет ассет с GitHub Release, если он существует"""
    base_url = upload_url.split("{")[0]
    response = requests.get(base_url, headers=get_headers())
    if response.status_code != 200:
        print(f"Не удалось получить список ассетов: {response.text}")
        return
    for asset in response.json():
        if asset["name"] == filename:
            del_url = asset["url"]
            del_response = requests.delete(del_url, headers=get_headers())
            if del_response.status_code == 204:
                print(f"Старый файл {filename} удалён")
            else:
                print(f"Не удалось удалить {filename}: {del_response.text}")


def upload_asset(upload_url, filepath, filename):
    delete_existing_asset(upload_url, filename)

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
        raise RuntimeError(f"Ошибка загрузки файла: {response.status_code} {response.text}")


def upload():
    if not os.path.exists(LOCAL_FILE):
        print(f"Файл не найден: {LOCAL_FILE}, пропуск загрузки")
        return

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    tag = f"prices-{date_str}"
    release_name = f"Цены продуктов — {date_str}"
    filename = f"clean_prices_{date_str}.csv"

    release = create_release(tag, release_name)
    upload_asset(release["upload_url"], LOCAL_FILE, filename)

    print(f"Файл {filename} загружен в GitHub Release {tag}")


if __name__ == "__main__":
    upload()
