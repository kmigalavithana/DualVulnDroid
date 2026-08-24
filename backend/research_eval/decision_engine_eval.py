"""
PHASE RESEARCH-EVAL-2, Parts 8-11: evaluates the EXISTING production
decision_engine.py combining the FROZEN RESEARCH-EVAL-1 XGBoost model
with the existing dataflow.py / security keyword-rule evidence, on the
same 168 frozen test rows.

decision_engine.py, dataflow.py, and predictor.py are imported and used
EXACTLY as they exist in production - not modified, not re-implemented.
decision_engine.py's VULNERABLE_THRESHOLD/SAFE_THRESHOLD are whatever it
already loads at import time (the existing calibrated thresholds in
ml/artifacts/decision_engine_thresholds.json if present, else its
hand-picked defaults) - this script does not recalibrate anything.

Two distinct evaluation views (Part 11), because conflating them would
misrepresent a selective/triage system as a plain classifier:

  ALL-CASE VIEW: what a real user actually sees for every one of the 168
  rows, including deferred (SUSPICIOUS_REVIEW) ones - using the engine's
  own documented real output (decision_result["vulnerable"] boolean,
  which decision_engine.py's own module docstring says already collapses
  SUSPICIOUS_REVIEW to False for backward compatibility). This is the
  view used for the false-negative/false-positive tables in
  error_analysis.py, because that is genuinely what the existing system
  would tell a user right now.

  AUTO-DECISION VIEW: precision/recall/F1/FPR/FNR computed ONLY over the
  rows the engine did NOT defer - the honest read of decision quality
  when it actually commits to an answer, with coverage reported
  alongside so a high AUTO-DECISION score achieved via heavy deferral is
  never presented as if it were unconditional performance.

Run from backend/, AFTER research_eval.train_xgboost has produced
research_eval_artifacts/xgboost/model.json:
    python -m research_eval.decision_engine_eval
"""

import csv
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import decision_engine
import predictor
from dataflow import analyze_sql_dataflow, analyze_cert_dataflow, sql_sink_safety_summary
from ml.evaluate import LABELS_ORDER, VULNERABLE_LABELS
from ml.experiment_d import rule_keyword_hit_for
from research_eval.data_split import load_split, ARTIFACT_DIR
from research_eval.features import load_features, transform, load_xgboost_booster, xgboost_predict

LABEL_TO_INT = {label: i for i, label in enumerate(LABELS_ORDER)}
INT_TO_LABEL = {i: label for label, i in LABEL_TO_INT.items()}
SQLI_LABELS = {"s0", "s1"}
CERT_LABELS = {"v0", "v1"}
OUT_DIR = os.path.join(ARTIFACT_DIR, "security_selection")


def document_decision_engine_logic():
    """Part 8: document the REAL, currently-loaded logic - not invented,
    read directly from the module's own state."""
    return {
        "source_file": "decision_engine.py (imported unmodified)",
        "currently_loaded_thresholds": {
            "vulnerable_threshold": decision_engine.VULNERABLE_THRESHOLD,
            "safe_threshold": decision_engine.SAFE_THRESHOLD,
            "source": decision_engine.CALIBRATION_SOURCE,
        },
        "evidence_weights": {
            "ml_prediction": decision_engine.ML_WEIGHT,
            "sql_traced_source_to_sink": decision_engine.TRACED_SOURCE_TO_SINK_WEIGHT,
            "sql_unparameterized_concatenation": decision_engine.UNPARAMETERIZED_CONCAT_WEIGHT,
            "sql_confirmed_parameterized": decision_engine.CONFIRMED_PARAMETERIZED_WEIGHT,
            "cert_vulnerable": decision_engine.CERT_VULNERABLE_WEIGHT,
            "cert_suspicious": decision_engine.CERT_SUSPICIOUS_WEIGHT,
            "cert_safe": decision_engine.CERT_SAFE_WEIGHT,
            "static_keyword_rule_corroboration": decision_engine.STATIC_RULE_WEIGHT,
        },
        "decision_rule": (
            "evidence_score >= vulnerable_threshold -> VULNERABLE; "
            "evidence_score <= safe_threshold -> SAFE; otherwise -> SUSPICIOUS_REVIEW"
        ),
        "boolean_vulnerable_mapping": "ONLY decision=='VULNERABLE' maps to vulnerable=True (decision_engine.py docstring)",
        "severity_mapping": "predictor._severity_from_decision (imported unmodified): VULNERABLE->CRITICAL/HIGH (by evidence_score>=3.0), SUSPICIOUS_REVIEW->MEDIUM, SAFE->LOW",
        "recommendation_mapping": dict(predictor.RECOMMENDATION_BY_DECISION),
    }


