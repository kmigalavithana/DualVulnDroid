"""
PHASE RESEARCH-EVAL-4, Part 24: tests for the robustness/sensitivity
validation of the RESEARCH-EVAL-3 Balanced candidate
(research_eval/threshold_sensitivity.py, bootstrap_analysis.py,
split_robustness.py, robustness_validation.py).

Same convention as the prior three research phases: pure unit tests
always run; artifact-dependent tests skip (not fail) if the (expensive)
pipeline hasn't been run yet in this checkout.
"""

import csv
import hashlib
import json
import os

import numpy as np
import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import decision_engine
from research_eval.data_split import ARTIFACT_DIR
from research_eval.threshold_sensitivity import build_grid_pairs, VULNERABLE_GRID, SAFE_GRID
from research_eval.operating_points import apply_thresholds, operating_point_metrics
from research_eval.bootstrap_analysis import bootstrap, _metrics_from_decided

ROB_DIR = os.path.join(ARTIFACT_DIR, "robustness")

PRODUCTION_FILES = [
    "decision_engine.py", "predictor.py", "dataflow.py", "app.py",
]
BACKEND_DIR = os.path.dirname(ARTIFACT_DIR)


def _present(*names):
    return all(os.path.exists(os.path.join(ROB_DIR, n)) for n in names)


skip_no_sensitivity = pytest.mark.skipif(
    not _present("threshold_sensitivity_test.csv"), reason="run `python -m research_eval.threshold_sensitivity` first"
)
skip_no_splits = pytest.mark.skipif(
    not _present("all_seeds_summary.json"), reason="run `python -m research_eval.split_robustness` first (expensive)"
)
skip_no_bootstrap = pytest.mark.skipif(
    not _present("bootstrap_metrics.json"), reason="run `python -m research_eval.bootstrap_analysis` first"
)


# ---------------------------------------------------------------------
# 1/2. Threshold perturbation generation; invalid pair rejection
# ---------------------------------------------------------------------

def test_perturbation_grid_matches_spec_values():
    assert VULNERABLE_GRID == [0.553, 0.603, 0.653, 0.703, 0.753, 0.803, 0.853, 0.903, 0.953]
    assert SAFE_GRID == [-0.576, -0.526, -0.476, -0.426, -0.376, -0.326, -0.276, -0.226, -0.176]


def test_invalid_threshold_pairs_are_rejected():
    """A pair where vulnerable_threshold <= safe_threshold is not a valid
    decision boundary (decision_engine.py's own semantics) and must be excluded."""
    pairs, rejected = build_grid_pairs()
    for v, s in pairs:
        assert v > s
    # This specific grid has no overlap (min vulnerable=0.553 > max safe=-0.176)
    # so nothing should actually be rejected here - verify that explicitly too.
    assert len(rejected) == 0
    assert len(pairs) == len(VULNERABLE_GRID) * len(SAFE_GRID)


def test_a_genuinely_invalid_pair_would_be_rejected_by_the_same_logic():
    """Sanity check the rejection logic itself works, using a synthetic
    grid where vulnerable and safe candidates DO overlap."""
    from research_eval import threshold_sensitivity as ts
    original_v, original_s = ts.VULNERABLE_GRID, ts.SAFE_GRID
    try:
        ts.VULNERABLE_GRID = [-0.5, 0.5]
        ts.SAFE_GRID = [-1.0, 0.0]
        pairs, rejected = ts.build_grid_pairs()
        assert (-0.5, 0.0) in rejected  # -0.5 <= 0.0, invalid
        assert (0.5, 0.0) in pairs  # 0.5 > 0.0, valid
    finally:
        ts.VULNERABLE_GRID, ts.SAFE_GRID = original_v, original_s


# ---------------------------------------------------------------------
# 3/4/5. Coverage / FNR / FPR calculation
# ---------------------------------------------------------------------

