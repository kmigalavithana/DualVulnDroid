"""
PHASE RESEARCH-EVAL-2, Part 22: tests for the security-aware model
selection evaluation (research_eval/security_model_selection.py,
decision_engine_eval.py, error_analysis.py, confidence_analysis.py).

Same convention as test_research_eval.py: pure unit tests always run;
artifact-dependent tests skip (not fail) if the pipeline hasn't been run
yet in this checkout.
"""

import csv
import json
import os

import numpy as np
import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import decision_engine
from ml.evaluate import VULNERABLE_LABELS
from research_eval.data_split import ARTIFACT_DIR
from research_eval.security_model_selection import verified_binary_confusion
from research_eval.decision_engine_eval import coverage_view, all_case_security_view, auto_decision_view

SEC_DIR = os.path.join(ARTIFACT_DIR, "security_selection")


def _present(*names):
    return all(os.path.exists(os.path.join(SEC_DIR, n)) for n in names)


skip_no_baseline = pytest.mark.skipif(
    not _present("baseline_metrics.json"), reason="run `python -m research_eval.security_model_selection` first"
)
skip_no_decision_engine = pytest.mark.skipif(
    not _present("decision_engine_metrics.json"), reason="run `python -m research_eval.decision_engine_eval` first"
)
skip_no_confidence = pytest.mark.skipif(
    not _present("confidence_analysis.csv"), reason="run `python -m research_eval.confidence_analysis` first"
)


# ---------------------------------------------------------------------
# 1/2. Same frozen test indices; binary mapping
# ---------------------------------------------------------------------

def test_binary_mapping_matches_production_unchanged():
    assert VULNERABLE_LABELS == {"s0", "v0"}


@skip_no_baseline
def test_same_frozen_test_indices_used_as_research_eval_1():
    with open(os.path.join(ARTIFACT_DIR, "test_indices.json")) as f:
        test_idx = json.load(f)
    with open(os.path.join(ARTIFACT_DIR, "svm", "test_metrics.json")) as f:
        svm_metrics = json.load(f)
    with open(os.path.join(ARTIFACT_DIR, "xgboost", "test_metrics.json")) as f:
        xgb_metrics = json.load(f)
    n_svm = sum(sum(row) for row in svm_metrics["confusion_matrix"])
    n_xgb = sum(sum(row) for row in xgb_metrics["confusion_matrix"])
    assert n_svm == len(test_idx) == n_xgb == 168


# ---------------------------------------------------------------------
# 3/4/5. TP/TN/FP/FN, FNR, FPR calculation
# ---------------------------------------------------------------------

def test_verified_binary_confusion_matches_hand_computed_example():
    y_true = ["s0", "s0", "s1", "v0", "v1", "v1"]
    y_pred = ["s0", "s1", "s1", "v1", "v1", "v0"]
    # true vuln: s0,s0,v0 (idx 0,1,3); true safe: s1,v1,v1 (idx 2,4,5)
    # pred vuln: s0,v0 (idx 0,5);      pred safe: s1,s1,v1,v1 (idx 1,2,3,4)
    # TP = true vuln & pred vuln = idx0 -> 1
    # FN = true vuln & pred safe = idx1, idx3 -> 2
    # FP = true safe & pred vuln = idx5 -> 1
    # TN = true safe & pred safe = idx2, idx4 -> 2
    result = verified_binary_confusion(y_true, y_pred)
    assert result["tp"] == 1
    assert result["fn"] == 2
    assert result["fp"] == 1
    assert result["tn"] == 2
    assert result["verified_independently"].startswith("PASSED")


def test_fnr_and_fpr_formulas():
    result = verified_binary_confusion(["s0", "s0", "s1"], ["s1", "s0", "s1"])
    # tp=1 (s0->s0), fn=1 (s0->s1), tn=1 (s1->s1), fp=0
    assert result["fnr"] == pytest.approx(1 / (1 + 1))  # fn/(fn+tp)
    assert result["fpr"] == pytest.approx(0 / (0 + 1))  # fp/(fp+tn)


# ---------------------------------------------------------------------
# 6. CWE-specific metric calculation (reuses evaluate_models, already
# covered by test_research_eval.py's vulnerability_specific tests - here
# we check the decision-engine-specific CWE breakdown shape instead).
# ---------------------------------------------------------------------

@skip_no_decision_engine
def test_decision_engine_cwe_breakdown_has_both_tasks():
    with open(os.path.join(SEC_DIR, "decision_engine_metrics.json")) as f:
        m = json.load(f)
    for view_key in ("cwe_breakdown_auto_decision_view", "cwe_breakdown_all_case_view"):
        assert "sql_injection_cwe_89" in m[view_key]
        assert "certificate_validation_cwe_295" in m[view_key]


