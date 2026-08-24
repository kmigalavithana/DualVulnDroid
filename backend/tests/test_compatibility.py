"""
Phase 8B/8C: unit tests for compatibility.py's pure, deterministic
functions - no DB, no APK, no mocking needed anywhere in this file.
"""

import compatibility


def _feature(name, required=None, required_explicit=False):
    return {"feature_name": name, "required": required, "required_explicit": required_explicit, "gl_es_version": None}


def test_compatible_when_device_android_version_meets_min_sdk():
    result = compatibility.evaluate_compatibility(min_sdk_version=23, android_version=30)
    assert result["status"] == compatibility.COMPATIBLE
    assert "satisfies" in result["reason"]


def test_compatible_when_device_android_version_exactly_equals_min_sdk():
    result = compatibility.evaluate_compatibility(min_sdk_version=23, android_version=23)
    assert result["status"] == compatibility.COMPATIBLE


def test_incompatible_when_device_android_version_below_min_sdk():
    result = compatibility.evaluate_compatibility(min_sdk_version=30, android_version=21)
    assert result["status"] == compatibility.INCOMPATIBLE
    assert "30" in result["reason"] and "21" in result["reason"]


def test_not_available_when_device_android_version_missing():
    result = compatibility.evaluate_compatibility(min_sdk_version=23, android_version=None)
    assert result["status"] == compatibility.NOT_AVAILABLE
    assert "Device Android version" in result["reason"]


def test_not_available_when_app_min_sdk_missing():
    result = compatibility.evaluate_compatibility(min_sdk_version=None, android_version=30)
    assert result["status"] == compatibility.NOT_AVAILABLE
    assert "minSdkVersion" in result["reason"]


def test_not_available_when_both_missing():
    result = compatibility.evaluate_compatibility(min_sdk_version=None, android_version=None)
    assert result["status"] == compatibility.NOT_AVAILABLE


def test_never_returns_a_bare_boolean():
    for min_sdk, android in [(23, 30), (30, 21), (23, None), (None, 30), (None, None)]:
        result = compatibility.evaluate_compatibility(min_sdk, android)
        assert result["status"] in (compatibility.COMPATIBLE, compatibility.INCOMPATIBLE, compatibility.NOT_AVAILABLE)
        assert isinstance(result["reason"], str) and result["reason"]


def test_hardware_compatibility_is_always_not_available_this_phase():
    # No verified source of an app's required RAM/architecture exists yet
    # - must never fabricate a hardware verdict, regardless of what the
    # caller's device profile contains.
    result = compatibility.hardware_compatibility_placeholder()
    assert result["status"] == compatibility.NOT_AVAILABLE
    assert "hardware" in result["reason"].lower()


# =====================================================
# Phase 8C, Part F: required-feature compatibility
# =====================================================
def test_required_feature_available_on_device():
    result = compatibility.evaluate_hardware_compatibility(
        required_features=[_feature("android.hardware.camera", True, True)],
        apk_abis=[], device_features=["android.hardware.camera"], device_abis=None,
    )
    assert result["checks"]["requiredFeatures"]["status"] == compatibility.COMPATIBLE
    assert result["status"] == compatibility.COMPATIBLE


def test_required_feature_missing_from_device():
    result = compatibility.evaluate_hardware_compatibility(
        required_features=[_feature("android.hardware.nfc", True, True)],
        apk_abis=[], device_features=["android.hardware.camera"], device_abis=None,
    )
    assert result["checks"]["requiredFeatures"]["status"] == compatibility.INCOMPATIBLE
    assert result["checks"]["requiredFeatures"]["missing"] == ["android.hardware.nfc"]
    assert result["status"] == compatibility.INCOMPATIBLE


def test_required_feature_device_data_unknown():
    result = compatibility.evaluate_hardware_compatibility(
        required_features=[_feature("android.hardware.nfc", True, True)],
        apk_abis=[], device_features=None, device_abis=None,
    )
    assert result["checks"]["requiredFeatures"]["status"] == compatibility.NOT_AVAILABLE
    assert result["status"] == compatibility.NOT_AVAILABLE


def test_optional_feature_missing_does_not_cause_incompatible():
    result = compatibility.evaluate_hardware_compatibility(
        required_features=[_feature("android.hardware.bluetooth", False, True)],
        apk_abis=[], device_features=[], device_abis=None,
    )
    assert result["checks"]["requiredFeatures"]["status"] == compatibility.COMPATIBLE


def test_absent_required_attribute_defaults_to_effectively_required():
    # Android's real platform default: android:required absent -> true.
    # This normalization happens here, explicitly, not in apk_scanner.py.
    result = compatibility.evaluate_hardware_compatibility(
        required_features=[_feature("android.hardware.telephony")],  # required=None, not explicit
        apk_abis=[], device_features=[], device_abis=None,
    )
    assert result["checks"]["requiredFeatures"]["status"] == compatibility.INCOMPATIBLE
    assert result["checks"]["requiredFeatures"]["missing"] == ["android.hardware.telephony"]


# =====================================================
# Phase 8C, Part G: ABI compatibility
# =====================================================
def test_abi_overlap_is_compatible():
    result = compatibility.evaluate_hardware_compatibility(
        required_features=[], apk_abis=["arm64-v8a", "armeabi-v7a"],
        device_features=None, device_abis=["arm64-v8a"],
    )
    assert result["checks"]["abi"]["status"] == compatibility.COMPATIBLE


def test_abi_mismatch_is_incompatible():
    result = compatibility.evaluate_hardware_compatibility(
        required_features=[], apk_abis=["x86", "x86_64"],
        device_features=None, device_abis=["arm64-v8a"],
    )
    assert result["checks"]["abi"]["status"] == compatibility.INCOMPATIBLE


