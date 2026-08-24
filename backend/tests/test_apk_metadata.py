"""
Phase 8A: tests for apk_scanner.extract_apk_metadata() - real
package_name / version_name / version_code / application_label /
permissions extraction from an APK's actual AndroidManifest.xml via
pyaxmlparser (a genuine binary-AXML decoder).

Two clearly separated kinds of test live here:

1. Parser-boundary UNIT tests (the majority of this file): they
   monkeypatch pyaxmlparser.APK itself with a small fake object exposing
   the same attributes (.package, .version_name, .version_code,
   .application, .permissions). These test OUR field-mapping/guard logic
   in extract_apk_metadata() - e.g. "a non-numeric versionCode becomes
   None, not a crash" - deterministically and portably (no real APK
   needed, safe to run in CI). They do NOT verify that pyaxmlparser
   itself can decode real binary AXML.

2. One real-APK INTEGRATION test at the bottom, which only runs against
   an actual compiled Android APK (genuine binary AXML, not a synthetic
   fixture) if one is available. This repo does not ship a real .apk
   fixture (committing one is impractical - real compiled APKs are
   megabytes and require the Android build toolchain, which isn't
   available in this project's environment; see Phase 8A's final
   report for how this was verified by hand instead: a real third-party
   APK was scanned via TestClient.post("/upload-apk") and the extracted
   package_name/version_name/version_code were confirmed against the
   APK's actual manifest). Point REAL_APK_FIXTURE_PATH at a real .apk to
   run it locally; otherwise it SKIPS honestly, the same pattern already
   used by tests/test_db_integration.py for MySQL.
"""

import os
import zipfile

import pytest

import apk_scanner


class _FakeAPK:
    """Stands in for pyaxmlparser.APK(path) at the constructor boundary -
    lets us drive extract_apk_metadata()'s field-mapping logic with known
    inputs without needing a real binary-AXML file on disk."""

    def __init__(self, package=None, version_name=None, version_code=None,
                 application=None, permissions=None, min_sdk_version=None,
                 target_sdk_version=None, debuggable_attr=None, allow_backup_attr=None,
                 uses_feature_tags=None, raise_on=None):
        self._package = package
        self._version_name = version_name
        self._version_code = version_code
        self._application = application
        self._permissions = permissions if permissions is not None else []
        # Raw strings, exactly as pyaxmlparser's real methods return them -
        # e.g. debuggable_attr="true"/"false"/None (attribute absent).
        self._min_sdk_version = min_sdk_version
        self._target_sdk_version = target_sdk_version
        self._debuggable_attr = debuggable_attr
        self._allow_backup_attr = allow_backup_attr
        # list of dicts like {"name": "android.hardware.camera", "required": "true"}
        # (values None/omitted mean the attribute is absent, exactly
        # like a real manifest with no android:required on that tag)
        self._uses_feature_tags = uses_feature_tags or []
        self._raise_on = raise_on or set()

    @property
    def package(self):
        if "package" in self._raise_on:
            raise RuntimeError("simulated manifest read failure (package)")
        return self._package

    @property
    def version_name(self):
        if "version_name" in self._raise_on:
            raise RuntimeError("simulated manifest read failure (version_name)")
        return self._version_name

    @property
    def version_code(self):
        if "version_code" in self._raise_on:
            raise RuntimeError("simulated manifest read failure (version_code)")
        return self._version_code

    @property
    def application(self):
        if "application" in self._raise_on:
            raise RuntimeError("simulated manifest read failure (application)")
        return self._application

    @property
    def permissions(self):
        if "permissions" in self._raise_on:
            raise RuntimeError("simulated manifest read failure (permissions)")
        return self._permissions

    def get_min_sdk_version(self):
        if "min_sdk_version" in self._raise_on:
            raise RuntimeError("simulated manifest read failure (min_sdk_version)")
        return self._min_sdk_version

    def get_target_sdk_version(self):
        if "target_sdk_version" in self._raise_on:
            raise RuntimeError("simulated manifest read failure (target_sdk_version)")
        return self._target_sdk_version

    def get_attribute_value(self, tag_name, attribute, format_value=False, **kwargs):
        if tag_name == "application" and attribute == "debuggable":
            if "debuggable" in self._raise_on:
                raise RuntimeError("simulated manifest read failure (debuggable)")
            return self._debuggable_attr
        if tag_name == "application" and attribute == "allowBackup":
            if "allow_backup" in self._raise_on:
                raise RuntimeError("simulated manifest read failure (allow_backup)")
            return self._allow_backup_attr
        return None

    def find_tags(self, tag_name, **kwargs):
        if "uses_feature" in self._raise_on:
            raise RuntimeError("simulated manifest read failure (uses-feature tags)")
        if tag_name == "uses-feature":
            return [_FakeElement(t) for t in self._uses_feature_tags]
        return []


