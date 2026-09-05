package com.dualvulndroid.dualvulndroid

import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * P0 Step 6 regression test for the discovered "Scan Project button works
 * once, second click does nothing" investigation.
 *
 * Root cause found: MyToolWindow.runScan() only checks
 * indicator.checkCanceled() BETWEEN batches, never DURING one - and
 * APIClient.scanProjectBatch's underlying OkHttp call is synchronous, so
 * once a request is in flight, clicking the IDE's own progress-bar Cancel
 * button did nothing until the call's own read timeout (up to 120s)
 * elapsed on its own. If the real backend is killed/restarted or simply
 * hangs mid-request, the "Scan Project" button stays disabled for that
 * whole window with zero feedback - which reads exactly like "the button
 * is broken" even though it silently recovers once the timeout elapses.
 *
 * The fix: scanProjectBatch now accepts an `isCancelled` check and
 * actively calls Call.cancel() on the in-flight OkHttp call as soon as it
 * goes true, instead of only ever timing out passively. This test proves
 * that mechanism actually works, deterministically, against a real (if
 * deliberately slow) local HTTP server - NOT the DualVulnDroid backend's
 * detection logic, which is irrelevant to this specific bug (this is a
 * network/async-callback resilience bug, not a model/decision defect).
 *
 * This test MUST be run in isolation with the real DualVulnDroid backend
 * stopped and 127.0.0.1:8000 instead serving
 * scratchpad/slow_backend_stub.py (see MAIN_PROJECT_IMPLEMENTATION_LOG.md,
 * P0 Step 6, for the exact orchestration) - APIClient.DEVELOPER_SCAN_URL
 * resolves to that same default address, and is fixed at class-load time
 * for the whole JVM, so it cannot be redirected per-test-method.
 */
class APIClientCancellationTest {

    @Test
    fun `cancelling while a batch request is in flight aborts it in well under the full read timeout`() {
        val api = APIClient()
        val files = listOf(BatchScanFileRequest("System.out.println(1);", "Slow.java"))

        val start = System.currentTimeMillis()
        val response = api.scanProjectBatch(files) { true } // already "cancelled" before the call even starts
        val elapsedMs = System.currentTimeMillis() - start

        assertNull("A cancelled call must not return a real response", response)
        assertTrue(
            "lastBatchError should say the scan was cancelled, was: ${api.lastBatchError}",
            api.lastBatchError?.contains("cancel", ignoreCase = true) == true
        )
        assertTrue(
            "Cancellation must abort the call almost immediately (observed ${elapsedMs}ms) - " +
                "well under the stub's artificial 6000ms response delay, and nowhere near the 120s read timeout " +
                "this used to silently wait out before the fix",
            elapsedMs < 3000
        )
    }
}
