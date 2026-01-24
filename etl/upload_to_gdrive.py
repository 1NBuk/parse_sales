import os
import json
from pathlib import Path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "processed" / "clean_prices.csv"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
FOLDER_ID = "PASTE_YOUR_FOLDER_ID"

def get_service():
    if "GDRIVE_KEY_JSON" in os.environ:
        info = json.loads(os.environ["GDRIVE_KEY_JSON"])
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file(
            BASE_DIR / "etl" / "gdrive_key.json",
            scopes=SCOPES
        )
    return build("drive", "v3", credentials=creds)

def upload():
    if not DATA_FILE.exists():
        raise FileNotFoundError(DATA_FILE)

    service = get_service()

    media = MediaFileUpload(
        DATA_FILE,
        mimetype="text/csv",
        resumable=True
    )

    service.files().create(
        body={
            "name": DATA_FILE.name,
            "parents": [FOLDER_ID]
        },
        media_body=media,
        fields="id"
    ).execute()

if __name__ == "__main__":
    upload()
