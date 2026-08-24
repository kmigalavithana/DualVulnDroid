"""
PHASE RESEARCH-EVAL-1, Part 6: Linear SVM on the common split.

Hyperparameter (C) selection: GridSearchCV, TRAIN ONLY (StratifiedKFold),
scoring=macro-F1. TEST is never touched until the model is frozen.

LinearSVC has no predict_proba; wrapped in CalibratedClassifierCV (fit on
TRAIN only, exactly as the existing production comparison in ml/train.py
already does) so ROC-AUC/vulnerable-score can be computed the same way
as the other two models.

Run from backend/:  python -m research_eval.train_svm
"""

import json
import os
import sys

import joblib
import numpy as np
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import GridSearchCV, StratifiedKFold

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml.evaluate import LABELS_ORDER
from research_eval.data_split import load_split, ARTIFACT_DIR
from research_eval.features import load_features, transform
from research_eval.evaluate_models import full_research_evaluation, train_only_cross_validation

RANDOM_SEED = 42
OUT_DIR = os.path.join(ARTIFACT_DIR, "svm")
LABEL_TO_INT = {label: i for i, label in enumerate(LABELS_ORDER)}
INT_TO_LABEL = {i: label for label, i in LABEL_TO_INT.items()}


def _vulnerable_score(model, X):
    probs = model.predict_proba(X)
    classes = list(model.classes_)
    vuln_idx = [classes.index(LABEL_TO_INT[l]) for l in ("s0", "v0") if LABEL_TO_INT[l] in classes]
    return probs[:, vuln_idx].sum(axis=1)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    train_df, val_df, test_df, _ = load_split()
    wv, cv, ctv = load_features()

    X_train = transform(train_df, wv, cv, ctv)
    X_val = transform(val_df, wv, cv, ctv)
    X_test = transform(test_df, wv, cv, ctv)
    y_train = np.array([LABEL_TO_INT[l] for l in train_df["label"]])
    y_val = np.array([LABEL_TO_INT[l] for l in val_df["label"]])
    y_test = np.array([LABEL_TO_INT[l] for l in test_df["label"]])

    # --- Hyperparameter search: TRAIN ONLY, cross-validated, never test ---
    n_splits = min(5, int(np.min(np.bincount(y_train))))
    param_grid = {"C": [0.01, 0.1, 1.0, 10.0]}
    grid = GridSearchCV(
        LinearSVC(class_weight="balanced", random_state=RANDOM_SEED, max_iter=5000),
        param_grid=param_grid,
        scoring="f1_macro",
        cv=StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_SEED),
        n_jobs=1,
    )
    grid.fit(X_train, y_train)
    best_C = grid.best_params_["C"]
    cv_results = {
        "candidates": param_grid["C"],
        # NOTE: sklearn's GridSearchCV.cv_results_ calls each held-out
        # cross-validation FOLD (within the TRAIN split) a "test" fold -
        # that is sklearn's own internal CV terminology, unrelated to this
        # project's held-out TEST SET. Renamed here to "cv_fold" to avoid
        # any ambiguity when this metadata is read later.
        "mean_cv_fold_f1_macro_per_candidate": [float(s) for s in grid.cv_results_["mean_test_score"]],
        "std_cv_fold_f1_macro_per_candidate": [float(s) for s in grid.cv_results_["std_test_score"]],
        "best_C": best_C,
        "best_cv_f1_macro": float(grid.best_score_),
        "n_splits": n_splits,
    }
    print(f"[svm] hyperparameter search (train-only CV): best C={best_C} cv_macro_f1={grid.best_score_:.4f}")

    # --- Freeze final model: calibrated LinearSVC at best_C, fit on TRAIN only ---
    final_model = CalibratedClassifierCV(
        LinearSVC(C=best_C, class_weight="balanced", random_state=RANDOM_SEED, max_iter=5000), cv=3
    )
    final_model.fit(X_train, y_train)

    # Additional robustness check (Part 14): CV mean/std of the frozen
    # configuration itself, train-only.
    robustness = train_only_cross_validation(
        LinearSVC(C=best_C, class_weight="balanced", random_state=RANDOM_SEED, max_iter=5000),
        X_train, y_train, seed=RANDOM_SEED,
    )

    # --- Evaluate on validation (reporting only - model already frozen) ---
    val_pred_int = final_model.predict(X_val)
    val_pred_labels = [INT_TO_LABEL[i] for i in val_pred_int]
    val_true_labels = [INT_TO_LABEL[i] for i in y_val]
    val_metrics = full_research_evaluation(val_true_labels, val_pred_labels, _vulnerable_score(final_model, X_val))

    # --- Evaluate on test EXACTLY ONCE ---
    test_pred_int = final_model.predict(X_test)
    test_pred_labels = [INT_TO_LABEL[i] for i in test_pred_int]
    test_true_labels = [INT_TO_LABEL[i] for i in y_test]
    test_metrics = full_research_evaluation(test_true_labels, test_pred_labels, _vulnerable_score(final_model, X_test))

    joblib.dump(final_model, os.path.join(OUT_DIR, "model.joblib"))

    metadata = {
        "model": "Linear SVM (LinearSVC, CalibratedClassifierCV for probabilities)",
        "random_seed": RANDOM_SEED,
        "feature_dims": int(X_train.shape[1]),
        "hyperparameter_search": cv_results,
        "final_hyperparameters": {
            "C": best_C,
            "class_weight": "balanced",
            "max_iter": 5000,
            "calibration": "CalibratedClassifierCV(cv=3), fit on train split only",
        },
        "train_only_cv_robustness_check": robustness,
        "split_sizes": {"train": len(train_df), "validation": len(val_df), "test": len(test_df)},
    }
    with open(os.path.join(OUT_DIR, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    with open(os.path.join(OUT_DIR, "validation_metrics.json"), "w") as f:
        json.dump(val_metrics, f, indent=2)
    with open(os.path.join(OUT_DIR, "test_metrics.json"), "w") as f:
        json.dump(test_metrics, f, indent=2)

    print(f"[svm] test acc={test_metrics['accuracy']:.4f} macro_f1={test_metrics['macro_f1']:.4f} "
          f"roc_auc={test_metrics['roc_auc']}")
    return final_model, metadata, val_metrics, test_metrics


if __name__ == "__main__":
    main()
