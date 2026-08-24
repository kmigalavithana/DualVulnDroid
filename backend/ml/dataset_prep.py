"""
Dataset preparation / leakage-prevention pipeline.

The raw dataset (dataset .csv) has only 3 columns: vulnerable_line,
explanation, label. There is NO application/project identifier, so a
true application-level train/val/test split (as recommended in general
ML-for-code guidance) is not possible with this schema - that is a real
limitation of the current dataset, documented in dataset_report.json
rather than silently worked around.

What IS possible, and what this script does:

1. Exact-duplicate-text-with-CONFLICTING-label detection. Inspecting the
   raw data found 244 distinct code snippets that appear more than once
   with a DIFFERENT label each time (e.g. "db.rawQuery(query, null);"
   labeled s0/vulnerable in one row and s1/secure in another). This is
   label noise, not just duplication: the same input text cannot
   deterministically map to two different ground-truth labels, and if
   the two copies land on opposite sides of a train/test split the test
   metric is contaminated. These rows are EXCLUDED from the working
   dataset (not silently dropped - saved separately for inspection).

2. Near-duplicate grouping via the same normalize_code() used for
   feature extraction (ml/feature_pipeline.py): two lines that differ
   only by a string literal, character literal, or number collapse to
   the same normalized template (e.g. two lines differing only by
   variable name still differ, but two differing only by a literal
   value normalize identically). Using this as the split "group id"
   with a group-aware shuffle split ensures near-duplicate template
   variants never straddle train/test/val.

3. Stratified-by-label, grouped 70/15/15 train/val/test split with a
   fixed random seed for reproducibility.
"""

import json
import os
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml.feature_pipeline import normalize_code

RAW_DATASET_PATH = os.path.join("..", "dataset .csv")
OUT_DIR = "ml/data"
RANDOM_SEED = 42


def load_raw():
    return pd.read_csv(RAW_DATASET_PATH)


def add_group_key(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["group_key"] = df["vulnerable_line"].apply(normalize_code)
    return df


def split_conflicting_labels(df: pd.DataFrame):
    """
    Returns (clean_df, excluded_df). excluded_df holds every row whose
    normalize_code() group_key (which also catches exact-text duplicates,
    since identical text always normalizes identically) appears elsewhere
    in the dataset with a DIFFERENT label - e.g. the same boilerplate line
    (a literal SQL DDL string, a stock CertificateFactory.getInstance call)
    reused verbatim or near-verbatim in both a "vulnerable" and a "safe"
    curated example, which is label noise a classifier cannot resolve
    from the text alone. Doing this at the group_key level (rather than
    exact text) also catches near-duplicates that differ only by a
    trailing comment or a literal value.
    """
    df = add_group_key(df)
    label_counts_per_group = df.groupby("group_key")["label"].nunique()
    conflicting_groups = set(label_counts_per_group[label_counts_per_group > 1].index)

    is_conflicting = df["group_key"].isin(conflicting_groups)
    clean = df[~is_conflicting].reset_index(drop=True)
    excluded = df[is_conflicting].drop(columns=["group_key"]).reset_index(drop=True)
    return clean, excluded, len(conflicting_groups)


def grouped_stratified_split(df: pd.DataFrame, test_size=0.15, val_size=0.15, seed=RANDOM_SEED):
    """
    Approximate stratified + grouped split: splits per-label so that each
    label's rows are divided ~70/15/15 while keeping every row that
    shares a group_key (near-duplicate template) on the same side of
    the split (a group_key can only appear within a single label, since
    the conflicting-label rows were already removed).
    """
    train_frames, val_frames, test_frames = [], [], []

    for label, sub in df.groupby("label"):
        groups = sub["group_key"]
        n_groups = groups.nunique()

        if n_groups < 3:
            # Too few distinct groups to split meaningfully - keep all in train.
            train_frames.append(sub)
            continue

        gss1 = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
        train_val_idx, test_idx = next(gss1.split(sub, groups=groups))
        train_val = sub.iloc[train_val_idx]
        test = sub.iloc[test_idx]

        val_fraction_of_remainder = val_size / (1 - test_size)
        remainder_groups = train_val["group_key"]
        if remainder_groups.nunique() < 3:
            train_frames.append(train_val)
            test_frames.append(test)
            continue

        gss2 = GroupShuffleSplit(n_splits=1, test_size=val_fraction_of_remainder, random_state=seed)
        train_idx, val_idx = next(gss2.split(train_val, groups=remainder_groups))

        train_frames.append(train_val.iloc[train_idx])
        val_frames.append(train_val.iloc[val_idx])
        test_frames.append(test)

    train_df = pd.concat(train_frames).sample(frac=1, random_state=seed).reset_index(drop=True)
    val_df = pd.concat(val_frames).sample(frac=1, random_state=seed).reset_index(drop=True) if val_frames else pd.DataFrame(columns=df.columns)
    test_df = pd.concat(test_frames).sample(frac=1, random_state=seed).reset_index(drop=True) if test_frames else pd.DataFrame(columns=df.columns)

    return train_df, val_df, test_df


def assert_no_group_leakage(train_df, val_df, test_df):
    train_groups = set(train_df["group_key"])
    val_groups = set(val_df["group_key"])
    test_groups = set(test_df["group_key"])
    assert train_groups.isdisjoint(test_groups), "LEAKAGE: group_key shared between train and test"
    assert train_groups.isdisjoint(val_groups), "LEAKAGE: group_key shared between train and val"
    assert val_groups.isdisjoint(test_groups), "LEAKAGE: group_key shared between val and test"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    raw = load_raw()
    clean, excluded, conflicting_group_count = split_conflicting_labels(raw)

    train_df, val_df, test_df = grouped_stratified_split(clean)
    assert_no_group_leakage(train_df, val_df, test_df)

    train_df.drop(columns=["group_key"]).to_csv(os.path.join(OUT_DIR, "train.csv"), index=False)
    val_df.drop(columns=["group_key"]).to_csv(os.path.join(OUT_DIR, "val.csv"), index=False)
    test_df.drop(columns=["group_key"]).to_csv(os.path.join(OUT_DIR, "test.csv"), index=False)
    excluded.to_csv(os.path.join(OUT_DIR, "excluded_conflicting_labels.csv"), index=False)

    report = {
        "random_seed": RANDOM_SEED,
        "raw_row_count": len(raw),
        "excluded_conflicting_label_rows": len(excluded),
        "excluded_conflicting_label_groups": conflicting_group_count,
        "clean_row_count": len(clean),
        "clean_label_distribution": clean["label"].value_counts().to_dict(),
        "distinct_group_keys_in_clean": int(clean["group_key"].nunique()),
        "split_sizes": {
            "train": len(train_df),
            "val": len(val_df),
            "test": len(test_df),
        },
        "split_label_distribution": {
            "train": train_df["label"].value_counts().to_dict(),
            "val": val_df["label"].value_counts().to_dict(),
            "test": test_df["label"].value_counts().to_dict(),
        },
        "leakage_check": "PASSED - no normalize_code() group_key shared across splits",
        "known_limitation": (
            "The dataset has no application/project identifier, so this is a "
            "near-duplicate-grouped split (via normalize_code() template "
            "matching), not a true application-level split. Two rows with "
            "identical code after literal/number normalization are always "
            "kept in the same split; rows from the same real-world app that "
            "happen to differ textually would not be detected as related."
        ),
    }
    with open(os.path.join(OUT_DIR, "dataset_report.json"), "w") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
