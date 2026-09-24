package com.dualvulndroid.dualvulndroid

import com.intellij.openapi.command.WriteCommandAction
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.TestDialog
import com.intellij.openapi.ui.TestDialogManager
import com.intellij.openapi.vfs.LocalFileSystem
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.psi.PsiDocumentManager
import com.intellij.testFramework.PlatformTestUtil
import com.intellij.testFramework.fixtures.BasePlatformTestCase
import java.io.File
import javax.swing.DefaultListModel
import javax.swing.JButton
import javax.swing.JLabel

/**
 * Scan-scope task: "Scan Current File" (renamed from "Scan Project") must
 * scan ONLY the file currently open/selected in the editor - via
 * FileEditorManager.getInstance(project).selectedFiles - and NEVER fall
 * back to ProjectFileCollector's whole-project walk, never scan another
 * open file, never scan a file that merely exists on disk.
 *
 * Covers, one test per requirement:
 *   1. Open vulnerable file A, scan -> only file A's finding is shown.
 *   2. Switch to safe file B, scan -> file A's findings are cleared, only
 *      file B (zero findings) is represented.
 *   3. Multiple files with vulnerabilities exist (on disk and/or open in
 *      another editor tab) while file A is active -> file B/C findings
 *      never appear.
 *   4. Edit the current file via an in-memory (Quick-Fix-style, unsaved)
 *      change, rescan -> the old finding disappears.
 *   5. No editor file selected -> no crash, a clear message.
 *   6. A non-Kotlin/Java file is selected -> no scan, a clear message.
 *
 * REQUIRES the real backend running and reachable at APIClient.BACKEND_URL
 * for every test except 5 and 6, which never reach the backend at all
 * (rejected before the availability check).
 */
