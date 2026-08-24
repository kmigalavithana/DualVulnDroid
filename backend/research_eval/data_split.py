"""
PHASE RESEARCH-EVAL-1, Part 3/4: ONE common, fixed, leakage-safe
train/validation/test split shared by all three models (Linear SVM,
Random Forest, XGBoost) in this research evaluation.

This does NOT re-implement dataset cleaning/splitting from scratch. It
reuses ml/dataset_prep.py's already-existing, already-validated
grouped + stratified 70/15/15 split (exact-duplicate-with-conflicting-
label exclusion, near-duplicate grouping via normalize_code(), group-
aware GroupShuffleSplit, fixed seed=42) UNMODIFIED, so this experiment's
split is guaranteed identical to the production dataset-prep pipeline
under the same seed - it does not invent a second, divergent splitting
algorithm.

What this script ADDS on top of dataset_prep.py (which only writes
train.csv/val.csv/test.csv with no stable positional reference):
  - a canonical, positionally-indexable "clean_dataset.csv" (the same
    conflict-free row population dataset_prep.py splits, saved with an
    explicit 0..N-1 row position)
  - train_indices.json / validation_indices.json / test_indices.json:
    the exact positions (into clean_dataset.csv) assigned to each split,
    so every one of the three model-training scripts can load the
    IDENTICAL rows by index rather than three independently-regenerated
    (if deterministic) splits
  - explicit exact-duplicate / near-duplicate / cross-split-overlap
    reporting (Part 4 of the spec), beyond dataset_prep.py's single
    pass/fail leakage assertion

Run from backend/:  python -m research_eval.data_split
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml.dataset_prep import (
    load_raw,
    split_conflicting_labels,
    grouped_stratified_split,
    assert_no_group_leakage,
    RANDOM_SEED,
)
from ml.feature_pipeline import normalize_code

ARTIFACT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "research_eval_artifacts")


def _exact_duplicate_report(df):
    """Exact-duplicate-text rows (same vulnerable_line, any label), reported
    separately from the near-duplicate/group_key check below - two rows can
    be exact-text duplicates while sharing the same label (not conflicting,
    so dataset_prep.py's conflict filter does not touch them), which is
    still worth reporting as required by Part 4 of the spec."""
    counts = df["vulnerable_line"].value_counts()
    dup_texts = counts[counts > 1]
    return {
        "exact_duplicate_text_groups": int(len(dup_texts)),
        "exact_duplicate_text_rows": int(dup_texts.sum()),
    }


def _near_duplicate_report(df):
    """Near-duplicate = same normalize_code() template (the project's
    existing near-duplicate definition, ml/feature_pipeline.normalize_code -
    used consistently for both training features and this leakage check,
    per Part 5's 'prefer the existing pipeline' instruction)."""
    counts = df["group_key"].value_counts()
    dup_groups = counts[counts > 1]
    return {
        "near_duplicate_template_groups": int(len(dup_groups)),
        "near_duplicate_template_rows": int(dup_groups.sum()),
    }


def _cross_split_report(train_df, val_df, test_df):
    train_groups, val_groups, test_groups = set(train_df["group_key"]), set(val_df["group_key"]), set(test_df["group_key"])
    train_texts, val_texts, test_texts = (
        set(train_df["vulnerable_line"]), set(val_df["vulnerable_line"]), set(test_df["vulnerable_line"]),
    )
    return {
        "cross_split_normalized_template_overlap": {
            "train_val": len(train_groups & val_groups),
            "train_test": len(train_groups & test_groups),
            "val_test": len(val_groups & test_groups),
        },
        "cross_split_exact_text_overlap": {
            "train_val": len(train_texts & val_texts),
            "train_test": len(train_texts & test_texts),
            "val_test": len(val_texts & test_texts),
        },
    }


def build_split():
    os.makedirs(ARTIFACT_DIR, exist_ok=True)

    raw = load_raw()
    clean, excluded, n_conflicting_groups = split_conflicting_labels(raw)
    # 0..N-1 position becomes an explicit column so it survives the
    # groupby/iloc/concat operations inside grouped_stratified_split()
    # (whose own final reset_index(drop=True) would otherwise discard it).
    clean_indexed = clean.reset_index().rename(columns={"index": "clean_index"})

    train_df, val_df, test_df = grouped_stratified_split(clean_indexed)
    assert_no_group_leakage(train_df, val_df, test_df)  # same assertion dataset_prep.py already relies on

    train_idx = sorted(int(i) for i in train_df["clean_index"])
    val_idx = sorted(int(i) for i in val_df["clean_index"])
    test_idx = sorted(int(i) for i in test_df["clean_index"])

    assert set(train_idx).isdisjoint(val_idx) and set(train_idx).isdisjoint(test_idx) and set(val_idx).isdisjoint(test_idx), \
        "index sets must be mutually disjoint"
    assert len(train_idx) + len(val_idx) + len(test_idx) == len(clean), "every clean row must be assigned to exactly one split"

    # Canonical, positionally-stable dataset every index file refers into.
    clean_out = clean.drop(columns=["group_key"]).reset_index(drop=True)
    clean_out.to_csv(os.path.join(ARTIFACT_DIR, "clean_dataset.csv"), index=False)
    excluded.to_csv(os.path.join(ARTIFACT_DIR, "excluded_conflicting_labels.csv"), index=False)

    with open(os.path.join(ARTIFACT_DIR, "train_indices.json"), "w") as f:
        json.dump(train_idx, f)
    with open(os.path.join(ARTIFACT_DIR, "validation_indices.json"), "w") as f:
        json.dump(val_idx, f)
    with open(os.path.join(ARTIFACT_DIR, "test_indices.json"), "w") as f:
        json.dump(test_idx, f)

    exact_dup = _exact_duplicate_report(clean)
    near_dup = _near_duplicate_report(clean)
    cross_split = _cross_split_report(train_df, val_df, test_df)

    metadata = {
        "random_seed": RANDOM_SEED,
        "raw_dataset_path": "dataset .csv",
        "raw_row_count": int(len(raw)),
        "raw_label_distribution": raw["label"].value_counts().to_dict(),
        "excluded_conflicting_label_rows": int(len(excluded)),
        "excluded_conflicting_label_groups": int(n_conflicting_groups),
        "exclusion_reason": (
            "Exact-duplicate-text-with-conflicting-label AND near-duplicate-"
            "template-with-conflicting-label rows: the same normalize_code() "
            "template maps to more than one distinct label elsewhere in the "
            "raw dataset. This is label noise, not benign duplication - kept "
            "out of train/val/test entirely (saved separately in "
            "excluded_conflicting_labels.csv, not silently dropped)."
        ),
        "clean_row_count": int(len(clean)),
        "clean_label_distribution": clean["label"].value_counts().to_dict(),
        "split_group_definition": "ml.feature_pipeline.normalize_code(vulnerable_line) - identical function used for TF-IDF/count text normalization",
        "split_sizes": {"train": len(train_idx), "validation": len(val_idx), "test": len(test_idx)},
        "split_fractions": {
            "train": round(len(train_idx) / len(clean), 4),
            "validation": round(len(val_idx) / len(clean), 4),
            "test": round(len(test_idx) / len(clean), 4),
        },
        "split_label_distribution": {
            "train": train_df["label"].value_counts().to_dict(),
            "validation": val_df["label"].value_counts().to_dict(),
            "test": test_df["label"].value_counts().to_dict(),
        },
        "leakage_check": {
            "group_key_disjoint_across_splits": "PASSED (assert_no_group_leakage)",
            **exact_dup,
            **near_dup,
            **cross_split,
        },
        "known_limitation": (
            "The dataset has no application/project identifier, so this is a "
            "near-duplicate-grouped split (via normalize_code() template "
            "matching), not a true application-level split - identical to the "
            "limitation already documented in ml/data/dataset_report.json."
        ),
        "reused_from": "ml.dataset_prep (split_conflicting_labels, grouped_stratified_split, assert_no_group_leakage) - not re-implemented",
    }
    with open(os.path.join(ARTIFACT_DIR, "split_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    return metadata


def load_split():
    """Used by all three train_*.py scripts and by evaluate_models.py /
    compare_models.py so every consumer reads the exact same on-disk split."""
    import pandas as pd

    clean = pd.read_csv(os.path.join(ARTIFACT_DIR, "clean_dataset.csv"))
    with open(os.path.join(ARTIFACT_DIR, "train_indices.json")) as f:
        train_idx = json.load(f)
    with open(os.path.join(ARTIFACT_DIR, "validation_indices.json")) as f:
        val_idx = json.load(f)
    with open(os.path.join(ARTIFACT_DIR, "test_indices.json")) as f:
        test_idx = json.load(f)

    train_df = clean.iloc[train_idx].reset_index(drop=True)
    val_df = clean.iloc[val_idx].reset_index(drop=True)
    test_df = clean.iloc[test_idx].reset_index(drop=True)
    return train_df, val_df, test_df, (train_idx, val_idx, test_idx)


if __name__ == "__main__":
    metadata = build_split()
    print(json.dumps(metadata, indent=2))
