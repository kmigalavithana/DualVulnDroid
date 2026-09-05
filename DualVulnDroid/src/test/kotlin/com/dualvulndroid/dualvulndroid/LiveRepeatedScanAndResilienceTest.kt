package com.dualvulndroid.dualvulndroid

import com.intellij.openapi.command.WriteCommandAction
import com.intellij.openapi.ui.TestDialog
import com.intellij.openapi.ui.TestDialogManager
import com.intellij.testFramework.PlatformTestUtil
import com.intellij.testFramework.fixtures.BasePlatformTestCase

/**
 * P0 Step 6: live IDE plugin GUI validation, real-code-path coverage that
 * LiveAnnotatorIntegrationTest.kt didn't already exercise - repeated
 * scans, the "safe HostnameVerifier delegate" cert case distinct from the
 * TrustManager one, scan-after-edit/switch-file/return, and the
 * MyToolWindow "Scan Project" button's re-entrancy guard specifically
 * (the previously reported "works once, second click doesn't" symptom).
 *
 * REQUIRES the real backend running and reachable at APIClient.BACKEND_URL
 * - same convention as LiveAnnotatorIntegrationTest.kt, no mocked backend
 * responses anywhere in this file.
 */
class LiveRepeatedScanAndResilienceTest : BasePlatformTestCase() {

    private var previousTestDialog: TestDialog? = null

    override fun setUp() {
        super.setUp()
        previousTestDialog = TestDialogManager.setTestDialog(TestDialog.OK)
    }

    override fun tearDown() {
        try {
            super.tearDown()
        } finally {
            TestDialogManager.setTestDialog(previousTestDialog ?: TestDialog.DEFAULT)
        }
    }

    private fun checkBackendReachable() {
        val probe = APIClient().scanCode("int x = 1;", "ReachabilityProbe.java")
        if (probe == null) {
            fail(
                "Real backend not reachable at ${APIClient.BACKEND_URL} - this live test requires " +
                    "the real FastAPI backend running. Start it and re-run."
            )
        }
    }

    private val vulnerableSqlCode = """
        public class LoginActivity {
            public void onCreate() {
                String username = getIntent().getStringExtra("username");
                String query = "SELECT * FROM users WHERE name=" + username;
                db.rawQuery(query, null);
            }
        }
    """.trimIndent()

    private val safeSqlCode = """
        public class LoginActivity {
            public void login(String userId) {
                db.rawQuery("SELECT * FROM users WHERE id=?", new String[]{userId});
            }
        }
    """.trimIndent()

    // ---- Case E: structurally safe TrustManager (both methods validate) ----
    fun testCaseEStructurallySafeTrustManagerProducesNoFinding() {
        checkBackendReachable()
        val code = """
            import java.security.cert.X509Certificate;
            import java.security.cert.CertificateException;
            public class RealTrustManager implements javax.net.ssl.X509TrustManager {
                public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
                    if (chain == null || chain.length == 0) {
                        throw new CertificateException("Empty chain");
                    }
                }
                public void checkClientTrusted(X509Certificate[] chain, String authType) throws CertificateException {
                    if (chain == null || chain.length == 0) {
                        throw new CertificateException("Empty chain");
                    }
                }
                public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
            }
        """.trimIndent()
        val file = myFixture.configureByText("StructurallySafeTrustManager.java", code)
        val annotator = CodeSentinelAnnotator()
        val results = annotator.doAnnotate(annotator.collectInformation(file, myFixture.editor, false)!!) ?: emptyList()
        println("[LIVE][E] Structurally safe TrustManager -> findings=${results.size}")
        // vulnerable=false is preserved even when decision lands on
        // SUSPICIOUS_REVIEW rather than a clean SAFE (see P0 Step 5's
        // documented model-bias finding) - CodeSentinelAnnotator only
        // ever surfaces a finding when vulnerable==true, so this must
        // stay empty either way.
        assertTrue("A structurally safe TrustManager must not be flagged as a finding", results.isEmpty())
    }

    // ---- Case D (distinct from E): safe HostnameVerifier that delegates ----
    fun testCaseDSafeHostnameVerifierDelegateProducesNoFinding() {
        checkBackendReachable()
        val code = """
            import javax.net.ssl.HostnameVerifier;
            import javax.net.ssl.HttpsURLConnection;
            import javax.net.ssl.SSLSession;
            public class NetworkConfig {
                HostnameVerifier verifier = new HostnameVerifier() {
                    public boolean verify(String hostname, SSLSession session) {
                        return HttpsURLConnection.getDefaultHostnameVerifier().verify(hostname, session);
                    }
                };
            }
        """.trimIndent()
        val file = myFixture.configureByText("SafeHostnameVerifier.java", code)
        val annotator = CodeSentinelAnnotator()
        val results = annotator.doAnnotate(annotator.collectInformation(file, myFixture.editor, false)!!) ?: emptyList()
        println("[LIVE][D] Safe HostnameVerifier delegate -> findings=${results.size}")
        assertTrue("A HostnameVerifier that delegates to the real default check must not be flagged", results.isEmpty())
    }

