"""
Research Phase Step 10.5 (continued) - QC and duplicate control ONLY.

This round found 10 new candidates, below the task's stop-condition-B
threshold of 20. Per the task's explicit instruction ("STOP when ... B)
fewer than 20 additional defensible samples can be found without lowering
the evidence standard"), no final_dataset_v3.csv is created. This script
still runs the full duplicate-control pipeline the task requires, so the
STOP decision is demonstrably backed by real QC work, not merely asserted.
"""
import os
import sys

import pandas as pd

ROOT = r"F:\vibe cording"
OUT_DIR = os.path.join(ROOT, "research_dataset")

sys.path.insert(0, os.path.join(ROOT, "backend"))
from ml.feature_pipeline import normalize_code  # noqa: E402

candidates = pd.read_csv(os.path.join(OUT_DIR, "collected", "cwe295_safe_candidates_10_5.csv"))
candidates["group_key"] = candidates["code"].apply(normalize_code)

v2 = pd.read_csv(os.path.join(ROOT, "final_dataset_v2.csv"))
v2["group_key"] = v2["code"].apply(normalize_code)

frozen_exact_texts = set(v2["code"])
frozen_norm = set(v2["group_key"])

candidates["exact_dup_vs_v2"] = candidates["code"].isin(frozen_exact_texts)
candidates["normalized_dup_vs_v2"] = candidates["group_key"].isin(frozen_norm)
candidates["exact_dup_internal"] = candidates.duplicated(subset=["code"], keep=False)
candidates["normalized_dup_internal"] = candidates["group_key"].duplicated(keep=False)


def adjudicate(row):
    if row["exact_dup_vs_v2"]:
        return "REJECTED_EXACT_DUPLICATE_OF_V2"
    if row["exact_dup_internal"]:
        return "REJECTED_EXACT_DUPLICATE_INTERNAL"
    if row["normalized_dup_vs_v2"]:
        return "REJECTED_NORMALIZED_DUPLICATE_OF_V2"
    if row["normalized_dup_internal"]:
        return "REJECTED_NORMALIZED_DUPLICATE_INTERNAL"
    if row["evidence_strength"] not in ("STRONG", "MODERATE"):
        return "REJECTED_WEAK_EVIDENCE"
    return "CONFIRMED_SAFE"


candidates["disposition"] = candidates.apply(adjudicate, axis=1)

adjudication_cols = [
    "sample_id", "cwe", "label", "code", "repository", "evidence_strength", "disposition",
    "exact_dup_vs_v2", "normalized_dup_vs_v2", "exact_dup_internal", "normalized_dup_internal",
]
candidates[adjudication_cols].to_csv(
    os.path.join(OUT_DIR, "audit", "cwe295_safe_adjudication_10_5.csv"), index=False
)

dup_mask = (
    candidates["exact_dup_vs_v2"] | candidates["normalized_dup_vs_v2"]
    | candidates["exact_dup_internal"] | candidates["normalized_dup_internal"]
)
candidates[dup_mask][
    ["sample_id", "code", "group_key", "exact_dup_vs_v2", "normalized_dup_vs_v2",
     "exact_dup_internal", "normalized_dup_internal"]
].to_csv(os.path.join(OUT_DIR, "audit", "cwe295_safe_duplicate_audit_10_5.csv"), index=False)

confirmed = candidates[candidates["disposition"] == "CONFIRMED_SAFE"]
print(f"Candidates: {len(candidates)} | Confirmed: {len(confirmed)} | Rejected: {len(candidates) - len(confirmed)}")
print(candidates["disposition"].value_counts())
print("\nRepository diversity (this round):")
print(candidates["repository"].value_counts())

# ---- Repository diversity analysis across the WHOLE CWE-295 safe collection to date ----
step10_confirmed = pd.read_csv(os.path.join(OUT_DIR, "collected", "cwe295_safe_confirmed.csv"))
combined_repos = pd.concat([
    step10_confirmed[["repository"]],
    confirmed[["repository"]] if len(confirmed) else pd.DataFrame(columns=["repository"]),
])
print("\nCombined repository distribution (Step 10 + Step 10.5 new CWE-295 safe collection):")
print(combined_repos["repository"].value_counts())
print("Total distinct repositories across both rounds:", combined_repos["repository"].nunique())

n_confirmed = len(confirmed)
if n_confirmed >= 100:
    verdict = "A_CWE295_SAFE_GE_100"
elif n_confirmed < 20:
    verdict = "B_STOP_FEWER_THAN_20"
else:
    verdict = "CONTINUE_ELIGIBLE"
print("\nVERDICT:", verdict)