class _FakeElement:
    """Minimal stand-in for an lxml Element - just enough of .get(key) to
    drive apk_scanner._extract_uses_features(), which reads
    NS_ANDROID + "name"/"required"/"glEsVersion" via this exact API."""

    def __init__(self, attrs_by_plain_name: dict):
        from apk_scanner import NS_ANDROID
        self._attrs = {NS_ANDROID + k: v for k, v in attrs_by_plain_name.items() if v is not None}

    def get(self, key):
        return self._attrs.get(key)


# =====================================================
# 1. Valid extraction - all fields present
# =====================================================
def test_valid_apk_metadata_extraction(monkeypatch):
    fake = _FakeAPK(
        package="com.example.realapp", version_name="2.4.1", version_code="241",
        application="Real App", permissions=["android.permission.INTERNET", "android.permission.CAMERA"],
        min_sdk_version="23", target_sdk_version="35", debuggable_attr="false", allow_backup_attr="true",
    )
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)

    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")

    assert result["package_name"] == "com.example.realapp"
    assert result["version_name"] == "2.4.1"
    assert result["version_code"] == 241  # coerced to int, matching AppVersion.version_code
    assert result["application_label"] == "Real App"
    assert result["permissions"] == ["android.permission.INTERNET", "android.permission.CAMERA"]
    assert result["min_sdk_version"] == 23
    assert result["target_sdk_version"] == 35
    assert result["debuggable"] is False
    assert result["allow_backup"] is True
    assert result["manifest_parse_error"] is None


# =====================================================
# 2. Package name
# =====================================================
def test_package_name_extracted(monkeypatch):
    fake = _FakeAPK(package="com.example.myapp")
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["package_name"] == "com.example.myapp"


def test_package_name_empty_string_becomes_none(monkeypatch):
    # pyaxmlparser returns '' (not None) when it can't resolve a package -
    # extract_apk_metadata must not treat '' as a real value.
    fake = _FakeAPK(package="")
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["package_name"] is None
    assert result["manifest_parse_error"] is not None


# =====================================================
# 3. Version name
# =====================================================
def test_version_name_extracted(monkeypatch):
    fake = _FakeAPK(package="com.example.myapp", version_name="1.0.0")
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["version_name"] == "1.0.0"


# =====================================================
# 4. Version code
# =====================================================
def test_version_code_extracted_and_coerced_to_int(monkeypatch):
    fake = _FakeAPK(package="com.example.myapp", version_code="30")
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["version_code"] == 30
    assert isinstance(result["version_code"], int)


def test_non_numeric_version_code_becomes_none_not_a_crash(monkeypatch):
    fake = _FakeAPK(package="com.example.myapp", version_code="not-a-number")
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["version_code"] is None  # never guessed/defaulted to 0 or 1


# =====================================================
# 5. Application label
# =====================================================
def test_application_label_extracted(monkeypatch):
    fake = _FakeAPK(package="com.example.myapp", application="My Cool App")
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["application_label"] == "My Cool App"


