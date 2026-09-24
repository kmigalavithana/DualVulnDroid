package com.dualvulndroid.dualvulndroid

import com.intellij.openapi.command.WriteCommandAction
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.TestDialog
import com.intellij.openapi.ui.TestDialogManager
import com.intellij.openapi.vfs.LocalFileSystem
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.psi.util.PsiTreeUtil
import com.intellij.testFramework.PlatformTestUtil
import com.intellij.testFramework.fixtures.BasePlatformTestCase
import org.jetbrains.kotlin.psi.KtCallExpression
import java.io.File
import javax.swing.DefaultListModel
import javax.swing.JButton
import javax.swing.JLabel

/**
 * Two-mode Tool Window: "Scan Project" (whole project) and "Scan File"
 * (only the active editor file) side by side. Drives the real MyToolWindow through its real private state
 * (same reflection pattern as ScanCurrentFileScopeTest/ToolWindowPresentationTest).
 *
 * Tests that actually scan REQUIRE the real FastAPI backend at
 * APIClient.BACKEND_URL (this suite never fakes backend responses); the
 * button/no-file/unsupported-file tests never reach it.
 */
class ScanProjectAndScanFileModesTest : BasePlatformTestCase() {

    private var previousTestDialog: TestDialog? = null

    override fun setUp() {
        super.setUp()
        // Applying a Quick Fix triggers FixVerificationRunner's real async
        // re-scan, which reports via a dialog - auto-answer it.
        previousTestDialog = TestDialogManager.setTestDialog(TestDialog.OK)
    }

    override fun tearDown() {
        try {
            srcDir().deleteRecursively()
            super.tearDown()
        } finally {
            TestDialogManager.setTestDialog(previousTestDialog ?: TestDialog.DEFAULT)
        }
    }

    // ---- fixtures ----

    // File A: Kotlin SQL concatenation (same shape QuickFixEndToEndTest
    // proves the real backend flags and SqlFixLocator can fix).
    private val sqlInjectionKotlin = """
        package com.example.securitytest

        import android.database.Cursor
        import android.database.sqlite.SQLiteDatabase

        class SqlInjectionVulnerable {

            fun findUser(db: SQLiteDatabase, userId: String): Cursor {

                val query = "SELECT * FROM users WHERE id=" + userId

                return db.rawQuery(query, null)
            }
        }
    """.trimIndent()

    // File B: Kotlin trust-all HostnameVerifier (same pattern the backend's
    // own tests/test_api.py proves is flagged CWE-295).
    private val certificateKotlin = """
        package com.example.securitytest

        import javax.net.ssl.HostnameVerifier
        import javax.net.ssl.SSLSession

        class CertificateVulnerable {
            val hv = object : HostnameVerifier {
                override fun verify(hostname: String, session: SSLSession): Boolean {
                    return true
                }
            }
        }
    """.trimIndent()

    // Java SQL with a traced external source (proven VULNERABLE by
    // LiveAnnotatorIntegrationTest). Unique class name: other tests leave
    // an identical LoginActivity.java behind, and ProjectFileCollector
    // de-duplicates identical content, which would hide this file.
    private val sqlInjectionJava = """
        public class TwoModeLoginActivity {
            public void onCreate() {
                String username = getIntent().getStringExtra("username");
                String query = "SELECT * FROM users WHERE name=" + username;
                db.rawQuery(query, null);
            }
        }
    """.trimIndent()

    // ---- helpers ----

    private fun checkBackendReachable() {
        val probe = APIClient().scanCode("int x = 1;", "ReachabilityProbe.java")
        if (probe == null) {
            fail(
                "Real backend not reachable at ${APIClient.BACKEND_URL} - this test requires the " +
                    "real FastAPI backend running. Start it and re-run."
            )
        }
    }

    private fun <T> field(toolWindow: MyToolWindow, name: String): T {
        @Suppress("UNCHECKED_CAST")
        return MyToolWindow::class.java.getDeclaredField(name).apply { isAccessible = true }.get(toolWindow) as T
    }

    private fun scanFileButtonOf(toolWindow: MyToolWindow): JButton = field(toolWindow, "testButton")
    private fun scanProjectButtonOf(toolWindow: MyToolWindow): JButton = field(toolWindow, "scanProjectButton")
    private fun statusOf(toolWindow: MyToolWindow): String = field<JLabel>(toolWindow, "statusLabel").text
    private fun summaryOf(toolWindow: MyToolWindow): String = field<JLabel>(toolWindow, "summaryLabel").text

    private fun emptyTextOf(toolWindow: MyToolWindow): String =
        field<com.intellij.ui.components.JBList<*>>(toolWindow, "findingsList").emptyText.text

