"""
APK source-level CWE-89 / CWE-295 scanning (Flutter APK Scan implementation
phase).

Bridges the existing, unmodified CWE-89/CWE-295 detection pipeline
(predictor.predict_code(), which is also what the IDE plugin's
/developer/predict and /developer/scan endpoints call) to compiled DEX
bytecode found inside an uploaded APK. No new vulnerability detector is
created here - dataflow.py/predictor.py/decision_engine.py are used
completely as-is, exactly as they already are for the IDE plugin, and are
never modified by this module.

Why this is needed at all: predict_code() and dataflow.py's regex-based
source-to-sink analysis expect ordinary, human-authored Java/Kotlin source
text (curly braces, real API call syntax like ".rawQuery(", "implements
HostnameVerifier", literal "+"-based string concatenation). An APK only
ever contains compiled DEX bytecode, not that source text. This module:

  1. Reads each classesN.dex directly from the APK's ZIP central directory
     as in-memory bytes (zf.read(name) - never zf.extract()/extractall()),
     so DEX handling has no filesystem write surface at all and therefore
     no Zip Slip / path-traversal exposure by construction.
  2. Parses the DEX and decompiles each class with androguard's DAD
     decompiler (androguard.decompiler.decompiler.DecompilerDAD) - genuine
     bytecode decompilation, not a smali disassembly (smali's syntax
     doesn't resemble Java/Kotlin closely enough for the existing
     regex-based dataflow analyzer or the ML model's text features to
     recognize anything).
  3. Normalizes decompiler-specific artifacts that a hand-written source
     file would never contain, so the UNCHANGED downstream analyzer sees
     ordinary-looking Java. This was verified necessary and sufficient by
     compiling and decompiling real test classes (see
     test_fixtures/apk_code_scan_fixtures/ and
     tests/test_apk_code_scanner.py) - without it, real vulnerable
     decompiled code produced ZERO findings (false negatives), not
     "close enough" findings:
       a. `new StringBuilder().append(a).append(b).toString()` -> `(a + b)`.
          javac always lowers source-level string "+" concatenation to
          StringBuilder calls; there is no way to tell from bytecode alone
          whether the original source used "+" or literal StringBuilder
          calls, so this resugars back to the common, idiomatic form (the
          same transformation a full decompiler like JADX applies
          internally) so dataflow.py's existing `_has_concatenation()`
          (which only recognizes '+'/'.plus('/'concat(') can see it.
       b. `return 1;` / `return 0;` -> `return true;` / `return false;`,
          scoped to methods whose declared return type is `boolean` (DEX
          has no boolean type - booleans are compiled to int 0/1), so
          dataflow.py's `HostnameVerifier.verify()` check (which looks for
          a literal `return true`) can recognize an unconditional-true
          verifier.
       c. A method/constructor body that decompiles to nothing but a bare
          `return;` (DAD always makes the implicit end-of-method return
          explicit, even for a genuinely empty method) is normalized back
          to an empty body, matching what the original source's `{ }`
          would have looked like - otherwise an empty (auto-accept)
          checkServerTrusted()/checkClientTrusted() is misread as "has a
          non-empty body" and downgraded from VULNERABLE to SUSPICIOUS.
     These are decompiler-output-format fixes only. They do not change
     dataflow.py/predictor.py's detection RULES in any way, and are not a
     second vulnerability detector.
  4. Feeds each decompiled-and-normalized class through the exact same
     predict_code() + to_developer_response() call the IDE plugin uses,
     and keeps only genuinely returned CWE-89/CWE-295 findings - never
     inventing a line number, file name, or confidence value.

Explicitly out of scope, on purpose (Phase 4's "do not claim original
source-code fidelity"): this produces DECOMPILED, RECONSTRUCTED code, not
the app's real original source. Variable names are decompiler-assigned
(pN/vN), comments are gone, and complex control flow may not decompile
perfectly. Every finding's file name is prefixed to make this explicit
(see DECOMPILED_SOURCE_LABEL below).
"""

