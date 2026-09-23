import logging
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from predictor import predict_code, to_developer_response, to_explain_response
from chatbot_logic import analyze_user_query, generate_chat_response
from apk_scanner import scan_apk_file
from apk_code_scanner import scan_apk_for_code_vulnerabilities
import compatibility
import alternatives
import database
import shutil
import tempfile
import os
import time

from db.session import get_db, DatabaseNotConfiguredError, check_connection
from db import crud, models
from db.security import create_access_token, decode_access_token
import jwt as pyjwt

# SmartApp (separate product/module, isolated in backend/smartapp/ - see
# that package's __init__.py) - its own router, its own provider, its own
# normalization. Does not touch any security detection code below.
from smartapp.router import router as smartapp_router

logger = logging.getLogger("dualvulndroid")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="DualVulnDroid API",
    version="2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SmartApp routes - isolated under /smartapp/*, implemented entirely in
# backend/smartapp/. See that package's __init__.py/router.py for why
# this is the only place SmartApp is wired into the security backend.
app.include_router(smartapp_router, prefix="/smartapp", tags=["smartapp"])

# ==========================================
# Centralized error handling (section 12)
# ==========================================
# 401 is intentionally not handled here: none of the /developer/* or
# /apps/* routes have an authentication mechanism yet (only /login,
# /register do, which are unrelated) - adding a fake 401 path with no
# real auth behind it would be theater, not error handling.

MAX_CODE_SIZE_BYTES = 200_000  # ~200KB; a legitimate size guard, not a made-up limit

# P0 Step 9: /predict (unlike /developer/predict's _guarded_predict() below)
# had NO size limit at all - an oversized "code" payload would go straight
# into feature extraction, XGBoost, SHAP, and data-flow analysis. Defaults
# to the SAME already-justified ~200KB Android-source-file ceiling as
# MAX_CODE_SIZE_BYTES (not a new, arbitrary number - a single real Android
# Java/Kotlin source file is realistically a few KB up to a few tens of
# KB; 200KB comfortably covers even unusually large generated/legacy
# files without being so loose it defeats the point), kept as its own
# env-configurable constant so this endpoint's limit can be tuned
# independently of /developer/predict's without touching that route's
# already-tested behavior.
PREDICT_MAX_CODE_SIZE_BYTES = int(os.getenv("PREDICT_MAX_CODE_SIZE_BYTES", str(MAX_CODE_SIZE_BYTES)))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.method} {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": "The server failed to process this request. Check backend logs for details."},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": "request_error", "detail": exc.detail})


@app.exception_handler(DatabaseNotConfiguredError)
async def database_not_configured_handler(request: Request, exc: DatabaseNotConfiguredError):
    # Phase 7, Part T: never a silent SQLite fallback - a clear 503
    # naming exactly what's missing and how to fix it.
    return JSONResponse(status_code=503, content={"error": "database_not_configured", "detail": str(exc)})


@app.on_event("startup")
def _startup_database_check():
    # Best-effort, loud, non-fatal (Part T) - endpoints that don't touch
    # the database (e.g. /predict) have nothing to do with MySQL and
    # must keep working even if this check fails.
    ok, message = check_connection()
    if ok:
        logger.info(f"[startup] {message}")
    else:
        logger.warning(f"[startup] {message}")


# ==========================================
# JWT authentication (Part D/M/U)
# ==========================================

def get_current_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> models.User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired.")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")

    user = db.query(models.User).filter(models.User.id == int(payload["sub"])).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User no longer exists.")
    return user


class CodeRequest(BaseModel):
    code: str
    fileName: str = ""

class RescanRequest(BaseModel):
    code: str
    fileName: str = ""
    previousSeverity: Optional[str] = None
    previousConfidence: Optional[float] = None

class BatchScanFile(BaseModel):
    code: str
    fileName: str = ""

class BatchScanRequest(BaseModel):
    files: list[BatchScanFile] = Field(..., min_length=1, max_length=200)

class UserQuery(BaseModel):
    app_name: str
    user_ram_mb: int = 2048
    user_android_version: int = 10
    user_id: int = None

class ChatMessage(BaseModel):
    message: str
    user_ram_mb: int = 2048
    user_android_version: int = 10
    user_id: int = None
    # Phase 12: real, unambiguous app context - the client already has this
    # ID from a real GET /apps/{id}/security fetch when a user opens chat
    # from an app's context, so the backend can look up REAL current data
    # by ID instead of fuzzy-matching an app name out of free text.
    app_id: int = None

class AuthRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str

class DeviceProfile(BaseModel):
    """Caller-supplied device data for /apps/{id}/compatibility. Every
    field optional and independently validated - a missing field is a
    legitimate NOT_AVAILABLE input, not a request error. Range bounds
    exist only to reject obviously-garbage input (e.g. a negative Android
    version), not to imply any of these are required.

    ramMb/architecture (Phase 8B) are kept for backward compatibility but
    are NEVER used in any compatibility computation - no verified source
    of an app's REQUIRED RAM/CPU model exists anywhere in this system
    (Part E: "do not use RAM as a compatibility signal"). features/abis
    (Phase 8C) ARE used - real device feature names and real supported
    ABI strings (e.g. Build.SUPPORTED_ABIS), checked against the app's
    real manifest-declared requirements."""
    androidVersion: Optional[int] = Field(None, ge=1, le=99)
    ramMb: Optional[int] = Field(None, ge=1)
    architecture: Optional[str] = Field(None, max_length=50)
    features: Optional[list[str]] = None
    abis: Optional[list[str]] = None

@app.post("/register")
def register(req: RegisterRequest):
    success = database.create_user(req.email, req.password, req.name)
    if success:
        return {"message": "User registered successfully."}
    else:
        raise HTTPException(status_code=400, detail="Email already exists.")

