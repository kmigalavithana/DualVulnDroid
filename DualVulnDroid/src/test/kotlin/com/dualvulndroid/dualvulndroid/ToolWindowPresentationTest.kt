package com.dualvulndroid.dualvulndroid

import com.intellij.openapi.command.WriteCommandAction
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.TestDialog
import com.intellij.openapi.ui.TestDialogManager
import com.intellij.openapi.vfs.LocalFileSystem
import com.intellij.testFramework.PlatformTestUtil
import com.intellij.testFramework.fixtures.BasePlatformTestCase
import com.intellij.ui.JBColor
import java.awt.event.MouseEvent
import java.io.File
import javax.swing.DefaultListModel
import javax.swing.JButton
import javax.swing.JLabel

/**
 * UI-presentation task (dashboard redesign), item 14: presentation-only
 * tests for the redesigned ToolWindow - header/status, compact summary
 * cards, grouped/compact findings rows, empty state, button
 * enable/disable, and theme-aware (JBColor) styling. Detection,
 * classification, deduplication, and navigation logic are exercised
 * elsewhere (FindingClassificationTest, ToolWindowFindingsPresentationTest,
 * FinalUIStateVerificationTest) and are unchanged by this redesign -
 * these tests are purely about what MyToolWindow now shows and how.
 *
 * Scan-scope task: "Scan Project" was renamed "Scan Current File" and now
 * scans ONLY the file currently open/selected in the editor - every
 * fixture below opens its file in the editor first (myFixture.openFileInEditor)
 * so it becomes the active selection startScan() reads. See
 * ScanCurrentFileScopeTest for the dedicated single-file-scope test suite
 * (multiple files present, only the active one scanned; Quick-Fix rescan;
 * no-selection/unsupported-file messages).
 *
 * REQUIRES the real backend running and reachable at APIClient.BACKEND_URL.
 */
class ToolWindowPresentationTest : BasePlatformTestCase() {

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
        public class LoginActivity {
            public void onCreate() {
                String username = getIntent().getStringExtra("username");
                String query = "SELECT * FROM users WHERE name=" + username;
                db.rawQuery(query, null);
            }
        }
    """.trimIndent()

    private val vulnerableCert = """
        import javax.net.ssl.HostnameVerifier;
        import javax.net.ssl.SSLSession;
        public class NetworkConfig {
            HostnameVerifier hv = new HostnameVerifier() {
                public boolean verify(String hostname, SSLSession session) {
                    return true;
                }
            };
        }
    """.trimIndent()

    private val safeSql = """
        public class LoginActivity {
            public void login(String userId) {
                db.rawQuery("SELECT * FROM users WHERE id=?", new String[]{userId});
            }
        }
    """.trimIndent()

    // A single file containing BOTH an unsafe concatenated SQL query AND an
    // unsafe HostnameVerifier - exercises the mixed-CWE grouping/summary
    // behavior within the scope of ONE currently-open file (a real project
    // file can legitimately contain both families at once; scanning two
    // SEPARATE files at once is no longer possible now that "Scan Current
    // File" only ever scans the single active editor file - see
    // ToolWindowFindingsPresentationTest's mixedSqlAndCertInOneFile for the
    // same established pattern).
    private val mixedSqlAndCert = """
        import java.awt.*;

        public Cursor findUser(SQLiteDatabase db, String username) {

            // UNSAFE: user input is directly concatenated
            String query =
                    "SELECT * FROM users WHERE username = '" + username + "'";

            return db.rawQuery(query, null);
        }

