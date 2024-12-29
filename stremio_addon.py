from flask import Flask, request, Response, jsonify
from flask_cors import CORS
import json
import requests
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os
import pickle
import re
import urllib.parse
import logging
import traceback  # Add this at the top with other imports

app = Flask(__name__)
CORS(app)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Google Drive API Setup
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.pickle"

# TMDB API Key - Replace with your actual key
TMDB_API_KEY = "01a6b843945b5e879ffc2e08e97003e5"


class GDriveSearchStrategy:
    def __init__(self, drive_service):
        self.service = drive_service

    def search_files_by_name(self, query):
        try:
            # Comprehensive video file extensions
            video_extensions = [
                ".mp4",
                ".avi",
                ".mkv",
                ".mov",
                ".wmv",
                ".flv",
                ".webm",
                ".m4v",
                ".mpg",
                ".mpeg",
            ]

            # Video mime types
            video_mime_types = [
                "video/mp4",
                "video/x-msvideo",
                "video/quicktime",
                "video/x-matroska",
                "video/x-ms-wmv",
                "video/mpeg",
            ]

            # Create search variations with more aggressive matching
            search_variations = [
                query,  # Original query
                query.lower(),  # Lowercase
                query.upper(),  # Uppercase
                query.replace(" ", ""),  # No spaces
                query.replace(" ", "_"),  # Underscore instead of space
                f"*{query}*",  # Wildcard matching
            ]

            # Construct search queries
            search_queries = []
            for variation in search_variations:
                # Multiple search strategies
                strategies = [
                    f"name contains '{variation}'",  # Direct name match
                    f"fullText contains '{variation}'",  # Full text search
                    f"name contains ' {variation} '",  # With spaces around
                    f"name contains '({variation})'",  # In parentheses
                ]

                # Mime type and extension conditions
                mime_type_query = " or ".join(
                    [f"mimeType='{mime}'" for mime in video_mime_types]
                )
                ext_conditions = " or ".join(
                    [f"name contains '{ext}'" for ext in video_extensions]
                )

                # Combine conditions
                for strategy in strategies:
                    search_queries.append(
                        f"({strategy} and (({mime_type_query}) or ({ext_conditions})))"
                    )

            # Combine all search queries
            full_search_query = " or ".join(search_queries)

            logger.debug(f"Full Search Query: {full_search_query}")

            # Perform search with more comprehensive parameters
            results = (
                self.service.files()
                .list(
                    q=full_search_query,
                    fields="files(id,name,mimeType)",
                    pageSize=200,  # Increased page size
                    orderBy="modifiedTime desc",  # Sort by most recently modified
                )
                .execute()
            )

            files = results.get("files", [])

            logger.debug(f"Raw Files Found: {len(files)}")

            # Log file details for debugging
            for file in files:
                logger.debug(
                    f"File Name: {file.get('name', 'N/A')}, Mime Type: {file.get('mimeType', 'N/A')}"
                )

            # Process and clean results
            processed_files = []
            seen = set()

            for file in files:
                # Additional filtering for video files
                if any(
                    ext in file.get("name", "").lower()
                    for ext in [".mp4", ".mkv", ".avi", ".mov"]
                ):
                    if file["id"] not in seen:
                        seen.add(file["id"])

                        # Clean filename
                        clean_name = self.clean_filename(file["name"])

                        processed_files.append(
                            {
                                "id": file["id"],
                                "name": clean_name,
                                "original_name": file["name"],
                            }
                        )

            logger.debug(f"Processed Files: {len(processed_files)}")
            return processed_files

        except Exception as e:
            logger.error(f"Comprehensive Error searching files: {e}")
            # Log the full traceback
            import traceback

            logger.error(traceback.format_exc())
            return []

    def clean_filename(self, filename):
        # Remove file extension
        name = os.path.splitext(filename)[0]

        # Remove common noise patterns
        noise_patterns = [
            r"\[.*?\]",  # Remove content in square brackets
            r"\(.*?\)",  # Remove content in parentheses
            r"\d{3,4}p",  # Remove resolution
            r"BluRay|WEB-DL|HDRip|DVDRip|x264|HEVC",  # Remove quality indicators
        ]

        for pattern in noise_patterns:
            name = re.sub(pattern, "", name, flags=re.IGNORECASE)

        # Remove extra spaces
        name = re.sub(r"\s+", " ", name).strip()

        return name


def authenticate():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)
    return creds


def get_access_token():
    creds = None
    # Load the credentials from the pickle file
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

    # If there are no valid credentials, run the flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for future use
        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)
    return creds.token


