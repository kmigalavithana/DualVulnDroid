"""
PHASE RESEARCH-EVAL-3: shared evidence-score computation and threshold-
application utilities for the decision-engine coverage/FNR trade-off
study.

decision_engine.py is imported and used EXACTLY as it exists in
production - compute_evidence() (raw evidence_score, unmodified) and
decide() (which already accepts vulnerable_threshold/safe_threshold as
parameters - this is the same public API ml/calibrate_decision_engine.py
already uses to search thresholds without touching the module's own
logic). Nothing here overrides or duplicates decision_engine.py's own
weight constants.

Run from backend/ (as a library, imported by coverage_optimization.py -
not meant to be run standalone, but importable for tests too).
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import decision_engine
from dataflow import analyze_sql_dataflow, analyze_cert_dataflow, sql_sink_safety_summary
from ml.evaluate import LABELS_ORDER, VULNERABLE_LABELS
from ml.experiment_d import rule_keyword_hit_for
from research_eval.features import load_features, transform, load_xgboost_booster, xgboost_predict

LABEL_TO_INT = {label: i for i, label in enumerate(LABELS_ORDER)}
INT_TO_LABEL = {i: label for label, i in LABEL_TO_INT.items()}
SQLI_LABELS = {"s0", "s1"}
CERT_LABELS = {"v0", "v1"}


def compute_evidence_scores(df, row_ids):
    """One evidence record per row: the frozen XGBoost prediction, the
    real dataflow/rule evidence, and decision_engine.compute_evidence()'s
    raw evidence_score - WITHOUT applying any vulnerable/safe threshold
    yet, so the same records can be re-scored against many candidate
    threshold pairs without re-running XGBoost or the dataflow analyzers."""
    wv, cv, ctv = load_features()
    X = transform(df, wv, cv, ctv)
    booster, num_boost_round = load_xgboost_booster()
    probs = xgboost_predict(booster, num_boost_round, X)

    records = []
    for i, row in df.reset_index(drop=True).iterrows():
        code = row["vulnerable_line"]
        true_label = row["label"]

        p = probs[i]
        top_idx = int(np.argmax(p))
        ml_label = INT_TO_LABEL[top_idx]
        ml_confidence_pct = float(p[top_idx] * 100)

        sql_flow = analyze_sql_dataflow(code)
        cert_flow = analyze_cert_dataflow(code)
        sink_safety = sql_sink_safety_summary(code)
        rule_hit = rule_keyword_hit_for(code, ml_label)

        evidence_score, reasons = decision_engine.compute_evidence(
            ml_label, ml_confidence_pct, sql_flow, cert_flow, sink_safety, rule_hit
        )

        records.append({
            "row_identifier": row_ids[i],
            "true_label": true_label,
            "true_is_vulnerable": true_label in VULNERABLE_LABELS,
            "xgb_prediction": ml_label,
            "xgb_confidence_pct": ml_confidence_pct,
            "evidence_score": evidence_score,
            "reasons": reasons,
        })
    return records


def apply_thresholds(evidence_records, vulnerable_threshold, safe_threshold):
    """decision_engine.decide() called exactly as production calls it,
    just with candidate thresholds instead of the module's currently-
    loaded ones - this is the same parameterized API
    ml/calibrate_decision_engine.py already relies on."""
    decided = []
    for r in evidence_records:
        decision = decision_engine.decide(r["evidence_score"], vulnerable_threshold, safe_threshold)
        decided.append({
            **r,
            "decision": decision,
            "final_vulnerable_flag": decision == "VULNERABLE",  # matches decision_engine.py's own documented mapping
            "deferred": decision == "SUSPICIOUS_REVIEW",
        })
    return decided


def _prf(tp, fp, fn):
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def operating_point_metrics(decided_records, vulnerable_threshold, safe_threshold):
    """Coverage = (VULNERABLE + SAFE) / total (Part 5). Precision/recall/
    F1/FPR/FNR computed ONLY over automatic (non-deferred) decisions -
    deferred cases are never counted as correct or incorrect (Part 6/10)."""
    total = len(decided_records)
    auto = [r for r in decided_records if not r["deferred"]]
    deferred_count = total - len(auto)
    coverage = len(auto) / total if total else 0.0

    tp = sum(1 for r in auto if r["true_is_vulnerable"] and r["final_vulnerable_flag"])
    tn = sum(1 for r in auto if not r["true_is_vulnerable"] and not r["final_vulnerable_flag"])
    fp = sum(1 for r in auto if not r["true_is_vulnerable"] and r["final_vulnerable_flag"])
    fn = sum(1 for r in auto if r["true_is_vulnerable"] and not r["final_vulnerable_flag"])

    precision, recall, f1 = _prf(tp, fp, fn)
    fpr = fp / (fp + tn) if (fp + tn) > 0 else None
    fnr = fn / (fn + tp) if (fn + tp) > 0 else None

    return {
        "vulnerable_threshold": vulnerable_threshold, "safe_threshold": safe_threshold,
        "total_cases": total, "automatic_decisions": len(auto), "deferred_count": deferred_count,
        "coverage": coverage,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "precision": precision, "recall": recall, "f1": f1,
        "fpr": fpr, "fnr": fnr,
        "vulnerability_recall": recall,  # recall IS vulnerability recall in this binary framing
        "vulnerability_fnr": fnr,
    }


def cwe_metrics_for_operating_point(decided_records):
    def task_metrics(task_labels):
        rows = [r for r in decided_records if r["true_label"] in task_labels and not r["deferred"]]
        support_including_deferred = sum(1 for r in decided_records if r["true_label"] in task_labels)
        if not rows:
            return {"support": support_including_deferred, "auto_decided_support": 0, "recall": None, "fnr": None, "precision": None, "f1": None}
        tp = sum(1 for r in rows if r["true_is_vulnerable"] and r["final_vulnerable_flag"])
        fp = sum(1 for r in rows if not r["true_is_vulnerable"] and r["final_vulnerable_flag"])
        fn = sum(1 for r in rows if r["true_is_vulnerable"] and not r["final_vulnerable_flag"])
        precision, recall, f1 = _prf(tp, fp, fn)
        fnr = fn / (fn + tp) if (fn + tp) > 0 else None
        return {"support": support_including_deferred, "auto_decided_support": len(rows),
                "tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1, "fnr": fnr}

    return {
        "sql_injection_cwe_89": task_metrics(SQLI_LABELS),
        "certificate_validation_cwe_295": task_metrics(CERT_LABELS),
    }


def build_threshold_grid(evidence_records):
    """Percentile-based grid over the ACTUAL observed validation
    evidence_score distribution (documented, not arbitrary), plus the
    spec's own explicitly-listed example values - both are reported
    together so the tested range and rationale are transparent."""
    scores = np.array([r["evidence_score"] for r in evidence_records])
    percentile_grid = sorted(set(np.round(np.percentile(scores, np.arange(2, 99, 2)), 3).tolist()))
    spec_vulnerable_examples = [1.0, 1.2, 1.379, 1.5, 1.7, 2.0]
    spec_safe_examples = [-0.7, -0.926, -1.1, -1.3, -1.5]

    vulnerable_candidates = sorted(set(percentile_grid + spec_vulnerable_examples))
    safe_candidates = sorted(set(percentile_grid + spec_safe_examples))

    return {
        "observed_score_range": {"min": float(scores.min()), "max": float(scores.max()),
                                  "mean": float(scores.mean()), "std": float(scores.std())},
        "vulnerable_threshold_candidates": vulnerable_candidates,
        "safe_threshold_candidates": safe_candidates,
        "rationale": (
            "Grid = 2nd-98th percentile (step 2) of the REAL validation evidence_score "
            "distribution, union'd with the spec's explicit example values (1.0/1.2/1.379/"
            "1.5/1.7/2.0 for vulnerable; -0.7/-0.926/-1.1/-1.3/-1.5 for safe). Only pairs "
            "with vulnerable_threshold > safe_threshold are evaluated (decision_engine.py's "
            "own semantics require this - a pair with vulnerable_threshold <= safe_threshold "
            "would leave no possible SUSPICIOUS_REVIEW band and is not a valid operating point "
            "for this engine, so such pairs are excluded rather than silently evaluated)."
        ),
    }
