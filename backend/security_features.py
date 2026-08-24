"""
Converts the results of the static/data-flow analyzers (dataflow.py) plus
a small set of direct structural checks into a fixed-order, deterministic
numeric feature vector. This is the bridge between "static analysis
findings" (dataflow.py) and "ML model input" (ml/feature_pipeline.py).

Every feature here is a pure function of the code text - no randomness,
no external state, so the same snippet always produces the same vector.
This is required for train/inference parity (ml/feature_pipeline.py uses
this same module for both).
"""

import re
from collections import OrderedDict

from dataflow import (
    analyze_sql_dataflow,
    analyze_cert_dataflow,
    sql_sink_safety_summary,
    SQL_SOURCES,
    SQL_SINK_NAMES,
    BUNDLE_SOURCE_RE,
)

FEATURE_NAMES = [
    # --- SQL Injection (CWE-89) ---
    "sql_source_detected",
    "sql_sink_detected",
    "sql_source_to_sink",
    "sql_string_concatenation",
    "sql_parameterized_query",
    "sql_user_input",
    "sql_raw_query",
    "sql_exec_sql",
    "sql_compile_statement",
    # --- Certificate Validation (CWE-295) ---
    "certificate_hostname_verifier",
    "certificate_return_true",
    "certificate_trust_manager",
    "certificate_empty_trust_check",
    "certificate_exception_validation",
    "certificate_default_verifier",
    "webview_ssl_error",
    "webview_handler_proceed",
    "webview_handler_cancel",
    # --- Data-flow structure (from dataflow.py, not raw keyword presence) ---
    "dataflow_depth",
    "interprocedural_flow",
    "unsafe_flow_count",
    "safe_flow_count",
    "suspicious_flow_count",
]

# Feature subsets used by the ablation study (ml/train.py) to isolate the
# contribution of "structural keyword" features vs "traced data-flow"
# features. Every name here must also appear in FEATURE_NAMES.
STRUCTURAL_FEATURE_NAMES = [
    "sql_string_concatenation", "sql_parameterized_query", "sql_user_input",
    "sql_raw_query", "sql_exec_sql", "sql_compile_statement",
    "certificate_hostname_verifier", "certificate_return_true",
    "certificate_trust_manager", "certificate_empty_trust_check",
    "certificate_exception_validation", "certificate_default_verifier",
    "webview_ssl_error", "webview_handler_proceed", "webview_handler_cancel",
]
DATAFLOW_FEATURE_NAMES = [
    "sql_source_detected", "sql_sink_detected", "sql_source_to_sink",
    "dataflow_depth", "interprocedural_flow",
    "unsafe_flow_count", "safe_flow_count", "suspicious_flow_count",
]
assert set(STRUCTURAL_FEATURE_NAMES) | set(DATAFLOW_FEATURE_NAMES) == set(FEATURE_NAMES)
assert set(STRUCTURAL_FEATURE_NAMES).isdisjoint(DATAFLOW_FEATURE_NAMES)


def extract_security_features(code: str) -> "OrderedDict[str, float]":
    """Returns FEATURE_NAMES -> value (0/1 for booleans, small ints for counts)."""
    features = OrderedDict((name, 0) for name in FEATURE_NAMES)

    if not code or not code.strip():
        return features

    lower = code.lower()

    sql_flow = analyze_sql_dataflow(code)
    cert_flow = analyze_cert_dataflow(code)
    sink_safety = sql_sink_safety_summary(code)

    # ---- SQL structural presence (independent of tracing) ----
    features["sql_source_detected"] = int(
        any(p.search(code) for p, _ in SQL_SOURCES)
        or (BUNDLE_SOURCE_RE.search(code) is not None and ".getString(" in code)
    )
    features["sql_sink_detected"] = int(any(p.search(code) for p, _ in SQL_SINK_NAMES))
    features["sql_raw_query"] = int(".rawquery(" in lower)
    features["sql_exec_sql"] = int(".execsql(" in lower)
    features["sql_compile_statement"] = int(".compilestatement(" in lower)
    features["sql_user_input"] = features["sql_source_detected"]

    # ---- SQL data-flow derived ----
    features["sql_source_to_sink"] = int(any(
        f["detection_basis"] in ("traced-source", "traced-source-interprocedural")
        for f in sql_flow
    ))
    features["sql_string_concatenation"] = int(any(
        f["detection_basis"] in ("unparameterized-concatenation", "traced-source", "traced-source-interprocedural")
        for f in sql_flow
    ))
    features["sql_parameterized_query"] = int(
        sink_safety["sinks_found"] > 0 and sink_safety["all_parameterized"]
    )

    # ---- Certificate structural presence ----
    features["certificate_hostname_verifier"] = int("hostnameverifier" in lower)
    features["certificate_trust_manager"] = int("x509trustmanager" in lower or "trustmanager" in lower)
    features["webview_ssl_error"] = int("onreceivedsslerror" in lower)
    features["webview_handler_proceed"] = int(bool(re.search(r'\bhandler\s*\.\s*proceed\s*\(\s*\)', code)))
    features["webview_handler_cancel"] = int(bool(re.search(r'\bhandler\s*\.\s*cancel\s*\(\s*\)', code)))
    features["certificate_return_true"] = int(any(
        f["component"] == "HostnameVerifier" and f["verdict"] in ("VULNERABLE", "SUSPICIOUS")
        and "unconditionally returns true" in f["explanation"]
        for f in cert_flow
    ))

    # ---- Certificate data-flow derived ----
    features["certificate_empty_trust_check"] = int(any(
        f["component"].startswith("X509TrustManager.") and "empty body" in f["explanation"]
        for f in cert_flow
    ))
    features["certificate_exception_validation"] = int(any(
        f["component"].startswith("X509TrustManager.") and f["verdict"] == "SAFE"
        for f in cert_flow
    ))
    features["certificate_default_verifier"] = int(any(
        f["component"] == "HostnameVerifier" and f["verdict"] == "SAFE"
        for f in cert_flow
    ) or "getdefaulthostnameverifier" in lower)

    # ---- Aggregate flow statistics ----
    all_paths = [f["path"] for f in sql_flow if f.get("path")] + [f["path"] for f in cert_flow if f.get("path")]
    features["dataflow_depth"] = max((len(p) for p in all_paths), default=0)
    features["interprocedural_flow"] = int(any(
        f["detection_basis"] == "traced-source-interprocedural" for f in sql_flow
    ))

    sql_safe_sinks = sink_safety["sinks_found"] if sink_safety["all_parameterized"] else 0
    cert_safe = sum(1 for f in cert_flow if f["verdict"] == "SAFE")
    cert_vulnerable = sum(1 for f in cert_flow if f["verdict"] == "VULNERABLE")
    cert_suspicious = sum(1 for f in cert_flow if f["verdict"] == "SUSPICIOUS")

    features["unsafe_flow_count"] = len(sql_flow) + cert_vulnerable
    features["safe_flow_count"] = sql_safe_sinks + cert_safe
    features["suspicious_flow_count"] = cert_suspicious

    return features


def extract_security_feature_vector(code: str) -> list:
    """Same as extract_security_features but returns a plain list in
    FEATURE_NAMES order, ready to be hstacked with TF-IDF/count matrices."""
    feats = extract_security_features(code)
    return [feats[name] for name in FEATURE_NAMES]
