package com.dualvulndroid.dualvulndroid

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Phase 5B: verifies the shared FindingDetailView model and its two
 * adapters (project-scan DeveloperScanResult, real-time LineScanResult)
 * without needing a live backend or the IntelliJ platform.
 */
class FindingModelTest {

    private fun sampleDeveloperResult(vulnerable: Boolean = true) = DeveloperScanResult(
        vulnerable = vulnerable,
        vulnerabilityType = "SQL Injection",
        cwe = "CWE-89",
        confidence = 87.5,
        severity = "HIGH",
        model = DeveloperModelInfo(name = "XGBoost-Hybrid", version = "production"),
        dataFlow = listOf(DeveloperDataFlowEntry(
            source = "Intent.getStringExtra()", sink = "rawQuery()",
            path = listOf("Intent.getStringExtra()", "query", "rawQuery()"), verdict = "VULNERABLE"
        )),
        securityFeatures = mapOf("sql_source_detected" to 1.0, "sql_sink_detected" to 1.0),
        decision = DeveloperDecision(
            riskLevel = "HIGH", recommendation = "REVIEW", decisionConfidence = 0.9,
            evidence = listOf(DecisionReason("dataflow_sql", "traced source-to-sink", 2.0))
        ),
        explanation = listOf("User-controlled input reaches SQL execution."),
        detections = listOf(Detection(line = 4, code = "db.rawQuery(query, null);", type = "SQL Injection"))
    )

    private fun sampleLineScanResult() = LineScanResult(
        lineText = "db.rawQuery(query, null);",
        vulnerabilityType = "SQL Injection",
        confidence = 87.55,
        startOffset = 10,
        endOffset = 36,
        sourceToSinkPath = listOf("Intent.getStringExtra()", "query", "rawQuery()"),
        dataflowExplanation = "traced source-to-sink",
        severity = "HIGH",
        predictionModel = "XGBoost-Hybrid",
        decision = "VULNERABLE",
        decisionEvidence = listOf(DecisionReason("dataflow_sql", "traced source-to-sink", 2.0)),
        lineNumber = 4,
        securityFeatures = mapOf("sql_source_detected" to 1.0, "sql_sink_detected" to 1.0),
        shapTopFeatures = listOf(ShapFeature("sql_sink_detected", 0.9))
    )

    // ---- Project-scan adapter ----
    @Test
    fun `DeveloperScanResult adapts to a fully populated detail view`() {
        val view = sampleDeveloperResult().toDetailView("Login.kt", line = 4)

        assertEquals("Login.kt", view.fileName)
        assertEquals(4, view.line)
        assertEquals("Login.kt:5", view.location)
        assertEquals("CWE-89", view.cwe)
        assertEquals("HIGH", view.severity)
        assertEquals("REVIEW", view.recommendation)
        assertEquals(listOf("Intent.getStringExtra()", "query", "rawQuery()"), view.sourceToSinkPath)
        assertEquals(1, view.evidence.size)
        // /developer/scan never carries SHAP contributions (only /developer/explain does) -
        // must be null, not fabricated.
        assertNull(view.shapFactors)
    }

    // ---- Real-time adapter ----
    @Test
    fun `LineScanResult adapts to a detail view with SHAP available`() {
        val view = sampleLineScanResult().toDetailView("Login.kt")

        assertEquals("Login.kt", view.fileName)
        assertEquals(4, view.line)
        assertEquals("HIGH", view.severity)
        assertEquals("VULNERABLE", view.decision)
        // /predict HAS shapTopFeatures - must be populated, not "Not available".
        assertEquals(1, view.shapFactors?.size)
        assertEquals("sql_sink_detected", view.shapFactors?.get(0)?.feature)
        // CWE isn't a /predict field - derived deterministically from vulnerabilityType.
        assertEquals("CWE-89", view.cwe)
        // /predict has no decision.recommendation equivalent - honestly null, not invented.
        assertNull(view.recommendation)
    }

    // ---- Section 5: missing fields render as "Not available", never fabricated ----
    @Test
    fun `renderDetailHtml shows Not available for missing fields instead of inventing them`() {
        val view = FindingDetailView(
            fileName = "Unknown.kt", line = null, vulnerabilityType = "SQL Injection",
            cwe = null, severity = null, confidence = 50.0, decision = null, recommendation = null,
            modelName = null, sourceToSinkPath = null, securityFeatures = null, shapFactors = null,
            evidence = emptyList(), explanation = emptyList()
        )
        val html = renderDetailHtml(view)

        assertTrue(html.contains("Not available"))
        assertTrue(!html.contains("null"))
    }

    // ---- Section 10: same input, both adapters must agree ----
    @Test
    fun `real-time and project-scan adapters agree on the same underlying finding`() {
        val fromProjectScan = sampleDeveloperResult().toDetailView("Login.kt", line = 4)
        val fromRealTime = sampleLineScanResult().toDetailView("Login.kt")

        assertEquals(fromProjectScan.vulnerabilityType, fromRealTime.vulnerabilityType)
        assertEquals(fromProjectScan.cwe, fromRealTime.cwe)
        assertEquals(fromProjectScan.severity, fromRealTime.severity)
        assertEquals(fromProjectScan.sourceToSinkPath, fromRealTime.sourceToSinkPath)
        assertEquals(fromProjectScan.location, fromRealTime.location)
    }

    // ---- Section 6: the editor annotation stays lightweight regardless
    // of how rich the underlying finding is ----
    @Test
    fun `LineScanResult toString-equivalent annotation message stays short`() {
        val result = sampleLineScanResult()
        val severityPrefix = result.severity?.let { "$it - " } ?: ""
        val annotationMessage = "$severityPrefix${result.vulnerabilityType} (${"%.2f".format(result.confidence)}%)"

        assertTrue("Annotation message should stay short: $annotationMessage", annotationMessage.length < 60)
    }
}