# Authenticate and create drive service
creds = authenticate()
drive_service = build("drive", "v3", credentials=creds)
gdrive_search = GDriveSearchStrategy(drive_service)


# Manifest Endpoint
@app.route("/manifest.json", methods=["GET"])
def manifest():
    return jsonify(
        {
            "id": "com.han.gdriveaddon",
            "version": "1.0.0",
            "name": "Google Drive Addon",
            "description": "Stream movies/series from Google Drive, Developed by Han",
            "types": ["movie"],
            "catalogs": [
                {
                    "type": "movie",
                    "id": "gdrive_movies",
                    "name": "Google Drive Movies",
                    "extra": [
                        {"name": "search", "isRequired": False},
                    ],
                }
            ],
            "resources": ["catalog", "stream"],
        }
    )


@app.route("/proxy/<file_id>", methods=["GET"])
def proxy_request(file_id):
    try:
        access_token = get_access_token()
        
        # Get file metadata first
        file_metadata = (
            drive_service.files()
            .get(fileId=file_id, fields="size,mimeType,name")
            .execute()
        )
        
        file_size = int(file_metadata.get("size", 0))
        original_mime = file_metadata.get("mimeType", "")
        file_name = file_metadata.get("name", "").lower()

        # Better MIME type handling for MKV files
        if file_name.endswith('.mkv'):
            mime_type = 'video/x-matroska'
        elif original_mime.startswith('video/'):
            mime_type = original_mime
        else:
            mime_type = 'video/mp4'  # fallback

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept-Ranges": "bytes",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "Range, Accept-Ranges, Content-Type, Origin",
            "Content-Type": mime_type,
            # Add additional headers for better codec support
            "Content-Disposition": f'inline; filename="{file_metadata.get("name")}"',
            "X-Content-Type-Options": "nosniff"
        }

        # Get the Range header from the incoming request
        range_header = request.headers.get("Range")
        
        if range_header:
            try:
                bytes_range = range_header.replace("bytes=", "").split("-")
                start_byte = int(bytes_range[0] if bytes_range[0] else 0)
                # Use smaller chunk size for better streaming
                chunk_size = 5 * 1024 * 1024  # 5MB chunks
                end_byte = int(bytes_range[1]) if bytes_range[1] else min(start_byte + chunk_size, file_size - 1)
            except (ValueError, IndexError) as e:
                logger.error(f"Invalid range header: {range_header}, error: {e}")
                start_byte = 0
                end_byte = min(5 * 1024 * 1024, file_size - 1)

            headers.update({
                "Content-Range": f"bytes {start_byte}-{end_byte}/{file_size}",
                "Content-Length": str(end_byte - start_byte + 1),
            })

            response = requests.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Range": f"bytes={start_byte}-{end_byte}",
                },
                stream=True
            )

            return Response(
                response.iter_content(chunk_size=8192),
                status=206,
                headers=headers,
                direct_passthrough=True
            )
        else:
            headers.update({
                "Content-Length": str(file_size),
            })

            response = requests.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media",
                headers={"Authorization": f"Bearer {access_token}"},
                stream=True
            )

            return Response(
                response.iter_content(chunk_size=8192),
                status=200,
                headers=headers,
                direct_passthrough=True
            )

    except Exception as e:
        logger.error(f"Proxy Error: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": "Failed to fetch file"}), 500


# Catalog Endpoint
@app.route("/catalog/movie/gdrive_movies.json", methods=["GET"])
def catalog():
    # Extract search parameter
    search = request.args.get("search", "").strip()

    logger.debug(f"Raw Search Parameter: {search}")

    # If no search term, return empty list
    if not search:
        return jsonify({"metas": []})

    # Decode URL-encoded search term
    try:
        search = urllib.parse.unquote(search)
    except Exception as e:
        logger.error(f"Error decoding search term: {e}")
        return jsonify({"metas": []})

    logger.debug(f"Processed Search Term: {search}")

    # Search files directly by name
    files = gdrive_search.search_files_by_name(search)

    # Prepare metas for Stremio
    metas = []
    for file in files:
        metas.append(
            {
                "id": f"gdrive_{file['id']}",
                "type": "movie",
                "name": file["name"],
                "poster": f"https://via.placeholder.com/150?text={urllib.parse.quote(file['name'])}",
                "original_name": file["original_name"],
            }
        )

    logger.debug(f"Final M etas: {metas}")
    return jsonify({"metas": metas})


def construct_streaming_url(file_id, access_token):
    return f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&access_token={access_token}"


