"""
PHASE RESEARCH-EVAL-1, Part 8: XGBoost on the common split.

Per the spec, XGBoost uses VALIDATION ONLY for early stopping and
hyperparameter/model selection (not train-only cross-validation like the
other two models - this mirrors XGBoost's own native early-stopping
mechanism, and is the same selection method already used in production
by ml/train.py's select_xgb_hyperparams). TEST is never touched until
the model is frozen.

Run from backend/:  python -m research_eval.train_xgboost
"""

import json
import os
import sys

import numpy as np
import xgboost as xgb
from sklearn.utils.class_weight import compute_class_weight

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml.evaluate import LABELS_ORDER
from research_eval.data_split import load_split, ARTIFACT_DIR
from research_eval.features import load_features, transform
from research_eval.evaluate_models import full_research_evaluation

RANDOM_SEED = 42
OUT_DIR = os.path.join(ARTIFACT_DIR, "xgboost")
LABEL_TO_INT = {label: i for i, label in enumerate(LABELS_ORDER)}
INT_TO_LABEL = {i: label for label, i in LABEL_TO_INT.items()}

HYPERPARAM_CANDIDATES = [
    {"max_depth": 4, "eta": 0.1},
    {"max_depth": 6, "eta": 0.1},
    {"max_depth": 6, "eta": 0.05},
    {"max_depth": 8, "eta": 0.1},
]


def _vulnerable_score(probs):
    return probs[:, LABEL_TO_INT["s0"]] + probs[:, LABEL_TO_INT["v0"]]


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

    class_weights = compute_class_weight("balanced", classes=np.arange(len(LABELS_ORDER)), y=y_train)
    train_w = np.array([class_weights[i] for i in y_train])

    dtrain = xgb.DMatrix(X_train, label=y_train, weight=train_w)
    dval = xgb.DMatrix(X_val, label=y_val)
    dtest = xgb.DMatrix(X_test, label=y_test)

    # --- Model/hyperparameter selection: VALIDATION ONLY, never test ---
    candidate_results = []
    best_f1, best_params, best_booster, best_rounds = -1, None, None, None
    for cand in HYPERPARAM_CANDIDATES:
        params = {
            "objective": "multi:softprob", "num_class": len(LABELS_ORDER),
            "eval_metric": "mlogloss", "seed": RANDOM_SEED, **cand,
        }
        booster = xgb.train(
            params, dtrain, num_boost_round=300,
            evals=[(dval, "val")], early_stopping_rounds=20, verbose_eval=False,
        )
        val_probs = booster.predict(dval, iteration_range=(0, booster.best_iteration + 1))
        val_pred_labels = [INT_TO_LABEL[i] for i in np.argmax(val_probs, axis=1)]
        val_true_labels = [INT_TO_LABEL[i] for i in y_val]
        val_f1 = full_research_evaluation(val_true_labels, val_pred_labels, _vulnerable_score(val_probs))["macro_f1"]
        candidate_results.append({**cand, "val_macro_f1": val_f1, "best_iteration": int(booster.best_iteration)})
        print(f"[xgboost] candidate {cand} -> val_macro_f1={val_f1:.4f} best_iter={booster.best_iteration}")
        if val_f1 > best_f1:
            best_f1, best_params, best_booster, best_rounds = val_f1, cand, booster, booster.best_iteration + 1

    print(f"[xgboost] selected {best_params} by validation macro-F1={best_f1:.4f}")

    # --- Frozen model: the booster already trained (with early stopping) at
    # the selected hyperparameters. Re-evaluate its validation metrics fully
    # (reporting only - selection already happened above) and test ONCE. ---
    val_probs = best_booster.predict(dval, iteration_range=(0, best_booster.best_iteration + 1))
    val_pred_labels = [INT_TO_LABEL[i] for i in np.argmax(val_probs, axis=1)]
    val_true_labels = [INT_TO_LABEL[i] for i in y_val]
    val_metrics = full_research_evaluation(val_true_labels, val_pred_labels, _vulnerable_score(val_probs))

    test_probs = best_booster.predict(dtest, iteration_range=(0, best_booster.best_iteration + 1))
    test_pred_labels = [INT_TO_LABEL[i] for i in np.argmax(test_probs, axis=1)]
    test_true_labels = [INT_TO_LABEL[i] for i in y_test]
    test_metrics = full_research_evaluation(test_true_labels, test_pred_labels, _vulnerable_score(test_probs))

    best_booster.save_model(os.path.join(OUT_DIR, "model.json"))

    metadata = {
        "model": "XGBoost (multi:softprob, 4-class)",
        "random_seed": RANDOM_SEED,
        "feature_dims": int(X_train.shape[1]),
        "hyperparameter_candidates_evaluated_on_validation": candidate_results,
        "selection_method": "max validation macro-F1 across candidates (validation used for early stopping AND model selection, never test)",
        "final_hyperparameters": {
            "objective": "multi:softprob", "num_class": len(LABELS_ORDER),
            "eval_metric": "mlogloss", "seed": RANDOM_SEED, **best_params,
            "num_boost_round_selected": int(best_rounds),
            "early_stopping_rounds": 20,
        },
        "class_balancing": "sklearn compute_class_weight('balanced') applied as XGBoost sample weights",
        "split_sizes": {"train": len(train_df), "validation": len(val_df), "test": len(test_df)},
    }
    with open(os.path.join(OUT_DIR, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    with open(os.path.join(OUT_DIR, "validation_metrics.json"), "w") as f:
        json.dump(val_metrics, f, indent=2)
    with open(os.path.join(OUT_DIR, "test_metrics.json"), "w") as f:
        json.dump(test_metrics, f, indent=2)

    print(f"[xgboost] test acc={test_metrics['accuracy']:.4f} macro_f1={test_metrics['macro_f1']:.4f} "
          f"roc_auc={test_metrics['roc_auc']}")
    return best_booster, metadata, val_metrics, test_metrics


if __name__ == "__main__":
    main()
