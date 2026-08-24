"""
PHASE RESEARCH-EVAL-4, Parts 8-11: robustness of the Balanced candidate
under alternative grouped+stratified splits of the SAME 1,128-row clean
dataset (different seeds), each with its own freshly-fit vectorizers and
freshly-trained XGBoost.

Scope note (Part 9): only XGBoost + Decision Engine is retrained per
alternative split, not the full SVM/RF/XGBoost comparison from
RESEARCH-EVAL-1. Reproducing all three models x 5 splits would be a
~5x cost multiplier on top of an already-expensive pipeline for a
question (decision-engine robustness) that XGBoost + Decision Engine
alone already answers - RQ1-RQ4 are about the Balanced operating
point's stability, not about re-litigating the SVM-vs-XGBoost model
comparison. This is a deliberate, documented scope decision, not a
silent omission.

The ORIGINAL frozen split/model/artifacts (research_eval_artifacts/{
train,validation,test}_indices.json, research_eval_artifacts/xgboost/)
are never read from or written to by this module except to load the raw
dataset path - everything alternative-split-specific is written under
research_eval_artifacts/robustness/split_<seed>/.

Run from backend/:  python -m research_eval.split_robustness
"""

import json
import os
import sys

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.utils.class_weight import compute_class_weight

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import decision_engine
from ml.dataset_prep import load_raw, split_conflicting_labels, grouped_stratified_split, assert_no_group_leakage
from ml.evaluate import LABELS_ORDER, VULNERABLE_LABELS
from ml.feature_pipeline import fit_vectorizers, build_feature_matrix
from research_eval.data_split import ARTIFACT_DIR as ORIGINAL_ARTIFACT_DIR
from research_eval.evaluate_models import full_research_evaluation
from research_eval.operating_points import (
    build_threshold_grid, apply_thresholds as apply_thresholds_to_evidence,
    operating_point_metrics, cwe_metrics_for_operating_point,
)
from dataflow import analyze_sql_dataflow, analyze_cert_dataflow, sql_sink_safety_summary
from ml.experiment_d import rule_keyword_hit_for

SEEDS = [42, 7, 21, 84, 123]
BALANCED_VULNERABLE = 0.753
BALANCED_SAFE = -0.376
LABEL_TO_INT = {label: i for i, label in enumerate(LABELS_ORDER)}
INT_TO_LABEL = {i: label for label, i in LABEL_TO_INT.items()}

ROBUSTNESS_DIR = os.path.join(ORIGINAL_ARTIFACT_DIR, "robustness")
XGB_HYPERPARAM_CANDIDATES = [
    {"max_depth": 4, "eta": 0.1}, {"max_depth": 6, "eta": 0.1},
    {"max_depth": 6, "eta": 0.05}, {"max_depth": 8, "eta": 0.1},
]


def split_dir(seed):
    return os.path.join(ROBUSTNESS_DIR, f"split_{seed}")


