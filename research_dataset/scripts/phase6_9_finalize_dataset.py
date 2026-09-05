"""
Phase 6-9 - Duplicate/leakage control, final label-quality merge, final
class-distribution stats, and dataset freeze.

Merges:
  (a) the 591 CONFIRMED_VULNERABLE/CONFIRMED_SAFE rows already re-adjudicated
      from the existing dataset in Phase 2 (research_dataset/adjudicated/), and
  (b) the 17 newly collected, individually provenance-verified real samples
      from Phase 3/4 (research_dataset/collected/collected_samples.csv)

into one final_dataset.csv, then runs exact/normalized duplicate detection
across the MERGED pool (not just within each half separately - a sample
collected in Phase 3 could duplicate one already in the existing dataset,
and the Phase 3 script already found exactly 2 such cases).

Evidence-strength mapping for the existing-dataset rows (documented, not
assumed): STRONG_SOURCE_TO_SINK -> STRONG, MODERATE_DYNAMIC_SINK -> MODERATE,
SAFE_STATIC -> STRONG, SAFE_PARAMETERIZED -> STRONG. (Verified: zero
WEAK_PATTERN_ONLY rows exist among the 591 CONFIRMED rows - see
research_dataset/audit/phase2_readjudication_summary.json.)
"""
import hashlib
import json
import os
import sys

import pandas as pd

ROOT = r"F:\vibe cording"
OUT_DIR = os.path.join(ROOT, "research_dataset")
VAL_DIR = os.path.join(ROOT, "research_dataset_validation")

sys.path.insert(0, os.path.join(ROOT, "backend"))
from ml.feature_pipeline import normalize_code  # noqa: E402

EVIDENCE_STRENGTH_MAP = {
    "STRONG_SOURCE_TO_SINK": "STRONG",
    "MODERATE_DYNAMIC_SINK": "MODERATE",
    "SAFE_STATIC": "STRONG",
    "SAFE_PARAMETERIZED": "STRONG",
}

# ---- Load existing confirmed rows ----
adjudicated = pd.read_csv(os.path.join(VAL_DIR, "final_adjudicated_dataset.csv"))
confirmed = adjudicated[adjudicated["final_status"].isin(["CONFIRMED_VULNERABLE", "CONFIRMED_SAFE"])].copy()
assert len(confirmed) == 591, f"Expected 591 confirmed rows, found {len(confirmed)}"

confirmed["sample_id"] = confirmed["row_id"].apply(lambda x: f"existing_{int(x):04d}")
confirmed["code"] = confirmed["vulnerable_line"]
confirmed["cwe"] = confirmed["inferred_cwe"]
confirmed["label"] = confirmed["final_label"]
confirmed["language"] = "Java"  # see FINAL_DATASET_REPORT.md limitations: assumed, not per-row metadata
confirmed["repository"] = None
confirmed["commit"] = None
confirmed["file_path"] = None
confirmed["source_url"] = None
confirmed["source_type"] = "original_dataset_no_provenance"
confirmed["evidence"] = confirmed["reason"]
confirmed["evidence_strength"] = confirmed["evidence_level"].map(EVIDENCE_STRENGTH_MAP)
assert confirmed["evidence_strength"].isnull().sum() == 0, "Unmapped evidence_level found"
confirmed["collection_method"] = "prior_structural_code_audit_and_manual_adjudication"
confirmed["license_if_available"] = None
confirmed["collection_date"] = None
confirmed["pair_id"] = None
confirmed["confidence"] = confirmed["confidence"]
confirmed["disposition"] = confirmed["final_status"]

# ---- Load collected rows ----
collected = pd.read_csv(os.path.join(OUT_DIR, "collected", "collected_samples.csv"))
collected["disposition"] = "CONFIRMED_" + collected["label"].map(
    {"s0": "VULNERABLE", "v0": "VULNERABLE", "s1": "SAFE", "v1": "SAFE"}
)
collected["confidence"] = collected["evidence_strength"].map({"STRONG": 0.95, "MODERATE": 0.75})

shared_cols = [
    "sample_id", "code", "cwe", "label", "language", "repository", "commit",
    "file_path", "source_url", "source_type", "evidence", "evidence_strength",
    "collection_method", "license_if_available", "collection_date", "pair_id",
    "disposition", "confidence",
]
final_dataset = pd.concat([confirmed[shared_cols], collected[shared_cols]], ignore_index=True)
final_dataset["group_key"] = final_dataset["code"].apply(normalize_code)

