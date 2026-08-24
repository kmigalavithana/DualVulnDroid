"""
PHASE RESEARCH-EVAL-5B: evaluates the FROZEN, already-fine-tuned CodeBERT
model (research_eval_artifacts/codebert/model/, selected by
codebert_train.py using validation macro-F1 only) on the frozen 168-row
TEST SET, exactly once. Loads the saved model/tokenizer from LOCAL disk
only - no HF Hub network access, so the earlier hf_xet download hang is
not a factor here at all.

Run from backend/, AFTER research_eval.codebert_train:
    python -m research_eval.codebert_evaluate
"""

import csv
import json
import os
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")  # local artifacts only - never touches the network
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml.evaluate import LABELS_ORDER, VULNERABLE_LABELS
from research_eval.data_split import load_split, ARTIFACT_DIR
from research_eval.evaluate_models import full_research_evaluation
from transformers import AutoTokenizer, AutoModelForSequenceClassification

LABEL_TO_INT = {label: i for i, label in enumerate(LABELS_ORDER)}
INT_TO_LABEL = {i: label for label, i in LABEL_TO_INT.items()}
OUT_DIR = os.path.join(ARTIFACT_DIR, "codebert")
CWE_BY_LABEL_PREFIX = {"s": "CWE-89 (SQL Injection)", "v": "CWE-295 (Certificate Validation)"}
BUCKETS = [(0.50, 0.60), (0.60, 0.70), (0.70, 0.80), (0.80, 0.90), (0.90, 1.0001)]
BUCKET_LABELS = ["0.50-0.59", "0.60-0.69", "0.70-0.79", "0.80-0.89", "0.90-1.00"]
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load_frozen_artifacts():
    tokenizer = AutoTokenizer.from_pretrained(os.path.join(OUT_DIR, "tokenizer"), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(os.path.join(OUT_DIR, "model"), local_files_only=True)
    model.to(DEVICE)
    model.eval()
    with open(os.path.join(OUT_DIR, "tokenizer", "sequence_length.json")) as f:
        max_len = json.load(f)["chosen_max_length"]
    return tokenizer, model, max_len


def predict_probs(tokenizer, model, texts, max_len, batch_size=8):
    all_probs = []
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch_texts = list(texts[i : i + batch_size])
            enc = tokenizer(batch_texts, max_length=max_len, truncation=True, padding="max_length", return_tensors="pt")
            enc = {k: v.to(DEVICE) for k, v in enc.items()}
            out = model(**enc)
            probs = torch.softmax(out.logits, dim=1).cpu().numpy()
            all_probs.append(probs)
    return np.concatenate(all_probs, axis=0)


def confusion_matrix_manual(y_true, y_pred, labels):
    idx = {l: i for i, l in enumerate(labels)}
    cm = [[0] * len(labels) for _ in labels]
    for t, p in zip(y_true, y_pred):
        cm[idx[t]][idx[p]] += 1
    return cm


def classification_report_per_class(y_true, y_pred, labels):
    from sklearn.metrics import precision_recall_fscore_support
    precision, recall, f1, support = precision_recall_fscore_support(y_true, y_pred, labels=labels, average=None, zero_division=0)
    return {labels[i]: {"precision": float(precision[i]), "recall": float(recall[i]), "f1": float(f1[i]), "support": int(support[i])} for i in range(len(labels))}


def cwe_metrics(y_true, y_pred, task_labels, positive_label):
    mask = [l in task_labels for l in y_true]
    n = sum(mask)
    if n == 0:
        return {"support": 0}
    yt = [l for l, m in zip(y_true, mask) if m]
    yp = [p for p, m in zip(y_pred, mask) if m]
    yt_bin = np.array([1 if l == positive_label else 0 for l in yt])
    yp_bin = np.array([1 if p == positive_label else 0 for p in yp])
    tp = int(np.sum((yt_bin == 1) & (yp_bin == 1)))
    tn = int(np.sum((yt_bin == 0) & (yp_bin == 0)))
    fp = int(np.sum((yt_bin == 0) & (yp_bin == 1)))
    fn = int(np.sum((yt_bin == 1) & (yp_bin == 0)))
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else None
    accuracy = (tp + tn) / n
    return {"support": n, "tp": tp, "tn": tn, "fp": fp, "fn": fn, "accuracy": accuracy, "precision": precision, "recall": recall, "f1": f1, "fnr": fnr}


def confidence_records(test_idx, y_true_labels, probs):
    records = []
    for i in range(len(y_true_labels)):
        p = probs[i]
        top_idx = int(np.argmax(p))
        pred_label = INT_TO_LABEL[top_idx]
        true_label = y_true_labels[i]
        records.append({
            "row_identifier": test_idx[i], "true_label": true_label, "predicted_label": pred_label,
            "predicted_probability": float(p[top_idx]), "true_class_probability": float(p[LABEL_TO_INT[true_label]]),
            "vulnerability_probability": float(p[LABEL_TO_INT["s0"]] + p[LABEL_TO_INT["v0"]]),
            "correct": bool(pred_label == true_label),
        })
    return records


def bucket_summary(records):
    summary = []
    for (lo, hi), name in zip(BUCKETS, BUCKET_LABELS):
        in_bucket = [r for r in records if lo <= r["predicted_probability"] < hi]
        n = len(in_bucket)
        if n == 0:
            summary.append({"bucket": name, "n_samples": 0, "accuracy": None, "vulnerability_recall": None, "false_negative_rate": None})
            continue
        accuracy = sum(r["correct"] for r in in_bucket) / n
        vuln_rows = [r for r in in_bucket if r["true_label"] in VULNERABLE_LABELS]
        if vuln_rows:
            correctly_flagged = sum(1 for r in vuln_rows if r["predicted_label"] in VULNERABLE_LABELS)
            recall = correctly_flagged / len(vuln_rows)
            fnr = 1 - recall
        else:
            recall, fnr = None, None
        summary.append({"bucket": name, "n_samples": n, "accuracy": accuracy, "vulnerability_recall": recall, "false_negative_rate": fnr})
    return summary


def calibration_check(y_true_labels, probs):
    from sklearn.metrics import brier_score_loss
    vuln_score = probs[:, LABEL_TO_INT["s0"]] + probs[:, LABEL_TO_INT["v0"]]
    y_true_bin = np.array([1 if l in VULNERABLE_LABELS else 0 for l in y_true_labels])
    brier = float(brier_score_loss(y_true_bin, vuln_score))
    bins = np.linspace(0, 1, 6)
    curve = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (vuln_score >= lo) & (vuln_score < hi if hi < 1 else vuln_score <= hi)
        n = int(mask.sum())
        if n == 0:
            curve.append({"bin": [round(float(lo), 2), round(float(hi), 2)], "n": 0, "mean_predicted": None, "observed_frequency": None})
            continue
        curve.append({"bin": [round(float(lo), 2), round(float(hi), 2)], "n": n,
                       "mean_predicted": float(vuln_score[mask].mean()), "observed_frequency": float(y_true_bin[mask].mean())})
    return {
        "method": "Brier score + 5-bin reliability curve, measured on the frozen TEST set's already-frozen predictions (not fit/refit).",
        "sample_size_caveat": f"n={len(y_true_labels)} - too small for a precise calibration guarantee, indicative only.",
        "brier_score": brier, "reliability_curve": curve,
    }


def _cwe(label):
    return CWE_BY_LABEL_PREFIX[label[0]]


def main():
    tokenizer, model, max_len = load_frozen_artifacts()
    _, _, test_df, (_, _, test_idx) = load_split()

    texts = list(test_df["vulnerable_line"])
    y_true_labels = list(test_df["label"])

    probs = predict_probs(tokenizer, model, texts, max_len)
    y_pred_labels = [INT_TO_LABEL[int(np.argmax(p))] for p in probs]
    vuln_score = probs[:, LABEL_TO_INT["s0"]] + probs[:, LABEL_TO_INT["v0"]]

    test_metrics = full_research_evaluation(y_true_labels, y_pred_labels, vuln_score)
    with open(os.path.join(OUT_DIR, "test_metrics.json"), "w") as f:
        json.dump(test_metrics, f, indent=2)

    per_class = classification_report_per_class(y_true_labels, y_pred_labels, LABELS_ORDER)
    with open(os.path.join(OUT_DIR, "classification_report.json"), "w") as f:
        json.dump(per_class, f, indent=2)

    cm = confusion_matrix_manual(y_true_labels, y_pred_labels, LABELS_ORDER)
    with open(os.path.join(OUT_DIR, "confusion_matrix.csv"), "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["true\\pred"] + LABELS_ORDER)
        for label, row in zip(LABELS_ORDER, cm):
            writer.writerow([label] + row)

    cwe89 = cwe_metrics(y_true_labels, y_pred_labels, {"s0", "s1"}, "s0")
    cwe295 = cwe_metrics(y_true_labels, y_pred_labels, {"v0", "v1"}, "v0")
    with open(os.path.join(OUT_DIR, "cwe_metrics.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["cwe"] + list(cwe89.keys()))
        writer.writeheader()
        writer.writerow({"cwe": "CWE-89", **cwe89})
        writer.writerow({"cwe": "CWE-295", **cwe295})

    conf_records = confidence_records(test_idx, y_true_labels, probs)
    with open(os.path.join(OUT_DIR, "confidence_analysis.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(conf_records[0].keys()))
        writer.writeheader()
        writer.writerows(conf_records)
    bucket_stats = bucket_summary(conf_records)
    with open(os.path.join(OUT_DIR, "confidence_bucket_summary.json"), "w") as f:
        json.dump({"n_test_samples": len(conf_records), "buckets": bucket_stats}, f, indent=2)

    fps, fns = [], []
    for i, (t, p) in enumerate(zip(y_true_labels, y_pred_labels)):
        t_vuln, p_vuln = t in VULNERABLE_LABELS, p in VULNERABLE_LABELS
        row = {
            "row_identifier": test_idx[i], "true_label": t, "predicted_label": p,
            "predicted_probability": round(float(probs[i][int(np.argmax(probs[i]))]), 4),
            "class_probabilities": json.dumps({LABELS_ORDER[j]: round(float(probs[i][j]), 4) for j in range(len(LABELS_ORDER))}),
            "cwe": _cwe(t), "code": test_df.iloc[i]["vulnerable_line"],
        }
        if t_vuln and not p_vuln:
            row["reason_for_miss"] = "Cause not established."
            fns.append(row)
        elif not t_vuln and p_vuln:
            fps.append(row)

    with open(os.path.join(OUT_DIR, "false_negatives.csv"), "w", newline="") as f:
        if fns:
            writer = csv.DictWriter(f, fieldnames=list(fns[0].keys()))
            writer.writeheader()
            writer.writerows(fns)
        else:
            f.write("")
    with open(os.path.join(OUT_DIR, "false_positives.csv"), "w", newline="") as f:
        if fps:
            writer = csv.DictWriter(f, fieldnames=list(fps[0].keys()))
            writer.writeheader()
            writer.writerows(fps)
        else:
            f.write("")

    calibration = calibration_check(y_true_labels, probs)
    with open(os.path.join(OUT_DIR, "calibration.json"), "w") as f:
        json.dump(calibration, f, indent=2)

    make_plots(cm, bucket_stats)

    print(json.dumps({
        "test_metrics_summary": {k: test_metrics[k] for k in ("accuracy", "macro_precision", "macro_recall", "macro_f1", "weighted_precision", "weighted_recall", "weighted_f1", "roc_auc", "false_positive_rate", "false_negative_rate")},
        "binary_confusion_matrix": test_metrics["binary_confusion_matrix"],
        "cwe89": cwe89, "cwe295": cwe295, "n_false_negatives": len(fns), "n_false_positives": len(fps),
    }, indent=2))
    return test_metrics, per_class, cm


def make_plots(cm, bucket_stats):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    plots_dir = os.path.join(OUT_DIR, "plots")
    os.makedirs(plots_dir, exist_ok=True)

    with open(os.path.join(OUT_DIR, "training_history.json")) as f:
        hist = json.load(f)["selected"]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(hist["history"]["train_loss"], label="train loss")
    ax.plot(hist["history"]["val_loss"], label="val loss")
    ax.axvline(hist["best_epoch"], color="gray", linestyle="--", label="selected epoch")
    ax.set_xlabel("Epoch"); ax.set_ylabel("Loss"); ax.set_title(f"CodeBERT ({hist['strategy']}) training vs validation loss")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(plots_dir, "training_validation_loss.png"), dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(hist["history"]["val_macro_f1"], label="val macro-F1")
    ax.axvline(hist["best_epoch"], color="gray", linestyle="--", label="selected epoch")
    ax.set_xlabel("Epoch"); ax.set_ylabel("Macro F1"); ax.set_title(f"CodeBERT ({hist['strategy']}) validation macro-F1")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(plots_dir, "training_validation_f1.png"), dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.5, 5))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(LABELS_ORDER))); ax.set_yticks(range(len(LABELS_ORDER)))
    ax.set_xticklabels(LABELS_ORDER); ax.set_yticklabels(LABELS_ORDER)
    ax.set_xlabel("Predicted"); ax.set_ylabel("True"); ax.set_title("CodeBERT confusion matrix (test)")
    vmax = max(max(row) for row in cm)
    for i in range(len(LABELS_ORDER)):
        for j in range(len(LABELS_ORDER)):
            ax.text(j, i, cm[i][j], ha="center", va="center", color="white" if cm[i][j] > vmax / 2 else "black")
    fig.tight_layout(); fig.savefig(os.path.join(plots_dir, "confusion_matrix.png"), dpi=150); plt.close(fig)

    buckets = [b for b in bucket_stats if b["n_samples"] > 0]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar([b["bucket"] for b in buckets], [b["accuracy"] for b in buckets], color="mediumseagreen")
    ax.set_xlabel("Confidence bucket"); ax.set_ylabel("Accuracy"); ax.set_title("CodeBERT accuracy by confidence bucket (test)")
    ax.set_ylim(0, 1)
    fig.tight_layout(); fig.savefig(os.path.join(plots_dir, "confidence_buckets.png"), dpi=150); plt.close(fig)


if __name__ == "__main__":
    main()