def test_application_label_unresolvable_is_null_not_filename(monkeypatch):
    fake = _FakeAPK(package="com.example.myapp", application=None)
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("some/upload/tmpABC123.apk")
    assert result["application_label"] is None
    assert result["application_label"] != "tmpABC123.apk"


# =====================================================
# 6. Permissions
# =====================================================
def test_permissions_extracted_as_list(monkeypatch):
    perms = ["android.permission.INTERNET", "android.permission.READ_SMS"]
    fake = _FakeAPK(package="com.example.myapp", permissions=perms)
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["permissions"] == perms


def test_no_permissions_is_empty_list_not_none(monkeypatch):
    fake = _FakeAPK(package="com.example.myapp", permissions=[])
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["permissions"] == []


# =====================================================
# 7. Invalid APK (constructor itself fails - e.g. not a zip, no manifest)
# =====================================================
def test_invalid_apk_does_not_crash_and_reports_error(monkeypatch):
    def _raise(path):
        raise ValueError("not a valid APK")
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", _raise)

    result = apk_scanner.extract_apk_metadata("corrupted.apk")

    assert result["package_name"] is None
    assert result["version_name"] is None
    assert result["version_code"] is None
    assert result["application_label"] is None
    assert result["permissions"] == []
    assert result["min_sdk_version"] is None
    assert result["target_sdk_version"] is None
    assert result["debuggable"] is None
    assert result["allow_backup"] is None
    assert "not a valid APK" in result["manifest_parse_error"]


def test_partial_manifest_failure_still_returns_fields_that_did_parse(monkeypatch):
    # A manifest that yields a real package name but blows up reading
    # versionCode (malformed attribute) should still report the package
    # name it DID genuinely read - partial real data, not an all-or-nothing
    # failure.
    fake = _FakeAPK(package="com.example.myapp", raise_on={"version_code"})
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["package_name"] == "com.example.myapp"
    assert result["version_code"] is None


# =====================================================
# 8. Missing version metadata entirely
# =====================================================
def test_missing_version_metadata_stores_none_not_guessed(monkeypatch):
    fake = _FakeAPK(package="com.example.myapp", version_name=None, version_code=None)
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["package_name"] == "com.example.myapp"
    assert result["version_name"] is None
    assert result["version_code"] is None


# =====================================================
# Phase 8B: minSdkVersion / targetSdkVersion / debuggable / allowBackup
# =====================================================
def test_min_sdk_version_extracted(monkeypatch):
    fake = _FakeAPK(package="com.example.myapp", min_sdk_version="23")
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["min_sdk_version"] == 23
    assert isinstance(result["min_sdk_version"], int)


def test_target_sdk_version_extracted(monkeypatch):
    fake = _FakeAPK(package="com.example.myapp", target_sdk_version="35")
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["target_sdk_version"] == 35


def test_explicit_debuggable_true(monkeypatch):
    fake = _FakeAPK(package="com.example.myapp", debuggable_attr="true")
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["debuggable"] is True


def test_explicit_debuggable_false(monkeypatch):
    fake = _FakeAPK(package="com.example.myapp", debuggable_attr="false")
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["debuggable"] is False


def test_missing_debuggable_is_none_not_false():
    # Distinguishes "explicitly false" from "attribute absent" - Android's
    # effective runtime default for a missing android:debuggable is
    # false, but this function reports the RAW manifest attribute, so an
    # absent attribute must be None, never silently coerced to False.
    import apk_scanner as scanner
    assert scanner._parse_manifest_bool(None) is None


def test_explicit_allow_backup_true(monkeypatch):
    fake = _FakeAPK(package="com.example.myapp", allow_backup_attr="true")
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["allow_backup"] is True


def test_explicit_allow_backup_false(monkeypatch):
    fake = _FakeAPK(package="com.example.myapp", allow_backup_attr="false")
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["allow_backup"] is False


def test_missing_allow_backup_is_none_not_true():
    # Android's effective runtime default for a missing android:allowBackup
    # is true, but again: raw manifest value only, never silently
    # substituted with that platform default.
    import apk_scanner as scanner
    assert scanner._parse_manifest_bool(None) is None


