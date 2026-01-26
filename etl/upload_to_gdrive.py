# import os
# from google.oauth2 import service_account
# from googleapiclient.discovery import build
# from googleapiclient.http import MediaFileUpload
#
# SCOPES = ["https://www.googleapis.com/auth/drive.file"]
#
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
#
# LOCAL_FILE = os.path.join(
# BASE_DIR, "..", "data", "processed", "clean_prices.csv"
# )
#
# FOLDER_ID = "16ytw-ZV05jveJksJjY4bwfuoK_OxXiAa"
#
# SERVICE_ACCOUNT_FILE = os.path.join(
# BASE_DIR, "gdrive_key.json"
# )
#
#
# def get_credentials():
# # CI / GitHub Actions
# if "GCP_PROJECT_ID" in os.environ:
#     return service_account.Credentials.from_service_account_info(
#         {
#             "type": "service_account",
#             "project_id": os.environ["GCP_PROJECT_ID"],
#             "private_key_id": os.environ["GCP_PRIVATE_KEY_ID"],
#             "private_key": os.environ["GCP_PRIVATE_KEY"].replace("\\n", "\n"),
#             "client_email": os.environ["GCP_CLIENT_EMAIL"],
#             "client_id": os.environ["GCP_CLIENT_ID"],
#             "token_uri": "https://oauth2.googleapis.com/token",
#         },
#         scopes=SCOPES,
#     )
#
# # Локальный запуск
# if not os.path.exists(SERVICE_ACCOUNT_FILE):
#     raise FileNotFoundError(
#         f"Не найден файл service account: {SERVICE_ACCOUNT_FILE}"
#     )
#
# return service_account.Credentials.from_service_account_file(
#     SERVICE_ACCOUNT_FILE, scopes=SCOPES
# )
#
#
# def upload():
# if not os.path.exists(LOCAL_FILE):
#     raise FileNotFoundError(f"Файл не найден: {LOCAL_FILE}")
#
# creds = get_credentials()
# service = build("drive", "v3", credentials=creds)
#
# media = MediaFileUpload(LOCAL_FILE, mimetype="text/csv")
#
# file_metadata = {
#     "name": "clean_prices.csv",
#     "parents": [FOLDER_ID],
# }
#
# service.files().create(
#     body=file_metadata,
#     media_body=media,
#     fields="id",
# ).execute()
#
# print("Файл успешно загружен в Google Drive")
#
#
# if __name__ == "__main__":
# upload()
