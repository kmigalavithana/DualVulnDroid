package com.dualvulndroid.dualvulndroid

import com.intellij.testFramework.fixtures.BasePlatformTestCase

/**
 * Plugin-fix task, STEP 8/9/14: "manual rescan bypasses stale cache."
 *
 * CodeSentinelAnnotator caches a scan result per (path, exact file text)
 * so an unchanged file isn't re-sent to the backend on every unrelated
 * highlighting pass. RescanCurrentFileAction calls
 * CodeSentinelAnnotator.forceRescan(path) before invoking a fresh scan
 * specifically so a manual rescan is never short-circuited by that cache
 * even when the text hasn't changed (e.g. the user just wants to confirm
 * against the current backend/model again).
 *
 * This is proven here via timing rather than reaching into private state:
 * a cache hit returns near-instantly (no debounce sleep, no network
 * call); a genuine fresh scan always takes at least the STEP 4 debounce
 * window (500ms) plus a real network round trip. If forceRescan() didn't
 * actually clear the cache, the second doAnnotate() call below would
 * return instantly instead.
 *
 * REQUIRES the real backend running and reachable at APIClient.BACKEND_URL,
 * per this suite's existing Live* test convention.
 */
class ForceRescanCacheInvalidationTest : BasePlatformTestCase() {

    private fun checkBackendReachable() {
        val probe = APIClient().scanCode("int x = 1;", "ReachabilityProbe.java")
        if (probe == null) {
            fail(
                "Real backend not reachable at ${APIClient.BACKEND_URL} - this live test requires " +
                    "the real FastAPI backend running. Start it and re-run."
            )
        }
    }

    fun testForceRescanClearsTheCacheSoAnUnchangedFileIsScannedAgain() {
        checkBackendReachable()

        val code = """
            public class LoginActivity {
                public void login(String userId) {
                    db.rawQuery("SELECT * FROM users WHERE id=?", new String[]{userId});
                }
            }
        """.trimIndent()
        val file = myFixture.configureByText("ForceRescan.java", code)
        val annotator = CodeSentinelAnnotator()

        // First scan: real network round trip + debounce, populates the cache.
        val first = annotator.doAnnotate(annotator.collectInformation(file, myFixture.editor, false)!!)
        assertNotNull(first)

        // Second call for the SAME (path, text) with no forceRescan in
        // between: must hit the cache and return near-instantly.
        val cachedStart = System.currentTimeMillis()
        annotator.doAnnotate(annotator.collectInformation(file, myFixture.editor, false)!!)
        val cachedElapsedMs = System.currentTimeMillis() - cachedStart
        assertTrue(
            "A repeat call for identical (path, text) should hit the cache and return near-instantly, " +
                "not re-run the debounce+network path (observed ${cachedElapsedMs}ms)",
            cachedElapsedMs < 300
        )

        // Now force a rescan for this path and repeat the IDENTICAL call -
        // must take at least the debounce window again, proving the cache
        // entry (and the short-circuit it enabled) was actually cleared.
        val path = file.virtualFile!!.path
        CodeSentinelAnnotator.forceRescan(path)

        val freshStart = System.currentTimeMillis()
        val fresh = annotator.doAnnotate(annotator.collectInformation(file, myFixture.editor, false)!!)
        val freshElapsedMs = System.currentTimeMillis() - freshStart

        assertNotNull("forceRescan must still produce a real result, not null", fresh)
        assertTrue(
            "After forceRescan(), an identical-text call must go through the real debounce+network " +
                "path again (>= ~400ms) instead of returning from the (supposedly cleared) cache " +
                "(observed ${freshElapsedMs}ms)",
            freshElapsedMs >= 400
        )
    }
}
