"""
Generates figure_ch6_5model_comparison.png for the new Chapter 6 from
verified data in backend/research_eval_artifacts/final_documentation/
model_comparison_table.csv. Does not modify any existing evaluation
artefact; writes only the new chart file into the thesis directory.
"""
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
CSV_PATH = HERE.parent / "model_comparison_table.csv"
OUT_PATH = HERE / "figure_ch6_5model_comparison.png"

rows = []
with open(CSV_PATH, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

models = [r["Model"] for r in rows]
macro_f1 = [float(r["Macro F1"]) for r in rows]
fnr = [float(r["FNR"]) for r in rows]

fig, ax = plt.subplots(figsize=(8, 5))
x = range(len(models))
width = 0.35
b1 = ax.bar([i - width / 2 for i in x], macro_f1, width, label="Macro F1", color="#3b6fa0")
b2 = ax.bar([i + width / 2 for i in x], fnr, width, label="FNR", color="#c0392b")
ax.set_xticks(list(x))
ax.set_xticklabels(models)
ax.set_ylim(0, 1.0)
ax.set_ylabel("Value")
ax.set_title("Five-model comparison: Macro F1 vs FNR (frozen 168-row test set)")
ax.legend()
for bars in (b1, b2):
    for bar in bars:
        h = bar.get_height()
        ax.annotate(f"{h:.4f}", (bar.get_x() + bar.get_width() / 2, h),
                    textcoords="offset points", xytext=(0, 3), ha="center", fontsize=8)
fig.tight_layout()
fig.savefig(OUT_PATH, dpi=150)
print(f"Saved: {OUT_PATH}")
print("Source data (verified from model_comparison_table.csv):")
for r in rows:
    print(" ", r)
