"""
PHASE RESEARCH-EVAL-4 main orchestrator: ties together
threshold_sensitivity.py, split_robustness.py, and bootstrap_analysis.py
into the final robustness classification, worst-case analysis, CWE
robustness check, hypothesis evaluation, and reproducibility record.

Run from backend/, AFTER threshold_sensitivity.py, split_robustness.py,
and bootstrap_analysis.py have all produced their artifacts:
    python -m research_eval.robustness_validation
"""

import csv
import json
import os
import platform
import sys

import numpy as np
import sklearn
import xgboost

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from research_eval.data_split import ARTIFACT_DIR as ORIGINAL_ARTIFACT_DIR
from research_eval.threshold_sensitivity import (
    main as run_threshold_sensitivity, BALANCED_VULNERABLE, BALANCED_SAFE,
    VULNERABLE_GRID, SAFE_GRID,
)
from research_eval.split_robustness import SEEDS

OUT_DIR = os.path.join(ORIGINAL_ARTIFACT_DIR, "robustness")
XGBOOST_FNR_FOR_PLOT = 0.25806451612903225  # RESEARCH-EVAL-1's frozen XGBoost test FNR, used as a reference line in split_fnr.png


def load_frozen_baselines():
    with open(os.path.join(ORIGINAL_ARTIFACT_DIR, "xgboost", "test_metrics.json")) as f:
        xgb_test = json.load(f)
    with open(os.path.join(ORIGINAL_ARTIFACT_DIR, "coverage_optimization", "test_operating_points.json")) as f:
        r3_test = json.load(f)
    return xgb_test, r3_test["test_results"]["balanced"]


def split_summary_table():
    with open(os.path.join(OUT_DIR, "all_seeds_summary.json")) as f:
        results = json.load(f)

    rows_fixed, rows_val_selected = [], []
    for r in results:
        seed = r["seed"]
        fx = r["fixed_threshold"]["test"]
        fx_cwe = r["fixed_threshold"]["test_cwe"]
        rows_fixed.append({
            "Seed": seed, "Coverage": fx["coverage"], "Recall": fx["recall"], "FNR": fx["fnr"], "FPR": fx["fpr"],
            "Deferred": fx["deferred_count"], "CWE-89 FNR": fx_cwe["sql_injection_cwe_89"].get("fnr"),
            "CWE-295 FNR": fx_cwe["certificate_validation_cwe_295"].get("fnr"),
        })
        vt = r["validation_selected_threshold_test_result"]["test"]
        vt_cwe = r["validation_selected_threshold_test_result"]["test_cwe"]
        if vt is not None:
            rows_val_selected.append({
                "Seed": seed, "Coverage": vt["coverage"], "Recall": vt["recall"], "FNR": vt["fnr"], "FPR": vt["fpr"],
                "Deferred": vt["deferred_count"], "CWE-89 FNR": vt_cwe["sql_injection_cwe_89"].get("fnr"),
                "CWE-295 FNR": vt_cwe["certificate_validation_cwe_295"].get("fnr"),
                "vulnerable_threshold": r["validation_selected_operating_point"]["vulnerable_threshold"],
                "safe_threshold": r["validation_selected_operating_point"]["safe_threshold"],
            })
        else:
            rows_val_selected.append({"Seed": seed, "Coverage": None, "Recall": None, "FNR": None, "FPR": None,
                                       "Deferred": None, "CWE-89 FNR": None, "CWE-295 FNR": None})
    return rows_fixed, rows_val_selected, results


def descriptive_stats(values):
    arr = np.array([v for v in values if v is not None], dtype=float)
    if len(arr) == 0:
        return {"n": 0}
    return {
        "n": int(len(arr)), "mean": float(arr.mean()), "median": float(np.median(arr)),
        "std": float(arr.std(ddof=1)) if len(arr) > 1 else 0.0,
        "min": float(arr.min()), "max": float(arr.max()),
    }


