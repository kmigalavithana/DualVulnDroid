"""
Deterministic, real-data-only Android compatibility foundation (Phase 8B:
Android version; Phase 8C: required hardware features + native-library
ABI). This is explicitly NOT a full device-compatibility engine - see
each function's docstring for exactly what it does and does not answer.
It never determines whether an app will actually run well, whether it's
available in the user's region, or anything about real-world performance/
quality/RAM requirements (no verified source of an app's REQUIRED RAM
exists anywhere in this system, so RAM is never used as a compatibility
signal here, even though DeviceProfile accepts it for possible future use).

Pure and deterministic: no I/O, no database access, no external calls.
Callers are responsible for supplying real, already-verified application
metadata (from a stored AppVersion row) and a real, caller-supplied
device profile. This module never invents either.
"""

from typing import Optional

COMPATIBLE = "COMPATIBLE"
INCOMPATIBLE = "INCOMPATIBLE"
NOT_AVAILABLE = "NOT_AVAILABLE"


def evaluate_compatibility(min_sdk_version: Optional[int], android_version: Optional[int]) -> dict:
    """
    Compares a device's real Android API level against an application's
    real minSdkVersion (from its manifest). Returns one of three explicit
    states - COMPATIBLE, INCOMPATIBLE, NOT_AVAILABLE - never a bare
    true/false, and never a guess when either input is missing.

    minSdkVersion compatibility does NOT guarantee: app functionality,
    hardware compatibility (RAM/storage/CPU architecture), performance,
    security, or Play Store availability. It only reflects whether the
    OS API level requirement is satisfied.
    """
    if min_sdk_version is None:
        return {
            "status": NOT_AVAILABLE,
            "reason": "The application's minimum required Android version (minSdkVersion) is not available.",
        }
    if android_version is None:
        return {
            "status": NOT_AVAILABLE,
            "reason": "Device Android version is unavailable.",
        }

    if android_version >= min_sdk_version:
        return {
            "status": COMPATIBLE,
            "reason": "Device Android version satisfies the application's minimum SDK requirement.",
        }

    return {
        "status": INCOMPATIBLE,
        "reason": (
            f"Device Android version ({android_version}) is lower than the "
            f"application's minimum required Android version ({min_sdk_version})."
        ),
    }


def hardware_compatibility_placeholder() -> dict:
    """
    No verified source of an application's REQUIRED RAM or CPU model
    exists anywhere in this system (nothing in the manifest extraction
    reports this, and nothing else provides a trusted source for it), so
    this never fabricates a verdict for those specifically, even when the
    caller's device profile includes ramMb. Always NOT_AVAILABLE. This is
    distinct from evaluate_hardware_compatibility() below, which DOES
    have a real, verified source (the manifest's own <uses-feature> and
    native-library declarations) for features/ABI.
    """
    return {
        "status": NOT_AVAILABLE,
        "reason": "Verified hardware requirements (RAM/CPU model) are not available.",
    }


def _effective_required(feature: dict) -> bool:
    """
    Phase 8C, Part A/F: normalizes a <uses-feature> declaration's
    android:required to a plain bool for compatibility purposes.

    This is the ONE place that applies Android's real, documented
    platform default: when android:required is absent from the manifest,
    Android treats the feature as required=true. apk_scanner.py's
    extraction deliberately does NOT apply this default itself (it
    reports required=None + required_explicit=False for an absent
    attribute, so the raw manifest fact stays distinguishable) - this
    function is the single, explicitly-labeled place that default gets
    applied, only for the purpose of deciding compatibility.
    """
    if feature.get("required_explicit"):
        return bool(feature.get("required"))
    return True  # Android's real default for an absent android:required