def test_malformed_min_sdk_version_becomes_none_not_a_crash(monkeypatch):
    fake = _FakeAPK(package="com.example.myapp", min_sdk_version="not-a-number")
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["min_sdk_version"] is None


def test_malformed_debuggable_value_becomes_none_not_a_crash(monkeypatch):
    # A manifest with a nonsensical android:debuggable value (not the XML
    # literal "true"/"false") must not crash or be guessed either way.
    fake = _FakeAPK(package="com.example.myapp", debuggable_attr="maybe")
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["debuggable"] is None


def test_partial_failure_on_sdk_and_flags_still_returns_core_fields(monkeypatch):
    fake = _FakeAPK(
        package="com.example.myapp", version_name="1.0",
        raise_on={"min_sdk_version", "target_sdk_version", "debuggable", "allow_backup"},
    )
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    # Core fields that parsed fine are still returned...
    assert result["package_name"] == "com.example.myapp"
    assert result["version_name"] == "1.0"
    # ...even though every Phase 8B field failed to read.
    assert result["min_sdk_version"] is None
    assert result["target_sdk_version"] is None
    assert result["debuggable"] is None
    assert result["allow_backup"] is None


def test_debuggable_and_allow_backup_true_do_not_create_a_vulnerability(monkeypatch, tmp_path):
    # Phase 8B, Part 11: these are metadata signals, never an automatic
    # CWE finding, risk_level change, or security_score penalty - the
    # existing vulnerability-detection logic (unrelated raw-string
    # cleartext/permission checks) must produce an identical result
    # regardless of debuggable/allow_backup.
    import zipfile

    def _make_apk(path):
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("AndroidManifest.xml", "<manifest></manifest>")

    fake_risky = _FakeAPK(package="com.example.myapp", debuggable_attr="true", allow_backup_attr="true")
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake_risky)
    apk_path = tmp_path / "risky_flags.apk"
    _make_apk(apk_path)
    report = apk_scanner.scan_apk_file(str(apk_path))

    assert report["debuggable"] is True
    assert report["allow_backup"] is True
    assert report["vulnerable"] is False
    assert report["risk_level"] == "low"
    assert report["detections"] == []
    assert report["security_score"] == 100


# =====================================================
# Phase 8C, Part A: <uses-feature> extraction
# =====================================================
def test_no_uses_feature_declarations(monkeypatch):
    fake = _FakeAPK(package="com.example.myapp", uses_feature_tags=[])
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["features"] == []


def test_one_required_feature(monkeypatch):
    fake = _FakeAPK(package="com.example.myapp", uses_feature_tags=[
        {"name": "android.hardware.camera", "required": "true"},
    ])
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["features"] == [
        {"feature_name": "android.hardware.camera", "gl_es_version": None, "required": True, "required_explicit": True},
    ]


def test_one_optional_feature(monkeypatch):
    fake = _FakeAPK(package="com.example.myapp", uses_feature_tags=[
        {"name": "android.hardware.camera.autofocus", "required": "false"},
    ])
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["features"] == [
        {"feature_name": "android.hardware.camera.autofocus", "gl_es_version": None, "required": False, "required_explicit": True},
    ]


def test_multiple_features(monkeypatch):
    fake = _FakeAPK(package="com.example.myapp", uses_feature_tags=[
        {"name": "android.hardware.camera", "required": "true"},
        {"name": "android.hardware.location.gps", "required": "true"},
        {"name": "android.hardware.bluetooth", "required": "false"},
        {"name": "android.hardware.nfc"},
    ])
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    names = [f["feature_name"] for f in result["features"]]
    assert names == ["android.hardware.camera", "android.hardware.location.gps",
                      "android.hardware.bluetooth", "android.hardware.nfc"]


