import os
import pickle
import requests
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.auth.transport.requests import Request

# Define the scope and token file
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
CREDENTIALS_FILE = "credentials.json"  # Your client_secret.json file
TOKEN_FILE = "token.pickle"


def authenticate():
    """Authenticate the user and return the Google Drive service."""
    creds = None
    # Check if the token.pickle file exists for stored credentials
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

    # If no valid credentials are available, prompt the user to log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)

    return creds


def get_drive_service():
    """Create a Google Drive service."""
    creds = authenticate()
    return build("drive", "v3", credentials=creds)


def get_file_url(file_id):
    """Get the streaming URL for the file."""
    try:
        drive_service = get_drive_service()

        # Get file details
        file = (
            drive_service.files()
            .get(fileId=file_id, fields="id,name,mimeType")
            .execute()
        )

        # Create the public streaming link
        file_url = f"https://drive.google.com/uc?export=stream&id={file['id']}"
        print(f"Streaming URL: {file_url}")
        return file_url

    except Exception as e:
        print(f"Error fetching file URL: {e}")
        return None


def main():
    # Example file ID (replace with actual file ID)
    file_id = "1gUIOC-CcInIPqi2hOQG3H7fkgaTMzR7J"  # Replace with your file's Google Drive ID
    streaming_url = get_file_url(file_id)
    if streaming_url:
        print(f"Access the video stream here: {streaming_url}")
    else:
        print("Could not generate streaming URL.")


if __name__ == "__main__":
    main()