def run_pipeline(test_df, test_idx):
    wv, cv, ctv = load_features()
    X_test = transform(test_df, wv, cv, ctv)
    booster, num_boost_round = load_xgboost_booster()
    probs = xgboost_predict(booster, num_boost_round, X_test)

    records = []
    for i, row in test_df.reset_index(drop=True).iterrows():
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

        result = decision_engine.evaluate(ml_label, ml_confidence_pct, sql_flow, cert_flow, sink_safety, rule_hit)
        decision = result["decision"]
        severity = predictor._severity_from_decision(decision, result["evidence_score"])
        recommendation = predictor.RECOMMENDATION_BY_DECISION[decision]

        records.append({
            "row_identifier": test_idx[i],
            "true_label": true_label,
            "true_is_vulnerable": true_label in VULNERABLE_LABELS,
            "xgb_prediction": ml_label,
            "xgb_confidence_pct": round(ml_confidence_pct, 3),
            "sql_dataflow_traced": bool([f for f in sql_flow if f["detection_basis"] in ("traced-source", "traced-source-interprocedural")]),
            "sql_dataflow_concat_only": bool([f for f in sql_flow if f["detection_basis"] == "unparameterized-concatenation"]),
            "sql_all_sinks_parameterized": bool(sink_safety.get("sinks_found", 0) > 0 and sink_safety.get("all_parameterized")),
            "cert_dataflow_verdict": (cert_flow[0]["verdict"] if cert_flow else "NONE"),
            "rule_keyword_hit": rule_hit,
            "evidence_score": result["evidence_score"],
            "decision": decision,
            "final_vulnerable_flag": result["vulnerable"],  # the engine's own documented real boolean output
            "deferred": decision == "SUSPICIOUS_REVIEW",
            "risk_level": severity,
            "recommendation": recommendation,
            "reasons": result["reasons"],
        })
    return records


def all_case_view(records):
    breakdown = {"VULNERABLE": 0, "SAFE": 0, "SUSPICIOUS_REVIEW": 0}
    for r in records:
        breakdown[r["decision"]] += 1
    return {
        "total_cases": len(records),
        "decision_breakdown": breakdown,
        "note": "Counts only - no accuracy claim is made about SUSPICIOUS_REVIEW cases here.",
    }


def coverage_view(records):
    total = len(records)
    auto_decided = sum(1 for r in records if not r["deferred"])
    deferred = total - auto_decided
    return {
        "total_cases": total,
        "automatically_decided_cases": auto_decided,
        "deferred_review_cases": deferred,
        "coverage": auto_decided / total,
        "deferred_fraction": deferred / total,
    }


def _prf(tp, fp, fn):
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def auto_decision_view(records):
    """Part 11B: precision/recall/F1/FPR/FNR over ONLY the non-deferred rows."""
    auto = [r for r in records if not r["deferred"]]
    if not auto:
        return {"coverage": 0.0, "n_auto_decided": 0, "note": "no cases were auto-decided"}

    tp = sum(1 for r in auto if r["true_is_vulnerable"] and r["final_vulnerable_flag"])
    tn = sum(1 for r in auto if not r["true_is_vulnerable"] and not r["final_vulnerable_flag"])
    fp = sum(1 for r in auto if not r["true_is_vulnerable"] and r["final_vulnerable_flag"])
    fn = sum(1 for r in auto if r["true_is_vulnerable"] and not r["final_vulnerable_flag"])

    precision, recall, f1 = _prf(tp, fp, fn)
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0

    return {
        "n_auto_decided": len(auto),
        "coverage": len(auto) / len(records),
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "precision": precision, "recall": recall, "f1": f1,
        "fpr": fpr, "fnr": fnr,
    }


