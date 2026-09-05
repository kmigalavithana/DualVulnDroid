"""
Phase 1 - Preserve current evidence.

Reads the ORIGINAL raw dataset (dataset .csv) READ-ONLY, computes integrity
statistics, and writes dataset_manifest.json. Never writes back to the raw
file. A copy of the raw file's bytes is stored under research_dataset/raw/
for redundancy (still never edited after creation).
"""
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone

import pandas as pd

ROOT = r"F:\vibe cording"
RAW_PATH = os.path.join(ROOT, "dataset .csv")
RESEARCH_DIR = os.path.join(ROOT, "research_dataset")
RAW_COPY_DIR = os.path.join(RESEARCH_DIR, "raw")

sys.path.insert(0, os.path.join(ROOT, "backend"))
from ml.feature_pipeline import normalize_code  # noqa: E402


def sha256_of(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    raw_sha256 = sha256_of(RAW_PATH)

    df = pd.read_csv(RAW_PATH)
    assert list(df.columns) == ["vulnerable_line", "explanation", "label"], (
        f"Unexpected schema: {list(df.columns)}"
    )

    row_count = len(df)
    null_count = int(df.isnull().sum().sum())
    label_distribution = df["label"].value_counts().to_dict()

    # "Exact duplicate" = identical vulnerable_line text (the code-level unit of
    # analysis), consistent with the definition already established and used in
    # research_dataset_validation/ (488 exact-duplicate rows / 244 groups) -
    # duplicated code that may carry the same or a conflicting label/explanation.
    exact_dup_mask = df.duplicated(subset=["vulnerable_line"], keep=False)
    exact_duplicate_count = int(exact_dup_mask.sum())
    exact_duplicate_full_row_mask = df.duplicated(subset=["vulnerable_line", "explanation", "label"], keep=False)
    exact_duplicate_full_row_count = int(exact_duplicate_full_row_mask.sum())

    norm_keys = df["vulnerable_line"].apply(normalize_code)
    normalized_duplicate_count = int(norm_keys.duplicated(keep=False).sum())

    # Copy raw bytes into research_dataset/raw/ for redundancy (read-only artifact).
    os.makedirs(RAW_COPY_DIR, exist_ok=True)
    raw_copy_path = os.path.join(RAW_COPY_DIR, "dataset_original_copy.csv")
    if not os.path.exists(raw_copy_path):
        shutil.copyfile(RAW_PATH, raw_copy_path)
    raw_copy_sha256 = sha256_of(raw_copy_path)
    assert raw_copy_sha256 == raw_sha256, "Raw copy does not match original byte-for-byte"

    manifest = {
        "filename": "dataset .csv",
        "absolute_path": RAW_PATH,
        "sha256": raw_sha256,
        "row_count": row_count,
        "schema": list(df.columns),
        "label_mapping": {
            "s0": "CWE-89 vulnerable",
            "s1": "CWE-89 safe",
            "v0": "CWE-295 vulnerable",
            "v1": "CWE-295 safe",
        },
        "label_distribution_raw": {str(k): int(v) for k, v in label_distribution.items()},
        "null_count": null_count,
        "exact_duplicate_row_count": exact_duplicate_count,
        "exact_duplicate_row_count_definition": "rows sharing identical vulnerable_line text (matches prior research_dataset_validation methodology)",
        "exact_duplicate_full_row_count": exact_duplicate_full_row_count,
        "exact_duplicate_full_row_count_definition": "rows identical across vulnerable_line+explanation+label (stricter, informational only)",
        "normalized_duplicate_row_count": normalized_duplicate_count,
        "raw_copy_path": raw_copy_path,
        "raw_copy_sha256": raw_copy_sha256,
        "creation_timestamp": datetime.now(timezone.utc).isoformat(),
        "immutable": True,
        "note": "This manifest describes dataset .csv as read-only source evidence. "
                "The file itself is never modified, overwritten, or deleted by any "
                "script in research_dataset/scripts/.",
    }

    out_path = os.path.join(RESEARCH_DIR, "raw", "dataset_manifest.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(json.dumps(manifest, indent=2))
    print("\nWrote", out_path)


if __name__ == "__main__":
    main()