import re
import sys
import time
import zipfile
from dataclasses import dataclass, field
from typing import Optional

from predictor import predict_code, to_developer_response, CWE_BY_TYPE

# androguard logs via loguru at DEBUG by default (very high volume - one
# line per parsed DEX structure/decompiled instruction). This scanner runs
# on every APK upload, so keep server logs readable; WARNING+ still
# surfaces anything androguard itself considers noteworthy.
try:
    from loguru import logger as _androguard_logger
    _androguard_logger.remove()
    _androguard_logger.add(sys.stderr, level="WARNING")
except Exception:
    pass

# =====================================================
# Safety / resource limits (Phase 13: APK is untrusted, hostile input)
# =====================================================

DEX_NAME_RE = re.compile(r'^classes\d*\.dex$')
MAX_DEX_ENTRY_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # 50MB per classes.dex - defends against a zip-bomb-style DEX entry
MAX_CLASSES_TO_ANALYZE = 300  # hard cap on how many classes get decompiled+scanned per APK
MAX_SCAN_SECONDS = 45.0  # wall-clock budget for the whole code-scan phase; bails out gracefully, never hangs the request

# Well-known third-party/framework package prefixes are skipped: findings
# inside a dependency's own internals aren't "the app's code", and
# skipping them keeps scan time and false-positive surface bounded for
# real-world APKs that can contain thousands of library classes. This is
# a scoping heuristic, not a detection-logic change - it only decides
# WHICH files get analyzed, never how a given file is analyzed.
_THIRDPARTY_PACKAGE_PREFIXES = (
    "androidx/", "android/support/", "com/google/android/", "com/google/firebase/",
    "com/google/gson/", "com/google/common/", "kotlin/", "kotlinx/",
    "okhttp3/", "okio/", "retrofit2/", "com/squareup/", "io/flutter/",
    "com/facebook/", "org/jetbrains/", "dagger/", "javax/", "org/json/",
    "com/android/", "androidx/lifecycle/",
)

# Every finding's file name carries this marker so a caller (and the
# Flutter UI) can never mistake reconstructed bytecode for the app's real
# original source file.
DECOMPILED_SOURCE_LABEL = "decompiled"


@dataclass
class ApkCodeScanResult:
    findings: list = field(default_factory=list)
    files_scanned: int = 0
    files_skipped_thirdparty: int = 0
    classes_total: int = 0
    truncated: bool = False
    truncation_reason: Optional[str] = None
    dex_entries_found: int = 0
    decompile_errors: int = 0


# =====================================================
# Decompiler-output normalization (see module docstring, point 3)
# =====================================================

def _find_matching_paren(text: str, open_idx: int) -> int:
    depth = 0
    i = open_idx
    in_str = False
    str_char = ''
    while i < len(text):
        c = text[i]
        if in_str:
            if c == '\\':
                i += 2
                continue
            if c == str_char:
                in_str = False
        else:
            if c in ('"', "'"):
                in_str = True
                str_char = c
            elif c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return len(text) - 1


def _find_matching_brace(text: str, open_idx: int) -> int:
    depth = 0
    i = open_idx
    in_str = False
    str_char = ''
    while i < len(text):
        c = text[i]
        if in_str:
            if c == '\\':
                i += 2
                continue
            if c == str_char:
                in_str = False
        else:
            if c in ('"', "'"):
                in_str = True
                str_char = c
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return len(text) - 1


