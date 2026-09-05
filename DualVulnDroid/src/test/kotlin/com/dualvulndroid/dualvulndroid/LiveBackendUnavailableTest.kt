package com.dualvulndroid.dualvulndroid

import com.intellij.testFramework.fixtures.BasePlatformTestCase

/**
 * P0 Step 6: the opposite condition of every other Live*Test in this
 * suite - this class REQUIRES the real backend to be UNREACHABLE (down,
 * not merely slow) and verifies the plugin degrades gracefully: no
 * exception propagates out of the real annotator/API client code paths,
 * a clear human-readable diagnostic is recorded, and no stale or
 * fabricated result is ever presented as a genuine finding.
 *
 * Run this class in isolation with the backend stopped - see
 * MAIN_PROJECT_IMPLEMENTATION_LOG.md, P0 Step 6, for the exact
 * stop/verify/restart sequence used.
 */
class LiveBackendUnavailableTest : BasePlatformTestCase() {

    private val vulnerableSqlCode = """
        public class LoginActivity {
            public void onCreate() {
                String username = getIntent().getStringExtra("username");
                String query = "SELECT * FROM users WHERE name=" + username;
                db.rawQuery(query, null);
            }
        }
    """.trimIndent()

    // The exact inverse of LiveAnnotatorIntegrationTest.checkBackendReachable():
    // that class's own docstring states its philosophy directly - "fails
    // loudly with a clear message rather than silently reporting a fake
    // pass" when its precondition isn't met. This class's precondition is
    // the opposite (backend must be DOWN), so it fails loudly and
    // explains why if a normal `gradlew test` run finds the backend
    // reachable, instead of leaving a confusing raw assertion error.
    private fun checkBackendUnreachable() {
        val probe = APIClient().scanCode("int x = 1;", "ReachabilityProbe.java")
        if (probe != null) {
            fail(
                "The real backend IS reachable at ${APIClient.BACKEND_URL} - this test class " +
                    "specifically requires it to be STOPPED (it verifies graceful degradation when " +
                    "the backend is unavailable). Stop the backend and re-run just this class; see " +
                    "MAIN_PROJECT_IMPLEMENTATION_LOG.md, P0 Step 6, for the exact stop/verify/restart sequence."
            )
        }
    }

    fun testAnnotatorDoesNotCrashAndReportsNoFindingWhenBackendIsUnreachable() {
        checkBackendUnreachable()
        val file = myFixture.configureByText("BackendDown.java", vulnerableSqlCode)
        val annotator = CodeSentinelAnnotator()

        val collected = annotator.collectInformation(file, myFixture.editor, false)
        assertNotNull("collectInformation must still succeed - it never talks to the backend itself", collected)

        // The real production code path - must not throw, even though the
        // backend is down.
        val results = annotator.doAnnotate(collected)

        assertTrue(
            "With the backend unreachable there must be NO finding presented at all - " +
                "never a stale or fabricated 'vulnerable' result standing in for a real one",
            results == null || results.isEmpty()
        )
    }

    fun testDirectScanCodeReturnsNullWithAClearDiagnosticWhenBackendIsUnreachable() {
        checkBackendUnreachable()
        val api = APIClient()
        val response = api.scanCode(vulnerableSqlCode, "BackendDown.java")

        assertNull("scanCode must return null, never a fabricated ScanResponse, when the backend cannot be reached", response)
        assertNotNull("APIClient.lastError must record a clear, human-readable reason", api.lastError)
        println("[LIVE][BackendDown] APIClient.lastError = ${api.lastError}")
    }

    fun testBatchScanReturnsNullWithAClearDiagnosticWhenBackendIsUnreachable() {
        checkBackendUnreachable()
        val api = APIClient()
        val response = api.scanProjectBatch(listOf(BatchScanFileRequest("int x = 1;", "X.java")))

        assertNull("scanProjectBatch must return null, never a fabricated BatchScanResponse, when the backend cannot be reached", response)
        assertNotNull("APIClient.lastBatchError must record a clear, human-readable reason", api.lastBatchError)
        println("[LIVE][BackendDown] APIClient.lastBatchError = ${api.lastBatchError}")
    }
}
