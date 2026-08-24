"""
PHASE RESEARCH-EVAL-1, Part 19: tests for the fair common-split model
comparison in research_eval/.

Two groups of tests:

1. Pure unit tests (evaluate_models.py's metric functions, on small
   synthetic inputs) - always run, no dependency on the full pipeline
   having been executed.

2. Artifact tests - verify the actual on-disk split/model/metric
   artifacts produced by `python -m research_eval.data_split` /
   `.features` / `.train_svm` / `.train_random_forest` / `.train_xgboost`
   / `.compare_models`. These are the tests that directly verify the
   spec's fairness requirements (identical split, no leakage, no
   test-time refitting, identical test samples across all 3 models,
   correct binary mapping, correct confusion-matrix dimensions). They
   skip (not fail) if the artifacts haven't been generated yet in this
   checkout, matching the project's existing convention for
   generated-artifact-dependent tests (e.g. the REAL_APK_FIXTURE_PATH
   tests in test_apk_metadata.py) - a missing artifact is a "not run
   yet" state, not a failure of the code itself.
"""

import json
import os

import numpy as np
import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research_eval.evaluate_models import (
    full_research_evaluation,
    vulnerability_specific_metrics,
    BINARY_MAPPING_DOC,
    SQLI_LABELS,
    CERT_LABELS,
)
from ml.evaluate import LABELS_ORDER, VULNERABLE_LABELS

ARTIFACT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "research_eval_artifacts")
MODEL_DIRS = {"Linear SVM": "svm", "Random Forest": "random_forest", "XGBoost": "xgboost"}


def _artifacts_present():
    return os.path.exists(os.path.join(ARTIFACT_DIR, "test_indices.json"))


def _models_trained():
    return all(
        os.path.exists(os.path.join(ARTIFACT_DIR, d, "test_metrics.json"))
        for d in MODEL_DIRS.values()
    )


skip_no_split = pytest.mark.skipif(not _artifacts_present(), reason="research_eval_artifacts/ split not generated yet - run `python -m research_eval.data_split` first")
skip_no_models = pytest.mark.skipif(not _models_trained(), reason="research_eval models not trained yet - run the three train_*.py scripts first")


# ---------------------------------------------------------------------
# 1. Pure unit tests - metric functions
# ---------------------------------------------------------------------

def test_binary_vulnerability_mapping_is_correct():
    """Part 7/11: VULNERABLE = {s0, v0}, SAFE = {s1, v1} - not invented for
    this phase, must match the existing production mapping exactly."""
    assert VULNERABLE_LABELS == {"s0", "v0"}
    assert SQLI_LABELS == {"s0", "s1"}
    assert CERT_LABELS == {"v0", "v1"}
    assert "s0, v0" in BINARY_MAPPING_DOC


def test_confusion_matrix_has_correct_dimensions():
    """Part 10: the 4-class confusion matrix must be 4x4, one row/column
    per label in LABELS_ORDER, regardless of which labels actually appear
    in a given (possibly small) sample."""
    y_true = ["s0", "s0", "v0", "v1", "s1"]
    y_pred = ["s0", "s1", "v0", "v1", "s1"]
    result = full_research_evaluation(y_true, y_pred, vulnerable_score=[0.9, 0.4, 0.8, 0.1, 0.2])
    cm = result["confusion_matrix"]
    assert len(cm) == len(LABELS_ORDER) == 4
    assert all(len(row) == 4 for row in cm)
    assert result["confusion_matrix_labels"] == LABELS_ORDER
    assert sum(sum(row) for row in cm) == len(y_true)


def test_metrics_are_generated_consistently_and_include_required_fields():
    """Part 9/10/11: one call must produce macro+weighted 4-class metrics,
    per-class report, binary FPR/FNR/ROC-AUC, and both CWE-specific
    breakdowns - the exact shape every train_*.py script relies on."""
    y_true = ["s0"] * 10 + ["s1"] * 10 + ["v0"] * 10 + ["v1"] * 10
    y_pred = ["s0"] * 8 + ["s1"] * 2 + ["s1"] * 8 + ["s0"] * 2 + ["v0"] * 9 + ["v1"] * 1 + ["v1"] * 10
    scores = [0.9] * 8 + [0.4] * 2 + [0.3] * 8 + [0.6] * 2 + [0.85] * 9 + [0.2] * 1 + [0.1] * 10

    result = full_research_evaluation(y_true, y_pred, vulnerable_score=scores)

    for key in ("accuracy", "macro_precision", "macro_recall", "macro_f1",
                "weighted_precision", "weighted_recall", "weighted_f1",
                "false_positive_rate", "false_negative_rate", "roc_auc",
                "per_class", "vulnerability_specific", "binary_mapping_documentation"):
        assert key in result, f"missing required metric field: {key}"

    for label in LABELS_ORDER:
        assert label in result["per_class"]
        for field in ("precision", "recall", "f1", "support"):
            assert field in result["per_class"][label]

    assert "sql_injection_cwe_89" in result["vulnerability_specific"]
    assert "certificate_validation_cwe_295" in result["vulnerability_specific"]