def _resugar_stringbuilder_concat(text: str) -> str:
    out = []
    i = 0
    pattern = re.compile(r'new\s+StringBuilder\s*\(\s*\)')
    while True:
        m = pattern.search(text, i)
        if not m:
            out.append(text[i:])
            break
        out.append(text[i:m.start()])
        pos = m.end()
        parts = []
        while True:
            am = re.match(r'\s*\.append\s*\(', text[pos:])
            if not am:
                break
            open_idx = pos + am.end() - 1
            close_idx = _find_matching_paren(text, open_idx)
            parts.append(text[open_idx + 1:close_idx])
            pos = close_idx + 1
        tm = re.match(r'\s*\.toString\s*\(\s*\)', text[pos:])
        if parts and tm:
            pos = pos + tm.end()
            out.append('(' + ' + '.join(p.strip() for p in parts) + ')')
        else:
            out.append(text[m.start():pos])
        i = pos
    return ''.join(out)


_BOOLEAN_METHOD_RE = re.compile(r'\bboolean\s+\w+\s*\([^)]*\)\s*\{')


def _resugar_boolean_literals(text: str) -> str:
    out = []
    i = 0
    while True:
        m = _BOOLEAN_METHOD_RE.search(text, i)
        if not m:
            out.append(text[i:])
            break
        out.append(text[i:m.end()])
        brace_idx = m.end() - 1
        end_idx = _find_matching_brace(text, brace_idx)
        body = text[brace_idx + 1:end_idx]
        body = re.sub(r'\breturn\s+1\s*;', 'return true;', body)
        body = re.sub(r'\breturn\s+0\s*;', 'return false;', body)
        out.append(body)
        out.append(text[end_idx])
        i = end_idx + 1
    return ''.join(out)


def _strip_noop_return_bodies(text: str) -> str:
    return re.sub(r'\{\s*return\s*;\s*\}', '{}', text)


def normalize_decompiled_source(text: str) -> str:
    """Applies all decompiler-output normalizations. Pure text
    transformation - never touches dataflow.py/predictor.py."""
    text = _resugar_stringbuilder_concat(text)
    text = _resugar_boolean_literals(text)
    text = _strip_noop_return_bodies(text)
    return text


# =====================================================
# Safe, in-memory DEX extraction (Phase 13: no Zip Slip surface at all -
# DEX bytes are read via ZipFile.read(), never written to disk/extracted)
# =====================================================

def _read_dex_entries(apk_path: str) -> list:
    """Returns a list of (entry_name, dex_bytes) for every classesN.dex
    member of the APK, read directly into memory. Skips (does not raise
    on) any entry whose declared uncompressed size exceeds
    MAX_DEX_ENTRY_UNCOMPRESSED_BYTES, defending against a zip-bomb-style
    DEX entry - a hostile APK is not trusted to report its own size
    honestly either, but zipfile's central-directory size field is
    checked before any decompression is attempted."""
    entries = []
    with zipfile.ZipFile(apk_path) as zf:
        for info in zf.infolist():
            name = info.filename.replace('\\', '/')
            if not DEX_NAME_RE.match(name.rsplit('/', 1)[-1]) or '/' in name:
                continue
            if info.file_size > MAX_DEX_ENTRY_UNCOMPRESSED_BYTES:
                continue
            try:
                data = zf.read(info.filename)
            except Exception:
                continue
            entries.append((name, data))
    return entries


def _is_thirdparty_class(class_descriptor: str) -> bool:
    # e.g. "Lcom/example/test/VulnDao;" -> "com/example/test/VulnDao"
    internal_name = class_descriptor.strip('L;')
    return any(internal_name.startswith(prefix) for prefix in _THIRDPARTY_PACKAGE_PREFIXES)


def _decompiled_file_label(class_descriptor: str) -> str:
    internal_name = class_descriptor.strip('L;')
    return f"{DECOMPILED_SOURCE_LABEL}/{internal_name}.java"


def _best_line_number(result: dict) -> Optional[int]:
    """Never fabricates a line number - returns the first genuinely
    reported one (dataFlow, then rule-based detections), or None."""
    for entry in result.get("dataFlow", []) or []:
        if entry.get("line") is not None:
            return entry["line"]
    for entry in result.get("detections", []) or []:
        if entry.get("line") is not None:
            return entry["line"]
    return None


