"""
Shared helpers: background cleanup tasks, URL downloading, and file-type
detection. Extracted from api_server.py so multiple routers can reuse them.
"""

import os
import shutil
import zipfile
import asyncio

import requests

from src.config import file_registry


# ---------------------------------------------------------------------------
# Background cleanup tasks
# ---------------------------------------------------------------------------
# Note: the original module defined two different functions both named
# `cleanup_file_after_delay`, so the first (registry-aware) one was silently
# shadowed. They are split here into two clearly-named helpers.

async def cleanup_registered_file(file_id: str, filepath: str, delay: int = 3600):
    """Remove a generated file and its registry entry after `delay` seconds."""
    await asyncio.sleep(delay)
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"Cleaned up: {filepath}")
        if file_id in file_registry:
            del file_registry[file_id]
            print(f"Removed file {file_id} from registry")
    except Exception as e:
        print(f"Error cleaning up {filepath}: {e}")


async def cleanup_file(file_path: str, delay: int = 60):
    """Remove a standalone temp file after `delay` seconds."""
    await asyncio.sleep(delay)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Cleaned up file: {file_path}")
    except Exception as e:
        print(f"Error cleaning up file {file_path}: {e}")


async def cleanup_directory(directory: str, delay: int = 3600):
    """Remove a directory tree after `delay` seconds."""
    await asyncio.sleep(delay)
    try:
        if os.path.exists(directory):
            shutil.rmtree(directory)
            print(f"Cleaned up directory: {directory}")
    except Exception as e:
        print(f"Error cleaning up directory {directory}: {e}")


# ---------------------------------------------------------------------------
# Downloading
# ---------------------------------------------------------------------------

def download_url_to_file(url: str, dest_path: str, timeout: int = 30) -> int:
    """
    Stream a URL to `dest_path`. Returns the number of bytes written.

    Raises requests.RequestException on any HTTP/transport failure so callers
    can distinguish download errors (400) from processing errors (500).
    """
    response = requests.get(url, timeout=timeout, stream=True)
    response.raise_for_status()

    bytes_written = 0
    with open(dest_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            bytes_written += len(chunk)
            f.write(chunk)
    return bytes_written


# ---------------------------------------------------------------------------
# File-type detection
# ---------------------------------------------------------------------------

class DetectedType:
    """Result of classifying a downloaded file."""

    def __init__(self, is_pdf, is_spreadsheet, is_word, is_image,
                 source_type, file_extension):
        self.is_pdf = is_pdf
        self.is_spreadsheet = is_spreadsheet
        self.is_word = is_word
        self.is_image = is_image
        self.source_type = source_type
        self.file_extension = file_extension


def detect_document_type(file_path: str, detected_mime: str) -> DetectedType:
    """
    Classify a downloaded file from its magic MIME plus, for OOXML, a peek
    inside the zip container.

    magic is unreliable for OOXML — depending on the libmagic build a .docx or
    .xlsx can come back as application/zip, octet-stream, or CDFV2. So unless
    it's already clearly a PDF/image, we peek inside: every OOXML file is a zip,
    and the marker part tells us which kind. Non-zip files raise BadZipFile and
    fall through to the image path unchanged.
    """
    mime_lower = detected_mime.lower()
    is_pdf = "pdf" in mime_lower
    is_spreadsheet = "spreadsheet" in mime_lower or "excel" in mime_lower
    is_word = "wordprocessing" in mime_lower or "msword" in mime_lower
    is_image = "image" in mime_lower

    if not (is_pdf or is_image or is_spreadsheet or is_word):
        try:
            with zipfile.ZipFile(file_path) as zf:
                names = zf.namelist()
            is_spreadsheet = any(n.startswith("xl/workbook.xml") for n in names)
            is_word = any(n.startswith("word/document.xml") for n in names)
        except zipfile.BadZipFile:
            print("Not a zip/OOXML container")
        except Exception as zip_error:
            print(f"Zip inspection failed: {zip_error}")

    if is_pdf:
        return DetectedType(True, False, False, False, "pdf", "pdf")
    if is_spreadsheet:
        return DetectedType(False, True, False, False, "spreadsheet", "xlsx")
    if is_word:
        return DetectedType(False, False, True, False, "document", "docx")

    # Image (or unknown → treated as image, matching prior behavior).
    if "jpeg" in mime_lower or "jpg" in mime_lower:
        ext = "jpg"
    elif "png" in mime_lower:
        ext = "png"
    elif "gif" in mime_lower:
        ext = "gif"
    elif "webp" in mime_lower:
        ext = "webp"
    else:
        ext = "jpg"  # default
    return DetectedType(False, False, False, True, "image", ext)
