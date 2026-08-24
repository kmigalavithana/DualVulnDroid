"""
PHASE RESEARCH-EVAL-1, Part 5: ONE shared feature-construction pipeline
for all three models.

This does not create a new feature pipeline - it reuses the project's
existing, already-production feature pipeline verbatim
(ml/feature_pipeline.py: normalize_code, fit_vectorizers,
build_feature_matrix, full_feature_names, backed by security_features.py
for the CWE-89/CWE-295 structural + data-flow feature block). The only
thing this module adds is fitting the vectorizers exactly ONCE (on the
TRAIN split only, never val/test) and persisting them under
research_eval_artifacts/shared_features/, so all three model-training
scripts load the identical, already-fitted vectorizers instead of each
independently re-fitting (which - since TfidfVectorizer/CountVectorizer
fitting is deterministic given the same input - would produce identical
vectorizers anyway, but loading one shared copy removes any risk of
divergence and matches the spec's "ONE consistent feature-construction
protocol" requirement unambiguously).

Run from backend/:  python -m research_eval.features
"""

import json
import os
import sys

import joblib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml.feature_pipeline import (
    fit_vectorizers,
    build_feature_matrix,
    full_feature_names,
    WORD_VECTORIZER_PARAMS,
    CHAR_VECTORIZER_PARAMS,
    COUNT_VECTORIZER_PARAMS,
)
from security_features import FEATURE_NAMES as SECURITY_FEATURE_NAMES
from research_eval.data_split import load_split, ARTIFACT_DIR

FEATURES_DIR = os.path.join(ARTIFACT_DIR, "shared_features")


def fit_and_save():
    train_df, _, _, _ = load_split()

    wv, cv, ctv = fit_vectorizers(train_df["vulnerable_line"])  # TRAIN ONLY - never val/test

    os.makedirs(FEATURES_DIR, exist_ok=True)
    joblib.dump(wv, os.path.join(FEATURES_DIR, "word_vectorizer.joblib"))
    joblib.dump(cv, os.path.join(FEATURES_DIR, "char_vectorizer.joblib"))
    joblib.dump(ctv, os.path.join(FEATURES_DIR, "count_vectorizer.joblib"))

    names = full_feature_names(wv, cv, ctv, include_security=True, security_feature_subset=None)
    metadata = {
        "fitted_on": "train split only (research_eval_artifacts/train_indices.json)",
        "fitted_on_n_samples": int(len(train_df)),
        "word_vectorizer_params": WORD_VECTORIZER_PARAMS,
        "char_vectorizer_params": CHAR_VECTORIZER_PARAMS,
        "count_vectorizer_params": COUNT_VECTORIZER_PARAMS,
        "security_feature_names": SECURITY_FEATURE_NAMES,
        "total_feature_dims": len(names),
        "text_feature_dims": len(names) - len(SECURITY_FEATURE_NAMES),
        "security_feature_dims": len(SECURITY_FEATURE_NAMES),
        "source_module": "ml.feature_pipeline (production feature pipeline, reused unmodified)",
    }
    with open(os.path.join(FEATURES_DIR, "feature_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    return wv, cv, ctv, metadata


def load_features():
    wv = joblib.load(os.path.join(FEATURES_DIR, "word_vectorizer.joblib"))
    cv = joblib.load(os.path.join(FEATURES_DIR, "char_vectorizer.joblib"))
    ctv = joblib.load(os.path.join(FEATURES_DIR, "count_vectorizer.joblib"))
    return wv, cv, ctv


def transform(df, wv, cv, ctv):
    """Transform-only (never re-fits) - safe to call on train, val, or test."""
    return build_feature_matrix(df["vulnerable_line"], wv, cv, ctv, include_security=True)


def load_xgboost_booster():
    """Loads the frozen research_eval XGBoost model AND its selected
    num_boost_round cutoff together. xgb.Booster.save_model() persists
    every tree trained before early stopping fired, not just the ones up
    to best_iteration - calling .predict() on a reloaded booster WITHOUT
    restricting iteration_range to the originally-selected round count
    silently uses extra, non-selected trees and produces predictions that
    do not match train_xgboost.py's own frozen test_metrics.json. Every
    script that reloads this model for further analysis must use the
    num_boost_round returned here.
    """
    import xgboost as xgb

    booster = xgb.Booster()
    booster.load_model(os.path.join(ARTIFACT_DIR, "xgboost", "model.json"))
    with open(os.path.join(ARTIFACT_DIR, "xgboost", "metadata.json")) as f:
        meta = json.load(f)
    num_boost_round = meta["final_hyperparameters"]["num_boost_round_selected"]
    return booster, num_boost_round


def xgboost_predict(booster, num_boost_round, X):
    import xgboost as xgb

    return booster.predict(xgb.DMatrix(X), iteration_range=(0, num_boost_round))


if __name__ == "__main__":
    _, _, _, metadata = fit_and_save()
    print(json.dumps(metadata, indent=2))
