"""
Shared configuration and process-wide state for the Sekure-ID API.

Keeping directories, the base domain, and the in-memory file registry in one
place lets every router import them without reaching back into api_server.py
(which would create a circular import).
"""

import os
from typing import Dict

# Public base URL used when building absolute file links in responses.
BASE_DOMAIN = os.getenv("BASE_DOMAIN", "http://localhost:8000")

# Working directories (created eagerly so every code path can assume they exist).
TEMP_DIR = os.path.join(os.getcwd(), "temp_reports")
DOWNLOADS_DIR = os.path.join(os.getcwd(), "downloads")
PDF_TEMP_DIR = os.path.join(os.getcwd(), "temp_pdf")
EXTRACT_TEMP_DIR = os.path.join(os.getcwd(), "temp_extract")
TRANSCRIBE_TEMP_DIR = os.path.join(os.getcwd(), "temp_transcribe")

for _directory in (TEMP_DIR, DOWNLOADS_DIR, PDF_TEMP_DIR, EXTRACT_TEMP_DIR,
                   TRANSCRIBE_TEMP_DIR):
    os.makedirs(_directory, exist_ok=True)

# Metadata for generated report files, keyed by file_id.
# In-memory only; a production deployment could back this with Redis.
file_registry: Dict[str, dict] = {}
