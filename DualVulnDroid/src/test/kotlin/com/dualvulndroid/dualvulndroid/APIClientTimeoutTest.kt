package com.dualvulndroid.dualvulndroid

import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Plugin-fix task, STEP 3/14: regression test for the root cause of the
 * reported "Backend did not respond in time (timeout)" failures during
 * ordinary real-time scans - the single-file /predict client used to be
 * built with connectTimeout=2s/readTimeout=2s (no callTimeout at all),
 * which is shorter than a real XGBoost+SHAP+data-flow /predict call can
 * legitimately take once more than one request is in flight (the backend
 * route is a synchronous FastAPI handler served from a finite threadpool
 * on a single uvicorn worker - see APIClient.kt's comment on `client`).
 *
 * This does not require a live backend - it only asserts on the
 * compile-time timeout configuration itself.
 */
class APIClientTimeoutTest {

    @Test
    fun `single-file client timeouts meet the spec minimums (connect=5s, write=10s, read=30s, call=35s)`() {
        assertTrue(
            "connectTimeout regressed below the 5s spec minimum (was 2s before this fix)",
            APIClient.CONNECT_TIMEOUT_S >= 5L
        )
        assertTrue(
            "writeTimeout regressed below the 10s spec minimum",
            APIClient.WRITE_TIMEOUT_S >= 10L
        )
        assertTrue(
            "readTimeout regressed below the 30s spec minimum (was 2s before this fix - the direct " +
                "cause of the reported false 'timeout' failures on ordinary /predict calls)",
            APIClient.READ_TIMEOUT_S >= 30L
        )
        assertTrue(
            "callTimeout (overall request budget) regressed below the 35s spec minimum",
            APIClient.CALL_TIMEOUT_S >= 35L
        )
    }

    @Test
    fun `at most one bounded retry is configured for transient failures`() {
        assertTrue(
            "MAX_TRANSIENT_RETRIES must be small and bounded - retrying every keystroke's failed " +
                "request indefinitely would make a genuinely down backend feel even slower",
            APIClient.MAX_TRANSIENT_RETRIES in 0..1
        )
    }
}
