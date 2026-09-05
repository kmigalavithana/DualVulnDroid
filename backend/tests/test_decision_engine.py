import decision_engine


def test_strong_traced_dataflow_overrides_mid_confidence_ml():
    """ML=0.61, strong traced SQL source-to-sink -> VULNERABLE (spec example)."""
    sql_flow = [{
        "detection_basis": "traced-source",
        "explanation": "User-controlled data reaches rawQuery() without parameterization.",
        "path": ["Intent.getStringExtra()", "username", "query", "rawQuery()"],
    }]
    result = decision_engine.evaluate(
        label="s0", ml_confidence_pct=61.0,
        sql_flow=sql_flow, cert_flow=[],
        sink_safety={"sinks_found": 0, "all_parameterized": False},
        rule_keyword_hit=True,
        vulnerable_threshold=decision_engine.VULNERABLE_THRESHOLD,
        safe_threshold=decision_engine.SAFE_THRESHOLD,
    )
    assert result["decision"] == "VULNERABLE"
    assert result["vulnerable"] is True


def test_confirmed_parameterization_overrides_mid_confidence_ml():
    """ML=0.51 (predicted vulnerable class), confirmed parameterized query -> SAFE (spec example)."""
    result = decision_engine.evaluate(
        label="s0", ml_confidence_pct=51.0,
        sql_flow=[], cert_flow=[],
        sink_safety={"sinks_found": 1, "all_parameterized": True},
        rule_keyword_hit=False,
        vulnerable_threshold=decision_engine.VULNERABLE_THRESHOLD,
        safe_threshold=decision_engine.SAFE_THRESHOLD,
    )
    assert result["decision"] == "SAFE"
    assert result["vulnerable"] is False


def test_no_dataflow_evidence_either_way_is_suspicious_review():
    """ML=0.55, no source-to-sink evidence -> SUSPICIOUS_REVIEW (spec example)."""
    result = decision_engine.evaluate(
        label="s0", ml_confidence_pct=55.0,
        sql_flow=[], cert_flow=[],
        sink_safety={"sinks_found": 0, "all_parameterized": False},
        rule_keyword_hit=False,
        vulnerable_threshold=decision_engine.VULNERABLE_THRESHOLD,
        safe_threshold=decision_engine.SAFE_THRESHOLD,
    )
    assert result["decision"] == "SUSPICIOUS_REVIEW"
    # Only a confident VULNERABLE verdict surfaces as vulnerable=True today -
    # SUSPICIOUS_REVIEW is exposed via `decision` for a future review-queue UI,
    # not force-shown as a red warning (see decision_engine.py module docstring).
    assert result["vulnerable"] is False


def test_vulnerable_cert_finding_drives_vulnerable_decision():
    cert_flow = [{"verdict": "VULNERABLE", "explanation": "handler.proceed() called unconditionally."}]
    result = decision_engine.evaluate(
        label="v0", ml_confidence_pct=40.0,
        sql_flow=[], cert_flow=cert_flow,
        sink_safety={"sinks_found": 0, "all_parameterized": False},
        rule_keyword_hit=False,
        vulnerable_threshold=decision_engine.VULNERABLE_THRESHOLD,
        safe_threshold=decision_engine.SAFE_THRESHOLD,
    )
    assert result["decision"] == "VULNERABLE"


def test_safe_trust_manager_with_keyword_hit_is_not_pushed_toward_vulnerable():
    """P0 Step 5 regression: a confirmed-SAFE cert data-flow verdict must
    suppress the static keyword rule's contribution - the mere presence
    of TrustManager-related API vocabulary ("checkServerTrusted" etc.)
    must not add a "supports vulnerable" nudge once the real structural
    check has already confirmed this exact code is safe. Before this fix,
    a genuinely safe TrustManager (ML confidently but wrongly predicting
    the vulnerable label - a known, undocumented model bias, not
    retrained/fixed here) landed on SUSPICIOUS_REVIEW partly because of
    this undirected +0.4 bump; this test locks in that the bump no longer
    applies in that specific situation."""
    cert_flow = [{
        "verdict": "SAFE",
        "explanation": "checkServerTrusted() can throw a CertificateException, indicating it actually validates the chain instead of accepting everything.",
    }]
    result = decision_engine.evaluate(
        label="v0", ml_confidence_pct=93.0,
        sql_flow=[], cert_flow=cert_flow,
        sink_safety={"sinks_found": 0, "all_parameterized": False},
        rule_keyword_hit=True,
    )
    sources = {r["source"] for r in result["reasons"]}
    assert "static_rule" not in sources
    # Still not forced all the way to SAFE by a hardcoded special case -
    # the confidently-wrong ML signal is real evidence too, so this stays
    # a genuinely ambiguous case rather than an invented SAFE verdict.
    assert result["decision"] == "SUSPICIOUS_REVIEW"


def test_confirmed_parameterized_sql_with_keyword_hit_is_not_pushed_toward_vulnerable():
    """Same fix, SQL side: a confirmed all-parameterized query must
    suppress the static rule bump too (e.g. "rawQuery(" itself is a
    RULE_KEYWORDS['s0'] keyword and appears in perfectly safe parameterized
    calls just as often as unsafe ones)."""
    result = decision_engine.evaluate(
        label="s0", ml_confidence_pct=70.0,
        sql_flow=[], cert_flow=[],
        sink_safety={"sinks_found": 1, "all_parameterized": True},
        rule_keyword_hit=True,
    )
    sources = {r["source"] for r in result["reasons"]}
    assert "static_rule" not in sources


def test_keyword_rule_still_applies_when_dataflow_is_genuinely_vulnerable():
    """The suppression above must not become a blanket "never add the
    keyword bump" - when the structural check actually found something
    unsafe (not a confirmed-safe verdict), the corroborating static rule
    must still contribute exactly as before."""
    cert_flow = [{"verdict": "VULNERABLE", "explanation": "handler.proceed() called unconditionally."}]
    result = decision_engine.evaluate(
        label="v0", ml_confidence_pct=99.0,
        sql_flow=[], cert_flow=cert_flow,
        sink_safety={"sinks_found": 0, "all_parameterized": False},
        rule_keyword_hit=True,
    )
    sources = {r["source"] for r in result["reasons"]}
    assert "static_rule" in sources
    assert result["decision"] == "VULNERABLE"


def test_reasons_are_populated_and_traceable():
    sql_flow = [{
        "detection_basis": "traced-source",
        "explanation": "traced",
        "path": ["Intent.getStringExtra()", "x", "rawQuery()"],
    }]
    result = decision_engine.evaluate(
        label="s0", ml_confidence_pct=90.0,
        sql_flow=sql_flow, cert_flow=[],
        sink_safety={"sinks_found": 0, "all_parameterized": False},
        rule_keyword_hit=True,
    )
    sources = {r["source"] for r in result["reasons"]}
    assert "ml_model" in sources
    assert "dataflow_sql" in sources
    assert "static_rule" in sources
