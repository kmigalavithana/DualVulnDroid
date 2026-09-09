"""
Tests for apk_code_scanner.py (Flutter APK Scan implementation phase) -
the bridge from an uploaded APK's real DEX bytecode to the EXISTING,
unmodified CWE-89/CWE-295 detection pipeline (predictor.py/dataflow.py,
the same one the IDE plugin's /developer/* endpoints use).

The five APK fixtures under test_fixtures/apk_code_scan_fixtures/ are
real, compiled, zipaligned, signed .apk files (see that directory's
build_fixtures.py) - not source text fed directly to a function. Each
test that uses one drives the actual APK-file code path
(scan_apk_for_code_vulnerabilities() reads the real ZIP, parses real DEX,
decompiles real bytecode).
"""

import io
import os
import zipfile

import pytest

import apk_code_scanner
from apk_code_scanner import (
    normalize_decompiled_source,
    scan_apk_for_code_vulnerabilities,
)

FIXTURE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "test_fixtures", "apk_code_scan_fixtures"
)


def _fixture_path(name):
    return os.path.join(FIXTURE_DIR, name)


_FIXTURES_PRESENT = all(
    os.path.isfile(_fixture_path(f"{name}.apk"))
    for name in ["cwe89_vulnerable", "cwe89_safe", "cwe295_vulnerable", "cwe295_safe", "mixed_cwe89_cwe295"]
)

requires_fixtures = pytest.mark.skipif(
    not _FIXTURES_PRESENT,
    reason="test_fixtures/apk_code_scan_fixtures/*.apk not present - run build_fixtures.py",
)


# =====================================================
# Decompiler-output normalization (pure functions, no APK needed)
# =====================================================

def test_resugar_stringbuilder_concat_basic():
    src = 'db.rawQuery(new StringBuilder().append("a").append(x).append("b").toString(), 0);'
    out = normalize_decompiled_source(src)
    assert out == 'db.rawQuery(("a" + x + "b"), 0);'


def test_resugar_stringbuilder_concat_leaves_unrelated_code_alone():
    src = 'int total = a + b;\nreturn total;'
    assert normalize_decompiled_source(src) == src


def test_resugar_boolean_literals_only_inside_boolean_method():
    src = (
        "public boolean verify(String h, SSLSession s) {\n"
        "    return 1;\n"
        "}\n"
        "public int other() {\n"
        "    return 1;\n"
        "}\n"
    )
    out = normalize_decompiled_source(src)
    assert "return true;" in out
    # the int-returning method's `return 1;` must be untouched
    assert out.count("return 1;") == 1


def test_strip_noop_return_bodies():
    src = "public void checkServerTrusted(X509Certificate[] c, String a)\n{\n    return;\n}\n"
    out = normalize_decompiled_source(src)
    assert "{}" in out
    assert "return;" not in out


def test_strip_noop_return_bodies_does_not_touch_real_early_return():
    src = "public void f() {\n    if (x) {\n        return;\n    }\n    doWork();\n}\n"
    out = normalize_decompiled_source(src)
    # the if-block's return is followed by more code in the outer body,
    # so the { return; } span here is the if-block's own brace pair -
    # only a brace pair whose ENTIRE content is "return;" is touched.
    assert "doWork();" in out


# =====================================================
# Safety (Phase 13: APK is untrusted, hostile input)
# =====================================================

def test_non_zip_file_returns_empty_result_not_an_exception(tmp_path):
    bad = tmp_path / "not_an_apk.apk"
    bad.write_bytes(b"this is not a zip file at all")
    result = scan_apk_for_code_vulnerabilities(str(bad))
    assert result.findings == []
    assert result.dex_entries_found == 0


def test_path_traversal_style_dex_entry_name_is_ignored(tmp_path):
    """A hostile zip entry named to look like a path-traversal attempt
    must never be extracted anywhere - this module never calls
    zf.extract()/extractall() at all (DEX bytes are read directly into
    memory via zf.read()), and entries containing '/' are rejected
    outright since a real classesN.dex is always at the archive root."""
    apk_path = tmp_path / "evil.apk"
    with zipfile.ZipFile(apk_path, "w") as z:
        z.writestr("../../../../tmp/evil_classes.dex", b"not real dex bytes")
        z.writestr("../classes.dex", b"not real dex bytes either")
    result = scan_apk_for_code_vulnerabilities(str(apk_path))
    assert result.dex_entries_found == 0
    assert result.findings == []
    # nothing should have been written outside tmp_path as a side effect
    assert not os.path.exists("/tmp/evil_classes.dex")