def worst_case_analysis(rows_fixed):
    worst_fnr = max(rows_fixed, key=lambda r: r["FNR"] if r["FNR"] is not None else -1)
    worst_fpr = max(rows_fixed, key=lambda r: r["FPR"] if r["FPR"] is not None else -1)
    lowest_coverage = min(rows_fixed, key=lambda r: r["Coverage"] if r["Coverage"] is not None else 2)
    highest_review = max(rows_fixed, key=lambda r: (1 - r["Coverage"]) if r["Coverage"] is not None else -1)
    worst_cwe89 = max(rows_fixed, key=lambda r: r["CWE-89 FNR"] if r["CWE-89 FNR"] is not None else -1)
    worst_cwe295 = max(rows_fixed, key=lambda r: r["CWE-295 FNR"] if r["CWE-295 FNR"] is not None else -1)
    return {
        "worst_fnr": {"seed": worst_fnr["Seed"], "value": worst_fnr["FNR"]},
        "worst_fpr": {"seed": worst_fpr["Seed"], "value": worst_fpr["FPR"]},
        "lowest_coverage": {"seed": lowest_coverage["Seed"], "value": lowest_coverage["Coverage"]},
        "highest_review_workload": {"seed": highest_review["Seed"], "value": 1 - highest_review["Coverage"] if highest_review["Coverage"] is not None else None},
        "worst_cwe89_fnr": {"seed": worst_cwe89["Seed"], "value": worst_cwe89["CWE-89 FNR"]},
        "worst_cwe295_fnr": {"seed": worst_cwe295["Seed"], "value": worst_cwe295["CWE-295 FNR"]},
    }


def evaluate_hypotheses(rows_fixed, xgb_test, bootstrap_metrics, sensitivity_ranges_test):
    xgboost_fnr = xgb_test["false_negative_rate"]

    h1_comparisons = [(r["Seed"], r["FNR"], r["FNR"] < xgboost_fnr if r["FNR"] is not None else None) for r in rows_fixed]
    n_better = sum(1 for _, _, better in h1_comparisons if better)
    n_total = sum(1 for _, _, better in h1_comparisons if better is not None)
    if n_better == n_total:
        h1_verdict = "SUPPORTED"
    elif n_better == 0:
        h1_verdict = "NOT SUPPORTED"
    else:
        h1_verdict = "INCONCLUSIVE"
    h1 = {"hypothesis": "H1: Balanced remains better than raw XGBoost FNR across alternative splits.",
          "evidence": h1_comparisons, "verdict": h1_verdict,
          "explanation": f"Balanced FNR was lower than XGBoost's own frozen test FNR ({xgboost_fnr:.4f}) on {n_better}/{n_total} alternative splits (fixed-threshold view)."}

    fnr_sens = sensitivity_ranges_test["fnr_sensitivity"]
    cov_sens = sensitivity_ranges_test["coverage_sensitivity"]
    bootstrap_fnr = bootstrap_metrics["overall"]["fnr"]
    interval_width = (bootstrap_fnr["95%_bootstrap_percentile_interval"][1] - bootstrap_fnr["95%_bootstrap_percentile_interval"][0]) if "95%_bootstrap_percentile_interval" in bootstrap_fnr else None
    h2_verdict = "INCONCLUSIVE"
    if fnr_sens < 0.05 and cov_sens < 0.15:
        h2_verdict = "SUPPORTED"
    elif fnr_sens > 0.15 or cov_sens > 0.30:
        h2_verdict = "NOT SUPPORTED"
    h2 = {"hypothesis": "H2: Balanced trade-off is stable under small threshold perturbations.",
          "evidence": {"fnr_sensitivity_test": fnr_sens, "coverage_sensitivity_test": cov_sens, "bootstrap_fnr_interval_width": interval_width},
          "verdict": h2_verdict,
          "explanation": f"Test-set FNR sensitivity across the +-0.2 perturbation grid is {fnr_sens:.4f} "
                          f"(coverage sensitivity {cov_sens:.4f}) - {'small enough' if h2_verdict=='SUPPORTED' else 'not small' if h2_verdict=='NOT SUPPORTED' else 'ambiguous'} "
                          f"relative to the point estimates being defended."}

    cwe89_fnrs = [r["CWE-89 FNR"] for r in rows_fixed if r["CWE-89 FNR"] is not None]
    cwe295_fnrs = [r["CWE-295 FNR"] for r in rows_fixed if r["CWE-295 FNR"] is not None]
    persists = all(c295 > c89 for c89, c295 in zip(cwe89_fnrs, cwe295_fnrs)) if cwe89_fnrs and cwe295_fnrs else None
    h3_verdict = "INCONCLUSIVE" if persists is None else ("SUPPORTED" if persists else "NOT SUPPORTED")
    h3 = {"hypothesis": "H3: CWE-89/CWE-295 asymmetry persists across alternative splits.",
          "evidence": {"cwe89_fnrs_by_seed": cwe89_fnrs, "cwe295_fnrs_by_seed": cwe295_fnrs}, "verdict": h3_verdict,
          "explanation": f"CWE-295 FNR exceeded CWE-89 FNR on {sum(1 for a,b in zip(cwe89_fnrs,cwe295_fnrs) if b>a)}/{len(cwe89_fnrs)} alternative splits."}

    h4_verdict = "INCONCLUSIVE"
    if h1_verdict == "SUPPORTED" and h2_verdict == "SUPPORTED":
        h4_verdict = "SUPPORTED"
    elif h1_verdict == "NOT SUPPORTED" or h2_verdict == "NOT SUPPORTED":
        h4_verdict = "NOT SUPPORTED"
    h4 = {"hypothesis": "H4: Enough robustness evidence exists to justify production integration.",
          "verdict": h4_verdict,
          "explanation": f"Derived from H1={h1_verdict} and H2={h2_verdict} - production integration requires BOTH "
                          f"cross-split generalization and threshold stability; a single INCONCLUSIVE/NOT SUPPORTED "
                          f"component is enough to withhold H4 support."}

    return {"H1": h1, "H2": h2, "H3": h3, "H4": h4}


