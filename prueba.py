from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly"
]

credentials = service_account.Credentials.from_service_account_file(
    "direct-glider-507615-h0-fffe84109ed5.json",
    scopes=SCOPES
)

drive = build(
    "drive",
    "v3",
    credentials=credentials
)

FILE_ID = "1ubI7JOJ4Qj8eghNEk8zZmHr8sg8we5EjAQkgTsyItzc"

archivo = drive.files().get(
    fileId=FILE_ID,
    fields="id,name,mimeType"
).execute()

print("Conexión correcta")
print("Archivo:", archivo["name"])
print("ID:", archivo["id"])