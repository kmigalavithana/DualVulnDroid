"""
Shared metric computation, used identically for every model/approach
being compared (rule-only, each ML algorithm, each ablation config) so
the numbers in the comparison tables are computed the same way.
"""

import numpy as np
from sklearn.metrics import (
    accuracy_score, precision_recall_fscore_support, matthews_corrcoef,
    confusion_matrix, roc_auc_score, average_precision_score, roc_curve,
    precision_recall_curve,
)

LABELS_ORDER = ["s0", "v0", "s1", "v1"]  # matches existing model_metadata.json convention
VULNERABLE_LABELS = {"s0", "v0"}


def multiclass_metrics(y_true_labels, y_pred_labels) -> dict:
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true_labels, y_pred_labels, labels=LABELS_ORDER, average="macro", zero_division=0
    )
    cm = confusion_matrix(y_true_labels, y_pred_labels, labels=LABELS_ORDER)
    return {
        "accuracy": float(accuracy_score(y_true_labels, y_pred_labels)),
        "macro_precision": float(precision),
        "macro_recall": float(recall),
        "macro_f1": float(f1),
        "mcc": float(matthews_corrcoef(y_true_labels, y_pred_labels)) if len(set(y_true_labels)) > 1 else None,
        "confusion_matrix": cm.tolist(),
        "confusion_matrix_labels": LABELS_ORDER,
    }


def binary_metrics(y_true_labels, y_pred_labels, vulnerable_score) -> dict:
    """
    Collapses the 4-class problem to vulnerable-vs-safe for the metrics
    that are inherently binary (ROC-AUC, PR-AUC, FPR, FNR).
    vulnerable_score: per-sample P(vulnerable) in [0,1] (e.g. P(s0)+P(v0)
    for a softmax model, or 1.0/0.0 for a rule-only decision).
    """
    y_true_bin = np.array([1 if l in VULNERABLE_LABELS else 0 for l in y_true_labels])
    y_pred_bin = np.array([1 if l in VULNERABLE_LABELS else 0 for l in y_pred_labels])
    vulnerable_score = np.array(vulnerable_score)

    tn, fp, fn, tp = confusion_matrix(y_true_bin, y_pred_bin, labels=[0, 1]).ravel()
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
    fnr = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0

    result = {
        "false_positive_rate": fpr,
        "false_negative_rate": fnr,
        "binary_confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }

    if len(set(y_true_bin)) > 1:
        result["roc_auc"] = float(roc_auc_score(y_true_bin, vulnerable_score))
        result["pr_auc"] = float(average_precision_score(y_true_bin, vulnerable_score))
        fpr_curve, tpr_curve, _ = roc_curve(y_true_bin, vulnerable_score)
        prec_curve, rec_curve, _ = precision_recall_curve(y_true_bin, vulnerable_score)
        result["roc_curve"] = {"fpr": fpr_curve.tolist(), "tpr": tpr_curve.tolist()}
        result["pr_curve"] = {"precision": prec_curve.tolist(), "recall": rec_curve.tolist()}
    else:
        result["roc_auc"] = None
        result["pr_auc"] = None
        result["roc_curve"] = None
        result["pr_curve"] = None

    return result


def full_evaluation(y_true_labels, y_pred_labels, vulnerable_score) -> dict:
    out = multiclass_metrics(y_true_labels, y_pred_labels)
    out.update(binary_metrics(y_true_labels, y_pred_labels, vulnerable_score))
    return out