def classify_robustness(hypotheses, sensitivity_ranges_test, bootstrap_metrics, xgb_test_fnr):
    fnr_sens = sensitivity_ranges_test["fnr_sensitivity"]
    bootstrap_fnr = bootstrap_metrics["overall"]["fnr"]
    interval_upper = bootstrap_fnr.get("95%_bootstrap_percentile_interval", [None, None])[1]
    interval_below_xgboost = interval_upper is not None and interval_upper < xgb_test_fnr

    h1_ok = hypotheses["H1"]["verdict"] == "SUPPORTED"
    h2_ok = hypotheses["H2"]["verdict"] == "SUPPORTED"
    h3_persists = hypotheses["H3"]["verdict"] == "SUPPORTED"

    if h1_ok and h2_ok and interval_below_xgboost and not h3_persists:
        classification = "ROBUST"
    elif not h1_ok or fnr_sens > 0.15 or h3_persists:
        classification = "SENSITIVE" if (h1_ok or h2_ok) else "INCONCLUSIVE"
    else:
        classification = "INCONCLUSIVE"

    return {
        "classification": classification,
        "reasoning": {
            "H1_cross_split_fnr_advantage": hypotheses["H1"]["verdict"],
            "H2_threshold_stability": hypotheses["H2"]["verdict"],
            "H3_cwe_asymmetry_persists": hypotheses["H3"]["verdict"],
            "bootstrap_95pct_upper_bound_below_xgboost_fnr": interval_below_xgboost,
            "bootstrap_fnr_interval": bootstrap_fnr.get("95%_bootstrap_percentile_interval"),
            "xgboost_frozen_test_fnr": xgb_test_fnr,
        },
    }


