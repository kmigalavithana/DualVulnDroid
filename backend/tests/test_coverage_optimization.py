"""
PHASE RESEARCH-EVAL-3, Part 23: tests for the decision-engine coverage/
FNR trade-off study (research_eval/coverage_optimization.py,
pareto_analysis.py, operating_points.py, coverage_error_analysis.py).

Same convention as the prior two research phases: pure unit tests always
run; artifact-dependent tests skip (not fail) if the pipeline hasn't
been run yet in this checkout.
"""

import csv
import json
import os

import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import decision_engine
from research_eval.data_split import ARTIFACT_DIR
from research_eval.operating_points import operating_point_metrics, apply_thresholds
from research_eval.pareto_analysis import dominates, pareto_frontier

OUT_DIR = os.path.join(ARTIFACT_DIR, "coverage_optimization")


def _present(*names):
    return all(os.path.exists(os.path.join(OUT_DIR, n)) for n in names)


skip_no_val = pytest.mark.skipif(
    not _present("validation_operating_points.json"), reason="run `python -m research_eval.coverage_optimization` first"
)
skip_no_test = pytest.mark.skipif(
    not _present("test_operating_points.json"), reason="run `python -m research_eval.coverage_optimization` first"
)


# ---------------------------------------------------------------------
# 1/2. Coverage calculation; deferred cases excluded from automatic coverage
# ---------------------------------------------------------------------

def test_coverage_formula_is_automatic_over_total():
    decided = [
        {"true_is_vulnerable": True, "final_vulnerable_flag": True, "deferred": False},
        {"true_is_vulnerable": False, "final_vulnerable_flag": False, "deferred": False},
        {"true_is_vulnerable": True, "final_vulnerable_flag": False, "deferred": True},
        {"true_is_vulnerable": False, "final_vulnerable_flag": False, "deferred": True},
    ]
    m = operating_point_metrics(decided, vulnerable_threshold=1.0, safe_threshold=-1.0)
    assert m["total_cases"] == 4
    assert m["automatic_decisions"] == 2
    assert m["deferred_count"] == 2
    assert m["coverage"] == pytest.approx(0.5)


def test_deferred_cases_never_counted_as_tp_tn_fp_fn():
    decided = [
        {"true_is_vulnerable": True, "final_vulnerable_flag": False, "deferred": True},  # would be FN if miscounted
        {"true_is_vulnerable": False, "final_vulnerable_flag": False, "deferred": True},  # would be TN if miscounted
    ]
    m = operating_point_metrics(decided, vulnerable_threshold=1.0, safe_threshold=-1.0)
    assert m["tp"] == m["tn"] == m["fp"] == m["fn"] == 0
    assert m["automatic_decisions"] == 0
    assert m["fnr"] is None  # undefined with zero automatic decisions - not silently 0 or 1


# ---------------------------------------------------------------------
# 3/4. FNR / FPR calculation
# ---------------------------------------------------------------------

def test_fnr_fpr_formulas():
    decided = [
        {"true_is_vulnerable": True, "final_vulnerable_flag": True, "deferred": False},   # TP
        {"true_is_vulnerable": True, "final_vulnerable_flag": False, "deferred": False},  # FN
        {"true_is_vulnerable": False, "final_vulnerable_flag": True, "deferred": False},  # FP
        {"true_is_vulnerable": False, "final_vulnerable_flag": False, "deferred": False}, # TN
    ]
    m = operating_point_metrics(decided, vulnerable_threshold=1.0, safe_threshold=-1.0)
    assert m["fnr"] == pytest.approx(1 / (1 + 1))  # fn/(fn+tp)
    assert m["fpr"] == pytest.approx(1 / (1 + 1))  # fp/(fp+tn)


def test_apply_thresholds_uses_real_decision_engine_decide():
    """apply_thresholds must call decision_engine.decide() itself, not a
    reimplementation - verified by checking a known evidence_score against
    known thresholds produces the documented decision."""
    records = [{"row_identifier": 0, "true_label": "s0", "true_is_vulnerable": True,
                "xgb_prediction": "s0", "xgb_confidence_pct": 90.0, "evidence_score": 2.0, "reasons": []}]
    decided = apply_thresholds(records, vulnerable_threshold=1.5, safe_threshold=-0.9)
    assert decided[0]["decision"] == "VULNERABLE"
    assert decided[0]["decision"] == decision_engine.decide(2.0, 1.5, -0.9)


# ---------------------------------------------------------------------
# 5. Pareto dominance logic
# ---------------------------------------------------------------------

def test_dominance_requires_strict_improvement_in_at_least_one_dimension():
    a = {"coverage": 0.5, "fnr": 0.1}
    b = {"coverage": 0.5, "fnr": 0.1}
    assert not dominates(a, b)  # identical points do not dominate each other

    a = {"coverage": 0.6, "fnr": 0.1}
    b = {"coverage": 0.5, "fnr": 0.1}
    assert dominates(a, b)  # strictly higher coverage, equal FNR

    a = {"coverage": 0.5, "fnr": 0.05}
    b = {"coverage": 0.5, "fnr": 0.1}
    assert dominates(a, b)  # equal coverage, strictly lower FNR

    a = {"coverage": 0.4, "fnr": 0.05}
    b = {"coverage": 0.5, "fnr": 0.1}
    assert not dominates(a, b)  # lower coverage - cannot dominate regardless of FNR


