import os
import zipfile
import shutil
import tempfile
import re
import pyaxmlparser
from pyaxmlparser.core import NS_ANDROID
from predictor import predict_url

# Real APK static analysis, no fabricated results.
#
# Scope of what this currently checks (all derived from bytes actually
# present in the uploaded file):
#   - AndroidManifest.xml: cleartext-traffic flag + declared permissions,
#     both derived from pyaxmlparser's real binary-AXML-decoded data (see
#     extract_apk_metadata() below) - not a raw-byte search. An earlier
#     version of this module searched for these as literal UTF-8
#     substrings directly in the manifest bytes, which never matches a
#     real aapt2-compiled APK (its AXML string pool is UTF-16LE); fixed
#     during the Flutter APK Scan validation phase (see
#     test_fixtures/vulnerable_test_apk/README.md, "Gap 1").
#   - AndroidManifest.xml: package name, version name/code, and
#     application label (Phase 8A), via pyaxmlparser - a real binary-AXML
#     decoder, not a heuristic. Any field it can't genuinely determine is
#     left as None; nothing here is ever inferred from the filename.
#   - URLs found anywhere in the extracted archive (dex, resources,
#     assets, etc.), checked against the rule-based heuristic in
#     predictor.predict_url().
#
# What this does NOT do yet: decompiled Java/Kotlin source-level
# SQL-Injection / Certificate-Validation analysis. That requires a DEX
# decompiler (e.g. JADX/Androguard) which is not wired in yet - see the
# "note" field in the returned report. CWE-89/CWE-295 findings only ever
# come from the separate source-code pipeline (predictor.py/
# decision_engine.py, used by the /developer/* endpoints and the IDE
# plugin) - db/crud.py's persist_apk_scan() always stores cwe=None for
# every finding this scanner produces, on purpose.

# Excludes whitespace/quotes/brackets/backslash (as before) plus C0
# control bytes (\x00-\x1f). Binary resource string pools (resources.arsc,
# compiled AXML) pack adjacent strings back-to-back separated by NUL and
# other control bytes with no whitespace - without this exclusion a run of
# several distinct URLs gets captured as one malformed string (Flutter APK
# Scan validation phase, "Gap 2" - confirmed live against
# test_fixtures/vulnerable_test_apk, which planted ~13 distinct URLs that
# were previously bled together into 7 malformed entries).
URL_PATTERN = re.compile(rb'https?://[^\s"\'<>\\\x00-\x1f]+')
MAX_EXTRACTED_URLS = 25


def _parse_manifest_int(raw_value):
    """Converts a raw AXML attribute string to int. None for anything
    that isn't a clean integer - never guessed, never defaulted to 0."""
    if raw_value is None:
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _parse_manifest_bool(raw_value):
    """Converts a raw AXML boolean-attribute string ('true'/'false') to
    a real Python bool. None for anything else, including an absent
    attribute - this is the RAW manifest value, never Android's
    "effective default" for a missing attribute (Android defaults
    android:debuggable to false and android:allowBackup to true when
    absent, but that's a platform-behavior inference, not something this
    APK's manifest actually declared - see extract_apk_metadata's
    docstring)."""
    if raw_value is None:
        return None
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, str):
        lowered = raw_value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    return None


# Real, known ABI directory names Android actually uses under lib/ in an
# APK. Anything else under lib/ (there isn't anything else in practice)
# would not be a real ABI and is deliberately not matched.
_KNOWN_ABIS = {"arm64-v8a", "armeabi-v7a", "armeabi", "x86", "x86_64"}


