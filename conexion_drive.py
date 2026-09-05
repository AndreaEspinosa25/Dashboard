import io
import os
import json
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

@st.cache_data(show_spinner="Descargando base de datos desde Google Drive...")
def descargar_excel_drive(file_id: str, credentials_path: str = None) -> bytes:
    """Descarga un archivo desde Google Drive y retorna sus bytes."""
    credentials = None
    
    env_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    
    if env_json:
        try:
            secret_dict = json.loads(env_json)
            credentials = service_account.Credentials.from_service_account_info(
                secret_dict, scopes=SCOPES
            )
        except json.JSONDecodeError:
            raise ValueError("La variable GOOGLE_SERVICE_ACCOUNT_JSON no contiene un JSON válido.")
    elif "gcp_service_account" in st.secrets:
        secret_dict = dict(st.secrets["gcp_service_account"])
        credentials = service_account.Credentials.from_service_account_info(
            secret_dict, scopes=SCOPES
        )
    elif credentials_path and os.path.exists(credentials_path):
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=SCOPES
        )
    else:
        raise FileNotFoundError("No se encontraron credenciales de Google Drive (ni en env, st.secrets, o archivo local).")
    
    drive = build("drive", "v3", credentials=credentials)
    
    file_metadata = drive.files().get(fileId=file_id, fields="mimeType").execute()
    if file_metadata.get("mimeType") == "application/vnd.google-apps.spreadsheet":
        request = drive.files().export_media(
            fileId=file_id, 
            mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        request = drive.files().get_media(fileId=file_id)
        
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    
    while done is False:
        status, done = downloader.next_chunk()
        
    return fh.getvalue()