        public HostnameVerifier getVerifier() {
            return new HostnameVerifier() {
                @Override
                public boolean verify(String hostname, SSLSession session) {
                    return true;
                }
            };
        }
    """.trimIndent()

    // ---- reflection into the redesigned private fields (no test-only fields added to production code) ----
    private fun testButtonOf(toolWindow: MyToolWindow) =
        MyToolWindow::class.java.getDeclaredField("testButton").apply { isAccessible = true }.get(toolWindow) as JButton

    private fun findingsListOf(toolWindow: MyToolWindow) =
        MyToolWindow::class.java.getDeclaredField("findingsList").apply { isAccessible = true }
            .get(toolWindow) as com.intellij.ui.components.JBList<*>

    private fun statusDotOf(toolWindow: MyToolWindow) =
        MyToolWindow::class.java.getDeclaredField("statusDot").apply { isAccessible = true }.get(toolWindow) as JLabel

    private fun summaryTextOf(toolWindow: MyToolWindow) =
        (MyToolWindow::class.java.getDeclaredField("summaryLabel").apply { isAccessible = true }.get(toolWindow) as JLabel).text

    @Suppress("UNCHECKED_CAST")
    private fun findingsOf(toolWindow: MyToolWindow): List<FindingEntry> {
        val listModel = MyToolWindow::class.java.getDeclaredField("listModel").apply { isAccessible = true }
            .get(toolWindow) as DefaultListModel<FindingEntry>
        return (0 until listModel.size()).map { listModel.getElementAt(it) }
    }

    private fun isScanningOf(toolWindow: MyToolWindow): Boolean =
        MyToolWindow::class.java.getDeclaredField("isScanning").apply { isAccessible = true }.getBoolean(toolWindow)

    private fun startScan(toolWindow: MyToolWindow, project: Project) {
        MyToolWindow::class.java.getDeclaredMethod("startScanOfFile", Project::class.java, com.intellij.openapi.vfs.VirtualFile::class.java)
            .apply { isAccessible = true }
            .invoke(toolWindow, project, com.intellij.openapi.fileEditor.FileEditorManager.getInstance(project).selectedFiles.firstOrNull())
    }

    private fun waitForScanToFinish(toolWindow: MyToolWindow) {
        val deadline = System.currentTimeMillis() + 30_000
        while (isScanningOf(toolWindow) && System.currentTimeMillis() < deadline) {
            PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
            Thread.sleep(50)
        }
    }

    // Creates ONE file on disk under src/ and opens it in the editor, so it
    // becomes FileEditorManager's active selection - exactly what
    // "Scan Current File" reads (never ProjectFileCollector's project-wide
    // walk).
    private fun withScannedFile(fileName: String, content: String, block: (MyToolWindow) -> Unit) {
        checkBackendReachable()
        val basePath = project.basePath!!
        val srcDir = File(basePath, "src")
        srcDir.mkdirs()
        val file = File(srcDir, fileName)
        file.writeText(content)
        val virtualFile = LocalFileSystem.getInstance().refreshAndFindFileByIoFile(file)!!
        try {
            myFixture.openFileInEditor(virtualFile)
            val toolWindow = MyToolWindow(project)
            startScan(toolWindow, project)
            waitForScanToFinish(toolWindow)
            block(toolWindow)
        } finally {
            srcDir.deleteRecursively()
        }
    }

    // ---- 1. Zero findings -> proper empty state (never "Nothing to show") ----
    fun testZeroFindingsShowsCleanEmptyStateNotNothingToShow() {
        withScannedFile("SafeLogin.java", safeSql) { toolWindow ->
            val findingsList = findingsListOf(toolWindow)
            val emptyText = findingsList.emptyText.text
            println("[PRESENTATION] empty state text = $emptyText")
            assertEquals("No security findings detected", emptyText)
            assertTrue("The findings list itself must be empty", findingsOf(toolWindow).isEmpty())
        }
    }

    // ---- 2. One CWE-89 finding -> correct summary and finding row ----
    fun testOneCwe89FindingShowsCorrectSummaryAndRow() {
        withScannedFile("LoginActivity.java", vulnerableSql) { toolWindow ->
            val findings = findingsOf(toolWindow)
            assertEquals(1, findings.size)
            assertEquals("CWE-89", findings[0].view.cwe)
            assertEquals("SQL Injection", findings[0].view.vulnerabilityType)

            val summary = summaryTextOf(toolWindow)
            assertTrue(summary.contains("SQL Injection (CWE-89): 1"))
            assertTrue(summary.contains("Certificate Validation (CWE-295): 0"))
            assertTrue(summary.contains("Total findings: 1"))
        }
    }

    // ---- 3. One CWE-295 finding -> correct summary and finding row ----
    fun testOneCwe295FindingShowsCorrectSummaryAndRow() {
        withScannedFile("NetworkConfig.java", vulnerableCert) { toolWindow ->
            val findings = findingsOf(toolWindow)
            assertEquals(1, findings.size)
            assertEquals("CWE-295", findings[0].view.cwe)
            assertEquals("Certificate Validation", findings[0].view.vulnerabilityType)

            val summary = summaryTextOf(toolWindow)
            assertTrue(summary.contains("SQL Injection (CWE-89): 0"))
            assertTrue(summary.contains("Certificate Validation (CWE-295): 1"))
            assertTrue(summary.contains("Total findings: 1"))
        }
    }

    // ---- 4/5. Mixed CWE-89 + CWE-295 (both within the ONE currently-open
    // file) -> correct grouped display, total == sum ----
    fun testMixedFindingsGroupCorrectlyAndTotalsAreConsistent() {
        // A filename unique to this test - "ss.java" is reused as a real
        // disk path by several other test classes in this suite; now that
        // MyToolWindow's scan reads the live Document rather than disk,
        // reusing that exact path risks picking up a stale Document from
        // an earlier test's use of the same path.
        withScannedFile("PresentationMixedGrouping.java", mixedSqlAndCert) { toolWindow ->
            val findings = findingsOf(toolWindow)
            val sql = findings.filter { it.view.cwe == "CWE-89" }
            val cert = findings.filter { it.view.cwe == "CWE-295" }
            assertTrue(sql.isNotEmpty())
            assertTrue(cert.isNotEmpty())

            val summary = summaryTextOf(toolWindow)
            val total = Regex("""Total findings: (\d+)""").find(summary)!!.groupValues[1].toInt()
            val sqlN = Regex("""SQL Injection \(CWE-89\): (\d+)""").find(summary)!!.groupValues[1].toInt()
            val certN = Regex("""Certificate Validation \(CWE-295\): (\d+)""").find(summary)!!.groupValues[1].toInt()
            assertEquals("Total must equal SQL + Cert counts - never desynchronized", sqlN + certN, total)
            assertEquals(sql.size, sqlN)
            assertEquals(cert.size, certN)

            // The renderer must draw a distinct group header for each CWE
            // present (item 5: never mix CWE-89 and CWE-295 in one
            // undifferentiated block) - verified against the REAL
            // renderer, not a re-implementation.
            val sorted = findings.sortedWith(compareBy({ it.view.cwe }, { it.view.fileName }, { it.view.line ?: -1 }))
            val renderer = FindingListCellRenderer()
            val model = DefaultListModel<FindingEntry>().apply { sorted.forEach(::addElement) }
            val list = javax.swing.JList(model)
            var headerCount = 0
            for (i in sorted.indices) {
                val component = renderer.getListCellRendererComponent(list, sorted[i], i, false, false) as javax.swing.JPanel
                // A group header adds a JSeparator as the panel's second-to-last... simplest signal: more than one child means a header+row were both added.
                if (component.componentCount > 2) headerCount++
            }
            assertEquals("Exactly one group header must be drawn per distinct CWE present", sorted.map { it.view.cwe }.distinct().size, headerCount)
        }
    }

    // ---- 6. Finding click (the NEW single-click-to-navigate row behavior) still navigates correctly ----
    fun testClickingAFindingRowNavigatesToTheCorrectFile() {
        withScannedFile("LoginActivity.java", vulnerableSql) { toolWindow ->
            val findingsList = findingsListOf(toolWindow)
            assertEquals(1, findingsList.model.size)

            val point = findingsList.indexToLocation(0)
            val clickEvent = MouseEvent(findingsList, MouseEvent.MOUSE_CLICKED, System.currentTimeMillis(), 0, point.x, point.y, 1, false)
            findingsList.mouseListeners.forEach { it.mouseClicked(clickEvent) }
            PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()

            assertTrue(
                "Clicking the row must open LoginActivity.java via the existing, unchanged navigateToFinding()",
                FileEditorManager.getInstance(project).openFiles.any { it.name == "LoginActivity.java" }
            )
        }
    }

    // ---- 7. Scan button disabled during scan, re-enabled (and re-labeled "Scan File") afterward ----
    fun testScanButtonDisabledDuringScanAndReEnabledAfter() {
        checkBackendReachable()
        val basePath = project.basePath!!
        val srcDir = File(basePath, "src")
        srcDir.mkdirs()
        val file = File(srcDir, "LoginActivity.java")
        file.writeText(vulnerableSql)
        val virtualFile = LocalFileSystem.getInstance().refreshAndFindFileByIoFile(file)!!

        try {
            myFixture.openFileInEditor(virtualFile)
            val toolWindow = MyToolWindow(project)
            val button = testButtonOf(toolWindow)
            assertEquals("Scan File", button.text)
            assertTrue(button.isEnabled)

            startScan(toolWindow, project)
            // startScan() sets isScanning/button state SYNCHRONOUSLY before
            // queuing the background task - observable immediately.
            assertFalse("Button must be disabled the instant a scan starts", button.isEnabled)
            assertEquals("Scanning...", button.text)

            waitForScanToFinish(toolWindow)
            assertTrue("Button must be re-enabled once the scan completes", button.isEnabled)
            assertEquals("Scan File", button.text)
        } finally {
            srcDir.deleteRecursively()
        }
    }

    // ---- 8. Repeated Scan Current File still works (button re-clickable, fresh results both times) ----
    fun testRepeatedScanCurrentFileStillWorksAfterRedesign() {
        checkBackendReachable()
        val basePath = project.basePath!!
        val srcDir = File(basePath, "src")
        srcDir.mkdirs()
        val file = File(srcDir, "LoginActivity.java")
        file.writeText(vulnerableSql)
        val virtualFile = LocalFileSystem.getInstance().refreshAndFindFileByIoFile(file)!!

        try {
            myFixture.openFileInEditor(virtualFile)
            val toolWindow = MyToolWindow(project)
            startScan(toolWindow, project)
            waitForScanToFinish(toolWindow)
            val first = findingsOf(toolWindow).size

            startScan(toolWindow, project)
            waitForScanToFinish(toolWindow)
            val second = findingsOf(toolWindow).size

            assertEquals(first, second)
            assertTrue(testButtonOf(toolWindow).isEnabled)
        } finally {
            srcDir.deleteRecursively()
        }
    }

    // ---- 10. "Scan Current File" always performs a FRESH re-scan: clicking
    // it again must clear the previous findings/counts and reflect the
    // CURRENT editor content, not accumulate or reuse stale results. The
    // edit is made via the in-memory Document (exactly the Quick Fix
    // workflow - MyToolWindow reads the live Document, never disk). ----
    fun testScanCurrentFileClearsPreviousFindingsOnRepeatedClicks() {
        checkBackendReachable()
        val basePath = project.basePath!!
        val srcDir = File(basePath, "src")
        srcDir.mkdirs()
        val file = File(srcDir, "LoginActivity.java")
        file.writeText(vulnerableSql)
        val virtualFile = LocalFileSystem.getInstance().refreshAndFindFileByIoFile(file)!!

        try {
            myFixture.openFileInEditor(virtualFile)
            val toolWindow = MyToolWindow(project)
            startScan(toolWindow, project)
            waitForScanToFinish(toolWindow)
            assertEquals(1, findingsOf(toolWindow).size)
            assertTrue(summaryTextOf(toolWindow).contains("SQL Injection (CWE-89): 1"))

            // Edit the SAME file's live Document to safe content (never
            // saved to disk) - a fresh click must see the NEW in-editor
            // state, never the previous scan's leftover findings/counts.
            val document = myFixture.editor.document
            WriteCommandAction.runWriteCommandAction(project) {
                document.setText(safeSql)
            }
            com.intellij.psi.PsiDocumentManager.getInstance(project).commitDocument(document)

            startScan(toolWindow, project)
            waitForScanToFinish(toolWindow)

            assertEquals(
                "A second click must show the CURRENT (now safe) result, not the previous scan's finding",
                0, findingsOf(toolWindow).size
            )
            assertTrue(
                "The summary must reflect the fresh scan, not stale counts from the first click",
                summaryTextOf(toolWindow).contains("SQL Injection (CWE-89): 0")
            )
        } finally {
            srcDir.deleteRecursively()
        }
    }

    // ---- 11. The exact Quick-Fix-then-rescan flow (requirement 4): a fix
    // applied via an in-memory PSI/Document edit - NOT yet saved to disk,
    // exactly what SafeSqlQuickFixKotlin.invoke() does - must still be
    // picked up by the very next "Scan Current File" click. MyToolWindow now
    // reads the file's live Document directly (never disk), so this is the
    // primary, expected path rather than a special case. ----
    fun testRescanAfterUnsavedInMemoryEditPicksUpTheFix() {
        checkBackendReachable()
        val basePath = project.basePath!!
        val srcDir = File(basePath, "src")
        srcDir.mkdirs()
        // A filename unique to this test (not "LoginActivity.java", reused
        // by several other tests in this class) so this test can never
        // collide with a leftover Document/VFS entry from a previously-run
        // test's own temp fixture.
        val file = File(srcDir, "RescanQuickFixCandidate.java")
        file.writeText(vulnerableSql)
        val virtualFile = com.intellij.openapi.vfs.LocalFileSystem.getInstance().refreshAndFindFileByIoFile(file)!!

        try {
            myFixture.openFileInEditor(virtualFile)
            val toolWindow = MyToolWindow(project)
            startScan(toolWindow, project)
            waitForScanToFinish(toolWindow)
            assertEquals("Expected the vulnerable finding before any fix", 1, findingsOf(toolWindow).size)

            // Simulate a Quick Fix: mutate the in-memory Document only -
            // exactly what SafeSqlQuickFixKotlin.invoke()'s PSI replace()
            // calls do - WITHOUT saving to disk.
            val document = myFixture.editor.document
            WriteCommandAction.runWriteCommandAction(project) {
                document.setText(safeSql)
            }
            com.intellij.psi.PsiDocumentManager.getInstance(project).commitDocument(document)
            assertFalse(
                "Sanity check: the in-memory edit must genuinely differ from what's still on disk " +
                    "(otherwise this test wouldn't be exercising the bug at all)",
                document.text == file.readText()
            )

            startScan(toolWindow, project)
            waitForScanToFinish(toolWindow)

            assertEquals(
                "Scan Current File must read the CURRENT Document content directly, so an applied-but-" +
                    "unsaved Quick Fix is reflected on the very next click - not just after a manual save",
                0, findingsOf(toolWindow).size
            )
        } finally {
            srcDir.deleteRecursively()
        }
    }

    // ---- 9. Colors used for status/rows are JBColor (theme-aware), never a raw hardcoded Color ----
    fun testStatusAndFindingColorsAreThemeAwareJBColor() {
        withScannedFile("PresentationMixedColors.java", mixedSqlAndCert) { toolWindow ->
            val dot = statusDotOf(toolWindow)
            assertTrue("The status dot's color must be a theme-aware JBColor, not a hardcoded Color", dot.foreground is JBColor)

            val findings = findingsOf(toolWindow).sortedWith(compareBy({ it.view.cwe }, { it.view.line ?: -1 }))
            assertTrue("Expected findings from the mixed SQL+Cert file to render", findings.isNotEmpty())
            // The status colors (CONFIRMED=red-ish, NEEDS REVIEW=orange-ish)
            // are declared as JBColor at compile time (see
            // FindingListCellRenderer) - everything else in a row's
            // foreground is delegated to UIUtil's theme-driven list
            // colors, which this test doesn't need to re-verify.
            val renderer = FindingListCellRenderer()
            val model = DefaultListModel<FindingEntry>().apply { findings.forEach(::addElement) }
            val list = javax.swing.JList(model)
            val component = renderer.getListCellRendererComponent(list, findings[0], 0, false, false)
            fun walk(c: java.awt.Component): List<java.awt.Component> =
                listOf(c) + (if (c is java.awt.Container) c.components.flatMap { walk(it) } else emptyList())
            val statusLabel = walk(component).filterIsInstance<JLabel>()
                .firstOrNull { it.text == "CONFIRMED" || it.text == "NEEDS REVIEW" }
            assertNotNull("The rendered row must contain a CONFIRMED/NEEDS REVIEW status label", statusLabel)
            assertTrue(
                "The status label's own color must be one of the plugin's JBColor constants",
                statusLabel!!.foreground === renderer.statusConfirmedColor || statusLabel.foreground === renderer.statusReviewColor
            )
        }
    }
}
