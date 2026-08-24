"""
Trains and compares:
  - 4 XGBoost feature-ablation configs (baseline TF-IDF/count only,
    +structural security features, +data-flow features, full hybrid)
  - Logistic Regression / Linear SVM / Random Forest on the full hybrid
    feature set (algorithm comparison)
  - Rule-only (Experiment A, via rule_only.py)

All models are trained on the SAME train split (ml/data/train.csv,
produced by dataset_prep.py) and evaluated on the SAME held-out test
split, with a fixed random seed, so the comparison table is apples-to-
apples. Nothing here reads or writes test.csv except for final
evaluation.

Run from backend/:  python -m ml.train
"""

import json
import os
import sys
import numpy as np
import pandas as pd
import joblib
import xgboost as xgb
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.utils.class_weight import compute_class_weight

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml.feature_pipeline import fit_vectorizers, build_feature_matrix, full_feature_names
from ml.evaluate import full_evaluation, LABELS_ORDER
from ml.rule_only import evaluate_rule_only
from security_features import STRUCTURAL_FEATURE_NAMES, DATAFLOW_FEATURE_NAMES

DATA_DIR = "ml/data"
ARTIFACT_DIR = "ml/artifacts"
REPORT_DIR = "ml/reports"
RANDOM_SEED = 42

LABEL_TO_INT = {label: i for i, label in enumerate(LABELS_ORDER)}
INT_TO_LABEL = {i: label for label, i in LABEL_TO_INT.items()}


def load_splits():
    train = pd.read_csv(os.path.join(DATA_DIR, "train.csv"))
    val = pd.read_csv(os.path.join(DATA_DIR, "val.csv"))
    test = pd.read_csv(os.path.join(DATA_DIR, "test.csv"))
    return train, val, test


def to_dmatrix(codes, labels, wv, cv, ctv, include_security, subset, weights=None):
    X = build_feature_matrix(codes, wv, cv, ctv, include_security=include_security, security_feature_subset=subset)
    y = np.array([LABEL_TO_INT[l] for l in labels])
    return xgb.DMatrix(X, label=y, weight=weights), X, y


def vulnerable_score_from_softprob(probs: np.ndarray) -> np.ndarray:
    # s0 (index 0) and v0 (index 1) are the two "vulnerable" classes.
    return probs[:, LABEL_TO_INT["s0"]] + probs[:, LABEL_TO_INT["v0"]]


def train_xgb_config(name, train_df, val_df, test_df, wv, cv, ctv, include_security, subset, params):
    class_weights = compute_class_weight(
        "balanced", classes=np.arange(len(LABELS_ORDER)),
        y=np.array([LABEL_TO_INT[l] for l in train_df["label"]])
    )
    train_w = np.array([class_weights[LABEL_TO_INT[l]] for l in train_df["label"]])

    dtrain, _, _ = to_dmatrix(train_df["vulnerable_line"], train_df["label"], wv, cv, ctv, include_security, subset, train_w)
    dval, _, y_val = to_dmatrix(val_df["vulnerable_line"], val_df["label"], wv, cv, ctv, include_security, subset)
    dtest, X_test, y_test = to_dmatrix(test_df["vulnerable_line"], test_df["label"], wv, cv, ctv, include_security, subset)

    booster = xgb.train(
        params, dtrain, num_boost_round=300,
        evals=[(dval, "val")], early_stopping_rounds=20, verbose_eval=False
    )

    val_probs = booster.predict(dval, iteration_range=(0, booster.best_iteration + 1))
    val_pred_labels = [INT_TO_LABEL[i] for i in np.argmax(val_probs, axis=1)]
    y_val_labels = [INT_TO_LABEL[i] for i in y_val]
    val_metrics = full_evaluation(y_val_labels, val_pred_labels, vulnerable_score_from_softprob(val_probs))

    probs = booster.predict(dtest, iteration_range=(0, booster.best_iteration + 1))
    pred_int = np.argmax(probs, axis=1)
    y_true_labels = [INT_TO_LABEL[i] for i in y_test]
    y_pred_labels = [INT_TO_LABEL[i] for i in pred_int]
    vuln_score = vulnerable_score_from_softprob(probs)

    metrics = full_evaluation(y_true_labels, y_pred_labels, vuln_score)
    metrics["best_iteration"] = int(booster.best_iteration)
    metrics["feature_dims"] = int(dtrain.num_col())
    metrics["validation_macro_f1"] = val_metrics["macro_f1"]
    metrics["validation_accuracy"] = val_metrics["accuracy"]

    return booster, metrics