class ScanCurrentFileScopeTest : BasePlatformTestCase() {

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
                "Real backend not reachable at ${APIClient.BACKEND_URL} - this test requires the " +
                    "real FastAPI backend running. Start it and re-run."
            )
        }
    }

    private val vulnerableSql = """
        public class SqlInjectionVulnerable {
            public void onCreate() {
                String username = getIntent().getStringExtra("username");
                String query = "SELECT * FROM users WHERE name=" + username;
                db.rawQuery(query, null);
            }
        }
    """.trimIndent()

    private val safeSql = """
        public class SqlInjectionVulnerable {
            public void login(String userId) {
                db.rawQuery("SELECT * FROM users WHERE id=?", new String[]{userId});
            }
        }
    """.trimIndent()

    private val vulnerableCert = """
        import javax.net.ssl.HostnameVerifier;
        import javax.net.ssl.SSLSession;
        public class CertificateValidationVulnerable {
            HostnameVerifier hv = new HostnameVerifier() {
                public boolean verify(String hostname, SSLSession session) {
                    return true;
                }
            };
        }
    """.trimIndent()

    // ---- reflection helpers into MyToolWindow's real private production
    // state - the same established pattern used throughout this suite
    // (ToolWindowPresentationTest, LiveRepeatedScanAndResilienceTest, etc). ----
    private fun testButtonOf(toolWindow: MyToolWindow) =
        MyToolWindow::class.java.getDeclaredField("testButton").apply { isAccessible = true }.get(toolWindow) as JButton

    private fun summaryTextOf(toolWindow: MyToolWindow): String =
        (MyToolWindow::class.java.getDeclaredField("summaryLabel").apply { isAccessible = true }.get(toolWindow) as JLabel).text

    private fun emptyTextOf(toolWindow: MyToolWindow): String {
        val findingsList = MyToolWindow::class.java.getDeclaredField("findingsList").apply { isAccessible = true }
            .get(toolWindow) as com.intellij.ui.components.JBList<*>
        return findingsList.emptyText.text
    }

    @Suppress("UNCHECKED_CAST")
    private fun findingsOf(toolWindow: MyToolWindow): List<FindingEntry> {
        val listModel = MyToolWindow::class.java.getDeclaredField("listModel").apply { isAccessible = true }
            .get(toolWindow) as DefaultListModel<FindingEntry>
        return (0 until listModel.size()).map { listModel.getElementAt(it) }
    }

    private fun isScanningOf(toolWindow: MyToolWindow): Boolean =
        MyToolWindow::class.java.getDeclaredField("isScanning").apply { isAccessible = true }.getBoolean(toolWindow)

    private fun startScan(toolWindow: MyToolWindow) {
        MyToolWindow::class.java.getDeclaredMethod("startScanOfFile", Project::class.java, com.intellij.openapi.vfs.VirtualFile::class.java)
            .apply { isAccessible = true }
            .invoke(toolWindow, project, com.intellij.openapi.fileEditor.FileEditorManager.getInstance(project).selectedFiles.firstOrNull())
    }

    private fun waitForScanToFinish(toolWindow: MyToolWindow) {
        // The "no file selected" / "unsupported file" paths never set
        // isScanning true (they return synchronously, before queuing any
        // background task) but still publish their status/empty-text via
        // ApplicationManager.invokeLater - so the queue must be pumped at
        // least once even when the while loop below never runs.
        PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
        val deadline = System.currentTimeMillis() + 30_000
        while (isScanningOf(toolWindow) && System.currentTimeMillis() < deadline) {
            PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
            Thread.sleep(50)
        }
    }

    // Writes fileName under <project>/src, refreshes the VFS, and opens it
    // in the editor - opening LAST makes it FileEditorManager's active
    // selection, which is exactly what MyToolWindow's new startScan() reads.
    private fun createAndOpen(fileName: String, content: String): VirtualFile {
        val basePath = project.basePath!!
        val srcDir = File(basePath, "src")
        srcDir.mkdirs()
        val file = File(srcDir, fileName)
        file.writeText(content)
        val virtualFile = LocalFileSystem.getInstance().refreshAndFindFileByIoFile(file)!!
        myFixture.openFileInEditor(virtualFile)
        return virtualFile
    }

    private fun srcDir(): File = File(project.basePath!!, "src")

    // ==========================================================
    // Test 1: open vulnerable file A, click Scan Current File -> only file
    // A is scanned, and the finding belongs to file A.
    // ==========================================================
    fun testOpenVulnerableFileAAndScanProducesOnlyFileAsFinding() {
        checkBackendReachable()
        try {
            createAndOpen("SqlInjectionVulnerable.java", vulnerableSql)

            val toolWindow = MyToolWindow(project)
            startScan(toolWindow)
            waitForScanToFinish(toolWindow)

            val findings = findingsOf(toolWindow)
            assertEquals("Exactly one finding must come back for the single scanned file", 1, findings.size)
            assertTrue(
                "The finding must belong to the currently open file",
                findings[0].view.fileName.replace('\\', '/').endsWith("SqlInjectionVulnerable.java")
            )
            assertEquals("CWE-89", findings[0].view.cwe)
        } finally {
            srcDir().deleteRecursively()
        }
    }

    // ==========================================================
    // Test 2: open safe file B, click Scan Current File -> file A's
    // findings are cleared, only file B (zero findings) is represented,
    // Total Findings reflects file B only.
    // ==========================================================
    fun testSwitchingToSafeFileBClearsFileAFindingsAndReflectsOnlyFileB() {
        checkBackendReachable()
        try {
            createAndOpen("SqlInjectionVulnerable.java", vulnerableSql)
            val toolWindow = MyToolWindow(project)
            startScan(toolWindow)
            waitForScanToFinish(toolWindow)
            assertEquals("Precondition: file A must produce a finding first", 1, findingsOf(toolWindow).size)

            createAndOpen("SafeLogin.java", safeSql)
            startScan(toolWindow)
            waitForScanToFinish(toolWindow)

            val findings = findingsOf(toolWindow)
            assertTrue(
                "File A's finding must be cleared once a different (now active) file is scanned",
                findings.none { it.view.fileName.replace('\\', '/').endsWith("SqlInjectionVulnerable.java") }
            )
            assertEquals("Only file B's (zero) findings must be represented", 0, findings.size)
            assertTrue(
                "Total findings in the summary must reflect file B only",
                summaryTextOf(toolWindow).contains("Total findings: 0")
            )
        } finally {
            srcDir().deleteRecursively()
        }
    }

    // ==========================================================
    // Test 3: multiple project files contain vulnerabilities (file B is
    // even open in another editor tab; file C exists on disk, unopened)
    // while file A is the active selection -> file B/C's findings must
    // NEVER appear.
    // ==========================================================
    fun testOtherVulnerableFilesNeverAppearWhileFileAIsActive() {
        checkBackendReachable()
        try {
            // File C: on disk only, never opened in any editor tab.
            val srcDirectory = srcDir()
            srcDirectory.mkdirs()
            File(srcDirectory, "UnopenedAlsoVulnerable.java").writeText(vulnerableCert)

            // File B: opened in an editor tab, but NOT the active one once
            // file A is opened afterward.
            createAndOpen("CertificateValidationVulnerable.java", vulnerableCert)
            // File A: opened LAST -> becomes FileEditorManager's active selection.
            createAndOpen("SqlInjectionVulnerable.java", vulnerableSql)

            val toolWindow = MyToolWindow(project)
            startScan(toolWindow)
            waitForScanToFinish(toolWindow)

            val findings = findingsOf(toolWindow)
            assertTrue("Must contain file A's SQL Injection finding", findings.any { it.view.cwe == "CWE-89" })
            assertTrue(
                "File B/C's Certificate Validation findings must NEVER appear - only the active file is scanned",
                findings.none { it.view.cwe == "CWE-295" }
            )
            assertTrue(
                "Every finding must belong to file A",
                findings.all { it.view.fileName.replace('\\', '/').endsWith("SqlInjectionVulnerable.java") }
            )
        } finally {
            srcDir().deleteRecursively()
        }
    }

    // ==========================================================
    // Test 4: edit the current file via an in-memory, unsaved change -
    // exactly what a Quick Fix does (SafeSqlQuickFixKotlin/Java) - then
    // click Scan Current File again -> the fixed code is read and the old
    // finding disappears.
    // ==========================================================
    fun testQuickFixStyleEditThenRescanRemovesThePreviousFinding() {
        checkBackendReachable()
        try {
            createAndOpen("SqlInjectionVulnerable.java", vulnerableSql)

            val toolWindow = MyToolWindow(project)
            startScan(toolWindow)
            waitForScanToFinish(toolWindow)
            assertEquals("Precondition: expected the vulnerable finding before the fix", 1, findingsOf(toolWindow).size)

            // Mutate the in-memory Document only - never saved to disk -
            // exactly what SafeSqlQuickFixKotlin/Java's invoke() does.
            val document = myFixture.editor.document
            WriteCommandAction.runWriteCommandAction(project) {
                document.setText(safeSql)
            }
            PsiDocumentManager.getInstance(project).commitDocument(document)

            startScan(toolWindow)
            waitForScanToFinish(toolWindow)

            assertEquals(
                "The fixed (currently in-editor, unsaved) code must be read, so the old finding disappears",
                0, findingsOf(toolWindow).size
            )
            assertTrue(
                "Total findings must be zero after the fix",
                summaryTextOf(toolWindow).contains("Total findings: 0")
            )
        } finally {
            srcDir().deleteRecursively()
        }
    }

    // ==========================================================
    // Test 5: click Scan Current File with no editor file selected -> no
    // crash, a clear user-friendly message, isScanning never gets stuck.
    // ==========================================================
    fun testNoFileSelectedNeverCrashesAndShowsAClearMessage() {
        FileEditorManager.getInstance(project).openFiles.forEach {
            FileEditorManager.getInstance(project).closeFile(it)
        }
        assertTrue("Precondition: no files should be open", FileEditorManager.getInstance(project).selectedFiles.isEmpty())

        val toolWindow = MyToolWindow(project)
        startScan(toolWindow)
        waitForScanToFinish(toolWindow)

        assertFalse("isScanning must never get stuck true when there is nothing to scan", isScanningOf(toolWindow))
        assertEquals("No file is currently open.", emptyTextOf(toolWindow))
        assertTrue("No findings must be shown", findingsOf(toolWindow).isEmpty())
        assertTrue("The button must remain enabled/clickable", testButtonOf(toolWindow).isEnabled)
    }

    // ==========================================================
    // Test 6: select a non-Kotlin/Java file -> no scan is performed, a
    // clear unsupported-file message is shown instead.
    // ==========================================================
    fun testNonSourceFileSelectedNeverScansAndShowsUnsupportedMessage() {
        val basePath = project.basePath!!
        val txtFile = File(basePath, "notes.txt")
        txtFile.writeText("just some notes, not source code")
        val virtualFile = LocalFileSystem.getInstance().refreshAndFindFileByIoFile(txtFile)!!
        try {
            myFixture.openFileInEditor(virtualFile)

            val toolWindow = MyToolWindow(project)
            startScan(toolWindow)
            waitForScanToFinish(toolWindow)

            assertFalse(isScanningOf(toolWindow))
            assertEquals("Only Kotlin (.kt) and Java (.java) files can be scanned.", emptyTextOf(toolWindow))
            assertTrue("No findings must be shown for an unsupported file type", findingsOf(toolWindow).isEmpty())
        } finally {
            txtFile.delete()
        }
    }

    // ---- Button label: the current-file scan button is "Scan File" ----
    fun testScanFileButtonLabel() {
        val toolWindow = MyToolWindow(project)
        assertEquals("Scan File", testButtonOf(toolWindow).text)
    }
}