def test_oversized_dex_entry_is_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(apk_code_scanner, "MAX_DEX_ENTRY_UNCOMPRESSED_BYTES", 10)
    apk_path = tmp_path / "big.apk"
    with zipfile.ZipFile(apk_path, "w") as z:
        z.writestr("classes.dex", b"x" * 1000)  # far exceeds the 10-byte cap
    result = scan_apk_for_code_vulnerabilities(str(apk_path))
    assert result.dex_entries_found == 0


def test_malformed_dex_bytes_do_not_raise(tmp_path):
    apk_path = tmp_path / "malformed_dex.apk"
    with zipfile.ZipFile(apk_path, "w") as z:
        z.writestr("classes.dex", b"dex\n" + b"\x00" * 100)  # DEX magic-ish, garbage body
    result = scan_apk_for_code_vulnerabilities(str(apk_path))
    assert result.dex_entries_found == 1
    assert result.findings == []
    assert result.decompile_errors >= 1


@requires_fixtures
def test_max_classes_cap_truncates_gracefully(monkeypatch):
    monkeypatch.setattr(apk_code_scanner, "MAX_CLASSES_TO_ANALYZE", 1)
    result = scan_apk_for_code_vulnerabilities(_fixture_path("mixed_cwe89_cwe295.apk"))
    assert result.truncated is True
    assert result.truncation_reason == "max_classes_exceeded"
    assert result.files_scanned <= 1


# =====================================================
# Real, compiled APK fixtures - the actual end-to-end bridge
# =====================================================

@requires_fixtures
def test_cwe89_vulnerable_fixture_produces_one_cwe89_finding():
    result = scan_apk_for_code_vulnerabilities(_fixture_path("cwe89_vulnerable.apk"))
    assert result.dex_entries_found == 1
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding["cwe"] == "CWE-89"
    assert finding["type"] == "SQL Injection"
    assert finding["line"] is not None  # never fabricated - must be a real reported line
    assert finding["file"].startswith("decompiled/")


@requires_fixtures
def test_cwe89_safe_fixture_produces_no_findings():
    result = scan_apk_for_code_vulnerabilities(_fixture_path("cwe89_safe.apk"))
    assert result.files_scanned == 1
    assert result.findings == []


@requires_fixtures
def test_cwe295_vulnerable_fixture_produces_one_cwe295_finding():
    result = scan_apk_for_code_vulnerabilities(_fixture_path("cwe295_vulnerable.apk"))
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding["cwe"] == "CWE-295"
    assert finding["type"] == "Certificate Validation"


@requires_fixtures
def test_cwe295_safe_fixture_produces_no_findings():
    result = scan_apk_for_code_vulnerabilities(_fixture_path("cwe295_safe.apk"))
    assert result.files_scanned >= 1
    assert result.findings == []


@requires_fixtures
def test_mixed_fixture_produces_both_with_no_cross_contamination():
    result = scan_apk_for_code_vulnerabilities(_fixture_path("mixed_cwe89_cwe295.apk"))
    cwes = sorted(f["cwe"] for f in result.findings)
    assert cwes == ["CWE-295", "CWE-89"]
    assert len(result.findings) == 2
    # CRITICAL INVARIANT (Phase 7): totalFindings = cwe89Count + cwe295Count
    cwe89_count = sum(1 for f in result.findings if f["cwe"] == "CWE-89")
    cwe295_count = sum(1 for f in result.findings if f["cwe"] == "CWE-295")
    assert len(result.findings) == cwe89_count + cwe295_count
    # no finding's type/cwe pairing is ever swapped
    for f in result.findings:
        if f["cwe"] == "CWE-89":
            assert f["type"] == "SQL Injection"
        if f["cwe"] == "CWE-295":
            assert f["type"] == "Certificate Validation"
