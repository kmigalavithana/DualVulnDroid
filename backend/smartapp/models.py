"""
SmartApp's normalized response shapes. Every metadata field is Optional -
a field no provider verified is None (or, for list-valued fields, an
empty list), never a guessed/default value: unavailable must stay
distinguishable from known.

realData/source/isLiveData are always literally true/"google_play" here -
an app only ever exists in a response because Google Play returned it.
Verified enrichment (Exodus, F-Droid, Play product-page facts) adds fields
on top and records its provenance in `metadataSources`.
"""

from typing import Optional

from pydantic import BaseModel


class SmartAppItem(BaseModel):
    # --- Google Play (primary source) ---
    id: Optional[str] = None
    name: Optional[str] = None
    packageName: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    iconUrl: Optional[str] = None
    rating: Optional[float] = None
    reviewCount: Optional[int] = None
    playStoreUrl: Optional[str] = None
    developer: Optional[str] = None
    realData: bool = True
    source: str = "google_play"

    # --- Store facts stated on the Google Play product page ---
    isFree: Optional[bool] = None
    price: Optional[str] = None
    currency: Optional[str] = None
    hasAds: Optional[bool] = None
    inAppPurchases: Optional[bool] = None
    dataSafety: list[str] = []

    # --- Privacy (Exodus) ---
    trackerCount: Optional[int] = None
    trackerNames: list[str] = []
    permissions: Optional[list[str]] = None
    privacyReportVersion: Optional[str] = None
    privacyDataSource: Optional[str] = None

    # --- Open source (F-Droid) ---
    isOpenSource: Optional[bool] = None
    license: Optional[str] = None
    antiFeatures: list[str] = []
    fdroidAvailable: Optional[bool] = None
    fdroidSourceUrl: Optional[str] = None

    # --- Never reported by any configured source; kept explicit as None ---
    sizeMb: Optional[float] = None
    supportsOffline: Optional[bool] = None

    # --- Provenance ---
    googlePlayDataAvailable: bool = True
    storeDetailsAvailable: bool = False
    privacyMetadataAvailable: bool = False
    openSourceMetadataAvailable: bool = False
    resourceMetadataAvailable: bool = False
    metadataSources: list[str] = ["google_play"]
    metadataUpdatedAt: Optional[str] = None
    privacyMetadataUpdatedAt: Optional[str] = None
    # Share (0-1) of the 7 recommendation attributes that are verified -
    # a data-completeness figure, NOT a prediction confidence.
    metadataCoverage: Optional[float] = None


class SmartAppSearchResponse(BaseModel):
    apps: list[SmartAppItem]
    source: str = "google_play"
    isLiveData: bool = True


class SmartAppDetails(SmartAppItem):
    version: Optional[str] = None
    releaseDate: Optional[str] = None
    updatedOn: Optional[str] = None
    screenshots: list[str] = []


class SmartAppDetailsResponse(BaseModel):
    app: SmartAppDetails
    source: str = "google_play"
    isLiveData: bool = True