def test_vulnerability_specific_split_uses_true_label_task_only():
    """Part 11: a row's TASK (SQLi vs cert) is determined by its TRUE
    label, never its prediction - a model that mispredicts across tasks
    (e.g. true=s0, predicted=v0) must still be scored within the SQLi
    task using its true task membership."""
    y_true = ["s0", "s1", "v0", "v1"]
    y_pred = ["v0", "s1", "s0", "v1"]  # first two predictions cross tasks
    result = vulnerability_specific_metrics(y_true, y_pred)
    assert result["sql_injection_cwe_89"]["support"] == 2  # s0, s1 rows only
    assert result["certificate_validation_cwe_295"]["support"] == 2  # v0, v1 rows only


def test_roc_auc_is_none_when_binary_labels_have_only_one_class():
    """Part 9: 'If ROC-AUC is not mathematically appropriate... explain
    why rather than fabricating a value' - here, explicitly return None
    rather than a fabricated/undefined AUC when only one binary class is
    present in the sample."""
    y_true = ["s1", "v1", "v1"]  # all SAFE - binary_true has only one class
    y_pred = ["s1", "v1", "v1"]
    result = full_research_evaluation(y_true, y_pred, vulnerable_score=[0.1, 0.05, 0.2])
    assert result["roc_auc"] is None


# ---------------------------------------------------------------------
# 2. Artifact tests - the actual generated split/models
# ---------------------------------------------------------------------

@skip_no_split
def test_split_indices_are_disjoint_and_cover_the_clean_dataset():
    """Part 4: no train/test (or train/val, val/test) overlap."""
    with open(os.path.join(ARTIFACT_DIR, "train_indices.json")) as f:
        train_idx = set(json.load(f))
    with open(os.path.join(ARTIFACT_DIR, "validation_indices.json")) as f:
        val_idx = set(json.load(f))
    with open(os.path.join(ARTIFACT_DIR, "test_indices.json")) as f:
        test_idx = set(json.load(f))

    assert train_idx.isdisjoint(val_idx), "LEAKAGE: train/validation index overlap"
    assert train_idx.isdisjoint(test_idx), "LEAKAGE: train/test index overlap"
    assert val_idx.isdisjoint(test_idx), "LEAKAGE: validation/test index overlap"

    import pandas as pd
    clean = pd.read_csv(os.path.join(ARTIFACT_DIR, "clean_dataset.csv"))
    assert len(train_idx) + len(val_idx) + len(test_idx) == len(clean), \
        "every row in the clean dataset must be assigned to exactly one split"


@skip_no_split
def test_split_metadata_reports_zero_cross_split_overlap():
    with open(os.path.join(ARTIFACT_DIR, "split_metadata.json")) as f:
        meta = json.load(f)
    overlap = meta["leakage_check"]["cross_split_normalized_template_overlap"]
    assert overlap == {"train_val": 0, "train_test": 0, "val_test": 0}
    text_overlap = meta["leakage_check"]["cross_split_exact_text_overlap"]
    assert text_overlap == {"train_val": 0, "train_test": 0, "val_test": 0}


@skip_no_split
def test_vectorizer_fitted_only_on_train_split():
    """Part 5: 'Do NOT fit vectorizers/scalers using the test set.'"""
    feature_meta_path = os.path.join(ARTIFACT_DIR, "shared_features", "feature_metadata.json")
    if not os.path.exists(feature_meta_path):
        pytest.skip("shared feature pipeline not fitted yet - run `python -m research_eval.features` first")
    with open(feature_meta_path) as f:
        meta = json.load(f)
    with open(os.path.join(ARTIFACT_DIR, "train_indices.json")) as f:
        train_idx = json.load(f)

    assert meta["fitted_on"] == "train split only (research_eval_artifacts/train_indices.json)"
    assert meta["fitted_on_n_samples"] == len(train_idx)


