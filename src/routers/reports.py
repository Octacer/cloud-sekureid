"""Attendance report generation and download endpoints."""

import os
import shutil
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse

from src.config import TEMP_DIR, DOWNLOADS_DIR, BASE_DOMAIN, file_registry
from src.helpers import cleanup_registered_file
from src.models import ReportRequest, ReportResponse
from sekureid_automation import SekureIDAutomation

router = APIRouter()


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
            background_tasks.add_task(cleanup_registered_file, file_id, final_path, 3600)

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


@router.post("/generate-report", response_model=ReportResponse)
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


@router.post("/generate-report-direct")
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


@router.get("/get-report-default", response_model=ReportResponse)
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


@router.get("/get-report-default-direct")
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


@router.get("/download/{file_id}")
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
