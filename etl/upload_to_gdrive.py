import os
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --------------------------
# Настройки
# --------------------------
# Папка на Google Drive, куда загружать файлы
FOLDER_ID = "16ytw-ZV05jveJksJjY4bwfuoK_OxXiAa"

# Локальный файл, который нужно загрузить
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_FILE = os.path.join(BASE_DIR, "..", "data", "processed", "clean_prices.csv")
SERVICE_ACCOUNT_FILE = r"C:\Users\User\PycharmProjects\parse_sales\etl\gdrive_key.json"
SCOPES = ["https://www.googleapis.com/auth/drive"]

# --------------------------
# Проверка наличия файла
# --------------------------
if not os.path.exists(LOCAL_FILE):
    raise FileNotFoundError(f"Файл не найден: {LOCAL_FILE}")

# --------------------------
# Авторизация через сервисный аккаунт
# --------------------------
creds = Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=SCOPES
)

service = build("drive", "v3", credentials=creds)

# --------------------------
# Подготовка имени файла с датой
# --------------------------
date_str = datetime.now().strftime("%Y-%m-%d")
filename = f"clean_prices_{date_str}.csv"

# --------------------------
# Метаданные файла
# --------------------------
file_metadata = {
    "name": filename,
    "parents": [FOLDER_ID]
}

media = MediaFileUpload(LOCAL_FILE, mimetype="text/csv")

# --------------------------
# Загрузка файла
# --------------------------
file = service.files().create(
    body=file_metadata,
    media_body=media,
    fields="id"
).execute()

print(f"Файл загружен в Google Drive, id={file['id']}")