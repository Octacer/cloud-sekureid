"""
FastAPI Server for Sekure-ID Report Generation

Thin entrypoint: wires together the routers defined under src/. Application
logic lives in src/routers/*, shared state in src/config.py, and reusable
helpers in src/helpers.py.
"""

import os
import shutil
from datetime import datetime

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.config import TEMP_DIR, DOWNLOADS_DIR
from src.routers import reports, debug, pdf, extract, images, vollna, serp, transcribe

app = FastAPI(
    title="Octacer Internal Tooling Platform",
    description=(
        "Octacer's internal tooling platform — a single API bundling attendance "
        "report generation, document & text extraction (OCR), image processing, "
        "audio/video transcription, and web automation."
    ),
    version="1.0.0"
)

# Mount downloads directory for static file serving
app.mount("/files", StaticFiles(directory=DOWNLOADS_DIR), name="files")

# Register routers
app.include_router(reports.router)
app.include_router(debug.router)
app.include_router(pdf.router)
app.include_router(extract.router)
app.include_router(images.router)
app.include_router(vollna.router)
app.include_router(serp.router)
app.include_router(transcribe.router)


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Octacer Internal Tooling Platform",
        "version": "1.0.0",
        "endpoints": {
            "POST /generate-report": "Generate report and return download URL (JSON)",
            "POST /generate-report-direct": "Generate and directly download Excel file",
            "GET /get-report-default": "Generate today's report with defaults (JSON with URL)",
            "GET /get-report-default-direct": "Generate and directly download today's report",
            "GET /download/{file_id}": "Download a generated report by file ID",
            "POST /pdf-to-png": "Convert PDF to PNG images (provide public PDF URL)",
            "POST /extract-text": "Extract text from image/PDF/spreadsheet/Word (provide public URL)",
            "POST /extract-text-file": "Extract text from an uploaded file (multipart) — image/PDF/spreadsheet/Word, no URL needed",
            "POST /resize-image": "Resize and/or convert an image (PNG/JPG/HEIC/WEBP → JPEG/PNG/WEBP)",
            "GET /get-vollna-cookies": "Get cookies from Vollna website after login",
            "POST /scrape-google-serp": "Scrape Google search results for a query",
            "POST /transcribe": "Transcribe an audio/video file to text (provide public URL)",
            "GET /debug": "List all debug sessions (when errors occur)",
            "GET /debug/{debug_id}": "Get debug files for a specific debug session",
            "GET /health": "Health check endpoint"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on server shutdown"""
    print("Cleaning up temporary files...")
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)


if __name__ == "__main__":
    import uvicorn

    print("Starting Sekure-ID Report Generator API...")
    print("API will be available at: http://localhost:8000")
    print("API documentation at: http://localhost:8000/docs")

    # Increase timeout to 5 minutes for long-running automation
    uvicorn.run(app, host="0.0.0.0", port=8000, timeout_keep_alive=600)