@skip_no_split
def test_validation_and_test_transform_does_not_refit_vectorizer():
    """Part 5: transforming val/test must reuse the train-fitted vocabulary
    unchanged - calling transform() must never mutate the fitted vectorizer."""
    features_dir = os.path.join(ARTIFACT_DIR, "shared_features")
    if not os.path.exists(os.path.join(features_dir, "word_vectorizer.joblib")):
        pytest.skip("shared feature pipeline not fitted yet")

    from research_eval.data_split import load_split
    from research_eval.features import load_features, transform

    train_df, val_df, test_df, _ = load_split()
    wv, cv, ctv = load_features()
    vocab_before = dict(wv.vocabulary_)

    _ = transform(val_df, wv, cv, ctv)
    _ = transform(test_df, wv, cv, ctv)

    assert wv.vocabulary_ == vocab_before, "transforming val/test must not mutate the train-fitted vectorizer"


@skip_no_models
def test_all_three_models_produce_predictions_for_the_identical_test_set():
    """Part 16/19: the whole point of this phase - every model's test
    metrics must have been computed over the exact same test rows."""
    with open(os.path.join(ARTIFACT_DIR, "test_indices.json")) as f:
        n_expected = len(json.load(f))

    sample_counts = {}
    for name, dirname in MODEL_DIRS.items():
        with open(os.path.join(ARTIFACT_DIR, dirname, "test_metrics.json")) as f:
            m = json.load(f)
        cm = m["confusion_matrix"]
        sample_counts[name] = sum(sum(row) for row in cm)

    for name, n in sample_counts.items():
        assert n == n_expected, f"{name} scored {n} test samples, expected {n_expected} (test_indices.json)"

    assert len(set(sample_counts.values())) == 1, \
        f"models did not all score the same number of test samples: {sample_counts}"


@skip_no_models
def test_each_model_confusion_matrix_is_4x4():
    for name, dirname in MODEL_DIRS.items():
        with open(os.path.join(ARTIFACT_DIR, dirname, "test_metrics.json")) as f:
            m = json.load(f)
        cm = m["confusion_matrix"]
        assert len(cm) == 4, f"{name}: confusion matrix has {len(cm)} rows, expected 4"
        assert all(len(row) == 4 for row in cm), f"{name}: confusion matrix rows are not all length 4"


@skip_no_models
def test_no_model_metadata_references_test_set_during_hyperparameter_selection():
    """Part 6/7/8/16: the hyperparameter search/selection record's own
    values must not equal the frozen test-set metrics - i.e. selection
    was not silently driven by test performance. (Note: sklearn's
    GridSearchCV.cv_results_ labels each held-out CV fold *within train*
    a "test" fold - that is sklearn's internal terminology for cross-
    validation, unrelated to this project's held-out test set, so this
    check compares actual values rather than key names.)"""
    for name, dirname in MODEL_DIRS.items():
        with open(os.path.join(ARTIFACT_DIR, dirname, "metadata.json")) as f:
            meta = json.load(f)
        with open(os.path.join(ARTIFACT_DIR, dirname, "test_metrics.json")) as f:
            test_metrics = json.load(f)

        search = meta.get("hyperparameter_search") or {"candidates": meta.get("hyperparameter_candidates_evaluated_on_validation")}
        search_values = json.dumps(search)

        # The exact frozen test-set macro-F1 must never appear as one of the
        # scores considered during selection.
        test_f1_str = json.dumps(round(test_metrics["macro_f1"], 6))
        assert test_f1_str not in search_values, (
            f"{name}: frozen test macro_f1 ({test_metrics['macro_f1']}) appears inside the "
            f"hyperparameter search record - selection may have used the test set"
        )


@skip_no_models
def test_comparison_summary_fairness_check_passed():
    summary_path = os.path.join(ARTIFACT_DIR, "comparison", "comparison_summary.json")
    if not os.path.exists(summary_path):
        pytest.skip("run `python -m research_eval.compare_models` first")
    with open(summary_path) as f:
        summary = json.load(f)
    assert summary["fairness_check"].startswith("PASSED")