def _extract_uses_features(apk) -> list:
    """
    Phase 8C, Part A: returns one dict per REAL <uses-feature> declaration
    found in the manifest - never invented, and never limited to a fixed
    example list (whatever the APK actually declares is what's returned).

    Each entry: {"feature_name": str|None, "gl_es_version": str|None,
    "required": bool|None, "required_explicit": bool}.

    Android semantics for android:required on <uses-feature>: when the
    attribute is genuinely present in the manifest, its value is
    authoritative and is reported as-is (required=True/False,
    required_explicit=True). When the attribute is absent,
    required=None and required_explicit=False - this function does NOT
    apply Android's platform-level implicit default (required=true when
    absent) itself; that would blur "the manifest actually declared this"
    with "the platform will behave this way regardless." Callers that
    need a normalized boolean for a compatibility decision must apply
    that default explicitly and label it as derived - see
    compatibility.py's evaluate_hardware_compatibility(), which treats
    required_explicit=False the same as required=True (Android's real
    documented default) but documents that choice at the point it's made,
    not silently here.

    <uses-feature> is a distinct manifest concept from <uses-permission>
    (declares hardware/software capabilities the app uses, not access
    rights) - this function only ever reads <uses-feature> tags.
    """
    features = []
    try:
        tags = apk.find_tags("uses-feature")
    except Exception:
        return features

    for tag in tags:
        try:
            name = tag.get(NS_ANDROID + "name")
            gl_es_version = tag.get(NS_ANDROID + "glEsVersion")
            if name is None and gl_es_version is None:
                continue  # not a usable declaration - nothing real to report

            required_raw = tag.get(NS_ANDROID + "required")
            required_explicit = required_raw is not None
            required = _parse_manifest_bool(required_raw) if required_explicit else None

            features.append({
                "feature_name": name,
                "gl_es_version": gl_es_version,
                "required": required,
                "required_explicit": required_explicit,
            })
        except Exception:
            continue

    return features


def extract_apk_abis(apk_path: str) -> list:
    """
    Phase 8C, Part B: inspects the APK's real ZIP contents for
    lib/<abi>/ directories - never assumed from the device, the APK
    filename, or anything else. Returns only ABI names that genuinely
    appear as a lib/<name>/ path inside this specific archive, sorted for
    determinism. Empty list when the APK has no lib/ entries at all -
    which does NOT mean "incompatible with everything" (see
    compatibility.py: an APK with no native libraries may be pure
    managed/Dex code and can run on any architecture the Android runtime
    supports - ABI evidence alone must never be treated as automatic
    incompatibility).
    """
    abis = set()
    try:
        with zipfile.ZipFile(apk_path, "r") as zip_ref:
            for name in zip_ref.namelist():
                parts = name.split("/")
                if len(parts) >= 2 and parts[0] == "lib" and parts[1] in _KNOWN_ABIS:
                    abis.add(parts[1])
    except Exception:
        return []
    return sorted(abis)


