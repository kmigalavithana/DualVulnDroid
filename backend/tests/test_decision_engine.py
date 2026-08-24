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
