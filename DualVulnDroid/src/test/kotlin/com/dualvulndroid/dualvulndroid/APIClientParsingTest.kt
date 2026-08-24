package com.dualvulndroid.dualvulndroid

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Phase 4, section 14: plain unit tests for the plugin's response
 * parsing (no IntelliJ platform fixture needed - this is pure Gson/data
 * class logic, decoupled from PSI/editor state).
 */
class APIClientParsingTest {

    private val gson = Gson()

    @Test
    fun `parses a full Phase 4 response with dataFlow, securityFeatures, decisionEvidence`() {
        val json = """
        {
          "prediction": "s0",
          "vulnerable": true,
          "vulnerabilityType": "SQL Injection",
          "confidence": 87.55,
          "explanation": "Query string passed to 'rawQuery()' is built via string concatenation.",
          "detections": [
            {"line": 1, "code": "db.rawQuery(query, null);", "type": "SQL Injection",
             "risk_weight": 1.0, "critical_words": [], "source_to_sink_path": ["Intent.getStringExtra()", "query", "rawQuery()"],
             "dataflow_explanation": "traced"}
          ],
          "dataFlow": [
            {"line": 1, "explanation": "traced", "path": ["Intent.getStringExtra()", "query", "rawQuery()"], "verdict": "VULNERABLE", "vulnerabilityType": "SQL Injection"}
          ],
          "predictionModel": "XGBoost-Hybrid",
          "decision": "VULNERABLE",
          "decisionEvidence": [
            {"source": "ml_model", "detail": "XGBoost predicts 's0' with 87.6% confidence", "contribution": 0.876},
            {"source": "dataflow_sql", "detail": "traced source-to-sink", "contribution": 2.0}
          ],
          "securityFeatures": {"sql_source_detected": 1, "sql_sink_detected": 1},
          "severity": "CRITICAL",
          "shapTopFeatures": [{"feature": "sql_sink_detected", "shapValue": 0.9}]
        }
        """.trimIndent()

        val response = gson.fromJson(json, ScanResponse::class.java)

        assertEquals("SQL Injection", response.vulnerabilityType)
        assertTrue(response.vulnerable)
        assertEquals("CRITICAL", response.severity)
        assertEquals("VULNERABLE", response.decision)
        assertEquals(1, response.dataFlow?.size)
        assertEquals("rawQuery()", response.dataFlow?.get(0)?.path?.last())
        assertEquals(2, response.decisionEvidence?.size)
        assertEquals(0.876, response.decisionEvidence?.get(0)?.contribution ?: 0.0, 0.001)
        assertEquals(1.0, response.securityFeatures?.get("sql_source_detected") ?: 0.0, 0.001)
        assertEquals("sql_sink_detected", response.shapTopFeatures?.get(0)?.feature)
    }

    @Test
    fun `parses a minimal legacy-shaped response without Phase 4 fields`() {
        // Simulates an older backend that predates Phase 3/4 - all the
        // new fields are nullable specifically so this doesn't crash.
        val json = """
        {
          "prediction": "s1",
          "vulnerable": false,
          "vulnerabilityType": "SQL Injection",
          "confidence": 91.2,
          "explanation": "Secure SQL query detected.",
          "detections": []
        }
        """.trimIndent()

        val response = gson.fromJson(json, ScanResponse::class.java)

        assertEquals(false, response.vulnerable)
        assertNull(response.severity)
        assertNull(response.decision)
        assertNull(response.decisionEvidence)
        assertNull(response.securityFeatures)
        assertNull(response.shapTopFeatures)
    }

    @Test
    fun `empty detections list parses to an empty list, not null`() {
        val json = """{"prediction":"none","vulnerable":false,"vulnerabilityType":"None","confidence":0.0,"explanation":"No code provided.","detections":[]}"""
        val response = gson.fromJson(json, ScanResponse::class.java)
        assertTrue(response.detections.isEmpty())
    }

    @Test(expected = com.google.gson.JsonSyntaxException::class)
    fun `malformed JSON throws instead of silently producing garbage`() {
        gson.fromJson("{not valid json", ScanResponse::class.java)
    }
}
