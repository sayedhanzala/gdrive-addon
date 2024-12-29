from googleapiclient.discovery import build
import os
import re


class GDriveSearchStrategy:
    def __init__(self, drive_service):
        self.service = drive_service

    def search_files_by_name(self, query):
        try:
            video_extensions = [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv"]
            video_mime_types = [
                "video/mp4",
                "video/x-msvideo",
                "video/quicktime",
                "video/x-matroska",
                "video/x-ms-wmv",
            ]

            search_query = f"name contains '{query}' and ("
            search_query += " or ".join(
                [f"mimeType='{mime}'" for mime in video_mime_types]
            )
            search_query += " or " + " or ".join(
                [f"name contains '{ext}'" for ext in video_extensions]
            )
            search_query += ")"

            results = (
                self.service.files()
                .list(
                    q=search_query,
                    fields="files(id,name,mimeType)",
                    pageSize=10,
                    orderBy="modifiedTime desc",
                )
                .execute()
            )

            files = results.get("files", [])
            return files
        except Exception as e:
            print(f"Error searching files: {e}")
            return []