    private fun findingsOf(toolWindow: MyToolWindow): List<FindingEntry> {
        val listModel: DefaultListModel<FindingEntry> = field(toolWindow, "listModel")
        return (0 until listModel.size()).map { listModel.getElementAt(it) }
    }

    private fun isScanningOf(toolWindow: MyToolWindow): Boolean =
        MyToolWindow::class.java.getDeclaredField("isScanning").apply { isAccessible = true }.getBoolean(toolWindow)

    private fun invoke(toolWindow: MyToolWindow, method: String) {
        MyToolWindow::class.java.getDeclaredMethod(method, Project::class.java)
            .apply { isAccessible = true }
            .invoke(toolWindow, project)
    }

    private fun scanFile(toolWindow: MyToolWindow) {
        MyToolWindow::class.java.getDeclaredMethod("startScanOfFile", Project::class.java, com.intellij.openapi.vfs.VirtualFile::class.java)
            .apply { isAccessible = true }
            .invoke(toolWindow, project, com.intellij.openapi.fileEditor.FileEditorManager.getInstance(project).selectedFiles.firstOrNull())
        waitForScanToFinish(toolWindow)
    }

    private fun scanProject(toolWindow: MyToolWindow) {
        invoke(toolWindow, "startProjectScan")
        waitForScanToFinish(toolWindow)
    }

    private fun waitForScanToFinish(toolWindow: MyToolWindow) {
        PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
        val deadline = System.currentTimeMillis() + 60_000
        while (isScanningOf(toolWindow) && System.currentTimeMillis() < deadline) {
            PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
            Thread.sleep(50)
        }
        assertFalse("Scan did not finish within 60s", isScanningOf(toolWindow))
        PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
    }

    private fun srcDir(): File = File(project.basePath!!, "src")

    private fun writeSource(fileName: String, content: String): VirtualFile {
        val dir = srcDir()
        dir.mkdirs()
        val file = File(dir, fileName)
        file.writeText(content)
        return LocalFileSystem.getInstance().refreshAndFindFileByIoFile(file)!!
    }

    private fun closeAllEditors() {
        val manager = FileEditorManager.getInstance(project)
        manager.openFiles.forEach { manager.closeFile(it) }
    }

    private fun fileNamesOf(findings: List<FindingEntry>) = findings.map { it.view.fileName }.toSet()

    // ==========================================================
    // 1/2. Both buttons exist, side by side, with the right labels.
    // ==========================================================
    fun testBothScanButtonsExist() {
        val toolWindow = MyToolWindow(project)
        assertEquals("Scan Project", scanProjectButtonOf(toolWindow).text)
        assertEquals("Scan File", scanFileButtonOf(toolWindow).text)
        assertTrue(scanProjectButtonOf(toolWindow).isEnabled)
        assertTrue(scanFileButtonOf(toolWindow).isEnabled)
        assertEquals(
            "Both buttons must share one row",
            scanProjectButtonOf(toolWindow).parent, scanFileButtonOf(toolWindow).parent
        )
    }

    // ==========================================================
    // 7. No active file: safe, clear message, never stuck, no backend call.
    // ==========================================================
    fun testNoActiveFileIsHandledSafely() {
        closeAllEditors()
        val toolWindow = MyToolWindow(project)

        scanFile(toolWindow)

        assertEquals("No file is currently open.", emptyTextOf(toolWindow))
        assertTrue(findingsOf(toolWindow).isEmpty())
        assertTrue(scanFileButtonOf(toolWindow).isEnabled)
        assertTrue(scanProjectButtonOf(toolWindow).isEnabled)
    }

    // ==========================================================
    // 8. Unsupported file: rejected with the exact message, never scanned.
    // ==========================================================
    fun testUnsupportedFileIsRejected() {
        val txt = writeSource("notes.txt", "just some notes, not source code")
        myFixture.openFileInEditor(txt)
        val toolWindow = MyToolWindow(project)

        scanFile(toolWindow)

        assertEquals("Only Kotlin (.kt) and Java (.java) files can be scanned.", emptyTextOf(toolWindow))
        assertTrue(findingsOf(toolWindow).isEmpty())
        assertFalse("An unsupported file must never reach the scanning state", isScanningOf(toolWindow))
    }