def test_missing_required_attribute_is_none_with_explicit_flag_false(monkeypatch):
    # android:required genuinely absent from this <uses-feature> tag -
    # must be reported as None/not-explicit, never silently guessed
    # either way at the extraction layer (the Android-default
    # normalization happens later, explicitly, in compatibility.py).
    fake = _FakeAPK(package="com.example.myapp", uses_feature_tags=[
        {"name": "android.hardware.sensor.accelerometer"},
    ])
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["features"][0]["required"] is None
    assert result["features"][0]["required_explicit"] is False


def test_malformed_feature_declaration_is_skipped_not_a_crash(monkeypatch):
    # A <uses-feature> tag with neither name nor glEsVersion is not a
    # usable declaration at all - dropped, not reported as a phantom
    # feature with feature_name=None.
    fake = _FakeAPK(package="com.example.myapp", uses_feature_tags=[
        {"required": "true"},  # no name, no glEsVersion - unusable
        {"name": "android.hardware.sensor.gyroscope", "required": "true"},
    ])
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert len(result["features"]) == 1
    assert result["features"][0]["feature_name"] == "android.hardware.sensor.gyroscope"


def test_gl_es_version_feature_captured(monkeypatch):
    fake = _FakeAPK(package="com.example.myapp", uses_feature_tags=[
        {"glEsVersion": "0x00020000", "required": "true"},
    ])
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["features"][0]["gl_es_version"] == "0x00020000"
    assert result["features"][0]["feature_name"] is None


def test_uses_feature_failure_does_not_crash_extraction(monkeypatch):
    fake = _FakeAPK(package="com.example.myapp", raise_on={"uses_feature"})
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["package_name"] == "com.example.myapp"  # unaffected
    assert result["features"] == []


def test_uses_feature_is_not_confused_with_uses_permission(monkeypatch):
    # Distinct manifest concepts - a uses-feature declaration must never
    # show up in permissions, and vice versa.
    fake = _FakeAPK(
        package="com.example.myapp",
        permissions=["android.permission.CAMERA"],
        uses_feature_tags=[{"name": "android.hardware.camera", "required": "true"}],
    )
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    result = apk_scanner.extract_apk_metadata("irrelevant/path.apk")
    assert result["permissions"] == ["android.permission.CAMERA"]
    assert [f["feature_name"] for f in result["features"]] == ["android.hardware.camera"]


# =====================================================
# Phase 8C, Part B: ABI extraction from real ZIP contents
# =====================================================
def test_abi_detection_single_abi(tmp_path):
    apk_path = tmp_path / "single_abi.apk"
    with zipfile.ZipFile(apk_path, "w") as z:
        z.writestr("lib/arm64-v8a/libfoo.so", b"fake")
        z.writestr("classes.dex", b"fake")
    assert apk_scanner.extract_apk_abis(str(apk_path)) == ["arm64-v8a"]


def test_abi_detection_multiple_abis(tmp_path):
    apk_path = tmp_path / "multi_abi.apk"
    with zipfile.ZipFile(apk_path, "w") as z:
        z.writestr("lib/arm64-v8a/libfoo.so", b"fake")
        z.writestr("lib/armeabi-v7a/libfoo.so", b"fake")
        z.writestr("lib/x86_64/libfoo.so", b"fake")
    assert apk_scanner.extract_apk_abis(str(apk_path)) == ["arm64-v8a", "armeabi-v7a", "x86_64"]


def test_abi_detection_ignores_non_abi_lib_subdirectories(tmp_path):
    apk_path = tmp_path / "bogus_abi.apk"
    with zipfile.ZipFile(apk_path, "w") as z:
        z.writestr("lib/arm64-v8a/libfoo.so", b"fake")
        z.writestr("lib/not-a-real-abi/libfoo.so", b"fake")
    assert apk_scanner.extract_apk_abis(str(apk_path)) == ["arm64-v8a"]