def extract_apk_metadata(apk_path: str) -> dict:
    """
    Extracts REAL package_name / version_name / version_code /
    application_label / permissions / min_sdk_version / target_sdk_version
    / debuggable / allow_backup from the APK's actual, compiled
    AndroidManifest.xml via pyaxmlparser (a genuine binary-AXML decoder,
    not the raw-string heuristic used elsewhere in this file).

    Every field is independently guarded: a field that can't genuinely be
    read from this specific APK is None (or [] for permissions) - never
    guessed, never derived from the filename. A field that DOES parse
    successfully is still returned even if a different field on the same
    APK fails (e.g. a manifest with a readable package name but a
    malformed versionCode attribute).

    debuggable/allow_backup (Phase 8B) are read via
    APK.get_attribute_value("application", <attr>), which returns the RAW
    android:debuggable / android:allowBackup attribute text straight from
    the <application> element - None means the attribute is genuinely
    absent from this manifest, not "false". This is deliberately NOT
    Android's effective runtime default for a missing attribute (which is
    debuggable=false, allowBackup=true) - this function only reports what
    the manifest actually declares. Any caller that wants the effective
    default must compute it explicitly and document it as derived, not
    raw, per Phase 8B's documentation requirement.

    min_sdk_version/target_sdk_version similarly come from the manifest's
    raw <uses-sdk> attributes (APK.get_min_sdk_version() /
    get_target_sdk_version()), not pyaxmlparser's
    get_effective_target_sdk_version() (which silently substitutes
    minSdkVersion or 1 when targetSdkVersion is absent) - a missing
    targetSdkVersion is reported as None here, never inferred.

    features (Phase 8C, Part A) is the real list of <uses-feature>
    declarations - see _extract_uses_features()'s docstring for the
    required/required_explicit distinction. Not to be confused with
    permissions (<uses-permission>), a different manifest concept.
    """
    metadata = {
        "package_name": None,
        "version_name": None,
        "version_code": None,
        "application_label": None,
        "permissions": [],
        "min_sdk_version": None,
        "target_sdk_version": None,
        "debuggable": None,
        "allow_backup": None,
        "uses_cleartext_traffic": None,
        "features": [],
        "manifest_parse_error": None,
    }

    try:
        apk = pyaxmlparser.APK(apk_path)
    except Exception as e:
        metadata["manifest_parse_error"] = f"Could not parse APK/manifest: {e}"
        return metadata

    try:
        package_name = apk.package
        metadata["package_name"] = package_name if package_name else None
    except Exception:
        pass

    try:
        version_name = apk.version_name
        metadata["version_name"] = version_name if version_name else None
    except Exception:
        pass

    try:
        version_code_raw = apk.version_code
        metadata["version_code"] = int(version_code_raw) if version_code_raw else None
    except Exception:
        metadata["version_code"] = None

    try:
        label = apk.application
        metadata["application_label"] = label if label else None
    except Exception:
        pass

    try:
        perms = apk.permissions
        metadata["permissions"] = list(perms) if perms else []
    except Exception:
        pass

    try:
        metadata["min_sdk_version"] = _parse_manifest_int(apk.get_min_sdk_version())
    except Exception:
        pass

    try:
        metadata["target_sdk_version"] = _parse_manifest_int(apk.get_target_sdk_version())
    except Exception:
        pass

    try:
        metadata["debuggable"] = _parse_manifest_bool(
            apk.get_attribute_value("application", "debuggable")
        )
    except Exception:
        pass

    try:
        metadata["allow_backup"] = _parse_manifest_bool(
            apk.get_attribute_value("application", "allowBackup")
        )
    except Exception:
        pass

    try:
        metadata["uses_cleartext_traffic"] = _parse_manifest_bool(
            apk.get_attribute_value("application", "usesCleartextTraffic")
        )
    except Exception:
        pass

    try:
        metadata["features"] = _extract_uses_features(apk)
    except Exception:
        pass

    if metadata["package_name"] is None:
        metadata["manifest_parse_error"] = (
            metadata["manifest_parse_error"]
            or "AndroidManifest.xml did not yield a usable package name."
        )

    return metadata


def _build_vulnerable_explanation(report: dict) -> str:
    """
    Phase 10B: a deterministic, evidence-based explanation for a
    VULNERABLE scan, built ONLY from this scanner's own real detections
    (cleartext traffic, dangerous permissions, suspicious URLs) - never
    SQL Injection or Certificate Validation, which are findings from the
    separate code-level dataflow/decision-engine pipeline
    (predictor.py/decision_engine.py), not this APK scanner. Called only
    when report["vulnerable"] is True, replacing the generic "APK scan
    completed." placeholder that was previously left in place for
    vulnerable scans (the safe branch already had a specific message).

    Stable, deterministic order matching the order these three checks
    run in scan_apk_file(): cleartext traffic, dangerous permissions,
    suspicious URLs. Given the same detections, always the same text -
    no randomness, no set-ordering dependence (dangerous_permissions is
    explicitly sorted() below for this reason).

    Evidence included is limited to what's safe to surface: permission
    NAMES (not secrets - these are just declared capability requests,
    already public in any APK's manifest) and a suspicious-URL COUNT
    (not the raw URLs themselves, which could incidentally contain
    tokens/session data in their query strings even when flagged for an
    unrelated reason - Part 6: "Do NOT expose secrets, tokens, API keys,
    passwords, or sensitive URLs").
    """
    findings = []  # (short_label, full_sentence) pairs, stable priority order

    has_cleartext = any(d.get("type") == "Network Security" for d in report["detections"])
    if has_cleartext:
        findings.append((
            "cleartext traffic",
            "The APK declares cleartext traffic, which may allow network "
            "communications to occur without transport encryption.",
        ))

    if report["dangerous_permissions"]:
        permission_list = ", ".join(sorted(report["dangerous_permissions"]))
        findings.append((
            "sensitive permissions",
            f"The APK requests potentially sensitive Android permissions: {permission_list}.",
        ))

    if report["malicious_urls"]:
        count = len(report["malicious_urls"])
        findings.append((
            "suspicious URLs",
            f"The APK contains {count} suspicious URL{'s' if count != 1 else ''} "
            "identified during static analysis.",
        ))

    if not findings:
        # Shouldn't happen given report["vulnerable"] is only ever set
        # True alongside one of the three findings above, but never
        # claim a specific finding that isn't actually there.
        return "The scan flagged this application as a security risk based on static analysis, but no specific finding could be described."

    if len(findings) == 1:
        return findings[0][1]

    labels = [label for label, _ in findings]
    joined_labels = (
        " and ".join(labels) if len(labels) == 2
        else ", ".join(labels[:-1]) + ", and " + labels[-1]
    )
    return f"The scan identified multiple security concerns: {joined_labels}."


