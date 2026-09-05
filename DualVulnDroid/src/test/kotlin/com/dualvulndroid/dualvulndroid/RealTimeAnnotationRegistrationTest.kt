package com.dualvulndroid.dualvulndroid

import com.intellij.lang.annotation.HighlightSeverity
import com.intellij.testFramework.fixtures.BasePlatformTestCase

/**
 * Debugging task: "IDE is not showing the expected inline vulnerability
 * warning." LiveAnnotatorIntegrationTest already proves collectInformation()/
 * doAnnotate() work correctly when CodeSentinelAnnotator is instantiated
 * directly - but that bypasses plugin.xml's <externalAnnotator> registration
 * entirely (`new CodeSentinelAnnotator()` is called by hand, not resolved by
 * the platform's extension point). It also stops before apply(), so it never
 * proves a real HighlightInfo (the thing that actually paints a squiggly line
 * in the editor) gets created.
 *
 * This test closes both gaps: myFixture.doHighlighting() runs the REAL,
 * REGISTERED highlighting pipeline - the same one a live editor session
 * uses - and returns the REAL HighlightInfo objects apply() produced,
 * requiring a real, reachable backend exactly like LiveAnnotatorIntegrationTest.
 */
class RealTimeAnnotationRegistrationTest : BasePlatformTestCase() {

    private fun checkBackendReachable() {
        val probe = APIClient().scanCode("int x = 1;", "ReachabilityProbe.java")
        if (probe == null) {
            fail(
                "Real backend not reachable at ${APIClient.BACKEND_URL} - this test requires the " +
                    "real FastAPI backend running. Start it and re-run."
            )
        }
    }

    // IMPORTANT (self-caught false lead): the light test fixture has no
    // Android SDK on its classpath, so doHighlighting() also returns a pile
    // of totally unrelated Kotlin-compiler ERROR-severity infos
    // (UNRESOLVED_REFERENCE, UNRESOLVED_IMPORT, etc. for android.* symbols).
    // An earlier version of this test filtered on severity==ERROR alone and
    // that made the "safe" case look falsely flagged. CodeSentinelAnnotator
    // only ever creates an annotation with a "CodeSentinel — ..." branded
    // message (UI-presentation task, item 1/10: e.g. "CodeSentinel — CWE-89
    // SQL Injection detected (confidence: 61%)" - see apply() in
    // CodeSentinelAnnotator.kt) - filter on THAT exact, distinctive prefix
    // so only DualVulnDroid's own security findings are counted, not
    // compiler noise from the missing classpath.
    private val dualVulnDroidFindingPattern = Regex("""CodeSentinel — (CWE-\d+ )?(SQL Injection|Certificate Validation)""")

    private fun highlightErrors(fileName: String, code: String): List<com.intellij.codeInsight.daemon.impl.HighlightInfo> {
        checkBackendReachable()
        myFixture.configureByText(fileName, code)
        val infos = myFixture.doHighlighting(HighlightSeverity.ERROR)
        val all = infos.filter { it.severity == HighlightSeverity.ERROR && it.description != null }
        println("[REG-TEST] all ERROR-severity infos (${all.size} total, includes unrelated compiler noise from the missing Android SDK classpath):")
        all.forEach { println("    [ALL] range=${it.startOffset}-${it.endOffset} text=${it.description}") }
        return all.filter { dualVulnDroidFindingPattern.containsMatchIn(it.description ?: "") }
    }

    fun testSqlVulnerable_TracedSource_ProducesRealHighlightInfo() {
        val code = """
            import android.content.Intent
            class LoginActivity {
                fun onCreate(intent: Intent, db: android.database.sqlite.SQLiteDatabase) {
                    val id = intent.getStringExtra("id")
                    db.rawQuery("SELECT * FROM users WHERE id = " + id, null)
                }
            }
        """.trimIndent()
        val infos = highlightErrors("LoginActivity.kt", code)
        println("[REG-TEST][SQL vulnerable] real HighlightInfo count=${infos.size}")
        infos.forEach { println("  -> [${it.severity}] range=${it.startOffset}-${it.endOffset} text=${it.description}") }
        assertTrue(
            "Expected a REAL, platform-registered HighlightInfo (ERROR severity) for traced-source SQL " +
                "concatenation into a sink - if this is empty while the direct annotator call in " +
                "LiveAnnotatorIntegrationTest succeeds, the bug is in plugin.xml registration or the " +
                "highlighting pipeline, not in CodeSentinelAnnotator's own logic.",
            infos.isNotEmpty()
        )
    }

