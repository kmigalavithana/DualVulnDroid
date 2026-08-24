"""
PHASE RESEARCH-EVAL-1, Part 7: Random Forest on the common split.

Hyperparameter (n_estimators, max_depth, min_samples_leaf) selection:
GridSearchCV, TRAIN ONLY (StratifiedKFold), scoring=macro-F1. TEST is
never touched until the model is frozen.

Run from backend/:  python -m research_eval.train_random_forest
"""

import json
import os
import sys

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GridSearchCV, StratifiedKFold

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml.evaluate import LABELS_ORDER
from research_eval.data_split import load_split, ARTIFACT_DIR
from research_eval.features import load_features, transform
from research_eval.evaluate_models import full_research_evaluation, train_only_cross_validation

RANDOM_SEED = 42
OUT_DIR = os.path.join(ARTIFACT_DIR, "random_forest")
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
    param_grid = {
        "n_estimators": [200, 400],
        "max_depth": [None, 20],
        "min_samples_leaf": [1, 2],
    }
    grid = GridSearchCV(
        RandomForestClassifier(class_weight="balanced", random_state=RANDOM_SEED, n_jobs=1),
        param_grid=param_grid,
        scoring="f1_macro",
        cv=StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_SEED),
        n_jobs=1,
    )
    grid.fit(X_train, y_train)
    best_params = grid.best_params_
    cv_results = {
        "param_grid": param_grid,
        "best_params": best_params,
        "best_cv_f1_macro": float(grid.best_score_),
        "n_splits": n_splits,
        "all_candidates_mean_f1_macro": [float(s) for s in grid.cv_results_["mean_test_score"]],
        "all_candidates_std_f1_macro": [float(s) for s in grid.cv_results_["std_test_score"]],
        "all_candidates_params": grid.cv_results_["params"],
    }
    print(f"[random_forest] hyperparameter search (train-only CV): best={best_params} cv_macro_f1={grid.best_score_:.4f}")

    # --- Freeze final model: fit on TRAIN only at the selected hyperparameters ---
    final_model = RandomForestClassifier(
        class_weight="balanced", random_state=RANDOM_SEED, n_jobs=1, **best_params
    )
    final_model.fit(X_train, y_train)

    robustness = train_only_cross_validation(
        RandomForestClassifier(class_weight="balanced", random_state=RANDOM_SEED, n_jobs=1, **best_params),
        X_train, y_train, seed=RANDOM_SEED,
    )

    # --- Evaluate on validation (reporting only) ---
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
        "model": "Random Forest (RandomForestClassifier)",
        "random_seed": RANDOM_SEED,
        "feature_dims": int(X_train.shape[1]),
        "hyperparameter_search": cv_results,
        "final_hyperparameters": {**best_params, "class_weight": "balanced"},
        "train_only_cv_robustness_check": robustness,
        "split_sizes": {"train": len(train_df), "validation": len(val_df), "test": len(test_df)},
    }
    with open(os.path.join(OUT_DIR, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    with open(os.path.join(OUT_DIR, "validation_metrics.json"), "w") as f:
        json.dump(val_metrics, f, indent=2)
    with open(os.path.join(OUT_DIR, "test_metrics.json"), "w") as f:
        json.dump(test_metrics, f, indent=2)

    print(f"[random_forest] test acc={test_metrics['accuracy']:.4f} macro_f1={test_metrics['macro_f1']:.4f} "
          f"roc_auc={test_metrics['roc_auc']}")
    return final_model, metadata, val_metrics, test_metrics


if __name__ == "__main__":
    main()