def test_apk_with_no_native_libraries_is_abi_compatible():
    # No lib/<abi>/ directories at all -> pure managed/Dex code -> no ABI
    # constraint exists to violate, regardless of the device's ABIs.
    result = compatibility.evaluate_hardware_compatibility(
        required_features=[], apk_abis=[], device_features=None, device_abis=["x86"],
    )
    assert result["checks"]["abi"]["status"] == compatibility.COMPATIBLE


def test_abi_unknown_device_abis_with_real_apk_requirement_is_not_available():
    result = compatibility.evaluate_hardware_compatibility(
        required_features=[], apk_abis=["arm64-v8a"], device_features=None, device_abis=None,
    )
    assert result["checks"]["abi"]["status"] == compatibility.NOT_AVAILABLE


# =====================================================
# Phase 8C, Part H: combined compatibility
# =====================================================
def test_combined_compatibility_all_pass():
    result = compatibility.evaluate_full_compatibility(
        min_sdk_version=21, android_version=30,
        required_features=[_feature("android.hardware.camera", True, True)],
        apk_abis=["arm64-v8a"], device_features=["android.hardware.camera"], device_abis=["arm64-v8a"],
    )
    assert result["status"] == compatibility.COMPATIBLE
    assert result["checks"]["androidVersion"]["status"] == compatibility.COMPATIBLE
    assert result["checks"]["requiredFeatures"]["status"] == compatibility.COMPATIBLE
    assert result["checks"]["abi"]["status"] == compatibility.COMPATIBLE
    assert result["reasons"] == []


def test_combined_compatibility_one_check_incompatible_drives_overall_incompatible():
    result = compatibility.evaluate_full_compatibility(
        min_sdk_version=21, android_version=30,
        required_features=[_feature("android.hardware.nfc", True, True)],
        apk_abis=["arm64-v8a"], device_features=[], device_abis=["arm64-v8a"],
    )
    assert result["status"] == compatibility.INCOMPATIBLE
    assert any("android.hardware.nfc" in r for r in result["reasons"])


def test_combined_compatibility_missing_info_is_not_available_not_incompatible():
    # Android version and ABI are both fine; required-features data is
    # simply missing - must NOT be downgraded to INCOMPATIBLE.
    result = compatibility.evaluate_full_compatibility(
        min_sdk_version=21, android_version=30,
        required_features=[_feature("android.hardware.nfc", True, True)],
        apk_abis=["arm64-v8a"], device_features=None, device_abis=["arm64-v8a"],
    )
    assert result["status"] == compatibility.NOT_AVAILABLE
    assert result["checks"]["requiredFeatures"]["status"] == compatibility.NOT_AVAILABLE
    assert result["reasons"] == []  # NOT_AVAILABLE checks never contribute a "reason"


def test_combined_compatibility_missing_device_profile_entirely():
    result = compatibility.evaluate_full_compatibility(
        min_sdk_version=21, android_version=None,
        required_features=[_feature("android.hardware.nfc", True, True)],
        apk_abis=["arm64-v8a"], device_features=None, device_abis=None,
    )
    assert result["status"] == compatibility.NOT_AVAILABLE
    assert result["checks"]["androidVersion"]["status"] == compatibility.NOT_AVAILABLE
    assert result["checks"]["requiredFeatures"]["status"] == compatibility.NOT_AVAILABLE
    assert result["checks"]["abi"]["status"] == compatibility.NOT_AVAILABLE


# =====================================================
# Part I: security vs compatibility separation
# =====================================================
def test_compatibility_failure_does_not_appear_as_a_security_field():
    result = compatibility.evaluate_full_compatibility(
        min_sdk_version=30, android_version=15,  # INCOMPATIBLE Android version
        required_features=[], apk_abis=[], device_features=None, device_abis=None,
    )
    # The compatibility result has no notion of "vulnerability", "cwe",
    # "risk_level" etc. - it is a completely separate vocabulary.
    assert set(result.keys()) == {"status", "checks", "reasons"}
    assert "riskLevel" not in result and "vulnerable" not in result


def test_high_security_risk_always_avoid_installing_regardless_of_compatibility():
    for compat_status in (compatibility.COMPATIBLE, compatibility.INCOMPATIBLE, compatibility.NOT_AVAILABLE):
        result = compatibility.combine_security_and_compatibility("HIGH", "AVOID_INSTALLING", compat_status)
        assert result["recommendation"] == compatibility.AVOID_INSTALLING


def test_compatibility_success_never_upgrades_a_risky_app_to_safe():
    result = compatibility.combine_security_and_compatibility("CRITICAL", "AVOID_INSTALLING", compatibility.COMPATIBLE)
    assert result["recommendation"] == compatibility.AVOID_INSTALLING
    assert "safe" not in result["reason"].lower()


def test_low_risk_app_incompatible_device_is_device_specific_not_a_security_verdict():
    result = compatibility.combine_security_and_compatibility("LOW", "SAFE_TO_INSTALL", compatibility.INCOMPATIBLE)
    assert result["recommendation"] == compatibility.DO_NOT_INSTALL_ON_THIS_DEVICE
    assert result["recommendation"] != compatibility.AVOID_INSTALLING  # not framed as a security finding


def test_low_risk_app_compatible_device_passes_through_existing_recommendation():
    result = compatibility.combine_security_and_compatibility("LOW", "SAFE_TO_INSTALL", compatibility.COMPATIBLE)
    assert result["recommendation"] == "SAFE_TO_INSTALL"


def test_security_unavailable_is_its_own_explicit_state():
    result = compatibility.combine_security_and_compatibility(None, None, compatibility.COMPATIBLE)
    assert result["recommendation"] == compatibility.SECURITY_ASSESSMENT_UNAVAILABLE