def test_apk_without_native_libraries_has_empty_abi_list(tmp_path):
    apk_path = tmp_path / "no_native.apk"
    with zipfile.ZipFile(apk_path, "w") as z:
        z.writestr("classes.dex", b"fake")
        z.writestr("AndroidManifest.xml", "<manifest></manifest>")
    assert apk_scanner.extract_apk_abis(str(apk_path)) == []


def test_abi_extraction_never_crashes_on_invalid_zip(tmp_path):
    bad_path = tmp_path / "not_a_zip.apk"
    bad_path.write_bytes(b"this is not a zip file")
    assert apk_scanner.extract_apk_abis(str(bad_path)) == []


# =====================================================
# scan_apk_file() integration with extract_apk_metadata() - the metadata
# fields actually reach the report dict returned to app.py, and a
# metadata-parse failure never prevents the existing (unrelated)
# cleartext-traffic/permission/URL detection logic from running.
# =====================================================
def test_scan_apk_file_merges_metadata_into_report(monkeypatch, tmp_path):
    fake = _FakeAPK(
        package="com.example.realapp", version_name="9.9.9", version_code="99",
        application="Real App", permissions=["android.permission.INTERNET"],
        min_sdk_version="24", target_sdk_version="34", debuggable_attr="false", allow_backup_attr="true",
    )
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)

    # A minimal real zip (so the existing zipfile-based detection logic
    # has something valid to open) with a plain-text manifest - fine here
    # since this test targets the metadata-merge wiring, not AXML
    # decoding (that's covered by the mocked unit tests above).
    import zipfile
    apk_path = tmp_path / "sample.apk"
    with zipfile.ZipFile(apk_path, "w") as z:
        z.writestr("AndroidManifest.xml", "<manifest package=\"com.example.realapp\"></manifest>")

    report = apk_scanner.scan_apk_file(str(apk_path))

    assert report["package_name"] == "com.example.realapp"
    assert report["version_name"] == "9.9.9"
    assert report["version_code"] == 99
    assert report["application_label"] == "Real App"
    assert report["permissions"] == ["android.permission.INTERNET"]
    assert report["min_sdk_version"] == 24
    assert report["target_sdk_version"] == 34
    assert report["debuggable"] is False
    assert report["allow_backup"] is True
    assert report["manifest_parse_error"] is None


def test_scan_apk_file_metadata_failure_does_not_block_existing_detection(monkeypatch, tmp_path):
    def _raise(path):
        raise ValueError("cannot decode manifest")
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", _raise)

    import zipfile
    apk_path = tmp_path / "sample.apk"
    with zipfile.ZipFile(apk_path, "w") as z:
        z.writestr("AndroidManifest.xml", 'usesCleartextTraffic="true"')

    report = apk_scanner.scan_apk_file(str(apk_path))

    # Metadata extraction failed honestly...
    assert report["package_name"] is None
    assert report["manifest_parse_error"] is not None
    # ...but the existing, unrelated raw-string detection still ran.
    assert report["vulnerable"] is True


# =====================================================
# Real-APK integration test - only runs with a genuine compiled APK.
# =====================================================
_REAL_APK_PATH = os.environ.get("REAL_APK_FIXTURE_PATH")


@pytest.mark.skipif(
    not _REAL_APK_PATH or not os.path.isfile(_REAL_APK_PATH),
    reason=(
        "REAL_APK_FIXTURE_PATH is not set to a real, compiled Android APK - "
        "skipping the real-manifest integration test. This repo doesn't ship "
        "a genuine .apk fixture (real compiled AXML requires the Android "
        "build toolchain). Set REAL_APK_FIXTURE_PATH to any real .apk to run "
        "this for real."
    ),
)
def test_real_apk_manifest_extraction():
    result = apk_scanner.extract_apk_metadata(_REAL_APK_PATH)
    assert result["manifest_parse_error"] is None
    assert result["package_name"]  # some genuinely non-empty real value
    assert isinstance(result["permissions"], list)
    # Phase 8B fields: not asserted to any specific value (this fixture's
    # real content isn't controlled by this test), just that extraction
    # didn't crash and produced a plausible type when present.
    assert result["min_sdk_version"] is None or isinstance(result["min_sdk_version"], int)
    assert result["target_sdk_version"] is None or isinstance(result["target_sdk_version"], int)
    assert result["debuggable"] is None or isinstance(result["debuggable"], bool)
    assert result["allow_backup"] is None or isinstance(result["allow_backup"], bool)
    # Phase 8C: features is always a real list (possibly empty - this
    # fixture may genuinely declare none), never asserted non-empty since
    # that depends on the specific real APK provided.
    assert isinstance(result["features"], list)
    for feature in result["features"]:
        assert "feature_name" in feature and "required" in feature and "required_explicit" in feature