def all_case_security_view(records):
    """The 'what a real user sees' binary view (Part 12/13's error tables
    use this same definition): every case counted, deferred ones included
    via the engine's own documented vulnerable=False-on-defer boolean."""
    tp = sum(1 for r in records if r["true_is_vulnerable"] and r["final_vulnerable_flag"])
    tn = sum(1 for r in records if not r["true_is_vulnerable"] and not r["final_vulnerable_flag"])
    fp = sum(1 for r in records if not r["true_is_vulnerable"] and r["final_vulnerable_flag"])
    fn = sum(1 for r in records if r["true_is_vulnerable"] and not r["final_vulnerable_flag"])
    precision, recall, f1 = _prf(tp, fp, fn)
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
    return {
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "precision": precision, "recall": recall, "f1": f1,
        "fpr": fpr, "fnr": fnr,
        "note": "Deferred (SUSPICIOUS_REVIEW) cases counted as final_vulnerable_flag=False here, "
                "matching the engine's own real, documented boolean output - this inflates FNR "
                "relative to the AUTO-DECISION VIEW and is reported as such, not hidden.",
    }


def cwe_breakdown(records, view_name, predicate_true_is_vulnerable_key="true_is_vulnerable"):
    def task_metrics(task_labels):
        rows = [r for r in records if r["true_label"] in task_labels]
        if not rows:
            return {"support": 0}
        tp = sum(1 for r in rows if r["true_is_vulnerable"] and r["final_vulnerable_flag"])
        fp = sum(1 for r in rows if not r["true_is_vulnerable"] and r["final_vulnerable_flag"])
        fn = sum(1 for r in rows if r["true_is_vulnerable"] and not r["final_vulnerable_flag"])
        tn = sum(1 for r in rows if not r["true_is_vulnerable"] and not r["final_vulnerable_flag"])
        precision, recall, f1 = _prf(tp, fp, fn)
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
        return {"support": len(rows), "tp": tp, "tn": tn, "fp": fp, "fn": fn,
                "precision": precision, "recall": recall, "f1": f1, "fnr": fnr}

    return {
        "view": view_name,
        "sql_injection_cwe_89": task_metrics(SQLI_LABELS),
        "certificate_validation_cwe_295": task_metrics(CERT_LABELS),
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    _, _, test_df, (_, _, test_idx) = load_split()

    records = run_pipeline(test_df, test_idx)

    logic_doc = document_decision_engine_logic()
    all_case = all_case_view(records)
    coverage = coverage_view(records)
    auto_view = auto_decision_view(records)
    all_case_binary = all_case_security_view(records)
    cwe_auto = cwe_breakdown([r for r in records if not r["deferred"]], "AUTO-DECISION VIEW (deferred cases excluded)")
    cwe_all = cwe_breakdown(records, "ALL-CASE VIEW (deferred cases count as not-vulnerable, per engine's real boolean output)")

    with open(os.path.join(OUT_DIR, "decision_engine_records.csv"), "w", newline="") as f:
        flat = [{**r, "reasons": json.dumps(r["reasons"])} for r in records]
        writer = csv.DictWriter(f, fieldnames=list(flat[0].keys()))
        writer.writeheader()
        writer.writerows(flat)

    output = {
        "decision_engine_logic": logic_doc,
        "all_case_view": all_case,
        "coverage": coverage,
        "auto_decision_view": auto_view,
        "all_case_binary_security_view": all_case_binary,
        "cwe_breakdown_auto_decision_view": cwe_auto,
        "cwe_breakdown_all_case_view": cwe_all,
    }
    with open(os.path.join(OUT_DIR, "decision_engine_metrics.json"), "w") as f:
        json.dump(output, f, indent=2)

    print(json.dumps(output, indent=2))
    return records, output


if __name__ == "__main__":
    main()
