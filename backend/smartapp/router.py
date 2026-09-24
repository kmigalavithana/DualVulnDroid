"""
SmartApp's isolated API surface. Mounted in app.py as:

    app.include_router(smartapp_router, prefix="/smartapp", tags=["smartapp"])

giving:

    GET /smartapp/apps/search
    GET /smartapp/apps/details/{package_name}

Nothing in this module touches predictor.py, dataflow.py,
security_features.py, the XGBoost model, the database, or any existing
/predict, /developer/*, or /apps/* security route - SmartApp is a
separate product/module with its own provider (provider.py) and
normalization (service.py).
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from . import service
from .models import SmartAppDetailsResponse, SmartAppSearchResponse
from .provider import SerpApiError

router = APIRouter()


@router.get("/apps/search", response_model=SmartAppSearchResponse)
def search_apps(
    q: Optional[str] = Query(None, description="Free-text search query."),
    category: Optional[str] = Query(None, description="A SmartApp category label, e.g. 'Notes'."),
    country: str = Query("us", description="Google Play store country code."),
    language: str = Query("en", description="Google Play store language code."),
    limit: int = Query(20, ge=1, le=50),
):
    if not (q and q.strip()) and not category:
        raise HTTPException(status_code=400, detail="Provide 'q' and/or 'category'.")
    try:
        apps = service.search_apps(query=q, category=category, country=country, language=language, limit=limit)
    except SerpApiError as exc:
        # 502: OUR backend is fine, the upstream Google Play provider call
        # failed - never masked as a fake empty/success result.
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return SmartAppSearchResponse(apps=apps)


@router.get("/apps/details/{package_name}", response_model=SmartAppDetailsResponse)
def app_details(
    package_name: str,
    country: str = Query("us", description="Google Play store country code."),
    language: str = Query("en", description="Google Play store language code."),
):
    try:
        details = service.get_app_details(package_name, country=country, language=language)
    except SerpApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if details is None:
        raise HTTPException(status_code=404, detail=f"No Google Play app found for package '{package_name}'.")
    return SmartAppDetailsResponse(app=details)
