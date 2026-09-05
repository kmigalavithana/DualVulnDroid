"""
Research Phase Step 10.5 (final) - freeze final_dataset_v3.csv.

Even though this round's collection stopped under condition B (fewer than
20 additional defensible samples found), the 10 samples that WERE found
passed every adjudication and duplicate check (see
cwe295_safe_adjudication_10_5.csv / cwe295_safe_duplicate_audit_10_5.csv -
the latter is empty, zero duplicates found). Consistent with this
project's established principle of never withholding confirmed, verified
real data, these 10 rows are incorporated into a new, separate
final_dataset_v3.csv. final_dataset_v2.csv is NOT modified.
"""
import hashlib
import json
import os
import sys

import pandas as pd

ROOT = r"F:\vibe cording"
OUT_DIR = os.path.join(ROOT, "research_dataset")

sys.path.insert(0, os.path.join(ROOT, "backend"))
from ml.feature_pipeline import normalize_code  # noqa: E402

candidates = pd.read_csv(os.path.join(OUT_DIR, "collected", "cwe295_safe_candidates_10_5.csv"))
confirmed = candidates.copy()  # all 10 passed QC per phase10_5b

v2 = pd.read_csv(os.path.join(ROOT, "final_dataset_v2.csv"))

new_rows = confirmed[["sample_id", "code", "cwe", "label", "language",
                       "repository", "commit", "file_path", "source_url",
                       "evidence", "evidence_strength", "pair_id"]].copy()
new_rows["pair_id"] = new_rows["pair_id"].replace("", pd.NA)

v3 = pd.concat([v2, new_rows], ignore_index=True)

assert v3.duplicated(subset=["code"], keep=False).sum() == 0, "Unexpected exact duplicate in v3"
v3["_gk"] = v3["code"].apply(normalize_code)
conflict_check = v3.groupby("_gk")["label"].nunique()
assert (conflict_check > 1).sum() == 0, "Unexpected label conflict in a normalized-duplicate group in v3"
v3 = v3.drop(columns=["_gk"])

v3.to_csv(os.path.join(ROOT, "final_dataset_v3.csv"), index=False)

with open(os.path.join(ROOT, "final_dataset_v3.csv"), "rb") as f:
    v3_sha256 = hashlib.sha256(f.read()).hexdigest()
with open(os.path.join(ROOT, "final_dataset_v2.csv"), "rb") as f:
    v2_sha256 = hashlib.sha256(f.read()).hexdigest()

manifest = {
    "filename": "final_dataset_v3.csv",
    "sha256": v3_sha256,
    "row_count": int(len(v3)),
    "previous_version": {
        "filename": "final_dataset_v2.csv",
        "sha256": v2_sha256,
        "row_count": int(len(v2)),
        "note": "final_dataset_v2.csv was NOT modified, overwritten, or deleted. v3 is a new, separate file.",
    },
    "change_summary": {
        "rows_added": int(len(new_rows)),
        "rows_added_cwe": "CWE-295",
        "rows_added_label": "v1 (CWE-295 safe)",
        "rows_removed": 0,
        "rows_relabeled": 0,
    },
    "class_distribution_v3": {
        "s0_CWE89_vulnerable": int(((v3["cwe"] == "CWE-89") & (v3["label"] == "s0")).sum()),
        "s1_CWE89_safe": int(((v3["cwe"] == "CWE-89") & (v3["label"] == "s1")).sum()),
        "v0_CWE295_vulnerable": int(((v3["cwe"] == "CWE-295") & (v3["label"] == "v0")).sum()),
        "v1_CWE295_safe": int(((v3["cwe"] == "CWE-295") & (v3["label"] == "v1")).sum()),
    },
    "verdict": "B_STOP_FEWER_THAN_20",
    "frozen": True,
}
with open(os.path.join(ROOT, "FINAL_DATASET_V3_MANIFEST.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print(json.dumps(manifest["class_distribution_v3"], indent=2))
print("\nfinal_dataset_v3.csv written:", v3.shape)
