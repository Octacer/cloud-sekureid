"""
FastAPI Server for Sekure-ID Report Generation
Exposes the automation as a REST API endpoint
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict
import os
import shutil
from datetime import datetime, timedelta
import uuid
import asyncio
from sekureid_automation import SekureIDAutomation


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


# Store for tracking download files
TEMP_DIR = os.path.join(os.getcwd(), "temp_reports")
DOWNLOADS_DIR = os.path.join(os.getcwd(), "downloads")
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
            debug_screenshot = os.path.join(download_dir, "error_screenshot.png")
            debug_page_source = os.path.join(download_dir, "error_page_source.html")
            page_source_file = os.path.join(download_dir, "page_source.html")

            # Check if debug files exist
            if os.path.exists(debug_screenshot):
                # Save debug files to a persistent location
                debug_id = str(uuid.uuid4())
                debug_dir = os.path.join(DOWNLOADS_DIR, f"debug_{debug_id}")
                os.makedirs(debug_dir, exist_ok=True)

                if os.path.exists(debug_screenshot):
                    shutil.copy(debug_screenshot, os.path.join(debug_dir, "error_screenshot.png"))
                if os.path.exists(debug_page_source):
                    shutil.copy(debug_page_source, os.path.join(debug_dir, "error_page_source.html"))
                if os.path.exists(page_source_file):
                    shutil.copy(page_source_file, os.path.join(debug_dir, "page_source.html"))

                base_url = str(request.base_url).rstrip('/')
                debug_info = {
                    "debug_screenshot": f"{base_url}/files/debug_{debug_id}/error_screenshot.png",
                    "debug_page_source": f"{base_url}/files/debug_{debug_id}/error_page_source.html",
                    "debug_id": debug_id
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

    uvicorn.run(app, host="0.0.0.0", port=8000)
