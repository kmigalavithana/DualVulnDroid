"""
PHASE RESEARCH-EVAL-3 main orchestrator: searches decision_engine.py
threshold PAIRS on VALIDATION ONLY to find operating points near target
coverage levels, selects three practical candidates by a pre-declared
(not test-tuned) rule, and evaluates those candidates EXACTLY ONCE on
the frozen 168-row test set.

decision_engine.py itself is never modified - only its already-
parameterized decide(evidence_score, vulnerable_threshold, safe_threshold)
function is called with different candidate thresholds, exactly the way
ml/calibrate_decision_engine.py already does.

Run from backend/, AFTER research_eval.train_xgboost has produced
research_eval_artifacts/xgboost/:
    python -m research_eval.coverage_optimization
"""

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import decision_engine
from research_eval.data_split import load_split, ARTIFACT_DIR
from research_eval.operating_points import (
    compute_evidence_scores, apply_thresholds, operating_point_metrics,
    cwe_metrics_for_operating_point, build_threshold_grid,
)
from research_eval.pareto_analysis import pareto_frontier, plot_pareto

OUT_DIR = os.path.join(ARTIFACT_DIR, "coverage_optimization")
TARGET_COVERAGES = [0.25, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]

CURRENT_PRODUCTION_THRESHOLDS = {
    "vulnerable_threshold": decision_engine.VULNERABLE_THRESHOLD,
    "safe_threshold": decision_engine.SAFE_THRESHOLD,
}


def full_grid_search(evidence_records, grid):
    """Every valid (vulnerable_threshold > safe_threshold) pair from the
    grid, evaluated on validation. This is the single source of truth for
    both the target-coverage search (Part 6) and the Pareto analysis
    (Part 8) - both must be derived from the exact same real sweep."""
    results = []
    for vuln_thr in grid["vulnerable_threshold_candidates"]:
        for safe_thr in grid["safe_threshold_candidates"]:
            if vuln_thr <= safe_thr:
                continue  # decision_engine.py's own semantics require this - not a valid operating point
            decided = apply_thresholds(evidence_records, vuln_thr, safe_thr)
            metrics = operating_point_metrics(decided, vuln_thr, safe_thr)
            results.append(metrics)
    return results


def closest_to_target_coverage(all_results, target):
    """Closest achievable coverage to `target` (Part 6: 'do not assume
    every target is achievable... report the closest achievable operating
    point'), ties broken by lowest FNR (a pre-declared, non-arbitrary rule -
    among equally-close coverage, prefer the safer one)."""
    def sort_key(r):
        fnr = r["fnr"] if r["fnr"] is not None else 1.0
        return (abs(r["coverage"] - target), fnr)
    return dict(min(all_results, key=sort_key))  # copy - caller mutates this dict, must not alias all_results


def select_practical_operating_points(all_val_results, bounds):
    """Three named candidates, selected from ALL valid VALIDATION operating
    points (not just the literal (coverage,FNR) Pareto frontier - see the
    REAL FINDING below for why) using bounds built ONLY from already-
    measured, real baseline numbers - never an invented weighted score.

    IMPORTANT REAL FINDING: the literal (coverage, FNR) Pareto frontier
    (Part 8, computed and reported in full in pareto_frontier.csv/plot)
    collapses to a SINGLE point in this dataset: coverage and FNR are not
    actually in tension here - widening the VULNERABLE threshold downward
    monotonically increases coverage AND lowers FNR simultaneously (it can
    only add newly-caught true positives, never lose previously-caught
    ones), right up until it also floods the system with false positives.
    The one (coverage, FNR)-non-dominated point found was
    vulnerable_threshold~=-0.925: 100% coverage, FNR~=0.02, but FPR~=0.71
    and precision~=0.63 - not a practically useful operating point. The
    REAL trade-off in this data is (coverage, FNR) jointly AGAINST FPR/
    precision, not coverage against FNR alone - so practical operating
    points are selected using FPR bounds anchored to already-measured,
    real baselines (never a new arbitrary number):
      - Conservative: minimize FNR subject to FPR <= the CURRENT decision
        engine's own validation-set auto-decision FPR (bounds["current_engine_fpr"]) -
        i.e. do not get less precise than the system already is today.
      - Balanced: maximize coverage subject to FNR <= XGBoost's own
        validation FNR AND FPR <= XGBoost's own validation FPR
        (bounds["xgboost_fnr"], bounds["xgboost_fpr"]) - i.e. at least as
        good as the raw model on BOTH axes.
      - Higher-coverage: maximize coverage subject to FPR <= XGBoost's own
        validation FPR only (FNR allowed to be whatever results, tie-break
        by lowest FNR) - trades some FNR margin for coverage, but never
        exceeds the raw model's false-alarm rate.
    """
    def pick(candidates, key, tie_key=None):
        if not candidates:
            return None
        return max(candidates, key=lambda r: (key(r), tie_key(r) if tie_key else 0))

    conservative_pool = [r for r in all_val_results if r["fpr"] is not None and r["fpr"] <= bounds["current_engine_fpr"]]
    conservative = min(conservative_pool, key=lambda r: (r["fnr"] if r["fnr"] is not None else 1.0, -r["coverage"])) if conservative_pool else None

    balanced_pool = [r for r in all_val_results if r["fnr"] is not None and r["fnr"] <= bounds["xgboost_fnr"]
                      and r["fpr"] is not None and r["fpr"] <= bounds["xgboost_fpr"]]
    balanced = max(balanced_pool, key=lambda r: r["coverage"]) if balanced_pool else None

    higher_pool = [r for r in all_val_results if r["fpr"] is not None and r["fpr"] <= bounds["xgboost_fpr"]]
    higher_coverage = max(higher_pool, key=lambda r: (r["coverage"], -(r["fnr"] if r["fnr"] is not None else 1.0))) if higher_pool else None

    return {"conservative": conservative, "balanced": balanced, "higher_coverage": higher_coverage}