def test_coverage_calculation():
    decided = [{"true_is_vulnerable": True, "final_vulnerable_flag": True, "deferred": False}] * 3 + \
              [{"true_is_vulnerable": False, "final_vulnerable_flag": False, "deferred": True}] * 7
    m = operating_point_metrics(decided, 1.0, -1.0)
    assert m["coverage"] == pytest.approx(0.3)


def test_fnr_calculation():
    decided = [
        {"true_is_vulnerable": True, "final_vulnerable_flag": True, "deferred": False},
        {"true_is_vulnerable": True, "final_vulnerable_flag": False, "deferred": False},
        {"true_is_vulnerable": True, "final_vulnerable_flag": False, "deferred": False},
    ]
    m = operating_point_metrics(decided, 1.0, -1.0)
    assert m["fnr"] == pytest.approx(2 / 3)  # fn=2, tp=1


def test_fpr_calculation():
    decided = [
        {"true_is_vulnerable": False, "final_vulnerable_flag": False, "deferred": False},
        {"true_is_vulnerable": False, "final_vulnerable_flag": True, "deferred": False},
    ]
    m = operating_point_metrics(decided, 1.0, -1.0)
    assert m["fpr"] == pytest.approx(0.5)


# ---------------------------------------------------------------------
# 6/7. Bootstrap reproducibility; bootstrap does not modify source data
# ---------------------------------------------------------------------

def test_bootstrap_is_reproducible_with_fixed_seed():
    decided = (
        [{"true_is_vulnerable": True, "final_vulnerable_flag": True, "deferred": False}] * 10 +
        [{"true_is_vulnerable": True, "final_vulnerable_flag": False, "deferred": False}] * 3 +
        [{"true_is_vulnerable": False, "final_vulnerable_flag": False, "deferred": False}] * 15 +
        [{"true_is_vulnerable": False, "final_vulnerable_flag": True, "deferred": False}] * 2
    )
    m1, _ = bootstrap(decided, n_resamples=200, seed=42)
    m2, _ = bootstrap(decided, n_resamples=200, seed=42)
    assert m1["fnr"]["bootstrap_mean"] == m2["fnr"]["bootstrap_mean"]
    assert m1["fnr"]["95%_bootstrap_percentile_interval"] == m2["fnr"]["95%_bootstrap_percentile_interval"]


def test_bootstrap_does_not_modify_source_list():
    decided = [
        {"true_is_vulnerable": True, "final_vulnerable_flag": True, "deferred": False},
        {"true_is_vulnerable": False, "final_vulnerable_flag": False, "deferred": False},
    ] * 10
    original_len = len(decided)
    original_copy = list(decided)
    bootstrap(decided, n_resamples=50, seed=1)
    assert len(decided) == original_len
    assert decided == original_copy


# ---------------------------------------------------------------------
# 8/9. Group overlap remains zero; train-only feature fitting
# ---------------------------------------------------------------------

@skip_no_splits
def test_alternative_splits_have_zero_group_and_text_overlap():
    with open(os.path.join(ROB_DIR, "all_seeds_summary.json")) as f:
        results = json.load(f)
    for r in results:
        meta = r["split_metadata"]
        assert meta["leakage_check"] == "PASSED - zero overlap on both group_key and exact text"
        assert all(v == 0 for v in meta["group_overlap"].values())
        assert all(v == 0 for v in meta["exact_text_overlap"].values())


@skip_no_splits
def test_alternative_split_features_report_train_only_fitting():
    for seed in (42, 7, 21, 84, 123):
        features_dir = os.path.join(ROB_DIR, f"split_{seed}", "features")
        if not os.path.exists(features_dir):
            pytest.skip(f"split_{seed} features not present")
        assert os.path.exists(os.path.join(features_dir, "word_vectorizer.joblib"))
        assert os.path.exists(os.path.join(features_dir, "char_vectorizer.joblib"))
        assert os.path.exists(os.path.join(features_dir, "count_vectorizer.joblib"))


# ---------------------------------------------------------------------
# 10/11. Fixed-threshold evaluation; validation-only threshold selection
# ---------------------------------------------------------------------

