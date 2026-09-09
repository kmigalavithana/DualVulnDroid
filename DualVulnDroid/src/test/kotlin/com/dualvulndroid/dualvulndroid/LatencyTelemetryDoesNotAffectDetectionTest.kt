package com.dualvulndroid.dualvulndroid

import com.intellij.testFramework.fixtures.BasePlatformTestCase

/**
 * Latency-measurement experiment task, Part 10 items 9/10 + Part 2's
 * "must not change detection results" / "must not create duplicate
 * requests". Requires the real backend (same precondition as
 * LiveAnnotatorIntegrationTest).
 */
class LatencyTelemetryDoesNotAffectDetectionTest : BasePlatformTestCase() {

    private val vulnerableSqlCode = """
        public class LoginActivity {
            public void onCreate() {
                String username = getIntent().getStringExtra("username");
                String query = "SELECT * FROM users WHERE name=" + username;
                db.rawQuery(query, null);
            }
        }
    """.trimIndent()

    private fun checkBackendReachable() {
        val probe = APIClient().scanCode("int x = 1;", "ReachabilityProbe.java")
        if (probe == null) {
            fail("Real backend not reachable at ${APIClient.BACKEND_URL} - this test requires it running.")
        }
    }

    override fun tearDown() {
        try {
            LatencyTelemetry.enabled = false
            LatencyTelemetry.reset()
        } finally {
            super.tearDown()
        }
    }

    // ---- 9. No changes to vulnerability classification ----
    fun testIdenticalCodeProducesIdenticalClassificationWithTelemetryOnOrOff() {
        checkBackendReachable()

        LatencyTelemetry.enabled = false
        val fileA = myFixture.configureByText("TelemetryOff.java", vulnerableSqlCode)
        val annotatorA = CodeSentinelAnnotator()
        val resultsA = annotatorA.doAnnotate(annotatorA.collectInformation(fileA, myFixture.editor, false))
        assertNotNull(resultsA)
        assertTrue(resultsA!!.isNotEmpty())

        LatencyTelemetry.enabled = true
        // A different path is required so this doesn't just hit
        // CodeSentinelAnnotator's own (path, text) result cache, which
        // would trivially "match" regardless of whether telemetry changed
        // anything - the real backend must be called again here for this
        // to be a meaningful comparison.
        val fileB = myFixture.configureByText("TelemetryOn.java", vulnerableSqlCode)
        val annotatorB = CodeSentinelAnnotator()
        val resultsB = annotatorB.doAnnotate(annotatorB.collectInformation(fileB, myFixture.editor, false))
        assertNotNull(resultsB)
        assertTrue(resultsB!!.isNotEmpty())

        assertEquals(resultsA.size, resultsB.size)
        val a = resultsA.first()
        val b = resultsB.first()
        assertEquals("vulnerabilityType must be identical regardless of telemetry", a.vulnerabilityType, b.vulnerabilityType)
        assertEquals("confidence must be identical regardless of telemetry", a.confidence, b.confidence)
        assertEquals("severity must be identical regardless of telemetry", a.severity, b.severity)
        assertEquals("decision must be identical regardless of telemetry", a.decision, b.decision)
    }

    // ---- 10. No duplicate scans ----
    fun testEnablingTelemetryNeverProducesMoreThanOneCompletedEventPerDistinctEdit() {
        checkBackendReachable()
        LatencyTelemetry.enabled = true
        LatencyTelemetry.reset()

        // Three genuinely distinct edits (distinct paths+text) driven
        // through the real annotator pipeline via the real daemon
        // (doHighlighting(), so apply() runs too) - each must produce
        // EXACTLY one completed measurement, never more (never a
        // duplicate request/measurement for the same edit).
        val templates = listOf(
            "NoDup1.java" to vulnerableSqlCode,
            "NoDup2.java" to "public class Safe { public void f() { int x = 1; } }",
            "NoDup3.java" to vulnerableSqlCode,
        )
        for ((name, code) in templates) {
            myFixture.configureByText(name, code)
            myFixture.doHighlighting()
        }

        val events = LatencyTelemetry.snapshot()
        assertEquals("exactly one completed measurement per distinct edit, never a duplicate", 3, events.size)
        assertEquals("each completed event must have a distinct key (distinct edit)", 3, events.map { it.key }.toSet().size)
    }
}