@pytest.mark.skipif(
    not _REAL_APK_PATH or not os.path.isfile(_REAL_APK_PATH),
    reason=(
        "REAL_APK_FIXTURE_PATH is not set to a real, compiled Android APK - "
        "skipping the real-ABI integration test."
    ),
)
def test_real_apk_abi_extraction():
    abis = apk_scanner.extract_apk_abis(_REAL_APK_PATH)
    assert isinstance(abis, list)
    for abi in abis:
        assert abi in apk_scanner._KNOWN_ABIS


# =====================================================
# Phase 10B: deterministic, evidence-based explanations for vulnerable
# APK scans. All fixtures are synthetic zips with a plain-text manifest -
# fine here since these tests target the raw-string detection + explanation
# logic (already the established pattern in this file), not AXML decoding.
# =====================================================

def _make_apk(tmp_path, name, manifest_text, extra_files=None):
    apk_path = tmp_path / name
    with zipfile.ZipFile(apk_path, "w") as z:
        z.writestr("AndroidManifest.xml", manifest_text)
        for fname, content in (extra_files or {}).items():
            z.writestr(fname, content)
    return str(apk_path)


# 1. Safe APK explanation
def test_safe_apk_explanation_unchanged(tmp_path):
    path = _make_apk(tmp_path, "safe.apk", 'android.permission.INTERNET')
    report = apk_scanner.scan_apk_file(path)
    assert report["vulnerable"] is False
    assert report["explanation"] == "No cleartext traffic, dangerous permissions, or suspicious URLs found in this scan."


# 2. Cleartext-only finding
def test_cleartext_only_explanation(tmp_path):
    path = _make_apk(tmp_path, "cleartext.apk", 'usesCleartextTraffic="true"')
    report = apk_scanner.scan_apk_file(path)
    assert report["vulnerable"] is True
    assert report["explanation"] == (
        "The APK declares cleartext traffic, which may allow network "
        "communications to occur without transport encryption."
    )


# 3. Dangerous-permission-only finding
def test_dangerous_permission_only_explanation(tmp_path):
    path = _make_apk(tmp_path, "perms.apk", 'android.permission.CAMERA android.permission.READ_CONTACTS')
    report = apk_scanner.scan_apk_file(path)
    assert report["vulnerable"] is True
    assert report["explanation"] == "The APK requests potentially sensitive Android permissions: CAMERA, READ_CONTACTS."


# 4. Suspicious-URL-only finding
def test_suspicious_url_only_explanation(tmp_path):
    # No cleartext flag, no dangerous permission - only a malicious-looking
    # URL (IP-literal host) embedded in a non-manifest file.
    path = _make_apk(tmp_path, "urls.apk", 'android.permission.INTERNET',
                      extra_files={"assets/config.json": "http://192.168.1.1/payload"})
    report = apk_scanner.scan_apk_file(path)
    assert report["vulnerable"] is True
    assert report["dangerous_permissions"] == []
    assert report["explanation"] == "The APK contains 1 suspicious URL identified during static analysis."


# 5. Multiple findings
def test_multiple_findings_explanation(tmp_path):
    path = _make_apk(tmp_path, "multi.apk", 'usesCleartextTraffic="true" android.permission.CAMERA')
    report = apk_scanner.scan_apk_file(path)
    assert report["vulnerable"] is True
    assert report["explanation"] == "The scan identified multiple security concerns: cleartext traffic and sensitive permissions."


