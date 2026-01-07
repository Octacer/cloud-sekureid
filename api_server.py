"""
FastAPI Server for Sekure-ID Report Generation
Exposes the automation as a REST API endpoint
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import os
import shutil
from datetime import datetime
import uuid
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


# Store for tracking download files
TEMP_DIR = os.path.join(os.getcwd(), "temp_reports")
os.makedirs(TEMP_DIR, exist_ok=True)


def cleanup_file(filepath: str):
    """Background task to cleanup file after download"""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"Cleaned up: {filepath}")
    except Exception as e:
        print(f"Error cleaning up {filepath}: {e}")


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Sekure-ID Report Generator API",
        "version": "1.0.0",
        "endpoints": {
            "POST /generate-report": "Generate and download attendance report",
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


@app.post("/generate-report")
async def generate_report(
    request: ReportRequest,
    background_tasks: BackgroundTasks
):
    """
    Generate attendance report and return Excel file

    Parameters:
    - company_code: Company code for login (default: 85)
    - username: Username for login (default: hisham.octacer)
    - password: Password for login
    - report_date: Date for report in YYYY-MM-DD format (default: today)

    Returns:
    - Excel file with attendance report
    """

    # Create unique download directory for this request
    request_id = str(uuid.uuid4())
    download_dir = os.path.join(TEMP_DIR, request_id)
    os.makedirs(download_dir, exist_ok=True)

    try:
        print(f"Processing report request: {request_id}")

        # Validate date format if provided
        if request.report_date:
            try:
                datetime.strptime(request.report_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date format. Use YYYY-MM-DD"
                )

        # Initialize automation
        automation = SekureIDAutomation(download_dir=download_dir)

        # Generate report
        excel_file = automation.generate_report(
            company_code=request.company_code,
            username=request.username,
            password=request.password,
            report_date=request.report_date
        )

        if not os.path.exists(excel_file):
            raise HTTPException(
                status_code=500,
                detail="Report generation failed - file not found"
            )

        # Generate a meaningful filename
        report_date = request.report_date or datetime.now().strftime("%Y-%m-%d")
        filename = f"attendance_report_{report_date}.xlsx"

        # Schedule cleanup after file is sent
        background_tasks.add_task(cleanup_file, excel_file)
        background_tasks.add_task(shutil.rmtree, download_dir, ignore_errors=True)

        # Return the Excel file
        return FileResponse(
            excel_file,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=filename,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        shutil.rmtree(download_dir, ignore_errors=True)
        raise

    except Exception as e:
        # Cleanup on error
        shutil.rmtree(download_dir, ignore_errors=True)

        print(f"Error generating report: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate report: {str(e)}"
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
