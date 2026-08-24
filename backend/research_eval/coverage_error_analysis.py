"""
PHASE RESEARCH-EVAL-3, Parts 14/15/16: for each selected operating point
(Conservative/Balanced/Higher-coverage), produce the CWE-specific metrics
table, the false-negative table, and the review-workload table required
by the spec - all read from the artifacts coverage_optimization.py
already wrote (no re-running of XGBoost/dataflow, no new test-set touch).

Run from backend/, AFTER coverage_optimization.py:
    python -m research_eval.coverage_error_analysis
"""

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from research_eval.data_split import load_split, ARTIFACT_DIR
from research_eval.operating_points import compute_evidence_scores, apply_thresholds, cwe_metrics_for_operating_point

OUT_DIR = os.path.join(ARTIFACT_DIR, "coverage_optimization")
CWE_BY_LABEL_PREFIX = {"s": "CWE-89", "v": "CWE-295"}


def _cwe(label):
    return CWE_BY_LABEL_PREFIX[label[0]]


def _miss_reason(record):
    if record["deferred"]:
        return (f"Evidence score {record['evidence_score']:.3f} fell inside the SUSPICIOUS_REVIEW band "
                f"(between this operating point's safe/vulnerable thresholds) - deferred, not flagged.")
    # Not deferred but still missed (final_vulnerable_flag=False while true_is_vulnerable=True) is
    # impossible under this engine's decide() logic for a non-deferred case UNLESS decision=="SAFE" -
    # report that fact plainly; do not guess further.
    return f"Decision engine committed to SAFE (evidence_score={record['evidence_score']:.3f}, below safe_threshold)."


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    _, val_df, test_df, (_, val_idx, test_idx) = load_split()

    with open(os.path.join(OUT_DIR, "test_operating_points.json")) as f:
        test_data = json.load(f)
    selected = test_data["selected_operating_points_validation"]

    test_evidence = compute_evidence_scores(test_df, test_idx)

    cwe_rows = []
    fn_rows = []
    workload_rows = []

    for name in ("conservative", "balanced", "higher_coverage"):
        point = selected.get(name)
        if point is None:
            continue
        decided = apply_thresholds(test_evidence, point["vulnerable_threshold"], point["safe_threshold"])
        cwe = cwe_metrics_for_operating_point(decided)

        for cwe_key, cwe_label in [("sql_injection_cwe_89", "CWE-89"), ("certificate_validation_cwe_295", "CWE-295")]:
            m = cwe[cwe_key]
            cwe_rows.append({
                "Operating Point": name, "CWE": cwe_label,
                "Recall": m.get("recall"), "FNR": m.get("fnr"),
                "Precision": m.get("precision"), "F1": m.get("f1"),
                "Support": m.get("support"), "Auto-decided support": m.get("auto_decided_support"),
            })

        for r in decided:
            if r["true_is_vulnerable"] and not r["final_vulnerable_flag"]:
                fn_rows.append({
                    "operating_point": name,
                    "test_identifier": r["row_identifier"],
                    "true_label": r["true_label"],
                    "cwe": _cwe(r["true_label"]),
                    "xgb_prediction": r["xgb_prediction"],
                    "xgb_confidence_pct": round(r["xgb_confidence_pct"], 3),
                    "evidence_score": round(r["evidence_score"], 3),
                    "decision": r["decision"],
                    "deferred": r["deferred"],
                    "reason_for_miss": _miss_reason(r),
                })

        total = len(decided)
        auto = sum(1 for r in decided if not r["deferred"])
        deferred = total - auto
        workload_rows.append({
            "operating_point": name,
            "vulnerable_threshold": point["vulnerable_threshold"], "safe_threshold": point["safe_threshold"],
            "total_cases": total, "automatic_decisions": auto, "deferred_cases": deferred,
            "coverage": auto / total if total else 0.0,
            "review_workload_pct": deferred / total if total else 0.0,
        })

    with open(os.path.join(OUT_DIR, "cwe_metrics.csv"), "w", newline="") as f:
        if cwe_rows:
            writer = csv.DictWriter(f, fieldnames=list(cwe_rows[0].keys()))
            writer.writeheader()
            writer.writerows(cwe_rows)

    with open(os.path.join(OUT_DIR, "false_negatives_by_operating_point.csv"), "w", newline="") as f:
        if fn_rows:
            writer = csv.DictWriter(f, fieldnames=list(fn_rows[0].keys()))
            writer.writeheader()
            writer.writerows(fn_rows)
        else:
            f.write("")

    with open(os.path.join(OUT_DIR, "review_workload.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(workload_rows[0].keys()))
        writer.writeheader()
        writer.writerows(workload_rows)

    fn_counts = {}
    for name in ("conservative", "balanced", "higher_coverage"):
        fn_counts[name] = sum(1 for r in fn_rows if r["operating_point"] == name)

    result = {
        "cwe_metrics": cwe_rows,
        "review_workload": workload_rows,
        "fn_counts_by_operating_point": fn_counts,
        "small_sample_caveat": (
            "Test set is only 168 rows; CWE-specific auto-decided support at some operating "
            "points is well under 30 - per-operating-point CWE FNR differences of one or two "
            "cases should be read as potentially unstable, not a robust trend."
        ),
    }
    print(json.dumps(result, indent=2, default=str))
    return result


if __name__ == "__main__":
    main()