def production_candidate_decision(classification, hypotheses):
    c = classification["classification"]
    if c == "ROBUST":
        decision = "A. ROBUST ENOUGH FOR NEXT PHASE"
    elif c == "SENSITIVE":
        decision = "B. PROMISING BUT MORE DATA REQUIRED"
    else:
        decision = "B. PROMISING BUT MORE DATA REQUIRED" if hypotheses["H1"]["verdict"] != "NOT SUPPORTED" else "C. NOT ROBUST ENOUGH"
    return decision


def write_csv(rows, path):
    if not rows:
        with open(path, "w") as f:
            f.write("")
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    xgb_test, r3_balanced_test = load_frozen_baselines()

    with open(os.path.join(OUT_DIR, "threshold_sensitivity_test.csv")) as f:
        test_grid_rows = list(csv.DictReader(f))
    for r in test_grid_rows:
        for k in r:
            if k not in ("vulnerable_threshold", "safe_threshold"):
                try:
                    r[k] = float(r[k]) if r[k] not in ("", None) else None
                except ValueError:
                    pass
    from research_eval.threshold_sensitivity import sensitivity_ranges
    test_ranges = sensitivity_ranges([{k: (float(v) if v not in ("", None) else None) for k, v in r.items() if k not in ("vulnerable_threshold", "safe_threshold")} for r in test_grid_rows])

    rows_fixed, rows_val_selected, split_results = split_summary_table()
    write_csv(rows_fixed, os.path.join(OUT_DIR, "split_robustness_fixed_threshold.csv"))
    write_csv(rows_val_selected, os.path.join(OUT_DIR, "split_robustness_validation_selected.csv"))

    summary_table = [{"Seed": r["Seed"], "Coverage": r["Coverage"], "Recall": r["Recall"], "FNR": r["FNR"],
                       "FPR": r["FPR"], "Deferred": r["Deferred"], "CWE-89 FNR": r["CWE-89 FNR"], "CWE-295 FNR": r["CWE-295 FNR"]}
                      for r in rows_fixed]
    write_csv(summary_table, os.path.join(OUT_DIR, "split_summary.csv"))

    split_stats = {
        "coverage": descriptive_stats([r["Coverage"] for r in rows_fixed]),
        "recall": descriptive_stats([r["Recall"] for r in rows_fixed]),
        "fnr": descriptive_stats([r["FNR"] for r in rows_fixed]),
        "fpr": descriptive_stats([r["FPR"] for r in rows_fixed]),
        "review_workload": descriptive_stats([1 - r["Coverage"] if r["Coverage"] is not None else None for r in rows_fixed]),
        "note": "Split-to-split variability statistics (mean/median/std/min/max across the 5 alternative-split fixed-threshold results) - NOT confidence intervals.",
    }
    with open(os.path.join(OUT_DIR, "split_statistics.json"), "w") as f:
        json.dump(split_stats, f, indent=2)

    cwe_robustness_rows = []
    for r in rows_fixed:
        cwe_robustness_rows.append({"Seed": r["Seed"], "CWE": "CWE-89", "FNR": r["CWE-89 FNR"]})
        cwe_robustness_rows.append({"Seed": r["Seed"], "CWE": "CWE-295", "FNR": r["CWE-295 FNR"]})
    write_csv(cwe_robustness_rows, os.path.join(OUT_DIR, "cwe_robustness.csv"))
    cwe_stats = {
        "cwe_89_fnr": descriptive_stats([r["CWE-89 FNR"] for r in rows_fixed]),
        "cwe_295_fnr": descriptive_stats([r["CWE-295 FNR"] for r in rows_fixed]),
        "original_finding_cwe89_fnr": 0.08, "original_finding_cwe295_fnr": 0.2542372881355932,
    }

    worst_case = worst_case_analysis(rows_fixed)
    with open(os.path.join(OUT_DIR, "worst_case_analysis.json"), "w") as f:
        json.dump(worst_case, f, indent=2)

    with open(os.path.join(OUT_DIR, "bootstrap_metrics.json")) as f:
        bootstrap_metrics = json.load(f)

    hypotheses = evaluate_hypotheses(rows_fixed, xgb_test, bootstrap_metrics, test_ranges)
    classification = classify_robustness(hypotheses, test_ranges, bootstrap_metrics, xgb_test["false_negative_rate"])
    decision = production_candidate_decision(classification, hypotheses)

    balanced_vs_xgboost = {
        "xgboost_fnr": xgb_test["false_negative_rate"], "balanced_fnr": r3_balanced_test["fnr"],
        "absolute_fnr_improvement": xgb_test["false_negative_rate"] - r3_balanced_test["fnr"],
        "relative_fnr_reduction": (xgb_test["false_negative_rate"] - r3_balanced_test["fnr"]) / xgb_test["false_negative_rate"],
        "xgboost_coverage": 1.0, "balanced_coverage": r3_balanced_test["coverage"],
        "xgboost_fpr": xgb_test["false_positive_rate"], "balanced_fpr": r3_balanced_test["fpr"],
        "balanced_review_workload": r3_balanced_test["deferred_count"] / r3_balanced_test["total_cases"],
        "note": "No statistical significance claimed - single frozen 168-row test set comparison.",
    }

    reproducibility = {
        "python_version": sys.version, "platform": platform.platform(),
        "scikit_learn_version": sklearn.__version__, "xgboost_version": xgboost.__version__,
        "original_split_seed": 42, "alternative_split_seeds": SEEDS,
        "bootstrap_seed": 42, "bootstrap_n_resamples": 10000,
        "frozen_model_artifact_path": "research_eval_artifacts/xgboost/model.json",
        "balanced_candidate_thresholds": {"vulnerable_threshold": BALANCED_VULNERABLE, "safe_threshold": BALANCED_SAFE},
        "perturbation_grid": {"vulnerable": VULNERABLE_GRID, "safe": SAFE_GRID},
    }
    with open(os.path.join(OUT_DIR, "reproducibility.json"), "w") as f:
        json.dump(reproducibility, f, indent=2)

    final_summary = {
        "balanced_vs_xgboost": balanced_vs_xgboost,
        "threshold_sensitivity_ranges_validation": None,  # filled by threshold_sensitivity.py's own run
        "threshold_sensitivity_ranges_test": test_ranges,
        "split_statistics": split_stats,
        "cwe_robustness_statistics": cwe_stats,
        "worst_case_analysis": worst_case,
        "bootstrap_summary": {k: v for k, v in bootstrap_metrics["overall"].items()},
        "hypotheses": hypotheses,
        "robustness_classification": classification,
        "production_candidate_decision": decision,
    }
    with open(os.path.join(OUT_DIR, "robustness_summary.json"), "w") as f:
        json.dump(final_summary, f, indent=2)

    make_plots(test_grid_rows, rows_fixed, cwe_robustness_rows, bootstrap_metrics)

    print(json.dumps({"classification": classification, "decision": decision, "hypotheses": {k: v["verdict"] for k, v in hypotheses.items()}}, indent=2))
    return final_summary