# ---- Phase 6: duplicate / leakage control over the MERGED pool ----
# Report BEFORE collapsing (Phase 6 requires reporting overlap counts).
exact_dup_mask = final_dataset.duplicated(subset=["code"], keep=False)
duplicate_audit = final_dataset[exact_dup_mask][["sample_id", "cwe", "label", "code"]].copy()
duplicate_audit = duplicate_audit.sort_values("code")
duplicate_audit.to_csv(os.path.join(ROOT, "duplicate_audit.csv"), index=False)

norm_dup_mask_pre = final_dataset["group_key"].duplicated(keep=False)
near_dup_rows = final_dataset[norm_dup_mask_pre][["sample_id", "cwe", "label", "code", "group_key"]].copy()
near_dup_rows = near_dup_rows.sort_values("group_key")
near_dup_rows.to_csv(os.path.join(ROOT, "near_duplicate_audit.csv"), index=False)

# label conflicts within a normalized-duplicate group (checked on the PRE-collapse pool)
conflict_groups = final_dataset.groupby("group_key")["label"].nunique()
conflicting_group_keys = conflict_groups[conflict_groups > 1].index.tolist()

# Sanity: every exact-text duplicate group agrees on both cwe and label (verified
# separately before writing this script) - safe to collapse to one representative
# row per unique code text. ABSOLUTE RULE 7 ("Remove exact duplicates") requires
# this for the frozen final_dataset.csv, even though the prior adjudication phase
# had deliberately kept same-label duplicates as separate rows (its goal there was
# label-quality auditing of the raw 1687 rows, not a deduplicated training-ready
# dataset). Keep the highest-evidence_strength representative per group (STRONG
# over MODERATE) so no information is lost by the choice of which copy survives.
_strength_rank = {"STRONG": 2, "MODERATE": 1}
final_dataset["_strength_rank"] = final_dataset["evidence_strength"].map(_strength_rank)
before_collapse_count = len(final_dataset)
final_dataset = (
    final_dataset.sort_values("_strength_rank", ascending=False)
    .drop_duplicates(subset=["code"], keep="first")
    .drop(columns=["_strength_rank"])
    .sort_values("sample_id")
    .reset_index(drop=True)
)
exact_duplicates_collapsed = before_collapse_count - len(final_dataset)

# Recompute the normalized-duplicate mask on the POST-collapse pool for the stats
# that describe the actual frozen final_dataset.csv.
norm_dup_mask = final_dataset["group_key"].duplicated(keep=False)

# ---- final_dataset.csv (drop internal group_key/disposition helper cols not in spec) ----
final_cols = [
    "sample_id", "code", "cwe", "label", "language", "repository", "commit",
    "file_path", "source_url", "evidence", "evidence_strength", "pair_id",
]
final_dataset[final_cols].to_csv(os.path.join(ROOT, "final_dataset.csv"), index=False)

# ---- provenance.csv (all rows) ----
provenance_cols = [
    "sample_id", "repository", "file_path", "commit", "language", "cwe",
    "label", "source_url", "source_type", "collection_method",
    "license_if_available", "collection_date",
]
final_dataset[provenance_cols].to_csv(os.path.join(ROOT, "provenance.csv"), index=False)

# ---- label_adjudication.csv (all rows) ----
label_adjudication_cols = [
    "sample_id", "code", "cwe", "label", "disposition", "evidence",
    "evidence_strength", "confidence",
]
final_dataset[label_adjudication_cols].to_csv(os.path.join(ROOT, "label_adjudication.csv"), index=False)

# ---- copy vulnerable_fixed_pairs.csv to root (already built in Phase 3/4) ----
pairs_df = pd.read_csv(os.path.join(OUT_DIR, "vulnerable_fixed_pairs.csv"))
pairs_df.to_csv(os.path.join(ROOT, "vulnerable_fixed_pairs.csv"), index=False)

