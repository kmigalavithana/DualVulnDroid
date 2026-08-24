"""
Generates the four recommended methodology figures for Chapter 3 as
simple, clean box-and-arrow diagrams using matplotlib (already a real
project dependency - see backend/requirements.txt). Purely a visual
rendering of the pipelines already described in prose in the chapter;
no new methodological content is introduced here.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from pathlib import Path

HERE = Path(__file__).parent
FONT = "DejaVu Sans"


def draw_flow(steps, out_path, title, box_width=6.6, box_height=0.62, gap=0.32, fontsize=10.5):
    n = len(steps)
    fig_height = n * (box_height + gap) + 0.6
    fig, ax = plt.subplots(figsize=(7.6, fig_height))
    ax.set_xlim(0, box_width + 1.4)
    ax.set_ylim(0, fig_height)
    ax.axis("off")

    y = fig_height - 0.5
    centers = []
    for label in steps:
        box = FancyBboxPatch(
            (0.7, y - box_height), box_width, box_height,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            linewidth=1.3, edgecolor="black", facecolor="#f2f2f2",
        )
        ax.add_patch(box)
        ax.text(
            0.7 + box_width / 2, y - box_height / 2, label,
            ha="center", va="center", fontsize=fontsize, family=FONT, wrap=True,
        )
        centers.append(y - box_height)
        y -= (box_height + gap)

    for i in range(len(centers) - 1):
        top_y = centers[i]
        bottom_y = centers[i + 1] + box_height
        arrow = FancyArrowPatch(
            (0.7 + box_width / 2, top_y), (0.7 + box_width / 2, bottom_y),
            arrowstyle="-|>", mutation_scale=14, linewidth=1.2, color="black",
        )
        ax.add_patch(arrow)

    plt.tight_layout()
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_path}")


def main():
    draw_flow(
        [
            "Raw vulnerability dataset (1,687 rows)",
            "Cleaning: normalize_code() + conflicting-label detection",
            "Exclusion of conflicting-label groups (559 rows) → clean dataset (1,128 rows)",
            "Grouped train / validation / test split (791 / 169 / 168, seed=42)",
            "Feature engineering (TF-IDF word/char + count + 23 security features)",
            "Model training (SVM, Random Forest, XGBoost — validation-based selection)",
            "Frozen test-set evaluation (each model evaluated once)",
            "Security-aware model comparison (accuracy, F1, ROC-AUC, FPR, FNR)",
            "Hybrid Decision Engine analysis (coverage vs. reliability)",
            "Robustness / threshold-sensitivity validation",
            "Production XGBoost selection and integration",
            "Backend, plugin, and Flutter application integration",
            "Final automated and real-environment validation",
        ],
        HERE / "figure_3_1_research_workflow.png",
        "Figure 3.1",
        fontsize=9.3,
    )

    draw_flow(
        [
            "Raw dataset (1,687 rows)",
            "normalize_code() applied to every row (grouping key)",
            "Exact-duplicate and near-duplicate template detection",
            "Rows whose normalized template maps to >1 label → conflicting group",
            "Conflicting groups excluded (559 rows) and stored separately",
            "Clean dataset (1,128 rows)",
            "Grouped split: every row's group stays on one side only",
            "Leakage check: zero group and zero exact-text overlap across splits",
        ],
        HERE / "figure_3_2_leakage_prevention.png",
        "Figure 3.2",
        fontsize=9.6,
    )

    draw_flow(
        [
            "Shared frozen split + shared feature/tokenizer inputs",
            "Classical ML: SVM, Random Forest, XGBoost\n(train-only hyperparameter search)",
            "Deep learning (research-only): LSTM (from-scratch),\nCodeBERT (fine-tuned, pretrained)",
            "Validation-only checkpoint / hyperparameter selection",
            "Each model evaluated on the frozen test set exactly once",
            "Identical metric protocol applied to every model\n(accuracy, macro-F1, ROC-AUC, per-CWE FNR/FPR)",
        ],
        HERE / "figure_3_3_ml_dl_methodology.png",
        "Figure 3.3",
        fontsize=9.8,
    )

    draw_flow(
        [
            "Production XGBoost prediction (class + confidence)",
            "Static / data-flow evidence\n(source→sink, concatenation, HostnameVerifier/TrustManager checks)",
            "Weighted evidence score\n(ML term + data-flow terms + static-rule corroboration)",
            "Compare evidence score to calibrated thresholds",
            "VULNERABLE  |  SUSPICIOUS_REVIEW  |  SAFE",
            "SHAP explanation (model-level) +\ndata-flow evidence (deterministic) reported separately",
        ],
        HERE / "figure_3_4_decision_methodology.png",
        "Figure 3.4",
        fontsize=9.8,
    )


if __name__ == "__main__":
    main()
