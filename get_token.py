from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import json
import os

# Define the scope for accessing Google Drive files
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# Path to client_secret.json
CLIENT_SECRET_FILE = "credentials.json"
TOKEN_FILE = "token.json"


def get_access_token():
    creds = None

    # Check if token file already exists
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as token:
            creds = json.load(token)

    # Refresh expired token
    if creds and creds.get("refresh_token"):
        from google.oauth2.credentials import Credentials

        credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            with open(TOKEN_FILE, "w") as token:
                token.write(credentials.to_json())
            return credentials.token
        return credentials.token

    # Generate new token if it doesn't exist or expired
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    creds = flow.run_local_server(port=0)
    with open(TOKEN_FILE, "w") as token:
        token.write(creds.to_json())

    return creds.token


if __name__ == "__main__":
    token = get_access_token()
    print("Access Token:", token)
