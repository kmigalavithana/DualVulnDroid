package com.dualvulndroid.dualvulndroid

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Plugin-fix task, STEP 2/10/14: checkBackendAvailability() must
 * distinguish "nothing is listening" from "it's up" - the two conditions
 * the plugin's old single generic "timeout... is it under heavy load?"
 * message conflated. This is what MyToolWindow.runScan() now checks
 * before even starting a project scan, so a developer with the backend
 * simply not started sees a clear message immediately, not after waiting
 * out a real request's read timeout.
 */
class BackendAvailabilityTest {

    // Deterministic, no live backend required: an ephemeral high port
    // essentially guaranteed to have nothing listening on it.
    private val definitelyUnusedUrl = "http://127.0.0.1:59999/"

    @Test
    fun `reports CONNECTION_REFUSED when nothing is listening on the target port`() {
        val result = APIClient().checkBackendAvailability(definitelyUnusedUrl)
        assertEquals(APIClient.BackendAvailability.CONNECTION_REFUSED, result.status)
        assertTrue(
            "Detail message should name the unreachable URL so the developer knows what to start/check",
            result.detail.contains(definitelyUnusedUrl)
        )
    }

    // ---- Requires the real backend running at APIClient.BACKEND_URL ----
    @Test
    fun `reports AVAILABLE when the real backend is reachable`() {
        val result = APIClient().checkBackendAvailability()
        if (result.status != APIClient.BackendAvailability.AVAILABLE) {
            org.junit.Assert.fail(
                "This test requires the real DualVulnDroid FastAPI backend running and reachable at " +
                    "${APIClient.BASE_URL} - got ${result.status}: ${result.detail}. Start the backend and re-run " +
                    "(same environment-dependent convention as LiveAnnotatorIntegrationTest.checkBackendReachable())."
            )
        }
        assertEquals(APIClient.BackendAvailability.AVAILABLE, result.status)
    }
}