def build_split_for_seed(seed):
    """Reuses ml.dataset_prep's exact, already-validated leakage-safe
    algorithm - just with a different seed - never overwrites the
    original research_eval_artifacts/{train,validation,test}_indices.json."""
    raw = load_raw()
    clean, excluded, n_conflicting = split_conflicting_labels(raw)  # seed-independent (label-noise exclusion, not splitting)
    clean_indexed = clean.reset_index().rename(columns={"index": "clean_index"})

    train_df, val_df, test_df = grouped_stratified_split(clean_indexed, seed=seed)
    assert_no_group_leakage(train_df, val_df, test_df)

    # Explicit anti-leakage checks (Part 26), not just trusted from the shared assertion:
    train_texts, val_texts, test_texts = set(train_df["vulnerable_line"]), set(val_df["vulnerable_line"]), set(test_df["vulnerable_line"])
    exact_text_overlap = {
        "train_val": len(train_texts & val_texts), "train_test": len(train_texts & test_texts), "val_test": len(val_texts & test_texts),
    }
    train_groups, val_groups, test_groups = set(train_df["group_key"]), set(val_df["group_key"]), set(test_df["group_key"])
    group_overlap = {
        "train_val": len(train_groups & val_groups), "train_test": len(train_groups & test_groups), "val_test": len(val_groups & test_groups),
    }
    if any(v > 0 for v in exact_text_overlap.values()) or any(v > 0 for v in group_overlap.values()):
        raise AssertionError(f"LEAKAGE DETECTED for seed={seed}: group_overlap={group_overlap} exact_text_overlap={exact_text_overlap}")

    out_dir = split_dir(seed)
    os.makedirs(out_dir, exist_ok=True)
    train_df.drop(columns=["group_key"]).to_csv(os.path.join(out_dir, "train.csv"), index=False)
    val_df.drop(columns=["group_key"]).to_csv(os.path.join(out_dir, "val.csv"), index=False)
    test_df.drop(columns=["group_key"]).to_csv(os.path.join(out_dir, "test.csv"), index=False)

    metadata = {
        "seed": seed, "raw_row_count": len(raw), "clean_row_count": len(clean),
        "split_sizes": {"train": len(train_df), "validation": len(val_df), "test": len(test_df)},
        "split_fractions": {"train": round(len(train_df) / len(clean), 4), "validation": round(len(val_df) / len(clean), 4), "test": round(len(test_df) / len(clean), 4)},
        "group_overlap": group_overlap, "exact_text_overlap": exact_text_overlap,
        "leakage_check": "PASSED - zero overlap on both group_key and exact text" if all(v == 0 for v in {**group_overlap, **exact_text_overlap}.values()) else "FAILED",
    }
    with open(os.path.join(out_dir, "split_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    return train_df, val_df, test_df, metadata


def fit_features_for_split(seed, train_df):
    """Vectorizers fit on THIS split's train only - never its own val/test,
    never the original split's data."""
    wv, cv, ctv = fit_vectorizers(train_df["vulnerable_line"])
    out_dir = os.path.join(split_dir(seed), "features")
    os.makedirs(out_dir, exist_ok=True)
    joblib.dump(wv, os.path.join(out_dir, "word_vectorizer.joblib"))
    joblib.dump(cv, os.path.join(out_dir, "char_vectorizer.joblib"))
    joblib.dump(ctv, os.path.join(out_dir, "count_vectorizer.joblib"))
    return wv, cv, ctv


def train_xgboost_for_split(seed, train_df, val_df, wv, cv, ctv):
    X_train = build_feature_matrix(train_df["vulnerable_line"], wv, cv, ctv, include_security=True)
    X_val = build_feature_matrix(val_df["vulnerable_line"], wv, cv, ctv, include_security=True)
    y_train = np.array([LABEL_TO_INT[l] for l in train_df["label"]])
    y_val = np.array([LABEL_TO_INT[l] for l in val_df["label"]])

    class_weights = compute_class_weight("balanced", classes=np.arange(len(LABELS_ORDER)), y=y_train)
    train_w = np.array([class_weights[i] for i in y_train])
    dtrain = xgb.DMatrix(X_train, label=y_train, weight=train_w)
    dval = xgb.DMatrix(X_val, label=y_val)

    best_f1, best_params, best_booster, best_rounds = -1, None, None, None
    for cand in XGB_HYPERPARAM_CANDIDATES:
        params = {"objective": "multi:softprob", "num_class": len(LABELS_ORDER), "eval_metric": "mlogloss", "seed": seed, **cand}
        booster = xgb.train(params, dtrain, num_boost_round=300, evals=[(dval, "val")], early_stopping_rounds=20, verbose_eval=False)
        probs = booster.predict(dval, iteration_range=(0, booster.best_iteration + 1))
        pred_labels = [INT_TO_LABEL[i] for i in np.argmax(probs, axis=1)]
        y_val_labels = [INT_TO_LABEL[i] for i in y_val]
        vuln_score = probs[:, LABEL_TO_INT["s0"]] + probs[:, LABEL_TO_INT["v0"]]
        f1 = full_research_evaluation(y_val_labels, pred_labels, vuln_score)["macro_f1"]
        if f1 > best_f1:
            best_f1, best_params, best_booster, best_rounds = f1, cand, booster, booster.best_iteration + 1

    out_dir = os.path.join(split_dir(seed), "xgboost")
    os.makedirs(out_dir, exist_ok=True)
    best_booster.save_model(os.path.join(out_dir, "model.json"))

    val_probs = best_booster.predict(dval, iteration_range=(0, best_booster.best_iteration + 1))
    val_pred_labels = [INT_TO_LABEL[i] for i in np.argmax(val_probs, axis=1)]
    y_val_labels = [INT_TO_LABEL[i] for i in y_val]
    val_vuln_score = val_probs[:, LABEL_TO_INT["s0"]] + val_probs[:, LABEL_TO_INT["v0"]]
    val_metrics = full_research_evaluation(y_val_labels, val_pred_labels, val_vuln_score)

    metadata = {
        "seed": seed, "selected_hyperparameters": {**best_params, "num_boost_round": int(best_rounds)},
        "early_stopping_rounds": 20, "selection_method": "max validation macro-F1 across 4 candidates (validation only)",
        "validation_macro_f1": best_f1, "feature_dims": int(X_train.shape[1]),
        "train_size": len(train_df), "validation_size": len(val_df),
    }
    with open(os.path.join(out_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    with open(os.path.join(out_dir, "validation_metrics.json"), "w") as f:
        json.dump(val_metrics, f, indent=2)

    return best_booster, best_rounds, metadata, val_metrics


def compute_evidence_for_split(df, booster, num_boost_round, wv, cv, ctv):
    X = build_feature_matrix(df["vulnerable_line"], wv, cv, ctv, include_security=True)
    probs = booster.predict(xgb.DMatrix(X), iteration_range=(0, num_boost_round))

    records = []
    for i, row in df.reset_index(drop=True).iterrows():
        code = row["vulnerable_line"]
        true_label = row["label"]
        p = probs[i]
        top_idx = int(np.argmax(p))
        ml_label = INT_TO_LABEL[top_idx]
        ml_confidence_pct = float(p[top_idx] * 100)

        sql_flow = analyze_sql_dataflow(code)
        cert_flow = analyze_cert_dataflow(code)
        sink_safety = sql_sink_safety_summary(code)
        rule_hit = rule_keyword_hit_for(code, ml_label)

        evidence_score, reasons = decision_engine.compute_evidence(ml_label, ml_confidence_pct, sql_flow, cert_flow, sink_safety, rule_hit)
        records.append({
            "row_identifier": int(row.get("clean_index", i)), "true_label": true_label,
            "true_is_vulnerable": true_label in VULNERABLE_LABELS,
            "xgb_prediction": ml_label, "xgb_confidence_pct": ml_confidence_pct,
            "evidence_score": evidence_score, "reasons": reasons,
        })
    return records


def evaluate_seed(seed):
    print(f"[split_robustness] seed={seed}: building split...")
    train_df, val_df, test_df, split_meta = build_split_for_seed(seed)

    print(f"[split_robustness] seed={seed}: fitting features on train only...")
    wv, cv, ctv = fit_features_for_split(seed, train_df)

    print(f"[split_robustness] seed={seed}: training XGBoost (validation-only selection)...")
    booster, num_boost_round, xgb_meta, xgb_val_metrics = train_xgboost_for_split(seed, train_df, val_df, wv, cv, ctv)

    val_evidence = compute_evidence_for_split(val_df, booster, num_boost_round, wv, cv, ctv)
    test_evidence = compute_evidence_for_split(test_df, booster, num_boost_round, wv, cv, ctv)

    # --- A. Fixed-threshold robustness: apply 0.753/-0.376 unchanged ---
    fixed_val_decided = apply_thresholds_to_evidence(val_evidence, BALANCED_VULNERABLE, BALANCED_SAFE)
    fixed_test_decided = apply_thresholds_to_evidence(test_evidence, BALANCED_VULNERABLE, BALANCED_SAFE)
    fixed_val_metrics = operating_point_metrics(fixed_val_decided, BALANCED_VULNERABLE, BALANCED_SAFE)
    fixed_test_metrics = operating_point_metrics(fixed_test_decided, BALANCED_VULNERABLE, BALANCED_SAFE)
    fixed_test_cwe = cwe_metrics_for_operating_point(fixed_test_decided)

    # --- B. Validation-selected robustness: reproduce the Balanced SELECTION
    # RULE (max coverage s.t. FNR<=this split's own XGBoost val FNR AND
    # FPR<=this split's own XGBoost val FPR) on THIS split's validation only,
    # then apply the result to THIS split's test exactly once. ---
    grid = build_threshold_grid(val_evidence)
    all_val_results = []
    for v in grid["vulnerable_threshold_candidates"]:
        for s in grid["safe_threshold_candidates"]:
            if v <= s:
                continue
            decided = apply_thresholds_to_evidence(val_evidence, v, s)
            all_val_results.append(operating_point_metrics(decided, v, s))

    bounds = {"xgboost_fnr": xgb_val_metrics["false_negative_rate"], "xgboost_fpr": xgb_val_metrics["false_positive_rate"]}
    eligible = [r for r in all_val_results if r["fnr"] is not None and r["fnr"] <= bounds["xgboost_fnr"]
                and r["fpr"] is not None and r["fpr"] <= bounds["xgboost_fpr"]]
    selected_point = max(eligible, key=lambda r: r["coverage"]) if eligible else None

    if selected_point is not None:
        vt_decided = apply_thresholds_to_evidence(test_evidence, selected_point["vulnerable_threshold"], selected_point["safe_threshold"])
        vt_test_metrics = operating_point_metrics(vt_decided, selected_point["vulnerable_threshold"], selected_point["safe_threshold"])
        vt_test_cwe = cwe_metrics_for_operating_point(vt_decided)
    else:
        vt_test_metrics, vt_test_cwe = None, None

    result = {
        "seed": seed, "split_metadata": split_meta, "xgboost_metadata": xgb_meta,
        "xgboost_validation_metrics": {"macro_f1": xgb_val_metrics["macro_f1"], "fnr": xgb_val_metrics["false_negative_rate"], "fpr": xgb_val_metrics["false_positive_rate"]},
        "fixed_threshold": {"validation": fixed_val_metrics, "test": fixed_test_metrics, "test_cwe": fixed_test_cwe},
        "validation_selected_bounds": bounds,
        "validation_selected_operating_point": selected_point,
        "validation_selected_threshold_test_result": {"test": vt_test_metrics, "test_cwe": vt_test_cwe},
    }

    out_dir = split_dir(seed)
    with open(os.path.join(out_dir, "robustness_result.json"), "w") as f:
        json.dump(result, f, indent=2)

    print(f"[split_robustness] seed={seed}: fixed-threshold test coverage={fixed_test_metrics['coverage']:.3f} "
          f"fnr={fixed_test_metrics['fnr']} | validation-selected test coverage="
          f"{vt_test_metrics['coverage'] if vt_test_metrics else None} fnr={vt_test_metrics['fnr'] if vt_test_metrics else None}")
    return result


def main():
    os.makedirs(ROBUSTNESS_DIR, exist_ok=True)
    results = []
    for seed in SEEDS:
        results.append(evaluate_seed(seed))

    with open(os.path.join(ROBUSTNESS_DIR, "all_seeds_summary.json"), "w") as f:
        json.dump(results, f, indent=2)

    return results


if __name__ == "__main__":
    main()