def scan_apk_file(apk_path: str):
    """
    Takes a path to an APK file, extracts its contents, scans the real
    manifest bytes and real extracted-file contents, and returns a risk
    report. Persists the result as the app's latest real assessment.
    """
    app_name = os.path.basename(apk_path)

    # Real manifest metadata (Phase 8A) - package name, version, label,
    # permissions, via a genuine binary-AXML decoder. Never touches the
    # dangerous/normal permission detection below, which stays exactly as
    # it was (Phase 7 instruction: preserve existing vulnerability
    # detection behavior).
    metadata = extract_apk_metadata(apk_path)
    # Real ZIP-content ABI detection (Phase 8C, Part B) - independent of
    # AXML parsing, so it's computed even if the manifest itself failed
    # to parse (a corrupted/missing manifest doesn't imply a corrupted
    # ZIP; lib/ directory listing is a separate, simpler real fact).
    abis = extract_apk_abis(apk_path)

    report = {
        "risk_level": "low",
        "vulnerable": False,
        "detections": [],
        "dangerous_permissions": [],
        "normal_permissions": [],
        "malicious_urls": [],
        "explanation": "APK scan completed.",
        "app_name": app_name,
        "package_name": metadata["package_name"],
        "version_name": metadata["version_name"],
        "version_code": metadata["version_code"],
        "application_label": metadata["application_label"],
        "permissions": metadata["permissions"],
        "min_sdk_version": metadata["min_sdk_version"],
        "target_sdk_version": metadata["target_sdk_version"],
        "debuggable": metadata["debuggable"],
        "allow_backup": metadata["allow_backup"],
        "features": metadata["features"],
        "abis": abis,
        "manifest_parse_error": metadata["manifest_parse_error"],
        "note": (
            "This scan covers AndroidManifest.xml configuration, declared "
            "permissions, and URLs found in the package. It does not yet "
            "include decompiled source-level SQL Injection or Certificate "
            "Validation analysis - use the Android Studio plugin's live "
            "scan on the app's source code for that."
        )
    }

    # List of common dangerous permissions
    DANGEROUS_LIST = [
        "CAMERA", "ACCESS_FINE_LOCATION", "ACCESS_COARSE_LOCATION",
        "READ_CONTACTS", "WRITE_CONTACTS", "RECORD_AUDIO",
        "READ_SMS", "SEND_SMS", "READ_CALL_LOG", "WRITE_CALL_LOG",
        "READ_EXTERNAL_STORAGE", "WRITE_EXTERNAL_STORAGE"
    ]
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Extract APK
        with zipfile.ZipFile(apk_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
            
        # 1. Cleartext-traffic flag + dangerous/normal permission split.
        #
        # Bug fix (Flutter APK Scan validation phase, test_fixtures/
        # vulnerable_test_apk/README.md's "Gap 1"): this used to re-open
        # AndroidManifest.xml and decode it as UTF-8, then search for the
        # literal substrings "usescleartexttraffic" and
        # "android.permission.XXX". A real, aapt2-compiled manifest's AXML
        # string pool is UTF-16LE, so those bytes are "u\0s\0e\0s\0..." and
        # neither search could ever match on a real APK - verified live
        # against the project's own vulnerable_test_apk fixture (which
        # plants 12 dangerous permissions and a cleartext-traffic flag):
        # the old code always reported dangerous_permissions=[] and no
        # "Network Security" detection despite pyaxmlparser (used two
        # lines above, in extract_apk_metadata()) correctly reading all 15
        # real permissions. Fixed by deriving both signals from the
        # already-correctly-decoded pyaxmlparser data instead of a second,
        # broken raw-byte search - no new dependency, no behavior change
        # to anything else in this function.
        for full_permission in metadata["permissions"]:
            perm_name = full_permission.rsplit(".", 1)[-1].upper()
            if perm_name in DANGEROUS_LIST:
                if perm_name not in report["dangerous_permissions"]:
                    report["dangerous_permissions"].append(perm_name)
            else:
                if perm_name not in report["normal_permissions"]:
                    report["normal_permissions"].append(perm_name)

        if report["dangerous_permissions"]:
            report["vulnerable"] = True
            report["risk_level"] = "high"
            report["detections"].append({
                "type": "Dangerous Permissions",
                "code": ", ".join(report["dangerous_permissions"]),
                "line": 0
            })

        # metadata["uses_cleartext_traffic"] is True only when the manifest
        # explicitly declares android:usesCleartextTraffic="true" - None
        # (attribute absent) is never treated as a finding, consistent
        # with how debuggable/allow_backup are already handled above.
        if metadata["uses_cleartext_traffic"] is True:
            report["vulnerable"] = True
            report["risk_level"] = "high"
            report["detections"].append({
                "type": "Network Security",
                "code": "android:usesCleartextTraffic=\"true\" found in Manifest",
                "line": 0
            })


        # 2. Real URL extraction: scan every extracted file's raw bytes for
        # URL-shaped strings (dex, resources.arsc, assets, etc. all store
        # string constants as readable text), then run each found URL
        # through the heuristic check. Nothing here is invented - if the
        # APK doesn't contain a suspicious URL, none is reported.
        found_urls = set()
        for root, _dirs, files in os.walk(temp_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, 'rb') as f:
                        data = f.read()
                    for match in URL_PATTERN.findall(data):
                        found_urls.add(match.decode('utf-8', errors='ignore'))
                        if len(found_urls) >= MAX_EXTRACTED_URLS:
                            break
                except Exception:
                    continue
            if len(found_urls) >= MAX_EXTRACTED_URLS:
                break

        for url in found_urls:
            url_report = predict_url(url)
            if url_report["is_malicious"]:
                report["malicious_urls"].append(url_report)

        if report["dangerous_permissions"] or report["malicious_urls"]:
            report["vulnerable"] = True
            report["risk_level"] = "high"
        elif report["normal_permissions"] or found_urls:
            report["risk_level"] = "medium" if not report["vulnerable"] else report["risk_level"]

        # Phase 10B: risk_level/vulnerable above are unchanged by this -
        # only the explanation text is being fixed here, not the
        # classification (Part 8).
        if report["vulnerable"]:
            report["explanation"] = _build_vulnerable_explanation(report)
        else:
            report["explanation"] = "No cleartext traffic, dangerous permissions, or suspicious URLs found in this scan."

        # Security score derived only from what was actually found above.
        score = 100
        score -= len(report["dangerous_permissions"]) * 5
        score -= len(report["malicious_urls"]) * 20
        score -= len(report["detections"]) * 10
        score = max(score, 10)
        report["security_score"] = score

        vulnerability_types = sorted({d["type"] for d in report["detections"]})
        if report["malicious_urls"]:
            vulnerability_types.append("Malicious URL")
        report["vulnerability_types"] = vulnerability_types

        # Phase 7: persistence moved out of the scanner and into
        # app.py's /upload-apk handler (db.crud.persist_apk_scan), which
        # can do the full application/version/scan/vulnerabilities/
        # ml_prediction/recommendation write as ONE transaction (Part Q).
        # scan_apk_file() now only returns the real analysis result.

    except zipfile.BadZipFile:
        report["risk_level"] = "high"
        report["vulnerable"] = True
        report["explanation"] = "Invalid or corrupted APK file."
        report["security_score"] = 10
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    return report
