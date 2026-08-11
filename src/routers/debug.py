"""Debug session listing endpoints (populated when report generation fails)."""

import os
from datetime import datetime

from fastapi import APIRouter, HTTPException

from src.config import DOWNLOADS_DIR

router = APIRouter()


@router.get("/debug/{debug_id}")
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


@router.get("/debug")
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