def _evaluate_required_features(features: Optional[list], device_features: Optional[list]) -> dict:
    """
    Phase 8C, Part F: for every <uses-feature> declaration that is
    effectively required (see _effective_required), checks whether the
    device profile reports that feature as present.

    - No effectively-required features at all -> COMPATIBLE (nothing to
      fail). Optional (required=false) features are never evaluated here
      and never cause an INCOMPATIBLE result on their own.
    - Required features exist but device_features is None (genuinely
      unknown, not an empty list) -> NOT_AVAILABLE.
    - device_features is a real (possibly empty) list -> INCOMPATIBLE if
      any required feature is missing from it, listing exactly which;
      COMPATIBLE otherwise.
    """
    required_names = [
        f.get("feature_name") for f in (features or [])
        if f.get("feature_name") and _effective_required(f)
    ]
    if not required_names:
        return {"status": COMPATIBLE, "missing": []}
    if device_features is None:
        return {"status": NOT_AVAILABLE, "missing": []}

    device_feature_set = set(device_features)
    missing = [name for name in required_names if name not in device_feature_set]
    if missing:
        return {"status": INCOMPATIBLE, "missing": missing}
    return {"status": COMPATIBLE, "missing": []}


def _evaluate_abi(apk_abis: Optional[list], device_abis: Optional[list]) -> dict:
    """
    Phase 8C, Part G: real native-library ABI overlap check.

    - apk_abis is empty ([], not None - meaning the APK genuinely has no
      lib/<abi>/ directories) -> COMPATIBLE. A pure managed/Dex-code APK
      has no native-library ABI requirement at all, so there is nothing
      for a device to fail to satisfy; ABI evidence alone must never be
      treated as automatic incompatibility (documented limitation: this
      does NOT rule out other reasons the app might not run).
    - apk_abis is non-empty but device_abis is None (genuinely unknown)
      -> NOT_AVAILABLE: a real constraint exists but can't be checked.
    - Both known -> COMPATIBLE if at least one APK ABI is in the device's
      supported ABI list, else INCOMPATIBLE.
    """
    if not apk_abis:
        return {"status": COMPATIBLE}
    if device_abis is None:
        return {"status": NOT_AVAILABLE}

    if set(apk_abis) & set(device_abis):
        return {"status": COMPATIBLE}
    return {"status": INCOMPATIBLE}


# Worst-first priority when combining several individual check statuses
# into one overall status: any real incompatibility always wins, then
# any missing information, and only COMPATIBLE if every check that ran
# actually passed. This is what "never downgrade to INCOMPATIBLE merely
# because information is missing" means in practice - NOT_AVAILABLE can
# only be produced by a genuine information gap, never manufactured by
# this priority ordering itself.
_STATUS_PRIORITY = {INCOMPATIBLE: 2, NOT_AVAILABLE: 1, COMPATIBLE: 0}


def evaluate_hardware_compatibility(required_features: Optional[list], apk_abis: Optional[list],
                                     device_features: Optional[list], device_abis: Optional[list]) -> dict:
    """
    Phase 8C, Part D: combines the required-<uses-feature> check (Part F)
    and the native-library ABI check (Part G) into one hardware
    compatibility verdict. Android-version compatibility is intentionally
    NOT included here - see evaluate_compatibility() and app.py's
    combined /apps/{id}/compatibility response for how the two are
    composed together (Part H).

    required_features: AppVersion.features_json - list of
        {feature_name, required, required_explicit, gl_es_version} dicts.
    apk_abis: AppVersion.abis_json - list of real ABI name strings.
    device_features/device_abis: caller-supplied DeviceProfile lists, or
        None when the caller didn't provide them (a real "unknown", not
        an empty list meaning "device has nothing").
    """
    features_result = _evaluate_required_features(required_features, device_features)
    abi_result = _evaluate_abi(apk_abis, device_abis)

    overall = max((features_result["status"], abi_result["status"]), key=lambda s: _STATUS_PRIORITY[s])

    return {
        "status": overall,
        "checks": {
            "requiredFeatures": features_result,
            "abi": abi_result,
        },
    }