    // ---- Repeated scans: same file, same annotator, 5 times in a row ----
    fun testRepeatedScansOfTheSameVulnerableFileAllTriggerCorrectly() {
        checkBackendReachable()
        val file = myFixture.configureByText("Repeated.java", vulnerableSqlCode)
        val annotator = CodeSentinelAnnotator()

        repeat(5) { i ->
            val collected = annotator.collectInformation(file, myFixture.editor, false)
            assertNotNull("Scan #${i + 1}: collectInformation returned null", collected)
            val results = annotator.doAnnotate(collected) ?: emptyList()
            assertTrue("Scan #${i + 1}: expected a real SQL Injection finding from the real backend, got none", results.isNotEmpty())
            assertEquals("Scan #${i + 1}: wrong vulnerability type", "SQL Injection", results.first().vulnerabilityType)
        }
    }

    fun testRepeatedScansOfTheSameSafeFileAllTriggerCorrectly() {
        checkBackendReachable()
        val file = myFixture.configureByText("RepeatedSafe.java", safeSqlCode)
        val annotator = CodeSentinelAnnotator()

        repeat(5) { i ->
            val collected = annotator.collectInformation(file, myFixture.editor, false)
            assertNotNull("Scan #${i + 1}: collectInformation returned null", collected)
            val results = annotator.doAnnotate(collected) ?: emptyList()
            assertTrue("Scan #${i + 1}: parameterized SQL must never be flagged, got ${results.size} findings", results.isEmpty())
        }
    }

    // ---- Scan after editing, after switching files, and after returning ----
    fun testScanAfterEditingSwitchingAndReturningToOriginalFile() {
        checkBackendReachable()
        val annotator = CodeSentinelAnnotator()

        // 1. Initial scan of the vulnerable version.
        val vulnFile = myFixture.configureByText("EditFlow.java", vulnerableSqlCode)
        val firstScan = annotator.doAnnotate(annotator.collectInformation(vulnFile, myFixture.editor, false)!!) ?: emptyList()
        assertTrue("Initial scan must find the real vulnerability", firstScan.isNotEmpty())

        // 2. Edit the SAME file, in place, to the safe parameterized form.
        WriteCommandAction.runWriteCommandAction(project) {
            myFixture.editor.document.setText(safeSqlCode)
        }
        PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
        val afterEditScan = annotator.doAnnotate(annotator.collectInformation(myFixture.file, myFixture.editor, false)!!) ?: emptyList()
        assertTrue("After editing to safe code, the real backend must confirm no finding - not the stale vulnerable result", afterEditScan.isEmpty())

        // 3. Switch to a second, unrelated file.
        val otherFile = myFixture.configureByText("EditFlowOther.java", "public class Other { void log() { System.out.println(1); } }")
        val otherScan = annotator.doAnnotate(annotator.collectInformation(otherFile, myFixture.editor, false)!!) ?: emptyList()
        assertTrue("Unrelated file must produce no finding", otherScan.isEmpty())

        // 4. Return to the (now-safe) original file's content and re-scan -
        // must reflect the EDITED content, not a stale cached vulnerable
        // result from step 1.
        val returnedFile = myFixture.configureByText("EditFlow.java", safeSqlCode)
        val returnScan = annotator.doAnnotate(annotator.collectInformation(returnedFile, myFixture.editor, false)!!) ?: emptyList()
        assertTrue("Returning to the edited file must still show no finding, not the original stale vulnerable result", returnScan.isEmpty())
    }

    // ---- The reported "button works once, second click doesn't" symptom:
    // MyToolWindow's own re-entrancy guard around the "Scan Project" button.
    // Reached via reflection (isScanning/startScan are private, real
    // production encapsulation - not loosened for this test, no
    // architecture change) so this exercises the REAL guard exactly as the
    // IDE runs it.
    fun testToolWindowScanButtonCanBeClickedRepeatedlyAfterEachScanCompletes() {
        checkBackendReachable()

        // MyToolWindow.startScan() requires <basePath>/app/src/main/java to
        // exist with at least one supported source file.
        val basePath = project.basePath!!
        val srcDir = java.io.File(basePath, "app/src/main/java")
        srcDir.mkdirs()
        val srcFile = java.io.File(srcDir, "LoginActivity.java")
        srcFile.writeText(vulnerableSqlCode)
        com.intellij.openapi.vfs.LocalFileSystem.getInstance().refreshAndFindFileByIoFile(srcDir)

        val toolWindow = MyToolWindow(project)
        val startScan = MyToolWindow::class.java.getDeclaredMethod("startScan", com.intellij.openapi.project.Project::class.java)
        startScan.isAccessible = true
        val isScanningField = MyToolWindow::class.java.getDeclaredField("isScanning")
        isScanningField.isAccessible = true

        fun waitForScanToFinish() {
            val deadline = System.currentTimeMillis() + 30_000
            while (isScanningField.getBoolean(toolWindow) && System.currentTimeMillis() < deadline) {
                PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
                Thread.sleep(50)
            }
        }

        try {
            repeat(3) { i ->
                assertFalse(
                    "Scan #${i + 1}: the button must be clickable (isScanning == false) before clicking - " +
                        "if this is ever true here, that IS the reported 'second click does nothing' bug",
                    isScanningField.getBoolean(toolWindow)
                )
                startScan.invoke(toolWindow, project)
                waitForScanToFinish()
                assertFalse(
                    "Scan #${i + 1}: isScanning must return to false once the scan completes",
                    isScanningField.getBoolean(toolWindow)
                )
            }
        } finally {
            srcFile.delete()
            srcDir.parentFile?.parentFile?.deleteRecursively()
        }
    }
}