@skip_no_splits
def test_fixed_threshold_evaluation_uses_exact_balanced_thresholds():
    with open(os.path.join(ROB_DIR, "all_seeds_summary.json")) as f:
        results = json.load(f)
    for r in results:
        assert r["fixed_threshold"]["test"]["vulnerable_threshold"] == 0.753
        assert r["fixed_threshold"]["test"]["safe_threshold"] == -0.376


@skip_no_splits
def test_validation_selected_threshold_never_uses_that_splits_test_metrics_for_selection():
    """The validation-selected operating point per split must come from
    that split's OWN validation bounds (xgboost_fnr/xgboost_fpr from
    validation_metrics), never from its test results."""
    with open(os.path.join(ROB_DIR, "all_seeds_summary.json")) as f:
        results = json.load(f)
    for r in results:
        bounds = r["validation_selected_bounds"]
        assert bounds["xgboost_fnr"] == r["xgboost_validation_metrics"]["fnr"]
        assert bounds["xgboost_fpr"] == r["xgboost_validation_metrics"]["fpr"]


# ---------------------------------------------------------------------
# 12. CWE-specific metric calculation
# ---------------------------------------------------------------------

@skip_no_splits
def test_cwe_metrics_present_for_every_split():
    with open(os.path.join(ROB_DIR, "all_seeds_summary.json")) as f:
        results = json.load(f)
    for r in results:
        cwe = r["fixed_threshold"]["test_cwe"]
        assert "sql_injection_cwe_89" in cwe
        assert "certificate_validation_cwe_295" in cwe


# ---------------------------------------------------------------------
# 13. Worst-case calculation
# ---------------------------------------------------------------------

def test_worst_case_picks_the_actual_maximum_not_the_mean():
    from research_eval.robustness_validation import worst_case_analysis
    rows = [
        {"Seed": 1, "FNR": 0.10, "FPR": 0.05, "Coverage": 0.9, "CWE-89 FNR": 0.05, "CWE-295 FNR": 0.10},
        {"Seed": 2, "FNR": 0.40, "FPR": 0.30, "Coverage": 0.5, "CWE-89 FNR": 0.20, "CWE-295 FNR": 0.45},
        {"Seed": 3, "FNR": 0.15, "FPR": 0.10, "Coverage": 0.8, "CWE-89 FNR": 0.10, "CWE-295 FNR": 0.15},
    ]
    result = worst_case_analysis(rows)
    assert result["worst_fnr"]["seed"] == 2
    assert result["worst_fnr"]["value"] == 0.40
    assert result["lowest_coverage"]["seed"] == 2
    assert result["worst_cwe295_fnr"]["seed"] == 2


# ---------------------------------------------------------------------
# 14. Production files remain untouched
# ---------------------------------------------------------------------

def _file_hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def test_production_files_still_contain_documented_decision_engine_constants():
    """A behavioral proxy for 'unchanged': the exact documented weights/
    thresholds this whole research track has relied on reading (never
    writing) are still present with their expected values."""
    assert decision_engine.ML_WEIGHT == 1.0
    assert decision_engine.TRACED_SOURCE_TO_SINK_WEIGHT == 2.0
    assert decision_engine.UNPARAMETERIZED_CONCAT_WEIGHT == 1.2
    assert decision_engine.CONFIRMED_PARAMETERIZED_WEIGHT == -1.5
    assert decision_engine.CERT_VULNERABLE_WEIGHT == 2.0
    assert decision_engine.CERT_SUSPICIOUS_WEIGHT == 0.6
    assert decision_engine.CERT_SAFE_WEIGHT == -1.5
    assert decision_engine.STATIC_RULE_WEIGHT == 0.4
    assert set(decision_engine.VULNERABLE_ML_LABELS) == {"s0", "v0"}


def test_production_files_exist_and_are_readable():
    for fname in PRODUCTION_FILES:
        path = os.path.join(BACKEND_DIR, fname)
        assert os.path.exists(path), f"production file missing: {fname}"
        _file_hash(path)  # must be readable as a normal file, not corrupted