def _evidence_for(result: dict) -> list:
    evidence = []
    for entry in result.get("dataFlow", []) or []:
        evidence.append({
            "line": entry.get("line"),
            "code": entry.get("code"),
            "explanation": entry.get("explanation"),
            "path": entry.get("path"),
        })
    if not evidence:
        for entry in result.get("detections", []) or []:
            evidence.append({
                "line": entry.get("line"),
                "code": entry.get("code"),
                "explanation": None,
                "path": None,
            })
    return evidence


def scan_apk_for_code_vulnerabilities(apk_path: str) -> ApkCodeScanResult:
    """
    Real, non-fabricated CWE-89/CWE-295 static analysis over an APK's
    decompiled DEX code, using the exact same predict_code() pipeline the
    IDE plugin uses. Never executes any code from the APK - decompilation
    and analysis are both purely static (androguard bytecode parsing +
    regex-based dataflow.py, same as always).
    """
    result = ApkCodeScanResult()
    deadline = time.monotonic() + MAX_SCAN_SECONDS

    try:
        dex_entries = _read_dex_entries(apk_path)
    except zipfile.BadZipFile:
        return result
    result.dex_entries_found = len(dex_entries)
    if not dex_entries:
        return result

    # Imported lazily: androguard's decompiler does real work at import
    # time (loguru setup etc.) that isn't needed for the manifest-only
    # scan path apk_scanner.py already covers, and this keeps that path's
    # startup/import cost unaffected.
    from androguard.core.dex import DEX
    from androguard.core.analysis.analysis import Analysis
    from androguard.decompiler.decompiler import DecompilerDAD

    for _entry_name, dex_bytes in dex_entries:
        if time.monotonic() > deadline:
            result.truncated = True
            result.truncation_reason = "time_budget_exceeded"
            break
        try:
            dex = DEX(dex_bytes)
            analysis = Analysis(dex)
            analysis.create_xref()
            decompiler = DecompilerDAD(dex, analysis)
        except Exception:
            result.decompile_errors += 1
            continue

        for cls in dex.get_classes():
            if time.monotonic() > deadline:
                result.truncated = True
                result.truncation_reason = "time_budget_exceeded"
                break

            class_descriptor = cls.get_name()
            result.classes_total += 1

            if _is_thirdparty_class(class_descriptor):
                result.files_skipped_thirdparty += 1
                continue

            if result.files_scanned >= MAX_CLASSES_TO_ANALYZE:
                result.truncated = True
                result.truncation_reason = "max_classes_exceeded"
                break

            try:
                decompiled_source = decompiler.get_source_class(cls)
            except Exception:
                result.decompile_errors += 1
                continue

            if not decompiled_source or not decompiled_source.strip():
                continue

            result.files_scanned += 1
            normalized_source = normalize_decompiled_source(decompiled_source)
            file_label = _decompiled_file_label(class_descriptor)

            try:
                prediction = predict_code(normalized_source, file_label)
            except Exception:
                result.decompile_errors += 1
                continue

            if not prediction.get("vulnerable"):
                continue

            response = to_developer_response(prediction)
            cwe = response.get("cwe")
            if cwe not in ("CWE-89", "CWE-295"):
                # predict_code()'s label space is only ever SQL Injection /
                # Certificate Validation (see predictor.LABEL_INFO) - this
                # branch is an explicit, honest guard, not expected to
                # trigger, rather than silently trusting that invariant.
                continue

            evidence = _evidence_for(prediction)
            line = _best_line_number(prediction)

            result.findings.append({
                "type": response["vulnerabilityType"],
                "cwe": cwe,
                "file": file_label,
                "line": line,
                "confidence": response["confidence"],
                "severity": response["severity"],
                "explanation": response["explanation"],
                "evidence": evidence,
            })

    return result
