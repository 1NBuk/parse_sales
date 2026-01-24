import os
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/drive.file']
LOCAL_FILE = os.path.join("data", "processed", "clean_prices.csv")
FOLDER_ID = "16ytw-ZV05jveJksJjY4bwfuoK_OxXiAa"

def upload():
    flow = InstalledAppFlow.from_client_secrets_file('etl/client_secret.json', SCOPES)
    creds = flow.run_local_server(port=0)
    service = build('drive', 'v3', credentials=creds)

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"clean_prices_{date_str}.csv"

    file_metadata = {
        'name': filename,
        'parents': [FOLDER_ID]
    }

    media = MediaFileUpload(LOCAL_FILE, mimetype='text/csv')
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    print(f"{filename} uploaded to Google Drive folder {FOLDER_ID}")

if __name__ == "__main__":
    upload()