# 6. Deterministic explanation ordering
def test_explanation_is_deterministic_across_repeated_scans(tmp_path):
    # Multiple category findings - the short-label summary must be
    # byte-identical across repeated scans of the same APK.
    path = _make_apk(tmp_path, "det.apk", 'usesCleartextTraffic="true" android.permission.CAMERA android.permission.READ_SMS')
    report_a = apk_scanner.scan_apk_file(path)
    report_b = apk_scanner.scan_apk_file(path)
    assert report_a["explanation"] == report_b["explanation"]
    assert report_a["explanation"] == "The scan identified multiple security concerns: cleartext traffic and sensitive permissions."

    # Permission ordering within a single-category sentence must also be
    # stable (sorted), independent of the manifest's own declaration order.
    perms_path = _make_apk(tmp_path, "det_perms.apk", 'android.permission.READ_SMS android.permission.CAMERA')
    perms_report_a = apk_scanner.scan_apk_file(perms_path)
    perms_report_b = apk_scanner.scan_apk_file(perms_path)
    assert perms_report_a["explanation"] == perms_report_b["explanation"]
    assert "CAMERA, READ_SMS" in perms_report_a["explanation"]


# 7. Vulnerable scan never uses the generic placeholder
def test_vulnerable_scan_never_uses_generic_placeholder(tmp_path):
    for manifest in ['usesCleartextTraffic="true"', 'android.permission.CAMERA']:
        path = _make_apk(tmp_path, f"generic_{hash(manifest) & 0xffff}.apk", manifest)
        report = apk_scanner.scan_apk_file(path)
        assert report["vulnerable"] is True
        assert report["explanation"] != "APK scan completed."


# 8. Invalid APK explanation preserved
def test_invalid_apk_explanation_unchanged(tmp_path):
    bad_path = tmp_path / "corrupted.apk"
    bad_path.write_bytes(b"this is not a zip file")
    report = apk_scanner.scan_apk_file(str(bad_path))
    assert report["explanation"] == "Invalid or corrupted APK file."


# 9. Explanation contains only actual detected findings
def test_explanation_only_mentions_real_findings(tmp_path):
    path = _make_apk(tmp_path, "cleartext_only.apk", 'usesCleartextTraffic="true"')
    report = apk_scanner.scan_apk_file(path)
    assert "permission" not in report["explanation"].lower()
    assert "url" not in report["explanation"].lower()
    assert "sql injection" not in report["explanation"].lower()
    assert "certificate" not in report["explanation"].lower()


# 10. Sensitive values are not leaked
def test_sensitive_url_content_is_never_leaked_only_a_count(tmp_path):
    sensitive_url = "http://192.168.1.1/api?token=SECRET123&password=hunter2"
    path = _make_apk(tmp_path, "sensitive.apk", 'android.permission.INTERNET',
                      extra_files={"assets/config.json": sensitive_url})
    report = apk_scanner.scan_apk_file(path)
    assert "SECRET123" not in report["explanation"]
    assert "hunter2" not in report["explanation"]
    assert "192.168.1.1" not in report["explanation"]
    assert "1 suspicious URL" in report["explanation"]


# 11. Risk level remains unchanged by the explanation-wording fix
def test_risk_level_and_vulnerable_flag_unaffected_by_explanation_change(tmp_path):
    # Same detections as the pre-Phase-10B behavior would have classified -
    # only the explanation TEXT is new, not risk_level/vulnerable/security_score.
    path = _make_apk(tmp_path, "riskcheck.apk", 'usesCleartextTraffic="true" android.permission.CAMERA')
    report = apk_scanner.scan_apk_file(path)
    assert report["risk_level"] == "high"
    assert report["vulnerable"] is True
    assert report["security_score"] == 75  # 100 - 5 (1 dangerous perm) - 10*2 (2 detections)
