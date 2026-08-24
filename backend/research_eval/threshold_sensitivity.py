"""
PHASE RESEARCH-EVAL-4, Parts 5-7: local threshold-sensitivity analysis
around the RESEARCH-EVAL-3 "Balanced" candidate (vulnerable_threshold=
0.753, safe_threshold=-0.376).

Pre-declared perturbation grid (spec's own literal example values, +-0.05
step out to +-0.2): every combination is valid here since
min(vulnerable_candidates)=0.553 > max(safe_candidates)=-0.176, so no
pair needs to be excluded by decision_engine.py's vulnerable>safe
requirement - still checked explicitly (build_grid_pairs), not assumed.

The SAME 81-pair grid is evaluated on VALIDATION first, then applied
UNCHANGED to the frozen TEST SET (Part 7: 'test set is for confirmation
only... do NOT select the best test-set point') - no selection logic
touches the test-set results here at all, they are simply computed and
reported alongside validation.

Run from backend/:  python -m research_eval.threshold_sensitivity
"""

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from research_eval.data_split import load_split, ARTIFACT_DIR as ORIGINAL_ARTIFACT_DIR
from research_eval.operating_points import compute_evidence_scores, apply_thresholds, operating_point_metrics, cwe_metrics_for_operating_point

OUT_DIR = os.path.join(ORIGINAL_ARTIFACT_DIR, "robustness")

BALANCED_VULNERABLE = 0.753
BALANCED_SAFE = -0.376

VULNERABLE_GRID = [0.553, 0.603, 0.653, 0.703, 0.753, 0.803, 0.853, 0.903, 0.953]
SAFE_GRID = [-0.576, -0.526, -0.476, -0.426, -0.376, -0.326, -0.276, -0.226, -0.176]


def build_grid_pairs():
    """Every (vulnerable, safe) combination from the pre-declared grid
    that is a technically valid decision boundary (vulnerable > safe) -
    decision_engine.py's own semantics, not re-implemented, just checked."""
    pairs = []
    rejected = []
    for v in VULNERABLE_GRID:
        for s in SAFE_GRID:
            if v > s:
                pairs.append((v, s))
            else:
                rejected.append((v, s))
    return pairs, rejected


def evaluate_grid(evidence_records, pairs, n_total):
    rows = []
    for v, s in pairs:
        decided = apply_thresholds(evidence_records, v, s)
        m = operating_point_metrics(decided, v, s)
        cwe = cwe_metrics_for_operating_point(decided)
        rows.append({
            "vulnerable_threshold": v, "safe_threshold": s,
            "delta_vulnerable": round(v - BALANCED_VULNERABLE, 3),
            "delta_safe": round(s - BALANCED_SAFE, 3),
            "coverage": m["coverage"], "automatic_decisions": m["automatic_decisions"], "deferred_cases": m["deferred_count"],
            "precision": m["precision"], "recall": m["recall"], "f1": m["f1"],
            "fpr": m["fpr"], "fnr": m["fnr"],
            "tp": m["tp"], "tn": m["tn"], "fp": m["fp"], "fn": m["fn"],
            "review_workload": m["deferred_count"] / n_total if n_total else None,
            "cwe89_recall": cwe["sql_injection_cwe_89"].get("recall"),
            "cwe89_fnr": cwe["sql_injection_cwe_89"].get("fnr"),
            "cwe295_recall": cwe["certificate_validation_cwe_295"].get("recall"),
            "cwe295_fnr": cwe["certificate_validation_cwe_295"].get("fnr"),
        })
    return rows