    // ==========================================================
    // 5. Kotlin current file scans successfully.
    // ==========================================================
    fun testKotlinCurrentFileScansSuccessfully() {
        checkBackendReachable()
        myFixture.openFileInEditor(writeSource("SqlInjectionVulnerable.kt", sqlInjectionKotlin))
        val toolWindow = MyToolWindow(project)

        scanFile(toolWindow)

        assertEquals("Scan complete", statusOf(toolWindow))
        val findings = findingsOf(toolWindow)
        assertTrue("Expected a real CWE-89 finding for the Kotlin file", findings.any { it.view.cwe == "CWE-89" })
        assertTrue(summaryOf(toolWindow).contains("Files scanned: 1"))
        assertTrue("The summary must report how long the scan took", summaryOf(toolWindow).contains("Scan time: "))
    }

    // ==========================================================
    // 6. Java current file scans successfully.
    // ==========================================================
    fun testJavaCurrentFileScansSuccessfully() {
        checkBackendReachable()
        myFixture.openFileInEditor(writeSource("TwoModeLoginActivity.java", sqlInjectionJava))
        val toolWindow = MyToolWindow(project)

        scanFile(toolWindow)

        assertEquals("Scan complete", statusOf(toolWindow))
        assertTrue(findingsOf(toolWindow).any { it.view.cwe == "CWE-89" })
        assertEquals(setOf("src/TwoModeLoginActivity.java"), fileNamesOf(findingsOf(toolWindow)))
    }

    // ==========================================================
    // 9. The requested A/B scenario: Scan File scans ONLY the active
    // file - A, then (after switching tabs) ONLY B.
    // ==========================================================
    fun testScanFileScansOnlyTheActiveFileAcrossTabSwitches() {
        checkBackendReachable()
        val fileA = writeSource("SqlInjectionVulnerable.kt", sqlInjectionKotlin)
        val fileB = writeSource("CertificateVulnerable.kt", certificateKotlin)
        val toolWindow = MyToolWindow(project)

        myFixture.openFileInEditor(fileA)
        PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
        scanFile(toolWindow)
        val findingsA = findingsOf(toolWindow)
        println("[TWO-MODE][A] findings=${findingsA.map { "${it.view.cwe}@${it.view.fileName}" }}")
        assertTrue("File A must produce its CWE-89 finding", findingsA.any { it.view.cwe == "CWE-89" })
        assertEquals("Scan File on A must scan ONLY A", setOf("src/SqlInjectionVulnerable.kt"), fileNamesOf(findingsA))
        assertTrue(summaryOf(toolWindow).contains("Files scanned: 1"))

        myFixture.openFileInEditor(fileB)
        PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
        scanFile(toolWindow)
        val findingsB = findingsOf(toolWindow)
        println("[TWO-MODE][B] findings=${findingsB.map { "${it.view.cwe}@${it.view.fileName}" }}")
        assertTrue("File B must produce its CWE-295 finding", findingsB.any { it.view.cwe == "CWE-295" })
        assertEquals("Scan File on B must scan ONLY B", setOf("src/CertificateVulnerable.kt"), fileNamesOf(findingsB))
        assertTrue(summaryOf(toolWindow).contains("Files scanned: 1"))
    }

    // ==========================================================
    // 10. Scan Project scans every supported file in the project.
    // ==========================================================
    fun testScanProjectScansTheWholeProject() {
        checkBackendReachable()
        writeSource("SqlInjectionVulnerable.kt", sqlInjectionKotlin)
        writeSource("CertificateVulnerable.kt", certificateKotlin)
        writeSource("TwoModeLoginActivity.java", sqlInjectionJava)
        closeAllEditors() // project scan must not depend on any open editor
        val toolWindow = MyToolWindow(project)

        scanProject(toolWindow)

        assertEquals("Project scan complete", statusOf(toolWindow))
        assertTrue("Scan Project must report how long the scan took (UAT-03 feedback)", summaryOf(toolWindow).contains("Scan time: "))
        val files = fileNamesOf(findingsOf(toolWindow))
        println("[TWO-MODE][PROJECT] findings from files=$files summary-files-line=${Regex("Files scanned: \\d+").find(summaryOf(toolWindow))?.value}")
        assertTrue(
            "Scan Project must report findings from every vulnerable file, got $files",
            files.containsAll(setOf("src/SqlInjectionVulnerable.kt", "src/CertificateVulnerable.kt", "src/TwoModeLoginActivity.java"))
        )
        val scanned = Regex("Files scanned: (\\d+)").find(summaryOf(toolWindow))!!.groupValues[1].toInt()
        assertTrue("Scan Project must scan all 3 source files, scanned=$scanned", scanned >= 3)
        assertEquals("Scan Project", scanProjectButtonOf(toolWindow).text)
        assertTrue(scanProjectButtonOf(toolWindow).isEnabled && scanFileButtonOf(toolWindow).isEnabled)
    }

