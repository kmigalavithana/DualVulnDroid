"""
Experiment A: rule-based-only detection (no ML at all), using the
project's own dataflow.py analyzers. This is the fairest possible
"rule-only" baseline since it's the same static analysis engine the
hybrid system uses, just without the XGBoost signal.

Each dataset row's own label tells us which CWE sub-task it belongs to
(s0/s1 = SQLi task, v0/v1 = certificate-validation task) - the dataset
has no other way to indicate "which vulnerability class is this row
about", so a rule-only system is evaluated within the matching task.
"""

from dataflow import analyze_sql_dataflow, analyze_cert_dataflow

SQLI_LABELS = {"s0", "s1"}
CERT_LABELS = {"v0", "v1"}


def rule_only_predict(code: str, task: str) -> str:
    """task: 'sqli' or 'cert'. Returns a predicted label in {s0,s1,v0,v1}."""
    if task == "sqli":
        findings = analyze_sql_dataflow(code)
        return "s0" if findings else "s1"
    else:
        findings = analyze_cert_dataflow(code)
        is_vulnerable = any(f["verdict"] in ("VULNERABLE", "SUSPICIOUS") for f in findings)
        return "v0" if is_vulnerable else "v1"


def evaluate_rule_only(df):
    """df needs columns vulnerable_line, label. Returns (y_true, y_pred, vulnerable_score)."""
    y_true, y_pred, scores = [], [], []
    for _, row in df.iterrows():
        code = row["vulnerable_line"]
        true_label = row["label"]
        task = "sqli" if true_label in SQLI_LABELS else "cert"
        pred_label = rule_only_predict(code, task)

        y_true.append(true_label)
        y_pred.append(pred_label)
        scores.append(1.0 if pred_label in ("s0", "v0") else 0.0)

    return y_true, y_pred, scores