# Stream Endpoint
@app.route("/stream/movie/<string:id>.json", methods=["GET", "OPTIONS"])
def stream(id):
    if request.method == "OPTIONS":
        response = jsonify({"streams": []})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add(
            "Access-Control-Allow-Headers", "Content-Type,Authorization"
        )
        response.headers.add("Access-Control-Allow-Methods", "GET,OPTIONS")
        return response

    try:
        logger.debug(f"Stream Request - ID: {id}")

        # If it's an IMDB ID, search the movie
        if id.startswith("tt"):
            movie_details = get_movie_details(id)
            search_query = movie_details.get("title", "")
            if not search_query:
                logger.debug(f"No movie title found for IMDB ID: {id}")
                return jsonify({"streams": []})
            files = gdrive_search.search_files_by_name(search_query)

        else:
            # Handle Google Drive file ID
            file_id = id.replace("gdrive_", "")
            try:
                file = drive_service.files().get(fileId=file_id).execute()
                files = [
                    {
                        "id": file_id,
                        "name": file.get("name", "Movie"),
                        "original_name": file.get("name", "Movie"),
                    }
                ]
            except Exception as e:
                logger.error(f"Error fetching file details: {e}")
                return jsonify({"streams": []})

        # Ensure the file is accessible
        for file in files:
            if not check_file_accessibility(file["id"]):
                return jsonify({"streams": []})

        # Generate streaming URLs
        streams = []
        for file in files:
            # Access token needs to be dynamically handled, retrieved from your authenticated session
            access_token = get_access_token()

            # Construct the streaming URL
            proxy_url = construct_streaming_url(file["id"], access_token)

            # Append to streams
            streams.append(
                {
                    "url": f"http://localhost:7000/proxy/{file['id']}",
                    "title": f"Google Drive: {file['name']}",
                    "type": "movie",
                }
            )

        logger.debug(f"Generated Streams: {streams}")
        return jsonify({"streams": streams})

    except Exception as e:
        logger.error(f"Error in stream endpoint: {e}")
        return jsonify({"streams": []})


# Helper function to check file accessibility


def check_file_accessibility(file_id):
    try:
        # Attempt to get file metadata
        file_metadata = (
            drive_service.files()
            .get(fileId=file_id, fields="id,name,mimeType,webContentLink")
            .execute()
        )

        # Create public permission if not already public
        permissions = drive_service.permissions().list(fileId=file_id).execute()
        if not any(
            perm["type"] == "anyone" for perm in permissions.get("permissions", [])
        ):
            drive_service.permissions().create(
                fileId=file_id, body={"type": "anyone", "role": "reader"}
            ).execute()

        # Log file details
        logger.debug("File Metadata:")
        logger.debug(f"ID: {file_metadata.get('id')}")
        logger.debug(f"Name: {file_metadata.get('name')}")
        logger.debug(f"Mime Type: {file_metadata.get('mimeType')}")
        logger.debug(f"Web Content Link: {file_metadata.get('webContentLink')}")

        return True

    except Exception as e:
        logger.error(f"File accessibility check failed: {e}")
        return False


# Add a helper function to verify and validate streaming URLs


def validate_streaming_url(url):

    try:

        # Send a HEAD request to check URL accessibility

        response = requests.head(url, allow_redirects=True, timeout=10)

        # Check if the URL is accessible and likely a video

        return (
            response.status_code == 200
            and "video" in response.headers.get("Content-Type", "").lower()
        )

    except Exception as e:

        logger.error(f"URL validation error: {e}")

        return False


def debug_url_accessibility(url):

    try:

        # Detailed URL accessibility check

        response = requests.get(url, stream=True, timeout=10)

        logger.debug(f"URL: {url}")

        logger.debug(f"Status Code: {response.status_code}")

        logger.debug(f"Headers: {response.headers}")

        # Check content type

        content_type = response.headers.get("Content-Type", "")

        logger.debug(f"Content Type: {content_type}")

        # Check if it's a video

        return "video" in content_type.lower()

    except Exception as e:

        logger.error(f"URL accessibility error: {e}")

        return False


def get_movie_details(imdb_id):

    try:

        url = f"https://api.themoviedb.org/3/find/{imdb_id}"

        params = {"api_key": TMDB_API_KEY, "external_source": "imdb_id"}

        response = requests.get(url, params=params).json()

        if response.get("movie_results"):

            movie = response["movie_results"][0]

            return {
                "title": movie.get("title", ""),
                "year": movie.get("release_date", "")[:4],
                "poster": f"https://image.tmdb.org/t/p/w500{movie.get('poster_path', '')}",
            }

        logger.debug(f"No movie found for IMDB ID: {imdb_id}")

        return {}

    except Exception as e:

        logger.error(f"TMDB API Error: {e}")

        return {}


if __name__ == "__main__":
    app.run(port=7000, debug=True)