    // ==========================================================
    // 11. Scan File after Scan Project: stale project findings from
    // other files are cleared - only the current file's remain.
    // ==========================================================
    fun testScanFileFindingsAreIsolatedFromAPreviousProjectScan() {
        checkBackendReachable()
        val fileA = writeSource("SqlInjectionVulnerable.kt", sqlInjectionKotlin)
        writeSource("CertificateVulnerable.kt", certificateKotlin)
        val toolWindow = MyToolWindow(project)

        scanProject(toolWindow)
        assertTrue("Precondition: project scan lists more than one file", fileNamesOf(findingsOf(toolWindow)).size > 1)

        myFixture.openFileInEditor(fileA)
        scanFile(toolWindow)
        assertEquals(setOf("src/SqlInjectionVulnerable.kt"), fileNamesOf(findingsOf(toolWindow)))
        assertEquals("Scan complete", statusOf(toolWindow))
    }

    // ==========================================================
    // 12. Scan Project after Scan File: project-wide findings are shown in
    // full, not limited to the previously scanned single file.
    // ==========================================================
    fun testScanProjectFindingsArePreservedAfterAScanFile() {
        checkBackendReachable()
        val fileA = writeSource("SqlInjectionVulnerable.kt", sqlInjectionKotlin)
        writeSource("CertificateVulnerable.kt", certificateKotlin)
        val toolWindow = MyToolWindow(project)

        myFixture.openFileInEditor(fileA)
        scanFile(toolWindow)
        assertEquals(setOf("src/SqlInjectionVulnerable.kt"), fileNamesOf(findingsOf(toolWindow)))

        scanProject(toolWindow)
        val files = fileNamesOf(findingsOf(toolWindow))
        assertTrue(files.containsAll(setOf("src/SqlInjectionVulnerable.kt", "src/CertificateVulnerable.kt")))
        assertEquals("Project scan complete", statusOf(toolWindow))
        // No duplicate rows carried over from the earlier file scan.
        val keys = findingsOf(toolWindow).map { "${it.view.fileName}|${it.view.cwe}|${it.view.line}" }
        assertEquals("No stale/duplicate findings", keys.size, keys.toSet().size)
    }

    // ==========================================================
    // 13/14. Scan File -> real-time annotator on the same file still
    // produces its annotation -> the existing SQL Quick Fix still applies
    // -> Scan File again reads the fixed in-memory Document and the
    // CWE-89 finding is gone.
    // ==========================================================
    fun testQuickFixAndRealTimeDetectionStillWorkAfterScanFile() {
        checkBackendReachable()
        myFixture.openFileInEditor(writeSource("SqlInjectionVulnerable.kt", sqlInjectionKotlin))
        val toolWindow = MyToolWindow(project)

        scanFile(toolWindow)
        assertTrue("Scan File must find CWE-89 first", findingsOf(toolWindow).any { it.view.cwe == "CWE-89" })

        // 14: the existing real-time annotator, untouched, on the same file.
        val psiFile = myFixture.file
        val annotator = CodeSentinelAnnotator()
        val collected = annotator.collectInformation(psiFile, myFixture.editor, false)
        assertNotNull("Real-time annotator must still accept a Kotlin file", collected)
        val realTime = annotator.doAnnotate(collected) ?: emptyList()
        val sqlFinding = realTime.firstOrNull { it.vulnerabilityType == "SQL Injection" }
        assertNotNull("Real-time detection must still flag the SQL injection", sqlFinding)

        // 13: the existing Quick Fix, untouched.
        val fix = SqlFixLocator.tryBuildFix(psiFile, sqlFinding!!, "SqlInjectionVulnerable.kt")
        assertNotNull("The existing parameterized-query Quick Fix must still be offered", fix)
        val call = PsiTreeUtil.findChildrenOfType(psiFile, KtCallExpression::class.java).first { it.text.contains("rawQuery") }
        WriteCommandAction.runWriteCommandAction(project) {
            fix!!.invoke(project, psiFile, myFixture.editor, call, call)
        }
        assertFalse(myFixture.editor.document.text.contains("\"SELECT * FROM users WHERE id=\" + userId"))

        scanFile(toolWindow)
        assertFalse(
            "Re-running Scan File after the Quick Fix must no longer report CWE-89",
            findingsOf(toolWindow).any { it.view.cwe == "CWE-89" }
        )
    }

    fun testScanDurationIsShownInMillisecondsOrSeconds() {
        assertEquals("850 ms", formatScanDuration(850))
        assertEquals("1.0 s", formatScanDuration(1000))
        assertEquals("2.4 s", formatScanDuration(2412))
    }
}
