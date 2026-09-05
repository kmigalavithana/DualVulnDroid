package com.dualvulndroid.dualvulndroid

import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.TestDialog
import com.intellij.openapi.ui.TestDialogManager
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
        MyToolWindow::class.java.getDeclaredMethod("startScan", Project::class.java)
            .apply { isAccessible = true }
            .invoke(toolWindow, project)
    }

    private fun waitForScanToFinish(toolWindow: MyToolWindow) {
        val deadline = System.currentTimeMillis() + 30_000
        while (isScanningOf(toolWindow) && System.currentTimeMillis() < deadline) {
            PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
            Thread.sleep(50)
        }
    }

    private fun withScannedProject(vararg files: Pair<String, String>, block: (MyToolWindow) -> Unit) {
        checkBackendReachable()
        val basePath = project.basePath!!
        val srcDir = File(basePath, "src")
        srcDir.mkdirs()
        files.forEach { (name, content) -> File(srcDir, name).writeText(content) }
        com.intellij.openapi.vfs.LocalFileSystem.getInstance().refreshAndFindFileByIoFile(srcDir)
        try {
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
        withScannedProject("SafeLogin.java" to safeSql) { toolWindow ->
            val findingsList = findingsListOf(toolWindow)
            val emptyText = findingsList.emptyText.text
            println("[PRESENTATION] empty state text = $emptyText")
            assertEquals("No security findings detected", emptyText)
            assertTrue("The findings list itself must be empty", findingsOf(toolWindow).isEmpty())
        }
    }

    // ---- 2. One CWE-89 finding -> correct summary and finding row ----
    fun testOneCwe89FindingShowsCorrectSummaryAndRow() {
        withScannedProject("LoginActivity.java" to vulnerableSql) { toolWindow ->
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
        withScannedProject("NetworkConfig.java" to vulnerableCert) { toolWindow ->
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

    // ---- 4/5. Mixed CWE-89 + CWE-295 -> correct grouped display, total == sum ----
    fun testMixedFindingsGroupCorrectlyAndTotalsAreConsistent() {
        withScannedProject("LoginActivity.java" to vulnerableSql, "NetworkConfig.java" to vulnerableCert) { toolWindow ->
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
        withScannedProject("LoginActivity.java" to vulnerableSql) { toolWindow ->
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

    // ---- 7. Scan button disabled during scan, re-enabled (and re-labeled) afterward ----
    fun testScanButtonDisabledDuringScanAndReEnabledAfter() {
        checkBackendReachable()
        val basePath = project.basePath!!
        val srcDir = File(basePath, "src")
        srcDir.mkdirs()
        File(srcDir, "LoginActivity.java").writeText(vulnerableSql)
        com.intellij.openapi.vfs.LocalFileSystem.getInstance().refreshAndFindFileByIoFile(srcDir)

        try {
            val toolWindow = MyToolWindow(project)
            val button = testButtonOf(toolWindow)
            assertEquals("Scan Project", button.text)
            assertTrue(button.isEnabled)

            startScan(toolWindow, project)
            // startScan() sets isScanning/button state SYNCHRONOUSLY before
            // queuing the background task - observable immediately.
            assertFalse("Button must be disabled the instant a scan starts", button.isEnabled)
            assertEquals("Scanning...", button.text)

            waitForScanToFinish(toolWindow)
            assertTrue("Button must be re-enabled once the scan completes", button.isEnabled)
            assertEquals("Scan Project", button.text)
        } finally {
            srcDir.deleteRecursively()
        }
    }

    // ---- 8. Repeated Scan Project still works (button re-clickable, fresh results both times) ----
    fun testRepeatedScanProjectStillWorksAfterRedesign() {
        checkBackendReachable()
        val basePath = project.basePath!!
        val srcDir = File(basePath, "src")
        srcDir.mkdirs()
        File(srcDir, "LoginActivity.java").writeText(vulnerableSql)
        com.intellij.openapi.vfs.LocalFileSystem.getInstance().refreshAndFindFileByIoFile(srcDir)

        try {
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

    // ---- 9. Colors used for status/rows are JBColor (theme-aware), never a raw hardcoded Color ----
    fun testStatusAndFindingColorsAreThemeAwareJBColor() {
        withScannedProject("LoginActivity.java" to vulnerableSql, "NetworkConfig.java" to vulnerableCert) { toolWindow ->
            val dot = statusDotOf(toolWindow)
            assertTrue("The status dot's color must be a theme-aware JBColor, not a hardcoded Color", dot.foreground is JBColor)

            val findings = findingsOf(toolWindow).sortedWith(compareBy({ it.view.cwe }, { it.view.line ?: -1 }))
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