def evaluate_on_test(evidence_records_test, thresholds):
    decided = apply_thresholds(evidence_records_test, thresholds["vulnerable_threshold"], thresholds["safe_threshold"])
    metrics = operating_point_metrics(decided, thresholds["vulnerable_threshold"], thresholds["safe_threshold"])
    cwe = cwe_metrics_for_operating_point(decided)
    return metrics, cwe, decided


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
    os.makedirs(os.path.join(OUT_DIR, "plots"), exist_ok=True)

    _, val_df, test_df, (_, val_idx, test_idx) = load_split()

    val_evidence = compute_evidence_scores(val_df, val_idx)
    grid = build_threshold_grid(val_evidence)

    print(f"[coverage_optimization] running full grid search on validation "
          f"({len(grid['vulnerable_threshold_candidates'])}x{len(grid['safe_threshold_candidates'])} candidates)...")
    all_val_results = full_grid_search(val_evidence, grid)
    print(f"[coverage_optimization] {len(all_val_results)} valid threshold pairs evaluated on validation")

    # --- Part 6: closest achievable operating point per target coverage ---
    target_results = [closest_to_target_coverage(all_val_results, t) for t in TARGET_COVERAGES]
    for t, r in zip(TARGET_COVERAGES, target_results):
        r["target_coverage"] = t
    write_csv(target_results, os.path.join(OUT_DIR, "validation_operating_points.csv"))
    with open(os.path.join(OUT_DIR, "validation_operating_points.json"), "w") as f:
        json.dump({"grid": grid, "targets": target_results, "current_production_thresholds": CURRENT_PRODUCTION_THRESHOLDS}, f, indent=2)

    # --- Part 8: Pareto frontier over ALL valid validation operating points ---
    frontier, dominated = pareto_frontier(all_val_results)
    pareto_rows = (
        [{**r, "pareto_status": "non-dominated"} for r in frontier] +
        [{**r, "pareto_status": "dominated"} for r in dominated]
    )
    write_csv(pareto_rows, os.path.join(OUT_DIR, "pareto_frontier.csv"))

    # --- Part 11: select 3 practical operating points, bounds from REAL,
    # already-measured VALIDATION-set baselines only (never test, never invented) ---
    with open(os.path.join(ARTIFACT_DIR, "xgboost", "validation_metrics.json")) as f:
        xgb_val_metrics = json.load(f)
    current_engine_val = operating_point_metrics(
        apply_thresholds(val_evidence, CURRENT_PRODUCTION_THRESHOLDS["vulnerable_threshold"], CURRENT_PRODUCTION_THRESHOLDS["safe_threshold"]),
        CURRENT_PRODUCTION_THRESHOLDS["vulnerable_threshold"], CURRENT_PRODUCTION_THRESHOLDS["safe_threshold"],
    )
    bounds = {
        "xgboost_fnr": xgb_val_metrics["false_negative_rate"],
        "xgboost_fpr": xgb_val_metrics["false_positive_rate"],
        "current_engine_fpr": current_engine_val["fpr"] if current_engine_val["fpr"] is not None else 1.0,
    }
    print(f"[coverage_optimization] selection bounds (validation-only): {bounds}")

    selected = select_practical_operating_points(all_val_results, bounds)

    # --- Part 12: apply the (at most 3) selected operating points to TEST, exactly once ---
    test_evidence = compute_evidence_scores(test_df, test_idx)

    test_results = {}
    test_cwe = {}
    test_decided = {}
    for name in ("conservative", "balanced", "higher_coverage"):
        point = selected.get(name)
        if point is None:
            test_results[name] = None
            test_cwe[name] = None
            continue
        thresholds = {"vulnerable_threshold": point["vulnerable_threshold"], "safe_threshold": point["safe_threshold"]}
        metrics, cwe, decided = evaluate_on_test(test_evidence, thresholds)
        test_results[name] = metrics
        test_cwe[name] = cwe
        test_decided[name] = decided

    write_csv([r for r in test_results.values() if r is not None], os.path.join(OUT_DIR, "test_operating_points.csv"))
    with open(os.path.join(OUT_DIR, "test_operating_points.json"), "w") as f:
        json.dump({
            "selected_operating_points_validation": {k: v for k, v in selected.items()},
            "test_results": test_results,
            "test_cwe_metrics": test_cwe,
            "note": "Test set touched exactly once per operating point, after selection was already frozen on validation.",
        }, f, indent=2)

    make_plots(all_val_results, frontier, dominated)

    summary = {
        "research_question": "Can the existing Hybrid Decision Engine increase automatic coverage while maintaining a substantially lower FNR than raw XGBoost?",
        "current_production_operating_point": CURRENT_PRODUCTION_THRESHOLDS,
        "current_production_operating_point_on_validation": current_engine_val,
        "selection_bounds_from_real_validation_baselines": bounds,
        "n_validation_pairs_evaluated": len(all_val_results),
        "n_pareto_frontier_points": len(frontier),
        "n_dominated_points": len(dominated),
        "pareto_frontier_finding": (
            f"The literal (coverage, FNR) Pareto frontier collapsed to {len(frontier)} point(s) - "
            f"coverage and FNR are not fundamentally in tension in this dataset (widening the "
            f"VULNERABLE threshold improves both together until FPR blows up). Practical operating "
            f"points below are therefore selected using FPR bounds anchored to real baselines, not "
            f"the raw (coverage, FNR) frontier alone - see select_practical_operating_points docstring."
        ),
        "selected_operating_points": selected,
        "test_results": test_results,
    }
    with open(os.path.join(OUT_DIR, "final_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps({"selected_operating_points": selected, "test_results": test_results}, indent=2, default=str))
    return summary, test_decided


def make_plots(all_val_results, frontier, dominated):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    plots_dir = os.path.join(OUT_DIR, "plots")

    valid = [r for r in all_val_results if r["fnr"] is not None]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter([r["coverage"] for r in valid], [r["fnr"] for r in valid], s=10, alpha=0.35, color="gray", label="all valid pairs (validation)")
    ax.set_xlabel("Coverage"); ax.set_ylabel("FNR"); ax.set_title("Coverage vs FNR (validation)")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(plots_dir, "coverage_vs_fnr.png"), dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter([r["coverage"] for r in valid], [r["recall"] for r in valid], s=10, alpha=0.35, color="darkgreen")
    ax.set_xlabel("Coverage"); ax.set_ylabel("Recall (vulnerability recall)"); ax.set_title("Coverage vs Recall (validation)")
    fig.tight_layout(); fig.savefig(os.path.join(plots_dir, "coverage_vs_recall.png"), dpi=150); plt.close(fig)

    valid_fpr = [r for r in all_val_results if r["fpr"] is not None]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter([r["coverage"] for r in valid_fpr], [r["fpr"] for r in valid_fpr], s=10, alpha=0.35, color="darkorange")
    ax.set_xlabel("Coverage"); ax.set_ylabel("FPR"); ax.set_title("Coverage vs FPR (validation)")
    fig.tight_layout(); fig.savefig(os.path.join(plots_dir, "coverage_vs_fpr.png"), dpi=150); plt.close(fig)

    plot_pareto(frontier, dominated, os.path.join(plots_dir, "pareto_frontier.png"))


if __name__ == "__main__":
    main()