def local_sensitivity(grid_rows):
    """1D slices holding one threshold fixed at the Balanced value while
    varying the other - the exact +-0.05/0.10/0.20 offsets requested in
    Part 6, extracted from the same grid (no separate evaluation needed:
    0.753+-{0.05,0.10,0.20} and -0.376+-{0.05,0.10,0.20} are all already
    points in the pre-declared 9-value grids)."""
    balanced_row = next(r for r in grid_rows if r["vulnerable_threshold"] == BALANCED_VULNERABLE and r["safe_threshold"] == BALANCED_SAFE)

    vary_vulnerable = [r for r in grid_rows if r["safe_threshold"] == BALANCED_SAFE]
    vary_safe = [r for r in grid_rows if r["vulnerable_threshold"] == BALANCED_VULNERABLE]

    def deltas(rows, key_field):
        out = []
        for r in sorted(rows, key=lambda x: x[key_field]):
            out.append({
                key_field: r[key_field],
                "delta_from_balanced": round(r[key_field] - (BALANCED_VULNERABLE if key_field == "vulnerable_threshold" else BALANCED_SAFE), 3),
                "coverage": r["coverage"], "delta_coverage": round(r["coverage"] - balanced_row["coverage"], 4),
                "fnr": r["fnr"], "delta_fnr": round((r["fnr"] - balanced_row["fnr"]), 4) if r["fnr"] is not None and balanced_row["fnr"] is not None else None,
                "fpr": r["fpr"], "delta_fpr": round((r["fpr"] - balanced_row["fpr"]), 4) if r["fpr"] is not None and balanced_row["fpr"] is not None else None,
                "recall": r["recall"], "delta_recall": round((r["recall"] - balanced_row["recall"]), 4) if r["recall"] is not None and balanced_row["recall"] is not None else None,
            })
        return out

    return {
        "balanced_point": balanced_row,
        "vary_vulnerable_threshold_fixed_safe": deltas(vary_vulnerable, "vulnerable_threshold"),
        "vary_safe_threshold_fixed_vulnerable": deltas(vary_safe, "safe_threshold"),
    }


def sensitivity_ranges(grid_rows):
    """Part 17: descriptive ranges within the local perturbation grid -
    NOT a weighted score, just max-min of each metric across the 81 pairs."""
    coverages = [r["coverage"] for r in grid_rows if r["coverage"] is not None]
    fnrs = [r["fnr"] for r in grid_rows if r["fnr"] is not None]
    fprs = [r["fpr"] for r in grid_rows if r["fpr"] is not None]
    return {
        "coverage_sensitivity": max(coverages) - min(coverages),
        "fnr_sensitivity": max(fnrs) - min(fnrs),
        "fpr_sensitivity": max(fprs) - min(fprs),
        "coverage_range": [min(coverages), max(coverages)],
        "fnr_range": [min(fnrs), max(fnrs)],
        "fpr_range": [min(fprs), max(fprs)],
    }


def write_csv(rows, path):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    _, val_df, test_df, (_, val_idx, test_idx) = load_split()

    pairs, rejected = build_grid_pairs()
    print(f"[threshold_sensitivity] {len(pairs)} valid pairs, {len(rejected)} rejected (vulnerable<=safe)")

    val_evidence = compute_evidence_scores(val_df, val_idx)
    val_rows = evaluate_grid(val_evidence, pairs, len(val_df))
    write_csv(val_rows, os.path.join(OUT_DIR, "threshold_sensitivity_validation.csv"))

    # Part 7: apply the SAME pre-declared grid to test, unchanged - confirmation only.
    test_evidence = compute_evidence_scores(test_df, test_idx)
    test_rows = evaluate_grid(test_evidence, pairs, len(test_df))
    write_csv(test_rows, os.path.join(OUT_DIR, "threshold_sensitivity_test.csv"))

    val_local = local_sensitivity(val_rows)
    test_local = local_sensitivity(test_rows)
    val_ranges = sensitivity_ranges(val_rows)
    test_ranges = sensitivity_ranges(test_rows)

    print(f"[threshold_sensitivity] validation sensitivity ranges: {val_ranges}")
    print(f"[threshold_sensitivity] test sensitivity ranges: {test_ranges}")

    return {
        "n_valid_pairs": len(pairs), "n_rejected_pairs": len(rejected),
        "validation_grid": val_rows, "test_grid": test_rows,
        "validation_local_sensitivity": val_local, "test_local_sensitivity": test_local,
        "validation_sensitivity_ranges": val_ranges, "test_sensitivity_ranges": test_ranges,
    }


if __name__ == "__main__":
    main()
