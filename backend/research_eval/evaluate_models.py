"""
PHASE RESEARCH-EVAL-1, Parts 9-14: shared metric computation for all
three models. Reuses ml/evaluate.py (the project's existing multiclass +
binary-vulnerable-vs-safe metric functions) unmodified, and adds:

  - weighted (not just macro) precision/recall/F1 (Part 9)
  - vulnerability-specific evaluation: SQL Injection (CWE-89, s0/s1 rows
    only) and Certificate Validation (CWE-295, v0/v1 rows only), each
    scored as its own binary task (Part 11) - exactly the same task
    split already used by ml/rule_only.py (SQLI_LABELS/CERT_LABELS), not
    a new invented mapping
  - the binary SAFE-vs-VULNERABLE mapping is exactly
    ml.evaluate.VULNERABLE_LABELS = {s0, v0}; documented explicitly here
    per Part 11's "do not invent a binary mapping, document exactly how"
    requirement
  - train-only cross-validation mean/std reporting (Part 14)
"""

import numpy as np
from sklearn.metrics import precision_recall_fscore_support, accuracy_score
from sklearn.model_selection import StratifiedKFold, cross_val_score

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml.evaluate import LABELS_ORDER, VULNERABLE_LABELS, multiclass_metrics, binary_metrics, full_evaluation

SQLI_LABELS = {"s0", "s1"}
CERT_LABELS = {"v0", "v1"}

BINARY_MAPPING_DOC = (
    "SAFE vs VULNERABLE binary mapping (from the dataset's own 4-class "
    "labels, not invented for this evaluation): VULNERABLE = {s0, v0} "
    "(s0 = SQL Injection / CWE-89, vulnerable; v0 = Certificate Validation "
    "/ CWE-295, vulnerable). SAFE = {s1, v1} (the safe counterpart of each "
    "task). This is the exact mapping already used in production by "
    "ml/evaluate.py's VULNERABLE_LABELS constant and predictor.py's "
    "LABEL_INFO table - not a new mapping introduced for this phase."
)


def weighted_metrics(y_true_labels, y_pred_labels) -> dict:
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true_labels, y_pred_labels, labels=LABELS_ORDER, average="weighted", zero_division=0
    )
    return {"weighted_precision": float(precision), "weighted_recall": float(recall), "weighted_f1": float(f1)}


def per_class_report(y_true_labels, y_pred_labels) -> dict:
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true_labels, y_pred_labels, labels=LABELS_ORDER, average=None, zero_division=0
    )
    return {
        label: {
            "precision": float(precision[i]),
            "recall": float(recall[i]),
            "f1": float(f1[i]),
            "support": int(support[i]),
        }
        for i, label in enumerate(LABELS_ORDER)
    }


def _binary_task_metrics(y_true_labels, y_pred_labels, task_labels, positive_labels) -> dict:
    """One CWE-specific task (SQL Injection or Certificate Validation),
    scored as its own binary problem restricted to rows whose TRUE label
    belongs to that task (a row's true label always determines which task
    it belongs to - there is no ambiguity)."""
    mask = [l in task_labels for l in y_true_labels]
    n = sum(mask)
    if n == 0:
        return {"support": 0, "note": "no test rows for this task"}

    y_true_task = [l for l, m in zip(y_true_labels, mask) if m]
    y_pred_task = [p for p, m in zip(y_pred_labels, mask) if m]

    y_true_bin = np.array([1 if l in positive_labels else 0 for l in y_true_task])
    y_pred_bin = np.array([1 if l in positive_labels else 0 for l in y_pred_task])

    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true_bin, y_pred_bin, labels=[0, 1], average="binary", pos_label=1, zero_division=0
    )
    return {
        "support": int(n),
        "accuracy": float(accuracy_score(y_true_bin, y_pred_bin)),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }


def vulnerability_specific_metrics(y_true_labels, y_pred_labels) -> dict:
    return {
        "sql_injection_cwe_89": _binary_task_metrics(y_true_labels, y_pred_labels, SQLI_LABELS, {"s0"}),
        "certificate_validation_cwe_295": _binary_task_metrics(y_true_labels, y_pred_labels, CERT_LABELS, {"v0"}),
    }


def full_research_evaluation(y_true_labels, y_pred_labels, vulnerable_score) -> dict:
    """Everything required by spec Parts 9-12 for one model's predictions
    on one split (val or test): 4-class macro+weighted, per-class report,
    confusion matrix, binary SAFE/VULNERABLE + FPR/FNR + ROC-AUC, and the
    two CWE-specific binary breakdowns."""
    out = full_evaluation(y_true_labels, y_pred_labels, vulnerable_score)
    out.update(weighted_metrics(y_true_labels, y_pred_labels))
    out["per_class"] = per_class_report(y_true_labels, y_pred_labels)
    out["vulnerability_specific"] = vulnerability_specific_metrics(y_true_labels, y_pred_labels)
    out["binary_mapping_documentation"] = BINARY_MAPPING_DOC
    return out


def train_only_cross_validation(estimator, X_train, y_train_int, seed, n_splits=5, scoring="f1_macro"):
    """Part 14: CV mean +/- std on TRAIN ONLY. Never touches val/test.
    Uses StratifiedKFold so each fold keeps the (imbalanced) 4-class
    distribution reasonably represented."""
    n_splits = min(n_splits, int(np.min(np.bincount(y_train_int))))
    if n_splits < 2:
        return {
            "performed": False,
            "reason": f"smallest class in train has fewer than 2 members after binning "
                      f"({n_splits} possible folds) - StratifiedKFold CV is not meaningful here",
        }
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    scores = cross_val_score(estimator, X_train, y_train_int, cv=skf, scoring=scoring, n_jobs=1)
    return {
        "performed": True,
        "n_splits": n_splits,
        "scoring": scoring,
        "fold_scores": [float(s) for s in scores],
        "mean": float(np.mean(scores)),
        "std": float(np.std(scores)),
    }
