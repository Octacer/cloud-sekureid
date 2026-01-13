"""
FastAPI Server for Sekure-ID Report Generation
Exposes the automation as a REST API endpoint
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, List
import os
import shutil
from datetime import datetime, timedelta
import uuid
import asyncio
import requests
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
import magic
from sekureid_automation import SekureIDAutomation
from vollna_automation import VollnaAutomation

# Get base URL from environment variable
BASE_DOMAIN = os.getenv("BASE_DOMAIN", "http://localhost:8000")


app = FastAPI(
    title="Sekure-ID Report Generator API",
    description="API to generate and download attendance reports from Sekure-ID Cloud",
    version="1.0.0"
)


class ReportRequest(BaseModel):
    company_code: str = "85"
    username: str = "hisham.octacer"
    password: str = "P@ss1234"
    report_date: Optional[str] = None  # Format: YYYY-MM-DD


class ReportResponse(BaseModel):
    report_url: str
    file_id: str
    report_date: str
    generated_at: str
    expires_in: int  # seconds


class PdfToImageRequest(BaseModel):
    pdf_url: HttpUrl  # Publicly accessible PDF URL


class VollnaCookiesRequest(BaseModel):
    email: str
    password: str
    final_url: str = "https://www.vollna.com/dashboard/filter/22703"


class VollnaCookiesResponse(BaseModel):
    cookies: str
    cookie_count: int
    extracted_at: str


class ImageInfo(BaseModel):
    page: int
    url: str
    filename: str


class PdfToImageResponse(BaseModel):
    images: List[ImageInfo]
    total_pages: int
    conversion_id: str
    generated_at: str
    expires_in: int  # seconds


class TextExtractionRequest(BaseModel):
    url: HttpUrl  # Publicly accessible URL to image or PDF


class TextExtractionResponse(BaseModel):
    text: str
    language: str
    extraction_method: str
    source_type: str  # 'image' or 'pdf'
    total_pages: int  # For PDFs, number of pages processed
    extracted_at: str
    request_id: str


# Store for tracking download files
TEMP_DIR = os.path.join(os.getcwd(), "temp_reports")
DOWNLOADS_DIR = os.path.join(os.getcwd(), "downloads")
PDF_TEMP_DIR = os.path.join(os.getcwd(), "temp_pdf")
os.makedirs(PDF_TEMP_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Mount downloads directory for static file serving
app.mount("/files", StaticFiles(directory=DOWNLOADS_DIR), name="files")

# Store file metadata (in-memory, could be Redis in production)
file_registry: Dict[str, dict] = {}


async def cleanup_file_after_delay(file_id: str, filepath: str, delay: int = 3600):
    """Background task to cleanup file after delay (default 1 hour)"""
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


async def cleanup_directory_after_delay(directory: str, delay: int = 3600):
    """Background task to cleanup directory after delay (default 1 hour)"""
    await asyncio.sleep(delay)
    try:
        if os.path.exists(directory):
            shutil.rmtree(directory)
            print(f"Cleaned up directory: {directory}")
    except Exception as e:
        print(f"Error cleaning up directory {directory}: {e}")


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Sekure-ID Report Generator API",
        "version": "1.0.0",
        "endpoints": {
            "POST /generate-report": "Generate report and return download URL (JSON)",
            "POST /generate-report-direct": "Generate and directly download Excel file",
            "GET /get-report-default": "Generate today's report with defaults (JSON with URL)",
            "GET /get-report-default-direct": "Generate and directly download today's report",
            "GET /download/{file_id}": "Download a generated report by file ID",
            "POST /pdf-to-png": "Convert PDF to PNG images (provide public PDF URL)",
            "POST /extract-text": "Extract text from image or PDF using OCR (provide public URL)",
            "GET /get-vollna-cookies": "Get cookies from Vollna website after login",
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


def _generate_report_internal(
    company_code: str,
    username: str,
    password: str,
    report_date: Optional[str],
    background_tasks: BackgroundTasks,
    request: Request,
    return_json: bool = True
):
    """
    Internal function to generate report (shared by POST and GET endpoints)

    Args:
        return_json: If True, returns JSON with download URL. If False, returns file directly.
    """
    # Create unique download directory for this request
    request_id = str(uuid.uuid4())
    download_dir = os.path.join(TEMP_DIR, request_id)
    os.makedirs(download_dir, exist_ok=True)

    try:
        print(f"Processing report request: {request_id}")

        # Validate date format if provided
        if report_date:
            try:
                datetime.strptime(report_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date format. Use YYYY-MM-DD"
                )

        # Initialize automation
        automation = SekureIDAutomation(download_dir=download_dir)

        # Generate report
        excel_file = automation.generate_report(
            company_code=company_code,
            username=username,
            password=password,
            report_date=report_date
        )

        if not os.path.exists(excel_file):
            raise HTTPException(
                status_code=500,
                detail="Report generation failed - file not found"
            )

        # Generate a meaningful filename with timestamp prefix and GUID
        report_date_str = report_date or datetime.now().strftime("%Y-%m-%d")
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        file_id = str(uuid.uuid4())
        filename = f"{timestamp}_{file_id}.xlsx"

        # Move file to downloads directory
        final_path = os.path.join(DOWNLOADS_DIR, filename)
        shutil.move(excel_file, final_path)

        # Cleanup temp directory
        shutil.rmtree(download_dir, ignore_errors=True)

        if return_json:
            # Store file metadata
            generated_at = datetime.now()
            expires_at = generated_at + timedelta(hours=1)
            file_registry[file_id] = {
                "filepath": final_path,
                "report_date": report_date_str,
                "generated_at": generated_at,
                "expires_at": expires_at
            }

            # Schedule cleanup after 1 hour
            background_tasks.add_task(cleanup_file_after_delay, file_id, final_path, 3600)

            # Build download URL
            base_url = str(request.base_url).rstrip('/')
            download_url = f"{base_url}/download/{file_id}"

            # Return JSON response
            return ReportResponse(
                report_url=download_url,
                file_id=file_id,
                report_date=report_date_str,
                generated_at=generated_at.isoformat(),
                expires_in=3600  # 1 hour
            )
        else:
            # Return file directly (for backwards compatibility)
            display_filename = f"attendance_report_{report_date_str}.xlsx"

            # Schedule immediate cleanup after response
            background_tasks.add_task(asyncio.sleep, 5)  # Wait 5 seconds
            background_tasks.add_task(lambda: os.remove(final_path) if os.path.exists(final_path) else None)

            return FileResponse(
                final_path,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename=display_filename,
                headers={
                    "Content-Disposition": f"attachment; filename={display_filename}"
                }
            )

    except HTTPException:
        # Re-raise HTTP exceptions
        shutil.rmtree(download_dir, ignore_errors=True)
        raise

    except Exception as e:
        # Check for debug files before cleanup
        debug_info = {}
        try:
            # Look for debug files (with timestamp patterns)
            debug_files_found = []
            if os.path.exists(download_dir):
                for filename in os.listdir(download_dir):
                    if filename.endswith('.png') or filename.endswith('.html'):
                        if 'screenshot' in filename or 'page_source' in filename:
                            debug_files_found.append(os.path.join(download_dir, filename))

            # Check if debug files exist
            if debug_files_found:
                # Save debug files to a persistent location
                debug_id = str(uuid.uuid4())
                debug_dir = os.path.join(DOWNLOADS_DIR, f"debug_{debug_id}")
                os.makedirs(debug_dir, exist_ok=True)

                debug_files = []

                for filepath in debug_files_found:
                    filename = os.path.basename(filepath)
                    dest_path = os.path.join(debug_dir, filename)
                    shutil.copy(filepath, dest_path)

                    file_type = "image" if filename.endswith('.png') else "html"
                    debug_files.append({
                        "name": filename,
                        "url": f"{BASE_DOMAIN}/files/debug_{debug_id}/{filename}",
                        "type": file_type
                    })

                # Find screenshot and page source for legacy fields
                screenshot_file = next((f for f in debug_files if 'screenshot' in f['name'] and f['type'] == 'image'), None)
                page_source_file = next((f for f in debug_files if 'page_source' in f['name'] and f['type'] == 'html'), None)

                debug_info = {
                    "debug_id": debug_id,
                    "debug_files": debug_files,
                    "view_all_url": f"{BASE_DOMAIN}/debug/{debug_id}",
                    # Legacy fields for backwards compatibility
                    "debug_screenshot": screenshot_file['url'] if screenshot_file else None,
                    "debug_page_source": page_source_file['url'] if page_source_file else None
                }
                print(f"Debug files saved. Debug ID: {debug_id}")
        except Exception as debug_error:
            print(f"Could not save debug files: {debug_error}")

        # Cleanup temp directory
        shutil.rmtree(download_dir, ignore_errors=True)

        print(f"Error generating report: {e}")

        # Include debug info in error response
        error_detail = {
            "error": str(e),
            "message": "Failed to generate report",
        }
        if debug_info:
            error_detail["debug"] = debug_info

        raise HTTPException(
            status_code=500,
            detail=error_detail
        )


@app.post("/generate-report", response_model=ReportResponse)
async def generate_report(
    report_request: ReportRequest,
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Generate attendance report and return JSON with download URL

    Parameters:
    - company_code: Company code for login (default: 85)
    - username: Username for login (default: hisham.octacer)
    - password: Password for login
    - report_date: Date for report in YYYY-MM-DD format (default: today)

    Returns:
    - JSON with report_url (download link), file_id, and metadata
    """
    return _generate_report_internal(
        company_code=report_request.company_code,
        username=report_request.username,
        password=report_request.password,
        report_date=report_request.report_date,
        background_tasks=background_tasks,
        request=request,
        return_json=True
    )


