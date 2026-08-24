"""
PHASE RESEARCH-EVAL-4, Parts 13/14: non-parametric bootstrap uncertainty
for the Balanced candidate (vulnerable_threshold=0.753, safe_threshold=
-0.376) on the ORIGINAL frozen 168-row test set.

Resamples ROWS (with replacement) from the already-computed, already-
frozen per-row decision-engine outcomes - it does not re-run XGBoost or
the dataflow analyzers per resample (that would be needlessly expensive
and add no information: each row's evidence_score/decision is fixed
once computed), and it never touches thresholds - purely descriptive
resampling of a fixed set of outcomes.

Run from backend/:  python -m research_eval.bootstrap_analysis
"""

import csv
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from research_eval.data_split import load_split, ARTIFACT_DIR as ORIGINAL_ARTIFACT_DIR
from research_eval.operating_points import compute_evidence_scores, apply_thresholds

OUT_DIR = os.path.join(ORIGINAL_ARTIFACT_DIR, "robustness")
BALANCED_VULNERABLE = 0.753
BALANCED_SAFE = -0.376
N_RESAMPLES = 10000
BOOTSTRAP_SEED = 42
MIN_SUPPORT_FOR_BOOTSTRAP = 15  # below this, resampling is reported as unreliable rather than fabricated


def _metrics_from_decided(decided):
    auto = [r for r in decided if not r["deferred"]]
    total = len(decided)
    tp = sum(1 for r in auto if r["true_is_vulnerable"] and r["final_vulnerable_flag"])
    tn = sum(1 for r in auto if not r["true_is_vulnerable"] and not r["final_vulnerable_flag"])
    fp = sum(1 for r in auto if not r["true_is_vulnerable"] and r["final_vulnerable_flag"])
    fn = sum(1 for r in auto if r["true_is_vulnerable"] and not r["final_vulnerable_flag"])
    coverage = len(auto) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None
    fpr = fp / (fp + tn) if (fp + tn) > 0 else None
    fnr = fn / (fn + tp) if (fn + tp) > 0 else None
    return {"coverage": coverage, "precision": precision, "recall": recall, "fpr": fpr, "fnr": fnr,
            "tp": tp, "tn": tn, "fp": fp, "fn": fn}


def bootstrap(decided, n_resamples=N_RESAMPLES, seed=BOOTSTRAP_SEED):
    rng = np.random.default_rng(seed)
    n = len(decided)
    decided_arr = np.array(decided, dtype=object)

    samples = {"coverage": [], "precision": [], "recall": [], "fpr": [], "fnr": []}
    for _ in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        resample = list(decided_arr[idx])
        m = _metrics_from_decided(resample)
        for key in samples:
            if m[key] is not None:
                samples[key].append(m[key])

    point_estimate = _metrics_from_decided(decided)

    result = {}
    for key in samples:
        arr = np.array(samples[key])
        if len(arr) < n_resamples * 0.5:  # most resamples had this metric undefined (e.g. zero vulnerable in resample)
            result[key] = {
                "point_estimate": point_estimate[key],
                "note": "Not sufficiently supported for reliable bootstrap estimation.",
            }
            continue
        result[key] = {
            "point_estimate": point_estimate[key],
            "bootstrap_mean": float(arr.mean()),
            "95%_bootstrap_percentile_interval": [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))],
            "n_valid_resamples": int(len(arr)),
        }
    return result, samples


def class_specific_bootstrap(decided, task_labels, n_resamples=N_RESAMPLES, seed=BOOTSTRAP_SEED):
    task_rows = [r for r in decided if r["true_label"] in task_labels]
    support = sum(1 for r in task_rows if not r["deferred"])
    if support < MIN_SUPPORT_FOR_BOOTSTRAP:
        return {"support": support, "note": "Not sufficiently supported for reliable bootstrap estimation."}

    rng = np.random.default_rng(seed)
    n = len(task_rows)
    arr = np.array(task_rows, dtype=object)
    fnrs = []
    for _ in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        resample = list(arr[idx])
        auto = [r for r in resample if not r["deferred"]]
        tp = sum(1 for r in auto if r["true_is_vulnerable"] and r["final_vulnerable_flag"])
        fn = sum(1 for r in auto if r["true_is_vulnerable"] and not r["final_vulnerable_flag"])
        if (fn + tp) > 0:
            fnrs.append(fn / (fn + tp))

    point_rows = [r for r in task_rows if not r["deferred"]]
    tp0 = sum(1 for r in point_rows if r["true_is_vulnerable"] and r["final_vulnerable_flag"])
    fn0 = sum(1 for r in point_rows if r["true_is_vulnerable"] and not r["final_vulnerable_flag"])
    point_fnr = fn0 / (fn0 + tp0) if (fn0 + tp0) > 0 else None

    if len(fnrs) < n_resamples * 0.5:
        return {"support": support, "point_estimate_fnr": point_fnr,
                "note": "Not sufficiently supported for reliable bootstrap estimation."}

    arr_fnr = np.array(fnrs)
    return {
        "support": support,
        "point_estimate_fnr": point_fnr,
        "bootstrap_mean_fnr": float(arr_fnr.mean()),
        "95%_bootstrap_percentile_interval_fnr": [float(np.percentile(arr_fnr, 2.5)), float(np.percentile(arr_fnr, 97.5))],
        "n_valid_resamples": int(len(arr_fnr)),
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    _, _, test_df, (_, _, test_idx) = load_split()

    test_evidence = compute_evidence_scores(test_df, test_idx)
    decided = apply_thresholds(test_evidence, BALANCED_VULNERABLE, BALANCED_SAFE)

    metrics, samples = bootstrap(decided)

    with open(os.path.join(OUT_DIR, "bootstrap_samples.csv"), "w", newline="") as f:
        writer = csv.writer(f)
        keys = list(samples.keys())
        writer.writerow(keys)
        max_len = max(len(v) for v in samples.values())
        for i in range(max_len):
            writer.writerow([samples[k][i] if i < len(samples[k]) else "" for k in keys])

    cwe89 = class_specific_bootstrap(decided, {"s0", "s1"})
    cwe295 = class_specific_bootstrap(decided, {"v0", "v1"})

    output = {
        "method": (
            f"Non-parametric row-level bootstrap, {N_RESAMPLES} resamples with replacement, "
            f"fixed seed={BOOTSTRAP_SEED}, over the ALREADY-FROZEN 168-row test set's Balanced-"
            f"threshold decision outcomes. Never used to tune thresholds or choose an operating point."
        ),
        "n_resamples": N_RESAMPLES, "bootstrap_seed": BOOTSTRAP_SEED,
        "thresholds_evaluated": {"vulnerable_threshold": BALANCED_VULNERABLE, "safe_threshold": BALANCED_SAFE},
        "overall": metrics,
        "cwe_89_fnr": cwe89,
        "cwe_295_fnr": cwe295,
    }
    with open(os.path.join(OUT_DIR, "bootstrap_metrics.json"), "w") as f:
        json.dump(output, f, indent=2)

    print(json.dumps(output, indent=2))
    return output


if __name__ == "__main__":
    main()