# ---------------------------------------------------------------------
# 7. Decision Engine coverage calculation
# ---------------------------------------------------------------------

def test_coverage_view_formula():
    records = [{"deferred": False}] * 3 + [{"deferred": True}] * 7
    result = coverage_view(records)
    assert result["total_cases"] == 10
    assert result["automatically_decided_cases"] == 3
    assert result["deferred_review_cases"] == 7
    assert result["coverage"] == pytest.approx(0.3)


# ---------------------------------------------------------------------
# 8. Deferred cases are not silently treated as correct
# ---------------------------------------------------------------------

def test_deferred_cases_excluded_from_auto_decision_view():
    """A deferred case must not contribute to auto_decision_view's
    tp/tn/fp/fn at all - not as correct, not as incorrect."""
    records = [
        {"deferred": False, "true_is_vulnerable": True, "final_vulnerable_flag": True},   # TP
        {"deferred": True, "true_is_vulnerable": True, "final_vulnerable_flag": False},   # deferred - must be excluded
        {"deferred": True, "true_is_vulnerable": False, "final_vulnerable_flag": False},  # deferred - must be excluded
    ]
    result = auto_decision_view(records)
    assert result["n_auto_decided"] == 1
    assert result["tp"] + result["tn"] + result["fp"] + result["fn"] == 1
    assert result["tp"] == 1


def test_all_case_view_documents_that_deferred_counts_as_not_vulnerable():
    """The ALL-CASE view is explicit that deferred cases ARE counted (as
    not-vulnerable, matching the engine's real boolean output) - this is
    a documented, deliberate choice, not a silent 'treat as correct'."""
    records = [
        {"true_is_vulnerable": True, "final_vulnerable_flag": False},  # deferred vulnerable case -> FN here
    ]
    result = all_case_security_view(records)
    assert result["fn"] == 1
    assert "note" in result
    assert "real, documented boolean output" in result["note"]


# ---------------------------------------------------------------------
# 9. XGBoost confidence extraction
# ---------------------------------------------------------------------

@skip_no_confidence
def test_confidence_csv_has_required_fields_and_valid_ranges():
    with open(os.path.join(SEC_DIR, "confidence_analysis.csv"), newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 168
    for field in ("row_identifier", "true_label", "predicted_label", "predicted_probability",
                  "vulnerability_probability", "correct"):
        assert field in rows[0]
    for r in rows:
        p = float(r["predicted_probability"])
        vp = float(r["vulnerability_probability"])
        assert 0.0 <= p <= 1.0001
        assert 0.0 <= vp <= 1.0001


# ---------------------------------------------------------------------
# 10. No test-set threshold tuning
# ---------------------------------------------------------------------

@skip_no_baseline
def test_threshold_selected_using_validation_only():
    with open(os.path.join(SEC_DIR, "model_selection_summary.json")) as f:
        summary = json.load(f)
    ta = summary["threshold_analysis"]
    assert "VALIDATION" in ta["selection_rule"] or "validation" in ta["selection_rule"]
    assert ta["selected_threshold"] in [0.30, 0.40, 0.50, 0.60, 0.70]
    # the sweep used to select must be the validation sweep, not a test sweep
    assert "validation_sweep" in ta
    assert "test_sweep" not in ta


# ---------------------------------------------------------------------
# 11. Decision Engine uses existing logic without modification
# ---------------------------------------------------------------------

def test_decision_engine_module_constants_unchanged():
    """Sanity check that decision_engine.py's real weight constants still
    exist with their documented values - this test would fail loudly if
    a future change silently altered the production decision logic this
    research phase relies on evaluating as-is."""
    assert decision_engine.ML_WEIGHT == 1.0
    assert decision_engine.TRACED_SOURCE_TO_SINK_WEIGHT == 2.0
    assert decision_engine.CERT_VULNERABLE_WEIGHT == 2.0
    assert decision_engine.STATIC_RULE_WEIGHT == 0.4
    assert set(decision_engine.VULNERABLE_ML_LABELS) == {"s0", "v0"}


@skip_no_decision_engine
def test_decision_engine_metrics_document_currently_loaded_thresholds_not_hardcoded():
    with open(os.path.join(SEC_DIR, "decision_engine_metrics.json")) as f:
        m = json.load(f)
    logic = m["decision_engine_logic"]
    # must reflect decision_engine.py's actual current module state, not a copy-pasted constant
    assert logic["currently_loaded_thresholds"]["vulnerable_threshold"] == decision_engine.VULNERABLE_THRESHOLD
    assert logic["currently_loaded_thresholds"]["safe_threshold"] == decision_engine.SAFE_THRESHOLD