def select_xgb_hyperparams(train_df, val_df, wv, cv, ctv):
    """Small bounded search (dataset is only ~790 train rows, this is fast)
    on the full-hybrid feature set, selected by validation macro-F1."""
    class_weights = compute_class_weight(
        "balanced", classes=np.arange(len(LABELS_ORDER)),
        y=np.array([LABEL_TO_INT[l] for l in train_df["label"]])
    )
    train_w = np.array([class_weights[LABEL_TO_INT[l]] for l in train_df["label"]])
    dtrain, _, _ = to_dmatrix(train_df["vulnerable_line"], train_df["label"], wv, cv, ctv, True, None, train_w)
    dval, _, y_val = to_dmatrix(val_df["vulnerable_line"], val_df["label"], wv, cv, ctv, True, None)
    y_val_labels = [INT_TO_LABEL[i] for i in y_val]

    candidates = [
        {"max_depth": 4, "eta": 0.1},
        {"max_depth": 6, "eta": 0.1},
        {"max_depth": 6, "eta": 0.05},
        {"max_depth": 8, "eta": 0.1},
    ]
    best_f1, best_params, best_rounds = -1, None, None

    for cand in candidates:
        params = {
            "objective": "multi:softprob", "num_class": len(LABELS_ORDER),
            "eval_metric": "mlogloss", "seed": RANDOM_SEED, **cand,
        }
        booster = xgb.train(params, dtrain, num_boost_round=300,
                             evals=[(dval, "val")], early_stopping_rounds=20, verbose_eval=False)
        probs = booster.predict(dval, iteration_range=(0, booster.best_iteration + 1))
        pred_labels = [INT_TO_LABEL[i] for i in np.argmax(probs, axis=1)]
        f1 = full_evaluation(y_val_labels, pred_labels, vulnerable_score_from_softprob(probs))["macro_f1"]
        if f1 > best_f1:
            best_f1, best_params, best_rounds = f1, cand, booster.best_iteration + 1

    return best_params, best_rounds, best_f1


def train_sklearn_model(name, model, train_df, test_df, wv, cv, ctv):
    X_train = build_feature_matrix(train_df["vulnerable_line"], wv, cv, ctv, include_security=True)
    y_train = np.array([LABEL_TO_INT[l] for l in train_df["label"]])
    X_test = build_feature_matrix(test_df["vulnerable_line"], wv, cv, ctv, include_security=True)
    y_test = np.array([LABEL_TO_INT[l] for l in test_df["label"]])

    model.fit(X_train, y_train)

    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(X_test)
        classes = list(model.classes_)
        vuln_idx = [classes.index(LABEL_TO_INT[l]) for l in ("s0", "v0") if LABEL_TO_INT[l] in classes]
        vuln_score = probs[:, vuln_idx].sum(axis=1)
    else:
        pred = model.predict(X_test)
        vuln_score = np.array([1.0 if INT_TO_LABEL[p] in ("s0", "v0") else 0.0 for p in pred])

    pred_int = model.predict(X_test)
    y_true_labels = [INT_TO_LABEL[i] for i in y_test]
    y_pred_labels = [INT_TO_LABEL[i] for i in pred_int]

    metrics = full_evaluation(y_true_labels, y_pred_labels, vuln_score)
    metrics["feature_dims"] = int(X_train.shape[1])
    return model, metrics