    fun testSqlSafe_Parameterized_ProducesNoHighlightInfo() {
        val code = """
            class LoginActivity {
                fun login(id: String, db: android.database.sqlite.SQLiteDatabase) {
                    db.rawQuery("SELECT * FROM users WHERE id = ?", arrayOf(id))
                }
            }
        """.trimIndent()
        val infos = highlightErrors("SafeLogin.kt", code)
        println("[REG-TEST][SQL safe] real HighlightInfo count=${infos.size}")
        assertTrue("Parameterized SQL must not produce a real ERROR-severity HighlightInfo", infos.isEmpty())
    }

    fun testCertificateVulnerable_EmptyTrustManager_ProducesRealHighlightInfo() {
        val code = """
            import javax.net.ssl.TrustManager
            import javax.net.ssl.X509TrustManager
            import java.security.cert.X509Certificate
            class NetworkConfig {
                val trustAllCerts = arrayOf<TrustManager>(
                    object : X509TrustManager {
                        override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {}
                        override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {}
                        override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
                    }
                )
            }
        """.trimIndent()
        val infos = highlightErrors("NetworkConfig.kt", code)
        println("[REG-TEST][Cert vulnerable] real HighlightInfo count=${infos.size}")
        infos.forEach { println("  -> [${it.severity}] range=${it.startOffset}-${it.endOffset} text=${it.description}") }
        assertTrue(
            "Expected a REAL HighlightInfo for an empty-body X509TrustManager (accepts every certificate)",
            infos.isNotEmpty()
        )
    }

    // ---- Root-cause regression test: rapid edits on the same file path ----
    // Reproduces the actual bug found during this audit: CodeSentinelAnnotator
    // used to key its in-flight/result cache on file PATH ALONE. IntelliJ's
    // daemon restarts highlighting on every edit, often faster than the
    // backend round trip completes - so while a user is actively typing, a
    // later keystroke's doAnnotate() call would see "a request for this path
    // is already in flight" (true, but for the OLDER, already-superseded
    // text) and return the old/empty cached result instead of scanning the
    // CURRENT text. This directly reproduces that race outside of real IDE
    // timing by firing two doAnnotate() calls for the SAME path back-to-back,
    // the second for genuinely different (vulnerable) text, and asserts the
    // second call is never suppressed by the first still being in flight.
    fun testRapidEditsOnSamePath_LatestTextIsNeverSuppressedByEarlierInFlightRequest() {
        checkBackendReachable()
        val path = "/src/RapidEdit.kt"

        val safeText = """
            class RapidEdit {
                fun login(id: String, db: android.database.sqlite.SQLiteDatabase) {
                    db.rawQuery("SELECT * FROM users WHERE id = ?", arrayOf(id))
                }
            }
        """.trimIndent()
        val vulnerableText = """
            import android.content.Intent
            class RapidEdit {
                fun onCreate(intent: Intent, db: android.database.sqlite.SQLiteDatabase) {
                    val id = intent.getStringExtra("id")
                    db.rawQuery("SELECT * FROM users WHERE id = " + id, null)
                }
            }
        """.trimIndent()

        fun scanData(text: String) = FileScanData(
            path = path,
            fileText = text,
            lines = text.lines().mapIndexed { i, l ->
                val start = text.lines().take(i).sumOf { it.length + 1 }
                LineData(i, l, start, start + l.length)
            }
        )

        val annotator = CodeSentinelAnnotator()
        val secondCallResult = java.util.concurrent.atomic.AtomicReference<List<LineScanResult>?>()
        val firstCallStarted = java.util.concurrent.CountDownLatch(1)

        // Simulate keystroke #1 (safe text) - starts a real backend call on
        // a background thread, exactly like the real daemon would.
        val firstThread = Thread {
            firstCallStarted.countDown()
            annotator.doAnnotate(scanData(safeText))
        }.apply { isDaemon = true; start() }

        firstCallStarted.await()
        // Give the first call a brief head start so it has genuinely
        // registered itself as "in flight" before the second one fires -
        // without sleeping long enough for it to have already completed
        // (the real backend round trip is tens of milliseconds; 5ms reliably
        // lands while it is still in flight without making the test slow).
        Thread.sleep(5)

        // Simulate keystroke #2 (vulnerable text) for the SAME path, fired
        // while call #1 is still very likely in flight.
        secondCallResult.set(annotator.doAnnotate(scanData(vulnerableText)))

        firstThread.join(10_000)

        val result = secondCallResult.get()
        println("[REG-TEST][race] second (latest, vulnerable) call result: ${result?.size ?: "NULL"} finding(s)")
        assertNotNull(
            "The second doAnnotate() call (latest text, genuinely vulnerable) must not return null just " +
                "because an earlier call for OLDER text on the same path was still in flight - this is " +
                "the exact root cause this fix addresses",
            result
        )
        assertTrue(
            "The second call must reflect the CURRENT (vulnerable) text's real backend result, not an " +
                "empty/stale one carried over from the first (safe-text) call",
            result!!.isNotEmpty()
        )
    }
}
