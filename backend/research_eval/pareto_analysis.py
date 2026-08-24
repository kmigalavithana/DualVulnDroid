"""
PHASE RESEARCH-EVAL-3, Part 7/8: Pareto dominance over (coverage, FNR)
operating points. A dominates B iff A has coverage >= B.coverage AND
A.fnr <= B.fnr, with at least one strict inequality - exactly the rule
given in the spec, implemented literally (no weighting, no invented
score).
"""


def dominates(a, b):
    if a["fnr"] is None or b["fnr"] is None:
        return False
    coverage_ge = a["coverage"] >= b["coverage"]
    fnr_le = a["fnr"] <= b["fnr"]
    strictly_better = a["coverage"] > b["coverage"] or a["fnr"] < b["fnr"]
    return coverage_ge and fnr_le and strictly_better


def pareto_frontier(operating_points):
    """Returns (frontier, dominated) - frontier = points not dominated by
    any other point in the set; dominated = everything else. Points with
    fnr=None (e.g. zero automatic decisions) are excluded from both, since
    FNR is undefined for them - they cannot meaningfully be compared."""
    candidates = [p for p in operating_points if p["fnr"] is not None]

    frontier, dominated = [], []
    for p in candidates:
        is_dominated = any(dominates(q, p) for q in candidates if q is not p)
        (dominated if is_dominated else frontier).append(p)

    frontier.sort(key=lambda r: r["coverage"])
    return frontier, dominated


def plot_pareto(frontier, dominated, out_path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    if dominated:
        ax.scatter([p["coverage"] for p in dominated], [p["fnr"] for p in dominated],
                   s=14, color="lightgray", label=f"dominated (n={len(dominated)})")
    if frontier:
        ax.scatter([p["coverage"] for p in frontier], [p["fnr"] for p in frontier],
                   s=28, color="crimson", label=f"Pareto frontier (n={len(frontier)})")
        ordered = sorted(frontier, key=lambda r: r["coverage"])
        ax.plot([p["coverage"] for p in ordered], [p["fnr"] for p in ordered], color="crimson", linewidth=1, alpha=0.6)
    ax.set_xlabel("Coverage")
    ax.set_ylabel("FNR")
    ax.set_title("Pareto frontier: coverage vs FNR (validation)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