def make_plots(test_grid_rows, rows_fixed, cwe_robustness_rows, bootstrap_metrics):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    plots_dir = os.path.join(OUT_DIR, "plots")
    os.makedirs(plots_dir, exist_ok=True)

    def f(r, k):
        v = r.get(k)
        return float(v) if v not in (None, "") else None

    cov = [f(r, "coverage") for r in test_grid_rows]
    fnr = [f(r, "fnr") for r in test_grid_rows]
    fpr = [f(r, "fpr") for r in test_grid_rows]
    vthr = [f(r, "vulnerable_threshold") for r in test_grid_rows]
    sthr = [f(r, "safe_threshold") for r in test_grid_rows]

    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.scatter(cov, fnr, s=14, color="crimson")
    ax.set_xlabel("Coverage"); ax.set_ylabel("FNR"); ax.set_title("Threshold sensitivity: Coverage vs FNR (test)")
    fig.tight_layout(); fig.savefig(os.path.join(plots_dir, "threshold_coverage_fnr.png"), dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.scatter(cov, fpr, s=14, color="darkorange")
    ax.set_xlabel("Coverage"); ax.set_ylabel("FPR"); ax.set_title("Threshold sensitivity: Coverage vs FPR (test)")
    fig.tight_layout(); fig.savefig(os.path.join(plots_dir, "threshold_coverage_fpr.png"), dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.scatter(vthr, fnr, s=14, color="steelblue")
    ax.axvline(BALANCED_VULNERABLE, color="gray", linestyle="--", label="Balanced")
    ax.set_xlabel("vulnerable_threshold"); ax.set_ylabel("FNR"); ax.set_title("FNR vs vulnerable_threshold (test)")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(plots_dir, "threshold_fnr_vulnerable_threshold.png"), dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.scatter(sthr, fnr, s=14, color="seagreen")
    ax.axvline(BALANCED_SAFE, color="gray", linestyle="--", label="Balanced")
    ax.set_xlabel("safe_threshold"); ax.set_ylabel("FNR"); ax.set_title("FNR vs safe_threshold (test)")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(plots_dir, "threshold_fnr_safe_threshold.png"), dpi=150); plt.close(fig)

    seeds = [r["Seed"] for r in rows_fixed]
    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.bar([str(s) for s in seeds], [r["FNR"] for r in rows_fixed], color="crimson")
    ax.axhline(XGBOOST_FNR_FOR_PLOT, color="black", linestyle="--", label="XGBoost baseline FNR")
    ax.set_xlabel("Split seed"); ax.set_ylabel("FNR (fixed-threshold)"); ax.set_title("FNR by split/seed")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(plots_dir, "split_fnr.png"), dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.bar([str(s) for s in seeds], [r["Coverage"] for r in rows_fixed], color="steelblue")
    ax.set_xlabel("Split seed"); ax.set_ylabel("Coverage (fixed-threshold)"); ax.set_title("Coverage by split/seed")
    fig.tight_layout(); fig.savefig(os.path.join(plots_dir, "split_coverage.png"), dpi=150); plt.close(fig)

    cwe89 = [r["FNR"] for r in cwe_robustness_rows if r["CWE"] == "CWE-89"]
    cwe295 = [r["FNR"] for r in cwe_robustness_rows if r["CWE"] == "CWE-295"]
    fig, ax = plt.subplots(figsize=(6.5, 5))
    x = np.arange(len(seeds))
    width = 0.35
    ax.bar(x - width / 2, cwe89, width, label="CWE-89", color="teal")
    ax.bar(x + width / 2, cwe295, width, label="CWE-295", color="indianred")
    ax.set_xticks(x); ax.set_xticklabels([str(s) for s in seeds])
    ax.set_xlabel("Split seed"); ax.set_ylabel("FNR"); ax.set_title("CWE-89 vs CWE-295 FNR by split")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(plots_dir, "cwe_fnr_comparison.png"), dpi=150); plt.close(fig)

    with open(os.path.join(OUT_DIR, "bootstrap_samples.csv")) as bf:
        bootstrap_rows = list(csv.DictReader(bf))
    fnr_samples = [float(r["fnr"]) for r in bootstrap_rows if r.get("fnr") not in (None, "")]
    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.hist(fnr_samples, bins=40, color="mediumpurple", edgecolor="white")
    point = bootstrap_metrics["overall"]["fnr"]["point_estimate"]
    ax.axvline(point, color="black", linestyle="-", label=f"point estimate ({point:.3f})")
    lo, hi = bootstrap_metrics["overall"]["fnr"]["95%_bootstrap_percentile_interval"]
    ax.axvline(lo, color="gray", linestyle="--", label="95% bootstrap interval")
    ax.axvline(hi, color="gray", linestyle="--")
    ax.set_xlabel("Bootstrap FNR"); ax.set_ylabel("Count"); ax.set_title("Bootstrap distribution: Balanced FNR (test)")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(plots_dir, "bootstrap_fnr.png"), dpi=150); plt.close(fig)


if __name__ == "__main__":
    main()
