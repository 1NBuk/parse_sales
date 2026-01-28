import os
from datetime import datetime
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")

LOCAL_FILE = os.path.join(
    BASE_DIR, "..", "data", "processed", "clean_prices.csv"
)

FOLDER_ID = "16ytw-ZV05jveJksJjY4bwfuoK_OxXiAa"


def get_credentials():
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(
            TOKEN_FILE, SCOPES
        )

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_FILE, SCOPES
        )
        creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return creds


def upload():
    if not os.path.exists(LOCAL_FILE):
        raise FileNotFoundError(f"Файл не найден: {LOCAL_FILE}")

    creds = get_credentials()
    service = build("drive", "v3", credentials=creds)

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"clean_prices_{date_str}.csv"

    file_metadata = {
        "name": filename,
        "parents": [FOLDER_ID]
    }

    media = MediaFileUpload(
        LOCAL_FILE,
        mimetype="text/csv"
    )

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()

    print(f"Файл загружен, id={file['id']}")


if __name__ == "__main__":
    upload()