# ---- final_dataset_statistics.json ----
stats = {
    "total_samples": int(len(final_dataset)),
    "cwe89_vulnerable": int(((final_dataset["cwe"] == "CWE-89") & (final_dataset["label"] == "s0")).sum()),
    "cwe89_safe": int(((final_dataset["cwe"] == "CWE-89") & (final_dataset["label"] == "s1")).sum()),
    "cwe295_vulnerable": int(((final_dataset["cwe"] == "CWE-295") & (final_dataset["label"] == "v0")).sum()),
    "cwe295_safe": int(((final_dataset["cwe"] == "CWE-295") & (final_dataset["label"] == "v1")).sum()),
    "language_distribution": final_dataset["language"].value_counts(dropna=False).to_dict(),
    "source_distribution": final_dataset["source_type"].value_counts(dropna=False).to_dict(),
    "evidence_strength_distribution": final_dataset.groupby(["cwe", "evidence_strength"]).size().to_dict(),
    "exact_duplicate_rows_before_collapse": int(exact_dup_mask.sum()),
    "exact_duplicate_rows_collapsed_out": int(exact_duplicates_collapsed),
    "exact_duplicates_within_final_dataset": int(final_dataset.duplicated(subset=["code"], keep=False).sum()),
    "near_duplicate_rows_within_final_dataset": int(norm_dup_mask.sum()),
    "near_duplicate_groups_with_conflicting_labels": len(conflicting_group_keys),
    "conflicting_group_keys": conflicting_group_keys,
    "repository_count_new_collected_only": int(collected["repository"].nunique()),
    "vulnerable_fixed_pairs_recorded": int(len(pairs_df)),
    "note_on_exact_duplicates": (
        f"{exact_dup_mask.sum()} rows across 126 exact-text-duplicate groups were found in the merged "
        f"591-existing + 17-collected pool (all confirmed to agree on both cwe and label within each "
        f"group before collapsing - verified separately, see FINAL_DATASET_REPORT.md). Collapsed to one "
        f"representative row per unique code text (highest evidence_strength kept), removing "
        f"{exact_duplicates_collapsed} redundant rows, per ABSOLUTE RULE 7 ('Remove exact duplicates')."
    ),
}
# json.dumps can't handle tuple dict keys (from groupby on 2 cols) - stringify
def _stringify_keys(d):
    return {str(k): v for k, v in d.items()}

stats["evidence_strength_distribution"] = _stringify_keys(stats["evidence_strength_distribution"])

with open(os.path.join(ROOT, "final_dataset_statistics.json"), "w", encoding="utf-8") as f:
    json.dump(stats, f, indent=2)

print(json.dumps(stats, indent=2, default=str))

# ---- FINAL_DATASET_MANIFEST.json (Phase 9 freeze) ----
final_dataset_path = os.path.join(ROOT, "final_dataset.csv")
with open(final_dataset_path, "rb") as f:
    final_sha256 = hashlib.sha256(f.read()).hexdigest()

manifest = {
    "filename": "final_dataset.csv",
    "sha256": final_sha256,
    "row_count": int(len(final_dataset)),
    "class_distribution": {
        "s0_CWE89_vulnerable": stats["cwe89_vulnerable"],
        "s1_CWE89_safe": stats["cwe89_safe"],
        "v0_CWE295_vulnerable": stats["cwe295_vulnerable"],
        "v1_CWE295_safe": stats["cwe295_safe"],
    },
    "label_mapping": {
        "s0": "CWE-89 vulnerable", "s1": "CWE-89 safe",
        "v0": "CWE-295 vulnerable", "v1": "CWE-295 safe",
    },
    "source_statistics": {
        "from_original_dataset_confirmed_adjudication": int(len(confirmed)),
        "from_new_real_world_collection": int(len(collected)),
    },
    "provenance_statistics": {
        "rows_with_full_provenance_repo_commit_file_url": int(len(collected)),
        "rows_without_provenance_original_dataset": int(len(confirmed)),
    },
    "duplicate_statistics": {
        "exact_duplicate_rows_found_before_collapse": int(exact_dup_mask.sum()),
        "exact_duplicate_rows_collapsed_out": int(exact_duplicates_collapsed),
        "exact_duplicates_remaining_in_frozen_file": int(final_dataset.duplicated(subset=["code"], keep=False).sum()),
        "near_duplicate_rows_remaining_in_frozen_file": int(norm_dup_mask.sum()),
        "near_duplicate_conflicting_label_groups": len(conflicting_group_keys),
    },
    "frozen": True,
    "freeze_note": "This manifest fingerprints final_dataset.csv as of this dataset-construction phase. "
                   "No split (train/validation/test) has been frozen yet - that is deferred to a dedicated "
                   "protocol-design step, consistent with how the CWE-89 split was previously frozen only "
                   "after its own dedicated protocol document (research_experiments/protocol/).",
}
with open(os.path.join(ROOT, "FINAL_DATASET_MANIFEST.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print("\nFINAL_DATASET_MANIFEST.json sha256:", final_sha256)