def main():
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    os.makedirs(REPORT_DIR, exist_ok=True)

    train_df, val_df, test_df = load_splits()
    print(f"[data] train={len(train_df)} val={len(val_df)} test={len(test_df)}")

    wv, cv, ctv = fit_vectorizers(train_df["vulnerable_line"])
    joblib.dump(wv, os.path.join(ARTIFACT_DIR, "word_vectorizer.pkl"))
    joblib.dump(cv, os.path.join(ARTIFACT_DIR, "char_vectorizer.pkl"))
    joblib.dump(ctv, os.path.join(ARTIFACT_DIR, "count_vectorizer.pkl"))
    print("[vectorizers] fit on train split only, saved.")

    best_params, best_rounds, best_val_f1 = select_xgb_hyperparams(train_df, val_df, wv, cv, ctv)
    print(f"[hparam search] best={best_params} rounds={best_rounds} val_macro_f1={best_val_f1:.4f}")

    xgb_params_base = {
        "objective": "multi:softprob", "num_class": len(LABELS_ORDER),
        "eval_metric": "mlogloss", "seed": RANDOM_SEED, **best_params,
    }

    ablation_configs = {
        "xgb_baseline_tfidf_only": dict(include_security=False, subset=None),
        "xgb_plus_structural_features": dict(include_security=True, subset=STRUCTURAL_FEATURE_NAMES),
        "xgb_plus_dataflow_features": dict(include_security=True, subset=DATAFLOW_FEATURE_NAMES),
        "xgb_full_hybrid": dict(include_security=True, subset=None),
    }

    results = {}
    boosters = {}
    for name, cfg in ablation_configs.items():
        booster, metrics = train_xgb_config(
            name, train_df, val_df, test_df, wv, cv, ctv,
            cfg["include_security"], cfg["subset"], dict(xgb_params_base)
        )
        results[name] = metrics
        boosters[name] = booster
        # Every ablation config's booster is kept for transparency/reproducibility,
        # even though only one gets promoted to the live "xgboost_model.json" below.
        booster.save_model(os.path.join(ARTIFACT_DIR, f"ablation_{name}.json"))
        print(f"[{name}] test acc={metrics['accuracy']:.4f} macro_f1={metrics['macro_f1']:.4f} "
              f"val_macro_f1={metrics['validation_macro_f1']:.4f} "
              f"roc_auc={metrics['roc_auc']} fpr={metrics['false_positive_rate']:.4f} fnr={metrics['false_negative_rate']:.4f}")

    # Select the PRODUCTION ablation config by VALIDATION macro-F1 (never by
    # test performance - that would be tuning the deployment choice on the
    # supposedly-held-out test set). See ml/reports/model_comparison.json for
    # how this compares to the other configs on the untouched test split.
    production_config_name = max(ablation_configs, key=lambda n: results[n]["validation_macro_f1"])
    boosters[production_config_name].save_model(os.path.join(ARTIFACT_DIR, "xgboost_model.json"))
    print(f"[production] selected '{production_config_name}' by validation macro-F1 "
          f"({results[production_config_name]['validation_macro_f1']:.4f}) -> ml/artifacts/xgboost_model.json")

    # ---- Algorithm comparison on the full hybrid feature set ----
    sklearn_models = {
        "logistic_regression": LogisticRegression(max_iter=2000, class_weight="balanced", random_state=RANDOM_SEED),
        "linear_svm": CalibratedClassifierCV(
            LinearSVC(class_weight="balanced", random_state=RANDOM_SEED, max_iter=5000), cv=3
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=300, class_weight="balanced", random_state=RANDOM_SEED
        ),
    }
    fitted_sklearn = {}
    for name, model in sklearn_models.items():
        fitted, metrics = train_sklearn_model(name, model, train_df, test_df, wv, cv, ctv)
        fitted_sklearn[name] = fitted
        results[name] = metrics
        print(f"[{name}] test acc={metrics['accuracy']:.4f} macro_f1={metrics['macro_f1']:.4f} "
              f"roc_auc={metrics['roc_auc']}")
    results["xgboost_full_hybrid_for_comparison"] = results["xgb_full_hybrid"]

    # ---- Experiment A: rule-only ----
    y_true_rule, y_pred_rule, scores_rule = evaluate_rule_only(test_df)
    results["rule_only"] = full_evaluation(y_true_rule, y_pred_rule, scores_rule)
    print(f"[rule_only] test acc={results['rule_only']['accuracy']:.4f} "
          f"macro_f1={results['rule_only']['macro_f1']:.4f} "
          f"fpr={results['rule_only']['false_positive_rate']:.4f} fnr={results['rule_only']['false_negative_rate']:.4f}")

    # ---- Save everything ----
    training_config = {
        "random_seed": RANDOM_SEED,
        "label_order": LABELS_ORDER,
        "production_config": production_config_name,
        "production_selection_method": "max validation_macro_f1 across the 4 ablation configs",
        "production_include_security_features": ablation_configs[production_config_name]["include_security"],
        "production_security_feature_subset": ablation_configs[production_config_name]["subset"],
        "xgb_hyperparams": xgb_params_base,
        "xgb_selected_rounds_hint": best_rounds,
        "val_macro_f1_at_selection": best_val_f1,
        "vectorizer_params": {
            "word": "max_features=5000, ngram_range=(1,3)",
            "char": "max_features=2000, ngram_range=(2,5), analyzer=char",
            "count": "max_features=1000, ngram_range=(1,2)",
        },
        "feature_dims": {name: results[name]["feature_dims"] for name in ablation_configs if "feature_dims" in results[name]},
        "class_balancing": "sklearn compute_class_weight('balanced') applied as XGBoost sample weights / sklearn class_weight",
    }
    with open(os.path.join(ARTIFACT_DIR, "training_config.json"), "w") as f:
        json.dump(training_config, f, indent=2)

    with open(os.path.join(REPORT_DIR, "model_comparison.json"), "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n[done] artifacts -> {ARTIFACT_DIR}/, reports -> {REPORT_DIR}/model_comparison.json")
    return results, boosters, fitted_sklearn, (wv, cv, ctv), (train_df, val_df, test_df)


if __name__ == "__main__":
    main()
