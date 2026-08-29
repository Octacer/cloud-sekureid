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

# Google Gemini — used by /analyze-media for hosted transcription + speaker
# diarization + language identification. The key is a secret supplied at
# runtime (never committed); when unset, /analyze-media returns a clear error
# and every other endpoint keeps working.

# API Key
# AQ.Ab8RN6I_HEAOLG4ymp5fMx6Otyc3LuSwAL7L34LWS1ONjeQSCA
# Name
# cloud_sekureid
# Project name
# projects/579057686918
# Project number
# 579057686918

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6I_HEAOLG4ymp5fMx6Otyc3LuSwAL7L34LWS1ONjeQSCA")
GEMINI_TRANSCRIBE_MODEL = os.getenv("GEMINI_TRANSCRIBE_MODEL", "gemini-3.5-transcribe")

# Working directories (created eagerly so every code path can assume they exist).
TEMP_DIR = os.path.join(os.getcwd(), "temp_reports")
DOWNLOADS_DIR = os.path.join(os.getcwd(), "downloads")
PDF_TEMP_DIR = os.path.join(os.getcwd(), "temp_pdf")
EXTRACT_TEMP_DIR = os.path.join(os.getcwd(), "temp_extract")
TRANSCRIBE_TEMP_DIR = os.path.join(os.getcwd(), "temp_transcribe")
ANALYZE_TEMP_DIR = os.path.join(os.getcwd(), "temp_analyze")

for _directory in (TEMP_DIR, DOWNLOADS_DIR, PDF_TEMP_DIR, EXTRACT_TEMP_DIR,
                   TRANSCRIBE_TEMP_DIR, ANALYZE_TEMP_DIR):
    os.makedirs(_directory, exist_ok=True)

# Metadata for generated report files, keyed by file_id.
# In-memory only; a production deployment could back this with Redis.
file_registry: Dict[str, dict] = {}
