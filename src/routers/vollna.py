"""Vollna cookie extraction endpoint."""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from src.models import VollnaCookiesResponse
from vollna_automation import VollnaAutomation

router = APIRouter()


@router.get("/get-vollna-cookies", response_model=VollnaCookiesResponse)
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