@app.post("/generate-report-direct")
async def generate_report_direct(
    report_request: ReportRequest,
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Generate attendance report and directly return Excel file

    Parameters:
    - company_code: Company code for login (default: 85)
    - username: Username for login (default: hisham.octacer)
    - password: Password for login
    - report_date: Date for report in YYYY-MM-DD format (default: today)

    Returns:
    - Excel file with attendance report (direct download)
    """
    return _generate_report_internal(
        company_code=report_request.company_code,
        username=report_request.username,
        password=report_request.password,
        report_date=report_request.report_date,
        background_tasks=background_tasks,
        request=request,
        return_json=False
    )


@app.get("/get-report-default", response_model=ReportResponse)
async def get_report_default(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Generate today's report with default credentials - Returns JSON with download URL

    This is a convenience endpoint that generates today's report using default credentials.
    Simply call: GET /get-report-default

    Returns:
    - JSON with report_url (download link), file_id, and metadata
    """
    return _generate_report_internal(
        company_code="85",
        username="hisham.octacer",
        password="P@ss1234",
        report_date=None,  # Today's date
        background_tasks=background_tasks,
        request=request,
        return_json=True
    )


@app.get("/get-report-default-direct")
async def get_report_default_direct(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Generate today's report with default credentials - Direct file download

    Returns:
    - Excel file with attendance report for today (direct download)
    """
    return _generate_report_internal(
        company_code="85",
        username="hisham.octacer",
        password="P@ss1234",
        report_date=None,  # Today's date
        background_tasks=background_tasks,
        request=request,
        return_json=False
    )


@app.get("/debug/{debug_id}")
async def get_debug_info(debug_id: str):
    """
    Get debug information and list of debug files for a specific debug ID

    Parameters:
    - debug_id: The debug ID returned in error response

    Returns:
    - JSON with list of available debug files and download URLs
    """
    debug_dir = os.path.join(DOWNLOADS_DIR, f"debug_{debug_id}")

    if not os.path.exists(debug_dir):
        raise HTTPException(
            status_code=404,
            detail="Debug session not found or has expired"
        )

    # List all files in debug directory
    debug_files = []
    base_url = str(Request).split("'")[1] if "'" in str(Request) else "http://localhost:8000"

    try:
        for filename in os.listdir(debug_dir):
            filepath = os.path.join(debug_dir, filename)
            if os.path.isfile(filepath):
                file_size = os.path.getsize(filepath)
                file_type = "image" if filename.endswith(".png") else "html"

                debug_files.append({
                    "name": filename,
                    "url": f"/files/debug_{debug_id}/{filename}",
                    "type": file_type,
                    "size": file_size
                })
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error reading debug files: {str(e)}"
        )

    return {
        "debug_id": debug_id,
        "files": debug_files,
        "total_files": len(debug_files),
        "message": "Use the URLs to download individual files"
    }


@app.get("/debug")
async def list_debug_sessions():
    """
    List all available debug sessions

    Returns:
    - JSON with list of all debug sessions available
    """
    debug_sessions = []

    try:
        for item in os.listdir(DOWNLOADS_DIR):
            if item.startswith("debug_") and os.path.isdir(os.path.join(DOWNLOADS_DIR, item)):
                debug_id = item.replace("debug_", "")
                debug_dir = os.path.join(DOWNLOADS_DIR, item)

                # Get directory stats
                stat = os.stat(debug_dir)
                created_time = datetime.fromtimestamp(stat.st_ctime)

                # Count files
                file_count = len([f for f in os.listdir(debug_dir) if os.path.isfile(os.path.join(debug_dir, f))])

                debug_sessions.append({
                    "debug_id": debug_id,
                    "created_at": created_time.isoformat(),
                    "file_count": file_count,
                    "view_url": f"/debug/{debug_id}"
                })

        # Sort by created time (newest first)
        debug_sessions.sort(key=lambda x: x["created_at"], reverse=True)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error listing debug sessions: {str(e)}"
        )

    return {
        "total_sessions": len(debug_sessions),
        "sessions": debug_sessions,
        "message": "Use view_url to see files for each session"
    }


@app.get("/download/{file_id}")
async def download_file(file_id: str):
    """
    Download a generated report by file ID

    Parameters:
    - file_id: The unique file ID returned from generate-report endpoint

    Returns:
    - Excel file download
    """
    # Check if file exists in registry
    if file_id not in file_registry:
        raise HTTPException(
            status_code=404,
            detail="File not found or has expired"
        )

    file_info = file_registry[file_id]
    filepath = file_info["filepath"]

    # Check if file has expired
    if datetime.now() > file_info["expires_at"]:
        # Clean up expired file
        if os.path.exists(filepath):
            os.remove(filepath)
        del file_registry[file_id]
        raise HTTPException(
            status_code=410,
            detail="File has expired"
        )

    # Check if file exists on disk
    if not os.path.exists(filepath):
        del file_registry[file_id]
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )

    # Return file
    display_filename = f"attendance_report_{file_info['report_date']}.xlsx"
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=display_filename,
        headers={
            "Content-Disposition": f"attachment; filename={display_filename}"
        }
    )


@app.post("/pdf-to-png", response_model=PdfToImageResponse)
async def pdf_to_png(
    request: PdfToImageRequest,
    background_tasks: BackgroundTasks
):
    """
    Convert PDF to PNG images

    Parameters:
    - pdf_url: Publicly accessible URL to the PDF file

    Returns:
    - JSON with list of PNG image URLs, one per page
    """
    conversion_id = str(uuid.uuid4())
    temp_pdf_dir = os.path.join(PDF_TEMP_DIR, conversion_id)
    os.makedirs(temp_pdf_dir, exist_ok=True)

    try:
        print(f"Processing PDF conversion request: {conversion_id}")
        print(f"→ PDF URL: {request.pdf_url}")

        # Download PDF file
        pdf_path = os.path.join(temp_pdf_dir, "input.pdf")
        print(f"→ Downloading PDF...")

        response = requests.get(str(request.pdf_url), timeout=30, stream=True)
        response.raise_for_status()

        with open(pdf_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"→ PDF downloaded: {os.path.getsize(pdf_path)} bytes")

        # Convert PDF to images
        print(f"→ Converting PDF to PNG images...")
        images = convert_from_path(
            pdf_path,
            dpi=200,  # High quality
            fmt='png'
        )

        total_pages = len(images)
        print(f"→ Converted {total_pages} pages")

        # Save images to downloads directory
        conversion_dir = os.path.join(DOWNLOADS_DIR, f"pdf_{conversion_id}")
        os.makedirs(conversion_dir, exist_ok=True)

        image_list = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for i, image in enumerate(images, start=1):
            image_filename = f"{timestamp}_page_{i}.png"
            image_path = os.path.join(conversion_dir, image_filename)
            image.save(image_path, 'PNG')

            image_url = f"{BASE_DOMAIN}/files/pdf_{conversion_id}/{image_filename}"
            image_list.append(ImageInfo(
                page=i,
                url=image_url,
                filename=image_filename
            ))
            print(f"→ Saved page {i}/{total_pages}: {image_filename}")

        # Cleanup temp directory
        shutil.rmtree(temp_pdf_dir, ignore_errors=True)

        # Schedule cleanup after 1 hour
        background_tasks.add_task(cleanup_directory_after_delay, conversion_dir, 3600)

        generated_at = datetime.now()

        print(f"→ Conversion complete: {conversion_id}\n")

        return PdfToImageResponse(
            images=image_list,
            total_pages=total_pages,
            conversion_id=conversion_id,
            generated_at=generated_at.isoformat(),
            expires_in=3600  # 1 hour
        )

    except requests.RequestException as e:
        # Cleanup temp directory
        shutil.rmtree(temp_pdf_dir, ignore_errors=True)
        print(f"Error downloading PDF: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download PDF from URL: {str(e)}"
        )

    except Exception as e:
        # Cleanup temp directory
        shutil.rmtree(temp_pdf_dir, ignore_errors=True)
        print(f"Error converting PDF: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to convert PDF to PNG: {str(e)}"
        )


@app.post("/extract-text", response_model=TextExtractionResponse)
async def extract_text(
    request_data: TextExtractionRequest,
    background_tasks: BackgroundTasks
):
    """
    Extract text from an image or PDF using OCR (Tesseract)

    Parameters:
    - image_or_pdf_url: Publicly accessible URL to an image (JPG, PNG, etc.) or PDF file

    Returns:
    - JSON with extracted text, language detected, and extraction metadata
    """
    request_id = str(uuid.uuid4())
    temp_extract_dir = os.path.join(os.getcwd(), "temp_extract", request_id)
    os.makedirs(temp_extract_dir, exist_ok=True)

    try:
        print(f"\n{'='*80}")
        print(f"Processing text extraction request: {request_id}")
        print(f"{'='*80}")
        print(f"→ URL: {request_data.url}")

        url_str = str(request_data.url)

        # Download file first
        print(f"→ Downloading file...")
        response = requests.get(url_str, timeout=30, stream=True)
        response.raise_for_status()

        # Save to temporary location first
        temp_raw_file = os.path.join(temp_extract_dir, "temp_raw")
        with open(temp_raw_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"→ File downloaded: {os.path.getsize(temp_raw_file)} bytes")

        # Detect file type from actual file content using magic bytes
        print(f"→ Detecting file type from content...")
        mime = magic.Magic(mime=True)
        detected_mime = mime.from_file(temp_raw_file)
        print(f"→ Detected MIME type: {detected_mime}")

        # Map MIME type to file extension
        is_pdf = 'pdf' in detected_mime.lower()

        if is_pdf:
            file_extension = 'pdf'
            source_type = 'pdf'
        elif 'image' in detected_mime.lower():
            source_type = 'image'
            if 'jpeg' in detected_mime.lower() or 'jpg' in detected_mime.lower():
                file_extension = 'jpg'
            elif 'png' in detected_mime.lower():
                file_extension = 'png'
            elif 'gif' in detected_mime.lower():
                file_extension = 'gif'
            elif 'webp' in detected_mime.lower():
                file_extension = 'webp'
            else:
                file_extension = 'jpg'  # default
        else:
            # Fallback: assume image
            source_type = 'image'
            file_extension = 'jpg'

        print(f"→ Source type: {source_type}")
        print(f"→ File extension: {file_extension}")

        # Rename temporary file to proper extension
        if is_pdf:
            temp_file = os.path.join(temp_extract_dir, "input.pdf")
        else:
            temp_file = os.path.join(temp_extract_dir, f"input.{file_extension}")

        os.rename(temp_raw_file, temp_file)

        print(f"→ File downloaded: {os.path.getsize(temp_file)} bytes")

        # Extract text
        extracted_text = ""
        total_pages = 0

        if is_pdf:
            print(f"→ Converting PDF to images for OCR...")
            # Convert PDF to images
            images = convert_from_path(temp_file, dpi=200)
            total_pages = len(images)
            print(f"→ PDF has {total_pages} pages")

            # Extract text from each page
            print(f"→ Extracting text from PDF pages...")
            page_texts = []
            for i, image in enumerate(images, start=1):
                print(f"  → Processing page {i}/{total_pages}...")
                page_text = pytesseract.image_to_string(image)
                page_texts.append(f"--- PAGE {i} ---\n{page_text}")

            extracted_text = "\n\n".join(page_texts)

        else:
            print(f"→ Extracting text from image...")
            # Open image and extract text
            image = Image.open(temp_file)
            extracted_text = pytesseract.image_to_string(image)
            total_pages = 1

        print(f"→ Text extraction complete")
        print(f"→ Extracted text length: {len(extracted_text)} characters")

        extracted_at = datetime.now()

        print(f"\n{'='*80}")
        print(f"Request completed successfully")
        print(f"{'='*80}\n")

        # Cleanup temp directory
        background_tasks.add_task(cleanup_directory_after_delay, temp_extract_dir, 60)

        return TextExtractionResponse(
            text=extracted_text,
            language="eng",  # Tesseract default, can be extended for language detection
            extraction_method="Tesseract OCR",
            source_type=source_type,
            total_pages=total_pages,
            extracted_at=extracted_at.isoformat(),
            request_id=request_id
        )

    except requests.RequestException as e:
        shutil.rmtree(temp_extract_dir, ignore_errors=True)
        print(f"Error downloading file: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download file from URL: {str(e)}"
        )

    except Exception as e:
        shutil.rmtree(temp_extract_dir, ignore_errors=True)
        print(f"Error extracting text: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract text: {str(e)}"
        )


@app.get("/get-vollna-cookies", response_model=VollnaCookiesResponse)
async def get_vollna_cookies(
    email: str = "mateo@brightdock.com",
    password: str = "Antonia.12",
    final_url: str = "https://www.vollna.com/dashboard/filter/22703"
):
    """
    Get cookies from Vollna website after login

    Parameters:
    - email: Email for login (default: mateo@brightdock.com)
    - password: Password for login (default: Antonia.12)
    - final_url: Final URL to navigate to after login (default: https://www.vollna.com/dashboard/filter/22703)

    Returns:
    - JSON with cookies as a string, cookie count, and extraction timestamp
    """
    request_id = str(uuid.uuid4())

    try:
        print(f"\n{'='*80}")
        print(f"Processing Vollna cookies request")
        print(f"{'='*80}")
        print(f"→ Request ID: {request_id}")
        print(f"→ Email: {email}")
        print(f"→ Final URL: {final_url}")
        print(f"→ Timestamp: {datetime.now().isoformat()}\n")

        # Initialize automation
        print("Initializing Vollna automation...")
        automation = VollnaAutomation()
        print("→ Automation initialized\n")

        # Get cookies
        print("Starting login and cookie extraction process...")
        cookie_string = automation.login_and_get_cookies(
            email=email,
            password=password,
            final_url=final_url
        )

        # Count cookies
        cookie_count = len(cookie_string.split("; ")) if cookie_string else 0

        extracted_at = datetime.now()

        print("Processing response...")
        print(f"→ Successfully extracted {cookie_count} cookies")
        print(f"→ Cookie string length: {len(cookie_string)} characters")
        print(f"→ Response timestamp: {extracted_at.isoformat()}")
        print(f"\n{'='*80}")
        print(f"Request completed successfully")
        print(f"{'='*80}\n")

        return VollnaCookiesResponse(
            cookies=cookie_string,
            cookie_count=cookie_count,
            extracted_at=extracted_at.isoformat()
        )

    except Exception as e:
        print(f"\n{'='*80}")
        print(f"✗ ERROR in Vollna cookies request")
        print(f"{'='*80}")
        print(f"→ Request ID: {request_id}")
        print(f"→ Error type: {type(e).__name__}")
        print(f"→ Error message: {str(e)}")
        print(f"→ Timestamp: {datetime.now().isoformat()}")
        print(f"{'='*80}\n")

        raise HTTPException(
            status_code=500,
            detail=f"Failed to get Vollna cookies: {str(e)}"
        )


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