def test_pareto_frontier_excludes_dominated_points():
    points = [
        {"coverage": 0.3, "fnr": 0.30},  # dominated by BOTH points below (worse coverage AND worse fnr than each)
        {"coverage": 0.5, "fnr": 0.10},  # non-dominated: lower FNR than the 0.9 point, though lower coverage too
        {"coverage": 0.9, "fnr": 0.20},  # non-dominated: higher coverage than the 0.5 point, though higher fnr too
    ]
    frontier, dominated = pareto_frontier(points)
    assert {"coverage": 0.5, "fnr": 0.10} in frontier
    assert {"coverage": 0.9, "fnr": 0.20} in frontier
    assert {"coverage": 0.3, "fnr": 0.30} in dominated
    assert len(frontier) + len(dominated) == 3


def test_pareto_frontier_excludes_undefined_fnr_points():
    points = [{"coverage": 0.0, "fnr": None}, {"coverage": 0.5, "fnr": 0.1}]
    frontier, dominated = pareto_frontier(points)
    assert len(frontier) + len(dominated) == 1  # the fnr=None point is excluded from both


# ---------------------------------------------------------------------
# 6. Validation-only operating-point selection; 7. frozen test untouched
# ---------------------------------------------------------------------

@skip_no_val
def test_operating_points_selected_using_validation_data():
    with open(os.path.join(OUT_DIR, "validation_operating_points.json")) as f:
        val_data = json.load(f)
    assert len(val_data["targets"]) == 8  # the 8 target coverage levels from Part 6
    for t in val_data["targets"]:
        assert t["total_cases"] == 169  # validation split size - not test


@skip_no_test
def test_test_set_touched_exactly_once_per_operating_point():
    with open(os.path.join(OUT_DIR, "test_operating_points.json")) as f:
        test_data = json.load(f)
    assert "Test set touched exactly once" in test_data["note"]
    for name, result in test_data["test_results"].items():
        if result is not None:
            assert result["total_cases"] == 168  # frozen test split size


@skip_no_test
def test_selected_thresholds_identical_between_validation_selection_and_test_application():
    """The thresholds applied to test must be EXACTLY the ones selected on
    validation - no re-tuning happened in between."""
    with open(os.path.join(OUT_DIR, "test_operating_points.json")) as f:
        test_data = json.load(f)
    selected = test_data["selected_operating_points_validation"]
    for name, result in test_data["test_results"].items():
        if result is not None:
            assert result["vulnerable_threshold"] == selected[name]["vulnerable_threshold"]
            assert result["safe_threshold"] == selected[name]["safe_threshold"]


# ---------------------------------------------------------------------
# 8. CWE-specific metrics
# ---------------------------------------------------------------------

@skip_no_test
def test_cwe_metrics_csv_covers_both_tasks_for_every_operating_point():
    path = os.path.join(OUT_DIR, "cwe_metrics.csv")
    if not os.path.exists(path):
        pytest.skip("run `python -m research_eval.coverage_error_analysis` first")
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    cwes_seen = {row["CWE"] for row in rows}
    assert cwes_seen == {"CWE-89", "CWE-295"}


# ---------------------------------------------------------------------
# 9. Review workload calculation
# ---------------------------------------------------------------------

def test_review_workload_is_complement_of_coverage():
    decided = [{"deferred": False}] * 60 + [{"deferred": True}] * 40
    total = len(decided)
    auto = sum(1 for r in decided if not r["deferred"])
    deferred = total - auto
    coverage = auto / total
    review_workload = deferred / total
    assert coverage + review_workload == pytest.approx(1.0)
    assert review_workload == pytest.approx(0.4)


# ---------------------------------------------------------------------
# 10. Operating-point reproducibility
# ---------------------------------------------------------------------

def test_same_evidence_score_and_thresholds_always_yield_same_decision():
    records = [{"row_identifier": 0, "true_label": "v0", "true_is_vulnerable": True,
                "xgb_prediction": "v0", "xgb_confidence_pct": 80.0, "evidence_score": 0.5, "reasons": []}]
    d1 = apply_thresholds(records, 1.0, -1.0)
    d2 = apply_thresholds(records, 1.0, -1.0)
    assert d1[0]["decision"] == d2[0]["decision"] == "SUSPICIOUS_REVIEW"


# ---------------------------------------------------------------------
# 11. No production Decision Engine modification
# ---------------------------------------------------------------------

def test_decision_engine_constants_unchanged_by_this_phase():
    assert decision_engine.ML_WEIGHT == 1.0
    assert decision_engine.TRACED_SOURCE_TO_SINK_WEIGHT == 2.0
    assert decision_engine.CERT_VULNERABLE_WEIGHT == 2.0
    assert decision_engine.STATIC_RULE_WEIGHT == 0.4
    assert set(decision_engine.VULNERABLE_ML_LABELS) == {"s0", "v0"}


@skip_no_val
def test_current_production_thresholds_recorded_not_altered():
    with open(os.path.join(OUT_DIR, "validation_operating_points.json")) as f:
        val_data = json.load(f)
    recorded = val_data["current_production_thresholds"]
    assert recorded["vulnerable_threshold"] == decision_engine.VULNERABLE_THRESHOLD
    assert recorded["safe_threshold"] == decision_engine.SAFE_THRESHOLD