def evaluate_full_compatibility(min_sdk_version: Optional[int], android_version: Optional[int],
                                 required_features: Optional[list], apk_abis: Optional[list],
                                 device_features: Optional[list], device_abis: Optional[list]) -> dict:
    """
    Phase 8C, Part H: the single combined compatibility response -
    Android version (Part D/8B) + required features (Part F) + ABI
    (Part G) - in the exact shape described in the phase spec:
    {"status": ..., "checks": {"androidVersion": {...}, "requiredFeatures": {...}, "abi": {...}}, "reasons": [...]}.

    "reasons" only ever lists real, human-readable explanations for
    whichever checks actually failed (INCOMPATIBLE) - never populated
    from a NOT_AVAILABLE or COMPATIBLE check, and never a generic
    boilerplate line.
    """
    android_result = evaluate_compatibility(min_sdk_version, android_version)
    hardware_result = evaluate_hardware_compatibility(required_features, apk_abis, device_features, device_abis)
    features_result = hardware_result["checks"]["requiredFeatures"]
    abi_result = hardware_result["checks"]["abi"]

    overall = max(
        (android_result["status"], features_result["status"], abi_result["status"]),
        key=lambda s: _STATUS_PRIORITY[s],
    )

    reasons = []
    if android_result["status"] == INCOMPATIBLE:
        reasons.append(android_result["reason"])
    if features_result["status"] == INCOMPATIBLE:
        for name in features_result["missing"]:
            reasons.append(f"Required hardware feature is not available on the device: {name}.")
    if abi_result["status"] == INCOMPATIBLE:
        reasons.append("The device's CPU architecture does not match any architecture this application was built for.")

    return {
        "status": overall,
        "checks": {
            "androidVersion": {"status": android_result["status"]},
            "requiredFeatures": {"status": features_result["status"], "missing": features_result["missing"]},
            "abi": {"status": abi_result["status"]},
        },
        "reasons": reasons,
    }


# =====================================================
# Part J: user decision foundation - combines a REAL security assessment
# (from the existing decision engine's stored result, never recomputed
# here) with a REAL compatibility assessment into one final, explicit
# recommendation. Never claims "safe" merely because compatibility is
# good, and never lets a compatibility problem masquerade as a security
# finding (Part I: the two stay completely separate signals).
# =====================================================

SECURITY_ASSESSMENT_UNAVAILABLE = "SECURITY_ASSESSMENT_UNAVAILABLE"
DO_NOT_INSTALL_ON_THIS_DEVICE = "DO_NOT_INSTALL_ON_THIS_DEVICE"

# Reused from db/models.py's RecommendationDecision vocabulary rather
# than inventing a parallel one - these are the SAME strings the
# existing decision engine already produces for a security-only
# assessment. Duplicated here (not imported) to keep this module free of
# a database dependency, per its own "pure, no I/O" contract.
AVOID_INSTALLING = "AVOID_INSTALLING"
HIGH_RISK_LEVELS = {"HIGH", "CRITICAL"}


def combine_security_and_compatibility(security_risk_level: Optional[str],
                                        security_recommendation: Optional[str],
                                        compatibility_status: str) -> dict:
    """
    security_risk_level/security_recommendation: the EXISTING decision
    engine's real, already-computed result for this scan (e.g. scan.risk_level,
    scan.recommendation) - this function never recalculates or second-guesses
    them, only combines them with compatibility.
    compatibility_status: COMPATIBLE / INCOMPATIBLE / NOT_AVAILABLE, from
    evaluate_full_compatibility()["status"].

    Decision table (security always takes priority over compatibility -
    a dangerous app is dangerous regardless of whether it happens to run):
      security unavailable                          -> SECURITY_ASSESSMENT_UNAVAILABLE
      security HIGH/CRITICAL                         -> AVOID_INSTALLING (compatibility irrelevant)
      security acceptable + compatibility INCOMPATIBLE -> DO_NOT_INSTALL_ON_THIS_DEVICE
      security acceptable + compatibility COMPATIBLE/NOT_AVAILABLE -> the existing
        security_recommendation, unchanged (this function never claims "safe"
        by itself - it only ever passes through what the decision engine
        already concluded).
    """
    if security_risk_level is None:
        return {
            "recommendation": SECURITY_ASSESSMENT_UNAVAILABLE,
            "reason": "This application has not been security-assessed yet.",
        }

    if security_risk_level.upper() in HIGH_RISK_LEVELS:
        return {
            "recommendation": AVOID_INSTALLING,
            "reason": "The security assessment found a high-risk result; device compatibility does not change this.",
        }

    if compatibility_status == INCOMPATIBLE:
        return {
            "recommendation": DO_NOT_INSTALL_ON_THIS_DEVICE,
            "reason": "The security assessment did not find a high-risk result, but this application is not compatible with the specified device.",
        }

    return {
        "recommendation": security_recommendation or "MANUAL_REVIEW",
        "reason": "Based on the existing security assessment; compatibility does not by itself make an application safe.",
    }
