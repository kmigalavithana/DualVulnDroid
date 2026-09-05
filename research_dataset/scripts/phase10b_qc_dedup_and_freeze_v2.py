"""
Research Phase Step 10 (continued) - QC, duplicate control, and v2 freeze.

Takes research_dataset/collected/cwe295_safe_candidates.csv (32 rows) and:
  1. Checks each candidate for exact-text and normalized-template duplication
     against BOTH the existing frozen 482-row final_dataset.csv AND the other
     candidates in this same batch.
  2. Applies the evidence-strength gate (STRONG/MODERATE enter; WEAK would be
     rejected - none were collected as WEAK, see collection script).
  3. Writes the required output files.
  4. Builds final_dataset_v2.csv (frozen 482 + confirmed new safe rows) and
     FINAL_DATASET_V2_MANIFEST.json, WITHOUT touching final_dataset.csv.
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

candidates = pd.read_csv(os.path.join(OUT_DIR, "collected", "cwe295_safe_candidates.csv"))
candidates["group_key"] = candidates["code"].apply(normalize_code)

frozen = pd.read_csv(os.path.join(ROOT, "final_dataset.csv"))
frozen["group_key"] = frozen["code"].apply(normalize_code)

# ---- exact-text duplicate check against frozen dataset ----
frozen_exact_texts = set(frozen["code"])
candidates["exact_dup_vs_frozen"] = candidates["code"].isin(frozen_exact_texts)

# ---- normalized-template duplicate check against frozen dataset ----
frozen_norm = set(frozen["group_key"])
candidates["normalized_dup_vs_frozen"] = candidates["group_key"].isin(frozen_norm)

# ---- internal exact/normalized duplicate check among the 32 candidates ----
candidates["exact_dup_internal"] = candidates.duplicated(subset=["code"], keep=False)
candidates["normalized_dup_internal"] = candidates["group_key"].duplicated(keep=False)

# ---- adjudication: STRONG/MODERATE evidence gate + duplicate rejection ----
def adjudicate(row):
    if row["exact_dup_vs_frozen"]:
        return "REJECTED_EXACT_DUPLICATE_OF_FROZEN"
    if row["exact_dup_internal"]:
        return "REJECTED_EXACT_DUPLICATE_INTERNAL"
    if row["normalized_dup_vs_frozen"]:
        return "REJECTED_NORMALIZED_DUPLICATE_OF_FROZEN"
    if row["normalized_dup_internal"]:
        return "REJECTED_NORMALIZED_DUPLICATE_INTERNAL"
    if row["evidence_strength"] not in ("STRONG", "MODERATE"):
        return "REJECTED_WEAK_EVIDENCE"
    return "CONFIRMED_SAFE"

candidates["disposition"] = candidates.apply(adjudicate, axis=1)

# ---- write cwe295_safe_adjudication.csv ----
adjudication_cols = [
    "sample_id", "cwe", "label", "code", "evidence_strength", "disposition",
    "exact_dup_vs_frozen", "normalized_dup_vs_frozen",
    "exact_dup_internal", "normalized_dup_internal", "evidence",
]
candidates[adjudication_cols].to_csv(
    os.path.join(OUT_DIR, "audit", "cwe295_safe_adjudication.csv"), index=False
)

# ---- write cwe295_safe_duplicate_audit.csv (only rows with any dup flag) ----
dup_mask = (
    candidates["exact_dup_vs_frozen"] | candidates["normalized_dup_vs_frozen"]
    | candidates["exact_dup_internal"] | candidates["normalized_dup_internal"]
)
candidates[dup_mask][
    ["sample_id", "code", "group_key", "exact_dup_vs_frozen", "normalized_dup_vs_frozen",
     "exact_dup_internal", "normalized_dup_internal"]
].to_csv(os.path.join(OUT_DIR, "audit", "cwe295_safe_duplicate_audit.csv"), index=False)

# ---- confirmed set ----
confirmed = candidates[candidates["disposition"] == "CONFIRMED_SAFE"].copy()
confirmed_cols = [
    "sample_id", "cwe", "label", "code", "language", "repository", "commit",
    "file_path", "source_url", "source_type", "evidence", "evidence_strength",
    "collection_date", "pair_id_if_available",
]
confirmed[confirmed_cols].to_csv(os.path.join(OUT_DIR, "collected", "cwe295_safe_confirmed.csv"), index=False)

# ---- provenance file for the confirmed set ----
provenance_cols = [
    "sample_id", "repository", "file_path", "commit", "language", "cwe",
    "label", "source_url", "source_type", "collection_method", "collection_date",
]
confirmed[provenance_cols].to_csv(os.path.join(OUT_DIR, "provenance", "cwe295_safe_provenance.csv"), index=False)

n_confirmed = len(confirmed)
n_rejected = len(candidates) - n_confirmed
print(f"Candidates: {len(candidates)} | Confirmed: {n_confirmed} | Rejected: {n_rejected}")
print(candidates["disposition"].value_counts())

# ---- verdict per the task's stop conditions ----
if n_confirmed < 50:
    verdict = "STOP_BLOCKER"
elif n_confirmed < 100:
    verdict = "PARTIALLY_READY"
elif n_confirmed < 150:
    verdict = "CWE295_SAFE_EXPANSION_SUCCESS"
else:
    verdict = "CWE295_SAFE_STRONGER_DATASET"
print("VERDICT:", verdict)

# =====================================================================
# Only build v2 if there is at least 1 confirmed row (regardless of verdict
# tier - the task says "Update the frozen dataset ONLY after all candidates
# have passed adjudication and duplicate checks", not "only if >=50" - the
# >=50/>=100/>=150 thresholds gate the REPORTED VERDICT LABEL, not whether
# confirmed real data gets recorded at all. Confirmed real data is never
# withheld from the versioned artifact just because a labeled milestone
# wasn't hit.)
# =====================================================================
if n_confirmed > 0:
    v2_new_rows = confirmed[["sample_id", "code", "cwe", "label", "language",
                              "repository", "commit", "file_path", "source_url",
                              "evidence", "evidence_strength"]].copy()
    v2_new_rows["pair_id"] = confirmed["pair_id_if_available"]

    v1 = pd.read_csv(os.path.join(ROOT, "final_dataset.csv"))
    v2 = pd.concat([v1, v2_new_rows], ignore_index=True)

    # Final safety check: zero exact-text duplicates and zero conflicting-label
    # normalized-duplicate groups in the merged v2 file.
    assert v2.duplicated(subset=["code"], keep=False).sum() == 0, "Unexpected exact duplicate in v2"
    v2["_gk"] = v2["code"].apply(normalize_code)
    conflict_check = v2.groupby("_gk")["label"].nunique()
    assert (conflict_check > 1).sum() == 0, "Unexpected label conflict in a normalized-duplicate group in v2"
    v2 = v2.drop(columns=["_gk"])

    v2.to_csv(os.path.join(ROOT, "final_dataset_v2.csv"), index=False)

    with open(os.path.join(ROOT, "final_dataset_v2.csv"), "rb") as f:
        v2_sha256 = hashlib.sha256(f.read()).hexdigest()
    with open(os.path.join(ROOT, "final_dataset.csv"), "rb") as f:
        v1_sha256 = hashlib.sha256(f.read()).hexdigest()

    manifest = {
        "filename": "final_dataset_v2.csv",
        "sha256": v2_sha256,
        "row_count": int(len(v2)),
        "previous_version": {
            "filename": "final_dataset.csv",
            "sha256": v1_sha256,
            "row_count": int(len(v1)),
            "note": "final_dataset.csv (v1) was NOT modified, overwritten, or deleted. v2 is a new, separate file.",
        },
        "change_summary": {
            "rows_added": int(n_confirmed),
            "rows_added_cwe": "CWE-295",
            "rows_added_label": "v1 (CWE-295 safe)",
            "rows_removed": 0,
            "rows_relabeled": 0,
        },
        "class_distribution_v2": {
            "s0_CWE89_vulnerable": int(((v2["cwe"] == "CWE-89") & (v2["label"] == "s0")).sum()),
            "s1_CWE89_safe": int(((v2["cwe"] == "CWE-89") & (v2["label"] == "s1")).sum()),
            "v0_CWE295_vulnerable": int(((v2["cwe"] == "CWE-295") & (v2["label"] == "v0")).sum()),
            "v1_CWE295_safe": int(((v2["cwe"] == "CWE-295") & (v2["label"] == "v1")).sum()),
        },
        "verdict": verdict,
        "frozen": True,
    }
    with open(os.path.join(ROOT, "FINAL_DATASET_V2_MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("\nfinal_dataset_v2.csv written:", manifest["class_distribution_v2"])
else:
    print("\nNo confirmed rows - final_dataset_v2.csv NOT created (nothing to add).")
