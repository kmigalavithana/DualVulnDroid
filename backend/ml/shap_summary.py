"""
Computes REAL global SHAP feature importance for the production model
over the held-out test set (mean |SHAP value| per feature, per class).
Run from backend/, after ml/train.py:  python -m ml.shap_summary
"""

import json
import os
import numpy as np
import pandas as pd
import joblib
import shap
import xgboost as xgb

from ml.feature_pipeline import build_feature_matrix, full_feature_names, load_production_feature_config
from ml.evaluate import LABELS_ORDER

ARTIFACT_DIR = "ml/artifacts"
DATA_DIR = "ml/data"
REPORT_DIR = "ml/reports"


def main():
    wv = joblib.load(os.path.join(ARTIFACT_DIR, "word_vectorizer.pkl"))
    cv = joblib.load(os.path.join(ARTIFACT_DIR, "char_vectorizer.pkl"))
    ctv = joblib.load(os.path.join(ARTIFACT_DIR, "count_vectorizer.pkl"))
    booster = xgb.Booster()
    booster.load_model(os.path.join(ARTIFACT_DIR, "xgboost_model.json"))

    include_security, subset = load_production_feature_config(ARTIFACT_DIR)
    feature_names = np.array(full_feature_names(wv, cv, ctv, include_security=include_security, security_feature_subset=subset))

    test_df = pd.read_csv(os.path.join(DATA_DIR, "test.csv"))
    X_test = build_feature_matrix(test_df["vulnerable_line"], wv, cv, ctv,
                                   include_security=include_security, security_feature_subset=subset)
    dtest = xgb.DMatrix(X_test)

    explainer = shap.TreeExplainer(booster)
    shap_values = explainer.shap_values(dtest)
    # shap_values shape: (n_samples, n_features, n_classes) for multi:softprob in recent SHAP versions
    if isinstance(shap_values, list):
        shap_values = np.stack(shap_values, axis=-1)

    result = {}
    for class_idx, class_label in enumerate(LABELS_ORDER):
        class_shap = shap_values[:, :, class_idx] if shap_values.ndim == 3 else shap_values
        mean_abs = np.abs(class_shap).mean(axis=0)
        top_idx = np.argsort(mean_abs)[-15:][::-1]
        result[class_label] = [
            {"feature": str(feature_names[i]), "mean_abs_shap": round(float(mean_abs[i]), 5)}
            for i in top_idx
        ]

    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(os.path.join(REPORT_DIR, "shap_summary.json"), "w") as f:
        json.dump(result, f, indent=2)

    for label in LABELS_ORDER:
        print(f"\nTop SHAP features for class '{label}':")
        for entry in result[label][:8]:
            print(f"  {entry['feature']:35s} {entry['mean_abs_shap']}")


if __name__ == "__main__":
    main()
