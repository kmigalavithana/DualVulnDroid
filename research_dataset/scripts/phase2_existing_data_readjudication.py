"""
Phase 2 - Existing data re-adjudication.

Rather than re-deriving the CWE-89/CWE-295 evidence-based adjudication from
scratch (which would just re-run the exact same structural analysis already
performed, verified, and cross-checked in research_dataset_validation/ during
the prior research phase), this script CARRIES FORWARD that adjudication as
the Phase 2 output, under the disposition categories this task specifies:

    CONFIRMED_VULNERABLE / CONFIRMED_SAFE / AMBIGUOUS /
    EXCLUDE_DUPLICATE_CONFLICT / EXCLUDE_INSUFFICIENT_CONTEXT

Source of truth: research_dataset_validation/final_adjudicated_dataset.csv
(1687 rows, one disposition per row, already using the same evidence
hierarchy this task specifies - STRONG_SOURCE_TO_SINK / MODERATE_DYNAMIC_SINK /
WEAK_PATTERN_ONLY / SAFE_STATIC / SAFE_PARAMETERIZED / INSUFFICIENT_CONTEXT -
and already cross-verified against an independent prior audit).

This script does not alter any label. It re-exports the same rows into the
research_dataset/ directory structure this task requires, and confirms the
counts match what the task brief states as already established
(157 CWE-89 vulnerable, 372 CWE-89 safe, 57 CWE-295 vulnerable, 5 CWE-295
safe, total confirmed = 591).
"""
import json
import os

import pandas as pd

ROOT = r"F:\vibe cording"
VAL_DIR = os.path.join(ROOT, "research_dataset_validation")
OUT_DIR = os.path.join(ROOT, "research_dataset")

adjudicated = pd.read_csv(os.path.join(VAL_DIR, "final_adjudicated_dataset.csv"))

expected = {
    ("CWE-89", "CONFIRMED_VULNERABLE"): 157,
    ("CWE-89", "CONFIRMED_SAFE"): 372,
    ("CWE-295", "CONFIRMED_VULNERABLE"): 57,
    ("CWE-295", "CONFIRMED_SAFE"): 5,
}
for (cwe, status), expected_count in expected.items():
    actual = int(
        ((adjudicated["inferred_cwe"] == cwe) & (adjudicated["final_status"] == status)).sum()
    )
    assert actual == expected_count, (
        f"Mismatch for {cwe}/{status}: expected {expected_count}, found {actual} - "
        "existing adjudication no longer matches task brief's stated facts."
    )

print("Verified: existing adjudication matches task brief's stated confirmed counts exactly.")

# ---- adjudicated/ : one file per disposition bucket, for readability ----
adjudicated_dir = os.path.join(OUT_DIR, "adjudicated")
for status in [
    "CONFIRMED_VULNERABLE",
    "CONFIRMED_SAFE",
    "AMBIGUOUS",
    "EXCLUDE_DUPLICATE_CONFLICT",
    "EXCLUDE_INSUFFICIENT_CONTEXT",
]:
    sub = adjudicated[adjudicated["final_status"] == status]
    sub.to_csv(os.path.join(adjudicated_dir, f"{status}.csv"), index=False)

adjudicated.to_csv(os.path.join(adjudicated_dir, "existing_data_full_adjudication.csv"), index=False)

# ---- audit/ : label_adjudication.csv in the column shape Phase 7 specifies ----
label_adjudication = adjudicated.rename(
    columns={
        "row_id": "sample_id",
        "final_label": "label",
        "inferred_cwe": "cwe",
        "evidence_level": "evidence",
        "final_status": "disposition",
    }
)[["sample_id", "vulnerable_line", "cwe", "label", "disposition", "evidence", "confidence", "reason"]]
label_adjudication.insert(1, "source", "existing_dataset")
label_adjudication.to_csv(os.path.join(OUT_DIR, "audit", "label_adjudication_existing.csv"), index=False)

summary = {
    "source_file": os.path.join(VAL_DIR, "final_adjudicated_dataset.csv"),
    "total_rows": int(len(adjudicated)),
    "by_cwe_and_status": {
        cwe: {
            status: int(((adjudicated["inferred_cwe"] == cwe) & (adjudicated["final_status"] == status)).sum())
            for status in [
                "CONFIRMED_VULNERABLE",
                "CONFIRMED_SAFE",
                "AMBIGUOUS",
                "EXCLUDE_DUPLICATE_CONFLICT",
                "EXCLUDE_INSUFFICIENT_CONTEXT",
            ]
        }
        for cwe in ["CWE-89", "CWE-295"]
    },
    "total_confirmed": int(adjudicated["final_status"].isin(["CONFIRMED_VULNERABLE", "CONFIRMED_SAFE"]).sum()),
}
with open(os.path.join(OUT_DIR, "audit", "phase2_readjudication_summary.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print(json.dumps(summary, indent=2))