@app.post("/login")
def login(req: AuthRequest):
    user = database.verify_user(req.email, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    # Phase 7: additive field only - existing clients that only read
    # "message"/"user" (the pre-Phase-7 shape) are unaffected. New
    # clients use "token" as a Bearer token on /user/history.
    token = create_access_token(user_id=user["id"], email=user["email"])
    return {"message": "Login successful.", "user": user, "token": token}

@app.get("/history/{user_id}")
def get_user_history(user_id: int):
    # Kept exactly as-is for backward compatibility (Part X) - this is a
    # legacy, UNAUTHENTICATED endpoint (trusts whatever id is in the URL).
    # GET /user/history below is the secure, JWT-protected replacement;
    # this one is not removed only because Part X requires it to keep
    # working, and is documented as a known limitation (Part Z).
    history = database.get_history(user_id)
    return {"history": history}


@app.get("/user/history")
def get_authenticated_user_history(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Part M: the SECURE history endpoint - only ever the authenticated
    user's own scans, derived from the JWT, never a client-supplied id."""
    return {"history": crud.get_user_history(db, current_user.id)}


@app.get("/user/chat-history")
def get_authenticated_user_chat_history(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Phase 14C: the read side of chat history. /ai-chat has always
    written every message to the chat_history table (database.save_chat_message),
    but no endpoint ever read it back, so a user's own chat history was
    never actually observable. Same security pattern as /user/history
    above - only ever the authenticated user's own messages, derived from
    the JWT, never a client-supplied id."""
    return {"history": crud.get_user_chat_history(db, current_user.id)}

@app.get("/")
def home():
    return {
        "message": "DualVulnDroid XGBoost Backend Running"
    }


@app.post("/predict")
def predict(request: CodeRequest, x_benchmark_timing: Optional[str] = Header(default=None)):
    # Kept exactly as-is (same request/response shape) for backward
    # compatibility with the existing Android Studio plugin (APIClient.kt
    # posts here by default). predict_code() itself already returns the
    # Phase 3/4 fields (decision, decisionEvidence, securityFeatures,
    # severity, shapTopFeatures) additively, so existing clients are
    # unaffected and updated clients get the richer data for free.
    #
    # P0 Step 9: reject an oversized `code` payload BEFORE it ever reaches
    # feature extraction/XGBoost/SHAP/data-flow analysis. Measured as real
    # UTF-8 byte length (matches MAX_CODE_SIZE_BYTES's own convention and
    # actually reflects request payload size, unlike Python's len(str)
    # which undercounts multi-byte characters) of the code field only -
    # fileName is never size-limited, since it isn't the vulnerability-
    # relevant input and rejecting on it would be exactly the "unrelated
    # JSON field" mistake this step is meant to avoid.
    code_size = len(request.code.encode("utf-8"))
    if code_size > PREDICT_MAX_CODE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"code exceeds the {PREDICT_MAX_CODE_SIZE_BYTES} byte limit "
                f"({code_size} bytes received). Configurable via the "
                "PREDICT_MAX_CODE_SIZE_BYTES environment variable."
            ),
        )

    # Latency-measurement experiment task, Part 3: timing is computed and
    # returned ONLY when this explicit opt-in header is present - a normal
    # request (no header) gets exactly the same response as before this
    # flag existed, and predict_code() itself performs zero extra work
    # when capture_timing is False (see its docstring). T3 is measured
    # here, at the earliest point this handler has the parsed request
    # body - not wall-clock time.time(), a monotonic clock, matching the
    # experiment's other timestamps.
    benchmark_timing = bool(x_benchmark_timing)
    t3 = time.perf_counter() if benchmark_timing else None
    result = predict_code(request.code, request.fileName, capture_timing=benchmark_timing)
    t5 = time.perf_counter() if benchmark_timing else None

    if benchmark_timing:
        inner_timing = result.pop("_timing", {})
        result["timing"] = {
            "backend_total_ms": (t5 - t3) * 1000,
            **inner_timing,
        }

    return result


def _guarded_predict(code: str, file_name: str) -> dict:
    """Shared entry point for every /developer/* route so the API layer
    never duplicates feature construction - it only ever calls
    predict_code(), the single shared pipeline entry point."""
    if len(code.encode("utf-8")) > MAX_CODE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail=f"code exceeds the {MAX_CODE_SIZE_BYTES} byte limit.")
    return predict_code(code, file_name)


# ==========================================
# Developer routes (Phase 4)
# ==========================================

@app.post("/developer/predict")
def developer_predict(request: CodeRequest):
    """Single-file/snippet scan with the full structured response
    (model info, decision, SHAP-ready security features, human-readable
    explanation) - see predictor.to_developer_response()."""
    result = _guarded_predict(request.code, request.fileName)
    return to_developer_response(result)


@app.post("/developer/scan")
def developer_scan(request: BatchScanRequest):
    """Batch variant of /developer/predict - scans multiple files in one
    request (the plugin's 'Scan Project' flow currently loops over files
    client-side calling /predict once per file; this reduces that to one
    round trip). Each file's own errors are isolated so one bad file
    doesn't fail the whole batch."""
    results = []
    for f in request.files:
        try:
            result = _guarded_predict(f.code, f.fileName)
            results.append({"fileName": f.fileName, "result": to_developer_response(result)})
        except HTTPException as e:
            results.append({"fileName": f.fileName, "error": e.detail})
    return {"files": results}


@app.post("/developer/explain")
def developer_explain(request: CodeRequest):
    """Dedicated 'why was this flagged?' endpoint - SHAP contributions,
    data-flow evidence, rule evidence, and a human-readable explanation,
    all derived from the same real analysis as /developer/predict."""
    result = _guarded_predict(request.code, request.fileName)
    return to_explain_response(result)


@app.post("/developer/rescan")
def developer_rescan(request: RescanRequest):
    """Re-scans code (e.g. after a fix) and, if the caller supplies the
    previous result, reports the real before/after change - never a
    fabricated 'improvement' number."""
    result = _guarded_predict(request.code, request.fileName)
    response = to_developer_response(result)

    comparison = None
    if request.previousSeverity is not None:
        severity_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        prev_rank = severity_rank.get(request.previousSeverity.upper())
        new_rank = severity_rank.get(response["severity"])
        if prev_rank is not None and new_rank is not None:
            comparison = {
                "previousSeverity": request.previousSeverity.upper(),
                "currentSeverity": response["severity"],
                "improved": new_rank < prev_rank,
                "regressed": new_rank > prev_rank,
            }
            if request.previousConfidence is not None:
                comparison["previousConfidence"] = request.previousConfidence
                comparison["currentConfidence"] = response["confidence"]

    response["comparison"] = comparison
    return response


@app.post("/decision")
def decision_only(request: CodeRequest):
    """Decision-Engine-only view: risk level, recommendation, confidence,
    and evidence, without the full detection/dataFlow payload."""
    result = _guarded_predict(request.code, request.fileName)
    return to_developer_response(result)["decision"]


# ==========================================
# App lookup routes (Phase 7, Part K/L/N) - real MySQL-backed queries.
# No hardcoded catalogue, no fabricated scores/compatibility, ever.
# ==========================================

_RISK_TO_RECOMMENDATION_LABEL = {
    "HIGH": "AVOID_INSTALLING",
    "MEDIUM": "INSTALL_WITH_CAUTION",
    "LOW": "SAFE_TO_INSTALL",
}


@app.get("/apps/search")
def apps_search(q: str, db: Session = Depends(get_db)):
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="q must not be empty.")
    return {"results": crud.search_applications(db, q.strip())}


@app.get("/apps/{app_id}")
def apps_get(app_id: int, db: Session = Depends(get_db)):
    app_row = crud.get_application_by_id(db, app_id)
    if app_row is None:
        raise HTTPException(status_code=404, detail=f"No application with id {app_id}.")
    return {
        "id": app_row.id, "app_name": app_row.app_name, "package_name": app_row.package_name,
        "developer": app_row.developer, "category": app_row.category, "icon_url": app_row.icon_url,
    }


@app.get("/apps/{app_id}/security")
def apps_get_security(app_id: int, db: Session = Depends(get_db)):
    """Part L: the full user-facing security response. Every value comes
    from an actual stored Scan/Vulnerability row - if the app was never
    scanned, says so honestly (Part K) instead of returning fake results."""
    application = crud.get_application_by_id(db, app_id)
    if application is None:
        raise HTTPException(status_code=404, detail=f"No application with id {app_id}.")

    scan = crud.get_latest_scan_for_application(db, app_id)
    if scan is None:
        return {
            "assessed": False,
            "message": "This application has not been assessed yet.",
        }

    vulnerabilities = [
        {
            "cwe": v.cwe, "type": v.type, "severity": v.severity, "confidence": v.confidence,
            "fileName": v.file_name, "lineNumber": v.line_number, "source": v.source,
            "sink": v.sink, "description": v.description, "status": v.status,
        }
        for v in scan.vulnerabilities
    ]

    # Flutter APK Scan implementation phase: a read-time-derived count over
    # the same vulnerabilities already fetched above - not a second
    # decision/score, purely a display convenience so Flutter doesn't have
    # to recompute it from the full list itself. cwe89Count/cwe295Count
    # only ever count real, already-stored cwe values (never a manifest/
    # permission/URL finding, which are always stored with cwe=None - see
    # db/crud.py's persist_apk_scan).
    cwe89_count = sum(1 for v in scan.vulnerabilities if v.cwe == "CWE-89")
    cwe295_count = sum(1 for v in scan.vulnerabilities if v.cwe == "CWE-295")
    code_findings_summary = {
        "cwe89Count": cwe89_count,
        "cwe295Count": cwe295_count,
        "totalFindings": cwe89_count + cwe295_count,
    }

    # Phase 10A: the real, already-stored explanation for this scan's
    # recommendation (Part 1/2). add_recommendation() is only ever called
    # once per scan today (see persist_apk_scan), but this picks the
    # most recently created row defensively rather than assuming index 0.
    # reason is apk_scanner.py's own real scan_report["explanation"]
    # text (e.g. "No cleartext traffic, dangerous permissions, or
    # suspicious URLs found in this scan.") - never regenerated here, and
    # None (not a fabricated fallback sentence) when nothing was stored.
    # (created_at, id) tiebreak: created_at has only second-resolution
    # (both SQLite's and MySQL's default DATETIME), so two rows inserted
    # within the same second would otherwise tie - id, an autoincrement
    # PK, reliably reflects true insertion order as the tiebreaker.
    latest_recommendation = max(scan.recommendations, key=lambda r: (r.created_at, r.id)) if scan.recommendations else None

    return {
        "assessed": True,
        "application": {
            "id": application.id,
            "name": application.app_name,
            "packageName": application.package_name,
        },
        "version": {
            "versionName": scan.app_version.version_name if scan.app_version else None,
            "versionCode": scan.app_version.version_code if scan.app_version else None,
            "analyzedAt": scan.app_version.analyzed_at.isoformat() if scan.app_version and scan.app_version.analyzed_at else None,
            # Phase 8B: real manifest facts about this specific build.
            "minSdkVersion": scan.app_version.min_sdk_version if scan.app_version else None,
            "targetSdkVersion": scan.app_version.target_sdk_version if scan.app_version else None,
            # Phase 8C: real <uses-feature> declarations and real
            # lib/<abi>/ directories found in this exact build.
            "features": scan.app_version.features_json if scan.app_version else None,
            "abis": scan.app_version.abis_json if scan.app_version else None,
        } if scan.app_version else None,
        "assessment": {
            "riskLevel": scan.risk_level,
            "recommendation": scan.recommendation or _RISK_TO_RECOMMENDATION_LABEL.get(scan.risk_level, "MANUAL_REVIEW"),
            "confidence": scan.confidence,
            # NULL, never fabricated, when the scan couldn't legitimately
            # compute one (Part G) - see apk_scanner.py's real score calc.
            "securityScore": scan.security_score,
            "assessedAt": scan.created_at.isoformat() if scan.created_at else None,
        },
        # Phase 10A: additive - "decision" intentionally mirrors
        # assessment.recommendation above (same real value, not a new
        # computation) so this block is self-contained for a client that
        # only wants the explanation, without also reading "assessment".
        # "reason" is the real stored recommendations.reason (Part 1/2) -
        # None when nothing was ever stored, never a generated fallback
        # sentence (Part 2: "Do NOT generate a fallback sentence in
        # Flutter" - the same rule applies here on the backend). "evidence"
        # is the same already-fetched vulnerabilities, restated with only
        # the fields Part 3 asks for - not a second decision engine, not a
        # new query, not a new score. No "model factors" field exists
        # here: no MLPrediction row is ever created anywhere in this
        # codebase today (db/crud.py's add_ml_prediction is defined but
        # never called), so there is no real SHAP/model-factor data to
        # expose - adding a permanently-null placeholder field would
        # imply data that structurally cannot exist yet.
        "recommendation": {
            "decision": scan.recommendation or _RISK_TO_RECOMMENDATION_LABEL.get(scan.risk_level, "MANUAL_REVIEW"),
            "reason": latest_recommendation.reason if latest_recommendation else None,
            "evidence": [
                {
                    "cwe": v.cwe, "type": v.type, "severity": v.severity,
                    "confidence": v.confidence, "source": v.source, "sink": v.sink,
                }
                for v in scan.vulnerabilities
            ],
        },
        "vulnerabilities": vulnerabilities,
        # Phase 8B: security-relevant manifest signals, kept separate from
        # the vulnerability list on purpose (Part 11) - these are NOT
        # vulnerability findings, and debuggable/allowBackup never affect
        # riskLevel/recommendation/securityScore above.
        "securityMetadata": {
            "debuggable": scan.app_version.debuggable if scan.app_version else None,
            "allowBackup": scan.app_version.allow_backup if scan.app_version else None,
        },
        "codeFindingsSummary": code_findings_summary,
        # No device profile is available on a GET request (Part 17: device
        # data only ever comes from the caller of POST
        # /apps/{id}/compatibility, never guessed here) - so androidVersion/
        # requiredFeatures/abi are all honestly NOT_AVAILABLE (or
        # COMPATIBLE for requiredFeatures/abi when the app itself declares
        # none, which is a real, checkable fact independent of any
        # device), using the real compatibility service rather than a
        # hardcoded placeholder string.
        "compatibility": compatibility.evaluate_full_compatibility(
            min_sdk_version=scan.app_version.min_sdk_version if scan.app_version else None,
            android_version=None,
            required_features=scan.app_version.features_json if scan.app_version else None,
            apk_abis=scan.app_version.abis_json if scan.app_version else None,
            device_features=None,
            device_abis=None,
        ),
    }


@app.post("/apps/{app_id}/compatibility")
def apps_check_compatibility(app_id: int, device: DeviceProfile, db: Session = Depends(get_db)):
    """
    Device-compatibility foundation (Part 17/H). The application's own
    security/manifest metadata always comes from the server's stored APK
    assessment (Part 18) - a client can never claim what an app's
    minSdkVersion/required features/ABIs are; only the device profile in
    the request body is caller-supplied. Combines Android-version (Part
    D/8B), required <uses-feature> (Part F), and native-library ABI (Part
    G) into one response (Part H), plus a real RAM-based hardware
    placeholder (still always NOT_AVAILABLE - Part E: RAM is never a
    compatibility signal here) and a final security+compatibility
    recommendation (Part J) that never claims "safe" from compatibility
    alone.
    """
    application = crud.get_application_by_id(db, app_id)
    if application is None:
        raise HTTPException(status_code=404, detail=f"No application with id {app_id}.")

    scan = crud.get_latest_scan_for_application(db, app_id)
    app_version = scan.app_version if scan else None
    min_sdk_version = app_version.min_sdk_version if app_version else None
    required_features = app_version.features_json if app_version else None
    apk_abis = app_version.abis_json if app_version else None

    full_compatibility = compatibility.evaluate_full_compatibility(
        min_sdk_version=min_sdk_version, android_version=device.androidVersion,
        required_features=required_features, apk_abis=apk_abis,
        device_features=device.features, device_abis=device.abis,
    )

    final = compatibility.combine_security_and_compatibility(
        security_risk_level=scan.risk_level if scan else None,
        security_recommendation=scan.recommendation if scan else None,
        compatibility_status=full_compatibility["status"],
    )

    return {
        "application": {"id": application.id, "packageName": application.package_name, "name": application.app_name},
        "compatibility": full_compatibility,
        "hardwareCompatibility": compatibility.hardware_compatibility_placeholder(),
        "finalRecommendation": final,
    }


@app.get("/apps/{app_id}/alternatives")
def apps_get_alternatives(app_id: int, db: Session = Depends(get_db)):
    """Part K/L/M/N: real alternatives only, never a fabricated list.
    First checks explicitly-curated AlternativeApp links (Phase 7
    behavior, unchanged); if none exist (which is effectively always
    true today, since nothing currently populates that table), falls
    back to the deterministic real-data ranking service over already-
    assessed applications in the database - never a fabricated
    candidate, score, rating, or popularity signal."""
    application = crud.get_application_by_id(db, app_id)
    if application is None:
        raise HTTPException(status_code=404, detail=f"No application with id {app_id}.")

    curated = crud.get_alternatives(db, app_id)
    if curated:
        return {"available": True, "alternatives": curated}

    latest_scan = crud.get_latest_scan_for_application(db, app_id)
    candidates = crud.get_candidate_applications_for_ranking(db, exclude_application_id=app_id)
    ranked = alternatives.rank_alternatives(
        target_application=application,
        target_risk_level=latest_scan.risk_level if latest_scan else None,
        candidates=candidates,
    )
    return {"available": len(ranked) > 0, "alternatives": ranked}


@app.post("/chat")
def chat(request: UserQuery):
    """
    Chatbot endpoint for mobile app dashboard.
    Takes user app query and device specs, returns risk info and recommendations.
    """
    result = analyze_user_query(
        app_name=request.app_name,
        user_ram_mb=request.user_ram_mb,
        user_android_version=request.user_android_version
    )
    
    # Save to history if logged in
    if request.user_id:
        database.save_scan_result(
            user_id=request.user_id,
            app_name=request.app_name,
            overall_score=result.get("security_score", 0),
            risk_level=result.get("risk_level", "unknown"),
            recommendation=result.get("recommendation", "")
        )
        
    return result

@app.post("/ai-chat")
async def ai_chat(request: ChatMessage):
    """
    Receives a natural language message and returns a conversational response.
    """
    bot_reply = generate_chat_response(
        request.message,
        request.user_ram_mb,
        request.user_android_version,
        app_id=request.app_id,
    )
    
    # Save to history if logged in
    if request.user_id:
        database.save_chat_message(request.user_id, request.message, bot_reply)
        
    return {"reply": bot_reply}

MAX_APK_SIZE_BYTES = 100 * 1024 * 1024  # 100MB - a legitimate upload-size guard (Part U)


@app.post("/upload-apk")
async def upload_apk(file: UploadFile = File(...), user_id: int = Form(None), db: Session = Depends(get_db)):
    """
    Receives an APK file, scans it for real, and persists application /
    version / scan / vulnerabilities / recommendation as ONE transaction
    (Part P/Q) - either the whole scan is recorded, or none of it is.
    Works for both logged-in and guest scans; either way the app becomes
    searchable, matching the existing (pre-Phase-7) guest-scan behavior.
    """
    if not file.filename.endswith('.apk'):
        raise HTTPException(status_code=400, detail="File must be an APK")

    fd, temp_path = tempfile.mkstemp(suffix=".apk")
    os.close(fd)

    try:
        size = 0
        with open(temp_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_APK_SIZE_BYTES:
                    raise HTTPException(status_code=413, detail=f"APK exceeds the {MAX_APK_SIZE_BYTES // (1024*1024)}MB upload limit.")
                buffer.write(chunk)

        scan_results = scan_apk_file(temp_path)
        # apk_scanner.scan_apk_file() only ever sees the temp file path
        # (it has no way to know the original upload's name), so its own
        # report["app_name"] is a meaningless "tmpXXXXXXXX.apk" - a real,
        # pre-existing bug (predates Phase 7). Fixed here at the API
        # layer, where the real filename is actually known, without
        # touching the scanner's detection logic at all.
        scan_results["app_name"] = file.filename

        # Flutter APK Scan implementation phase: real CWE-89/CWE-295
        # source-level findings, bridged from this APK's decompiled DEX
        # bytecode through the SAME predictor.py/dataflow.py pipeline the
        # IDE plugin uses (see apk_code_scanner.py's module docstring for
        # exactly how). Wrapped defensively - a decompilation problem on
        # some unusual APK must never take down the existing, reliable
        # manifest/permission/URL scan above; a genuinely empty result
        # (0 findings, 0 files scanned) is modeled the same way any other
        # "nothing found" result is modeled elsewhere: honestly, not as an
        # error.
        try:
            code_scan = scan_apk_for_code_vulnerabilities(temp_path)
        except Exception as e:
            logger.warning(f"[upload-apk] code-level CWE-89/CWE-295 scan failed: {e}")
            code_scan = None

        if code_scan is not None:
            cwe89_count = sum(1 for f in code_scan.findings if f["cwe"] == "CWE-89")
            cwe295_count = sum(1 for f in code_scan.findings if f["cwe"] == "CWE-295")
            scan_results["codeAnalysis"] = {
                "filesScanned": code_scan.files_scanned,
                "classesTotal": code_scan.classes_total,
                "filesSkippedThirdParty": code_scan.files_skipped_thirdparty,
                "truncated": code_scan.truncated,
                "truncationReason": code_scan.truncation_reason,
                "totalFindings": len(code_scan.findings),
                "cwe89Count": cwe89_count,
                "cwe295Count": cwe295_count,
                "findings": code_scan.findings,
                "note": (
                    "CWE-89/CWE-295 findings here come from decompiling this APK's DEX "
                    "bytecode back into reconstructed Java-like source (see each finding's "
                    "\"file\" path, prefixed 'decompiled/') and running it through the same "
                    "detection pipeline the DualVulnDroid IDE plugin uses. This is "
                    "decompiled, reconstructed code, not the app's original source."
                ),
            }
        else:
            scan_results["codeAnalysis"] = {
                "filesScanned": 0, "classesTotal": 0, "filesSkippedThirdParty": 0,
                "truncated": False, "truncationReason": None,
                "totalFindings": 0, "cwe89Count": 0, "cwe295Count": 0, "findings": [],
                "note": "Code-level CWE-89/CWE-295 analysis could not run for this APK.",
            }

        scan = crud.persist_apk_scan(db, user_id=user_id, scan_report=scan_results)
        scan_results["scan_id"] = scan.id

        # Phase 8A: additive, real-data application/version/scan block -
        # all existing top-level fields above are untouched, so existing
        # clients keep working. application_id/version_id are None here
        # only when the manifest genuinely had no usable package_name/
        # version, never guessed.
        application = scan.application
        app_version = scan.app_version
        scan_results["application"] = {
            "id": application.id,
            "packageName": application.package_name,
            "name": application.app_name,
        } if application else None
        scan_results["version"] = {
            "id": app_version.id,
            "versionName": app_version.version_name,
            "versionCode": app_version.version_code,
            # Phase 8B: real manifest facts about this specific build.
            "minSdkVersion": app_version.min_sdk_version,
            "targetSdkVersion": app_version.target_sdk_version,
            # Phase 8C: real <uses-feature> declarations and real
            # lib/<abi>/ directories found in this exact build.
            "features": app_version.features_json,
            "abis": app_version.abis_json,
        } if app_version else None
        scan_results["scan"] = {
            "id": scan.id,
            "status": scan.scan_status,
        }
        # Phase 8B: security-relevant manifest signals, kept separate from
        # the vulnerability-detection fields above on purpose (Part 11) -
        # these are NOT vulnerability findings, just facts a user may want
        # to weigh themselves. debuggable=True/allow_backup=True never
        # trigger a detection, risk_level change, or security_score
        # penalty anywhere in this file or apk_scanner.py.
        scan_results["securityMetadata"] = {
            "debuggable": app_version.debuggable if app_version else scan_results.get("debuggable"),
            "allowBackup": app_version.allow_backup if app_version else scan_results.get("allow_backup"),
        }

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return scan_results
