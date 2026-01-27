import os
import requests
from datetime import datetime

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_OWNER = "1NBuk"
REPO_NAME = "parse_sales"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LOCAL_FILE = os.path.join(
    BASE_DIR, "..", "data", "processed", "clean_prices.csv"
)


def get_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
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

    response = requests.post(url, headers=get_headers(), json=payload)

    if response.status_code == 201:
        return response.json()

    if response.status_code == 422:
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/tags/{tag}"
        return requests.get(url, headers=get_headers()).json()

    raise RuntimeError(response.text)


def delete_asset_if_exists(release_id, filename):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/{release_id}/assets"
    assets = requests.get(url, headers=get_headers()).json()

    for asset in assets:
        if asset["name"] == filename:
            requests.delete(asset["url"], headers=get_headers())


def upload_asset(upload_url, filepath, filename):
    upload_url = upload_url.split("{")[0]

    headers = {
        **get_headers(),
        "Content-Type": "text/csv"
    }

    with open(filepath, "rb") as f:
        response = requests.post(
            upload_url,
            headers=headers,
            params={"name": filename},
            data=f
        )

    if response.status_code != 201:
        raise RuntimeError(response.text)


def upload():
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    tag = f"prices-{date_str}"
    filename = f"clean_prices_{date_str}.csv"

    release = create_release(tag, f"Цены продуктов — {date_str}")
    delete_asset_if_exists(release["id"], filename)
    upload_asset(release["upload_url"], LOCAL_FILE, filename)

    print(f"✔ Загружен {filename}")
