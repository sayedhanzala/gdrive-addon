from flask import Flask, jsonify, request
from flask_cors import CORS
from auth import authenticate
from gdrive import GDriveSearchStrategy
from googleapiclient.discovery import build


app = Flask(__name__)
CORS(app)

# Authenticate with Google
creds = authenticate()
drive_service = build("drive", "v3", credentials=creds)
gdrive_search = GDriveSearchStrategy(drive_service)


# Manifest Endpoint
@app.route("/manifest.json", methods=["GET"])
def manifest():
    return jsonify(
        {
            "id": "com.gdrive.addon",
            "version": "1.0.0",
            "name": "Google Drive Addon",
            "description": "Stream videos from Google Drive",
            "types": ["movie"],
            "catalogs": [
                {"type": "movie", "id": "gdrive_movies", "name": "Google Drive Movies"}
            ],
            "resources": ["catalog", "stream"],
        }
    )


# Catalog Endpoint
@app.route("/catalog/movie/gdrive_movies.json", methods=["GET"])
def catalog():
    search = request.args.get("search", "").strip()

    if not search:
        return jsonify({"metas": []})

    # Search files based on query
    files = gdrive_search.search_files_by_name(search)

    metas = []
    for file in files:
        metas.append(
            {
                "id": f"gdrive_{file['id']}",
                "type": "movie",
                "name": file["name"],
                "poster": f"https://via.placeholder.com/150?text={file['name']}",
                "original_name": file["name"],
            }
        )

    return jsonify({"metas": metas})


# Stream Endpoint
@app.route("/stream/movie/<string:id>.json", methods=["GET"])
def stream(id):
    file_id = id.replace("gdrive_", "")
    try:
        file = drive_service.files().get(fileId=file_id).execute()
        file_name = file.get("name", "Unknown")

        # Create a streaming URL
        access_token = "your_access_token"  # You need to implement token generation
        stream_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        return jsonify(
            {"streams": [{"url": stream_url, "title": file_name, "type": "movie"}]}
        )
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"streams": []})


if __name__ == "__main__":
    app.run(debug=True, port=7000)
