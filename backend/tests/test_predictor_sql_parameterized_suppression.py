"""
End-to-end regression test for the CodeSentinel false-positive fix:
predict_code()'s rule/SHAP line-localization loop used to suppress its
own "?" placeholder line ONLY when the placeholder character was on the
exact same line as the matched keyword (e.g. "rawquery("). A variable-
indirected parameterized query - `val sql = "...?..."` on one line,
`db.rawQuery(sql, args)` on a later one - split those across lines, so
the keyword line ("...db.rawQuery(") was never suppressed even though
dataflow.py's own sql_sink_safety_summary() (fixed alongside this) can
now correctly confirm the whole file's SQL sinks are parameterized.

This test exercises the real predict_code() pipeline (ML + rule scan +
data-flow + hybrid decision engine) end-to-end, rather than re-asserting
dataflow.py's unit behavior - see test_dataflow.py for that.

Run from backend/:  python -m pytest tests/test_predictor_sql_parameterized_suppression.py -v
"""

from predictor import predict_code

SAFE_VARIABLE_INDIRECTED_SQL = '''
package com.example.securitytest

import android.database.sqlite.SQLiteDatabase

class LoginDatabase {

    fun login(db: SQLiteDatabase, username: String, password: String) {

        val sql = "SELECT * FROM users WHERE username = ? AND password = ?"

        val result = db.rawQuery(
            sql,
            arrayOf(username, password)
        )

        if (result.moveToFirst()) {
            println("Login successful")
        } else {
            println("Login failed")
        }

        result.close()
    }
}
'''


def test_variable_indirected_parameterized_query_has_no_false_sink_detection():
    """The rule/SHAP scan must not report a "SQL Injection" detection for
    the `db.rawQuery(` line once dataflow confirms every sink in the file
    is parameterized - even though the '?' characters live on an earlier,
    separate line."""
    result = predict_code(SAFE_VARIABLE_INDIRECTED_SQL, "SqlInjectionSafe.kt")

    rawquery_line_detections = [
        d for d in result["detections"]
        if "rawquery(" in d["code"].lower() and "source_to_sink_path" not in d
    ]
    assert rawquery_line_detections == []


def test_variable_indirected_parameterized_query_gets_no_static_rule_evidence():
    """Without a real (non-suppressed) rule-scan hit, decision_engine must
    not receive the "static_rule" +0.4 contribution that used to push this
    genuinely safe query into SUSPICIOUS_REVIEW."""
    result = predict_code(SAFE_VARIABLE_INDIRECTED_SQL, "SqlInjectionSafe.kt")

    static_rule_reasons = [
        r for r in result["decisionEvidence"] if r["source"] == "static_rule"
    ]
    assert static_rule_reasons == []
