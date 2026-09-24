package com.dualvulndroid.dualvulndroid

import com.intellij.openapi.command.WriteCommandAction
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.TestDialog
import com.intellij.openapi.ui.TestDialogManager
import com.intellij.openapi.util.Disposer
import com.intellij.openapi.vfs.LocalFileSystem
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.psi.util.PsiTreeUtil
import com.intellij.testFramework.PlatformTestUtil
import com.intellij.testFramework.fixtures.BasePlatformTestCase
import org.jetbrains.kotlin.psi.KtCallExpression
import java.io.File
import javax.swing.Action
import javax.swing.DefaultListModel
import javax.swing.JLabel

/**
 * "Scan File" UX: the dialog shows the current open file and offers
 * [Scan Current File] (scans exactly the active editor VirtualFile),
 * [Choose Another File] (native chooser -> the chosen file is opened as the
 * active editor tab and ONLY that VirtualFile is scanned) and [Cancel].
 * Unsupported file -> no Scan Current File; no file -> [Choose File] [Cancel]. The Tool Window itself has no permanent
 * CURRENT FILE section - file information lives only in the dialog.
 * Nothing is scanned without an explicit click. These tests click the real button
 * handler (onScanFileClicked) and answer the dialog and native chooser
 * through MyToolWindow's scanFilePrompt / sourceFileChooser hooks (a real
 * modal can't be clicked in a headless test); a separate test builds the
 * REAL ScanFileDialog and checks its buttons. Scanning tests need the real
 * backend (never faked).
 */
class ScanFileTargetPromptTest : BasePlatformTestCase() {

    private var previousTestDialog: TestDialog? = null

    override fun setUp() {
        super.setUp()
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

    private val sqlKotlin = """
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

    private val certKotlin = """
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

    private val sqlJava = """
        public class PromptLoginActivity {
            public void onCreate() {
                String username = getIntent().getStringExtra("username");
                String query = "SELECT * FROM users WHERE name=" + username;
                db.rawQuery(query, null);
            }
        }
    """.trimIndent()

    private val mainKotlin = "package com.example.securitytest\n\nfun main() {\n    println(\"hello\")\n}\n"

    // ---- helpers ----

    private fun checkBackendReachable() {
        if (APIClient().scanCode("int x = 1;", "ReachabilityProbe.java") == null) {
            fail("Real backend not reachable at ${APIClient.BACKEND_URL} - start the real FastAPI backend and re-run.")
        }
    }

    private fun <T> field(toolWindow: MyToolWindow, name: String): T {
        @Suppress("UNCHECKED_CAST")
        return MyToolWindow::class.java.getDeclaredField(name).apply { isAccessible = true }.get(toolWindow) as T
    }

    private fun statusOf(tw: MyToolWindow) = field<JLabel>(tw, "statusLabel").text
    private fun summaryOf(tw: MyToolWindow) = field<JLabel>(tw, "summaryLabel").text

    private fun findingsOf(tw: MyToolWindow): List<FindingEntry> {
        val model: DefaultListModel<FindingEntry> = field(tw, "listModel")
        return (0 until model.size()).map { model.getElementAt(it) }
    }

    private fun fileNamesOf(tw: MyToolWindow) = findingsOf(tw).map { it.view.fileName }.toSet()

    private fun isScanningOf(tw: MyToolWindow) =
        MyToolWindow::class.java.getDeclaredField("isScanning").apply { isAccessible = true }.getBoolean(tw)

    private fun callPrivate(tw: MyToolWindow, method: String) {
        MyToolWindow::class.java.getDeclaredMethod(method, Project::class.java).apply { isAccessible = true }.invoke(tw, project)
    }

    private fun waitForScan(tw: MyToolWindow) {
        PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
        val deadline = System.currentTimeMillis() + 60_000
        while (isScanningOf(tw) && System.currentTimeMillis() < deadline) {
            PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
            Thread.sleep(50)
        }
        assertFalse("Scan did not finish within 60s", isScanningOf(tw))
        PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
    }

    /** Records what the dialog was shown, answers with [choice], and the chooser with [chosen]. */
    private class Answers(val choice: ScanFileChoice, val chosen: VirtualFile? = null) {
        var promptedWith: ScanFilePromptInfo? = null
        var chooserCalls = 0
    }

    private fun toolWindowAnswering(answers: Answers): MyToolWindow =
        MyToolWindow(project).apply {
            scanFilePrompt = { info -> answers.promptedWith = info; answers.choice }
            sourceFileChooser = { answers.chooserCalls++; answers.chosen }
        }

    /** Click "Scan File" and let any resulting scan finish. */
    private fun clickScanFile(tw: MyToolWindow) {
        callPrivate(tw, "onScanFileClicked")
        waitForScan(tw)
    }

    private fun srcDir() = File(project.basePath!!, "src")

    private fun writeSource(name: String, content: String): VirtualFile {
        srcDir().mkdirs()
        val file = File(srcDir(), name).apply { writeText(content) }
        return LocalFileSystem.getInstance().refreshAndFindFileByIoFile(file)!!
    }

    private fun closeAllEditors() {
        val manager = FileEditorManager.getInstance(project)
        manager.openFiles.forEach { manager.closeFile(it) }
    }

    private fun activeFile(): VirtualFile? = FileEditorManager.getInstance(project).selectedFiles.firstOrNull()

    // ==========================================================
    // Clicking "Scan File" opens the dialog with the current open file -
    // nothing is scanned by opening it (Cancel here).
    // ==========================================================
    fun testClickingScanFileOpensTheDialogWithTheCurrentFileAsInformationOnly() {
        val fileA = writeSource("SqlInjectionVulnerable.kt", sqlKotlin)
        myFixture.openFileInEditor(fileA)
        val answers = Answers(ScanFileChoice.CANCEL)
        val tw = toolWindowAnswering(answers)

        clickScanFile(tw)

        assertEquals(
            ScanFilePromptInfo("SqlInjectionVulnerable.kt", "src/SqlInjectionVulnerable.kt", CurrentFileStatus.SUPPORTED),
            answers.promptedWith
        )
        assertFalse(isScanningOf(tw))
        assertTrue("The current open file must never be scanned automatically", findingsOf(tw).isEmpty())
    }

    // ==========================================================
    // 7 + 8. The REAL ScanFileDialog's buttons per current-file state:
    // supported -> Scan Current File / Choose Another File / Cancel;
    // unsupported -> no Scan Current File; no file -> Choose File / Cancel.
    // ==========================================================
    fun testRealDialogButtonsForEachCurrentFileState() {
        fun actionsOf(info: ScanFilePromptInfo): List<String> {
            val dialog = ScanFileDialog(project, info)
            try {
                val method = ScanFileDialog::class.java.getDeclaredMethod("createActions").apply { isAccessible = true }
                @Suppress("UNCHECKED_CAST")
                val actions = method.invoke(dialog) as Array<Action>
                assertTrue(actions.all { it.isEnabled })
                return actions.map { (it.getValue(Action.NAME) as String).replace("_", "") }
            } finally {
                Disposer.dispose(dialog.disposable)
            }
        }

        assertEquals(
            listOf("Scan Current File", "Choose Another File", "Cancel"),
            actionsOf(ScanFilePromptInfo("SqlInjectionVulnerable.kt", "src/SqlInjectionVulnerable.kt", CurrentFileStatus.SUPPORTED))
        )
        assertEquals(
            listOf("Choose Another File", "Cancel"),
            actionsOf(ScanFilePromptInfo("example.xml", "src/example.xml", CurrentFileStatus.UNSUPPORTED))
        )
        assertEquals(listOf("Choose File", "Cancel"), actionsOf(ScanFilePromptInfo(null, null, CurrentFileStatus.NONE)))
    }

    // ==========================================================
    // 1 + 10. Scan Current File on an active .kt: scans exactly that
    // VirtualFile, never opens the chooser, never scans the project; the
    // active editor is unchanged and navigation lands on the finding line.
    // ==========================================================
    fun testScanCurrentFileScansTheActiveKotlinFileOnly() {
        checkBackendReachable()
        val sql = writeSource("SqlInjectionVulnerable.kt", sqlKotlin)
        writeSource("CertificateVulnerable.kt", certKotlin)
        myFixture.openFileInEditor(sql)
        val answers = Answers(ScanFileChoice.SCAN_CURRENT_FILE)
        val tw = toolWindowAnswering(answers)

        clickScanFile(tw)

        assertEquals(CurrentFileStatus.SUPPORTED, answers.promptedWith!!.status)
        assertEquals("Scan Current File must never open the file chooser", 0, answers.chooserCalls)
        assertEquals(sql, activeFile())
        assertEquals("Only the current file may be scanned", setOf("src/SqlInjectionVulnerable.kt"), fileNamesOf(tw))
        assertTrue(findingsOf(tw).any { it.view.cwe == "CWE-89" })
        assertTrue(summaryOf(tw).contains("Files scanned: 1"))
        assertEquals("Scan complete", statusOf(tw))

        val finding = findingsOf(tw).first { it.view.cwe == "CWE-89" }
        Class.forName("com.dualvulndroid.dualvulndroid.MyToolWindowKt")
            .getDeclaredMethod("navigateToFinding", Project::class.java, FindingEntry::class.java)
            .apply { isAccessible = true }
            .invoke(null, project, finding)
        PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
        assertEquals(sql, activeFile())
        assertEquals(finding.view.line, FileEditorManager.getInstance(project).selectedTextEditor!!.caretModel.logicalPosition.line)
    }

    // ==========================================================
    // 2. Scan Current File on an active .java file.
    // ==========================================================
    fun testScanCurrentFileScansTheActiveJavaFileOnly() {
        checkBackendReachable()
        writeSource("SqlInjectionVulnerable.kt", sqlKotlin)
        val javaFile = writeSource("PromptLoginActivity.java", sqlJava)
        myFixture.openFileInEditor(javaFile)
        val answers = Answers(ScanFileChoice.SCAN_CURRENT_FILE)
        val tw = toolWindowAnswering(answers)

        clickScanFile(tw)

        assertEquals(0, answers.chooserCalls)
        assertEquals(javaFile, activeFile())
        assertEquals(setOf("src/PromptLoginActivity.java"), fileNamesOf(tw))
        assertTrue(findingsOf(tw).any { it.view.cwe == "CWE-89" })
        assertTrue(summaryOf(tw).contains("Files scanned: 1"))
    }

    // ==========================================================
    // 7. Unsupported current file: Scan Current File is not offered, and
    // even a forced SCAN_CURRENT_FILE answer never scans it.
    // ==========================================================
    fun testUnsupportedCurrentFileCannotBeScannedAsCurrentFile() {
        val xml = writeSource("example.xml", "<resources/>")
        myFixture.openFileInEditor(xml)
        val answers = Answers(ScanFileChoice.SCAN_CURRENT_FILE)
        val tw = toolWindowAnswering(answers)

        clickScanFile(tw)

        val info = answers.promptedWith!!
        assertEquals(ScanFilePromptInfo("example.xml", "src/example.xml", CurrentFileStatus.UNSUPPORTED), info)
        assertFalse(info.canScanCurrentFile)
        assertEquals("Choose Another File", info.chooseButtonLabel)
        assertEquals(0, answers.chooserCalls)
        assertFalse(isScanningOf(tw))
        assertTrue(findingsOf(tw).isEmpty())
        assertEquals("Ready", statusOf(tw))
    }

    // ==========================================================
    // 3, 4, 5. Main.kt open -> Choose Another File -> CertificateVulnerable.kt.
    // The chooser opens once; the chosen .kt opens as the active tab
    // (Main.kt stays open, no duplicate); exactly that one file is
    // scanned; Main.kt and other project files are not.
    // ==========================================================
    fun testChooseKotlinFileOpensItActiveAndScansExactlyThatFile() {
        checkBackendReachable()
        val main = writeSource("Main.kt", mainKotlin)
        val cert = writeSource("CertificateVulnerable.kt", certKotlin)
        writeSource("SqlInjectionVulnerable.kt", sqlKotlin)
        myFixture.openFileInEditor(main)
        val manager = FileEditorManager.getInstance(project)
        assertEquals("Precondition: Main.kt is the active editor", main, activeFile())

        val answers = Answers(ScanFileChoice.CHOOSE_FILE, chosen = cert)
        val tw = toolWindowAnswering(answers)
        clickScanFile(tw)

        assertEquals("Main.kt", answers.promptedWith!!.fileName)
        assertEquals("Choose File must open the native chooser exactly once", 1, answers.chooserCalls)
        assertTrue("The chosen .kt file must be open in the editor", manager.isFileOpen(cert))
        assertEquals("The chosen file must be the active editor tab", cert, activeFile())
        assertTrue("Main.kt stays open (normal tab behavior)", manager.isFileOpen(main))
        assertEquals("No duplicate editor for the chosen file", 1, manager.openFiles.count { it == cert })
        assertEquals("Only the chosen file may be scanned", setOf("src/CertificateVulnerable.kt"), fileNamesOf(tw))
        assertTrue(findingsOf(tw).any { it.view.cwe == "CWE-295" })
        assertFalse("Other project files must not be scanned", findingsOf(tw).any { it.view.cwe == "CWE-89" })
        assertTrue(summaryOf(tw).contains("Files scanned: 1"))
        assertEquals("Scan complete", statusOf(tw))
    }

    // ==========================================================
    // 3, 4, 5. Choosing a .java file: opened, active, scanned - and the
    // previously active (vulnerable!) .kt file is NOT scanned.
    // ==========================================================
    fun testChooseJavaFileOpensItAndThePreviouslyActiveFileIsNotScanned() {
        checkBackendReachable()
        val previous = writeSource("SqlInjectionVulnerable.kt", sqlKotlin)
        val javaFile = writeSource("PromptLoginActivity.java", sqlJava)
        myFixture.openFileInEditor(previous)
        val tw = toolWindowAnswering(Answers(ScanFileChoice.CHOOSE_FILE, chosen = javaFile))

        clickScanFile(tw)

        assertTrue(FileEditorManager.getInstance(project).isFileOpen(javaFile))
        assertEquals(javaFile, activeFile())
        assertEquals(setOf("src/PromptLoginActivity.java"), fileNamesOf(tw))
        assertTrue(findingsOf(tw).any { it.view.cwe == "CWE-89" })
        assertFalse(
            "The previously active file must never be scanned",
            findingsOf(tw).any { it.view.fileName == "src/SqlInjectionVulnerable.kt" }
        )
        assertTrue(summaryOf(tw).contains("Files scanned: 1"))
    }

    // ==========================================================
    // Each Scan File -> Choose Another File scans exactly the chosen file;
    // findings of the previous file never leak into the new results.
    // ==========================================================
    fun testEachChooseFileScansOnlyTheLatestChosenFile() {
        checkBackendReachable()
        val sql = writeSource("SqlInjectionVulnerable.kt", sqlKotlin)
        val cert = writeSource("CertificateVulnerable.kt", certKotlin)
        myFixture.openFileInEditor(sql)
        val tw = toolWindowAnswering(Answers(ScanFileChoice.CHOOSE_FILE, chosen = sql))

        clickScanFile(tw)
        assertEquals(sql, activeFile())
        assertEquals(setOf("src/SqlInjectionVulnerable.kt"), fileNamesOf(tw))
        assertTrue(summaryOf(tw).contains("Files scanned: 1"))

        tw.sourceFileChooser = { cert }
        clickScanFile(tw)
        assertEquals(cert, activeFile())
        assertEquals("Findings of the previous scan must not leak in", setOf("src/CertificateVulnerable.kt"), fileNamesOf(tw))
        assertTrue(summaryOf(tw).contains("Files scanned: 1"))
    }

    // ==========================================================
    // The Tool Window is simple again: [Scan Project] [Scan File], then
    // status/results. No permanent CURRENT FILE section, no permanent
    // Choose File button - and a tab switch never triggers a scan.
    // ==========================================================
    fun testToolWindowHasNoPermanentCurrentFileSectionOrChooseFileButton() {
        val tw = MyToolWindow(project)
        val content = tw.getContent()
        fun all(c: java.awt.Component): List<java.awt.Component> =
            listOf(c) + ((c as? java.awt.Container)?.components?.flatMap { all(it) } ?: emptyList())
        val components = all(content)

        val buttons = components.filterIsInstance<javax.swing.JButton>().map { it.text }
        assertEquals(listOf("Scan Project", "Scan File"), buttons)
        val labels = components.filterIsInstance<JLabel>().map { it.text ?: "" }
        assertFalse("No permanent CURRENT FILE heading", labels.any { it.contains("CURRENT FILE") })
        assertFalse("No permanent current-file name", labels.any { it == MyToolWindow.NO_FILE_OPEN_MESSAGE })
        for (removed in listOf("currentFileSectionLabel", "currentFileNameLabel", "currentFilePathLabel", "chooseFileButton", "chosenScanTarget")) {
            assertTrue("$removed must be gone", MyToolWindow::class.java.declaredFields.none { it.name == removed })
        }

        // Opening/switching files never scans anything.
        myFixture.openFileInEditor(writeSource("SqlInjectionVulnerable.kt", sqlKotlin))
        PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
        assertFalse(isScanningOf(tw))
        assertTrue(findingsOf(tw).isEmpty())
        assertEquals("Ready", statusOf(tw))
    }

    // ==========================================================
    // The REAL dialog's text: "Current open file:" + name + path + "What do
    // you want to scan?"; the unsupported message; or "No file is currently open.".
    // ==========================================================
    fun testRealDialogShowsCurrentOpenFileInformation() {
        fun textsOf(info: ScanFilePromptInfo): List<String> {
            val dialog = ScanFileDialog(project, info)
            try {
                val panel = ScanFileDialog::class.java.getDeclaredMethod("createCenterPanel").apply { isAccessible = true }
                    .invoke(dialog) as java.awt.Container
                return panel.components.filterIsInstance<JLabel>().map { it.text }.filter { it.isNotBlank() }
            } finally {
                Disposer.dispose(dialog.disposable)
            }
        }

        assertEquals(
            listOf("Current open file:", "SqlInjectionVulnerable.kt", "src/SqlInjectionVulnerable.kt", "What do you want to scan?"),
            textsOf(ScanFilePromptInfo("SqlInjectionVulnerable.kt", "src/SqlInjectionVulnerable.kt", CurrentFileStatus.SUPPORTED))
        )
        assertEquals(
            listOf("Current open file:", "example.xml", "src/example.xml", "Only Kotlin (.kt) and Java (.java) files can be scanned."),
            textsOf(ScanFilePromptInfo("example.xml", "src/example.xml", CurrentFileStatus.UNSUPPORTED))
        )
        assertEquals(listOf("No file is currently open."), textsOf(ScanFilePromptInfo(null, null, CurrentFileStatus.NONE)))
    }

    // No file open: the dialog says so, and Choose File still works.
    fun testNoCurrentFileStillLetsTheUserChooseAFile() {
        checkBackendReachable()
        closeAllEditors()
        val cert = writeSource("CertificateVulnerable.kt", certKotlin)
        val answers = Answers(ScanFileChoice.CHOOSE_FILE, chosen = cert)
        val tw = toolWindowAnswering(answers)

        clickScanFile(tw)

        assertEquals(ScanFilePromptInfo(null, null, CurrentFileStatus.NONE), answers.promptedWith)
        assertEquals(cert, activeFile())
        assertEquals(setOf("src/CertificateVulnerable.kt"), fileNamesOf(tw))
    }

    // ==========================================================
    // 10. Existing navigation, unchanged: clicking the finding of the
    // chosen file lands on its exact line in that file.
    // ==========================================================
    fun testNavigationFromAChosenFileFindingLandsOnItsLine() {
        checkBackendReachable()
        myFixture.openFileInEditor(writeSource("Main.kt", mainKotlin))
        val cert = writeSource("CertificateVulnerable.kt", certKotlin)
        val tw = toolWindowAnswering(Answers(ScanFileChoice.CHOOSE_FILE, chosen = cert))
        clickScanFile(tw)

        val finding = findingsOf(tw).single { it.view.cwe == "CWE-295" }
        assertEquals(File(cert.path), finding.navigableFile)
        val navigate = Class.forName("com.dualvulndroid.dualvulndroid.MyToolWindowKt")
            .getDeclaredMethod("navigateToFinding", Project::class.java, FindingEntry::class.java)
            .apply { isAccessible = true }
        navigate.invoke(null, project, finding)
        PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()

        val editor = FileEditorManager.getInstance(project).selectedTextEditor!!
        assertEquals(cert, activeFile())
        assertEquals("Navigation must land on the finding's line", finding.view.line, editor.caretModel.logicalPosition.line)
    }

    // ==========================================================
    // 6. Cancel (dialog) and cancel (chooser): no scan, no editor switch,
    // findings/status/summary exactly as they were.
    // ==========================================================
    fun testCancelDoesNothing() {
        checkBackendReachable()
        val sql = writeSource("SqlInjectionVulnerable.kt", sqlKotlin)
        val cert = writeSource("CertificateVulnerable.kt", certKotlin)
        myFixture.openFileInEditor(cert)
        val tw = toolWindowAnswering(Answers(ScanFileChoice.CHOOSE_FILE, chosen = sql))
        clickScanFile(tw)
        val findingsBefore = findingsOf(tw)
        val statusBefore = statusOf(tw)
        val summaryBefore = summaryOf(tw)
        assertTrue("Precondition: a real earlier scan produced findings", findingsBefore.isNotEmpty())
        assertEquals(sql, activeFile())

        // Cancel in the dialog: the chooser is never opened.
        var chooserCalls = 0
        tw.scanFilePrompt = { ScanFileChoice.CANCEL }
        tw.sourceFileChooser = { chooserCalls++; cert }
        clickScanFile(tw)
        assertEquals(0, chooserCalls)

        // Choose Another File, then cancel the native chooser.
        tw.scanFilePrompt = { ScanFileChoice.CHOOSE_FILE }
        tw.sourceFileChooser = { chooserCalls++; null }
        clickScanFile(tw)
        assertEquals(1, chooserCalls)

        assertFalse(isScanningOf(tw))
        assertEquals("No editor switch on cancel", sql, activeFile())
        assertEquals(findingsBefore, findingsOf(tw))
        assertEquals(statusBefore, statusOf(tw))
        assertEquals(summaryBefore, summaryOf(tw))
    }

    // ==========================================================
    // 9. Scan Project is unchanged: no prompt, whole project scanned.
    // ==========================================================
    fun testScanProjectDoesNotPromptAndScansTheWholeProject() {
        checkBackendReachable()
        writeSource("SqlInjectionVulnerable.kt", sqlKotlin)
        writeSource("CertificateVulnerable.kt", certKotlin)
        writeSource("PromptLoginActivity.java", sqlJava)
        val answers = Answers(ScanFileChoice.CANCEL)
        val tw = toolWindowAnswering(answers)

        callPrivate(tw, "startProjectScan")
        waitForScan(tw)

        assertNull("Scan Project must never show the Scan File dialog", answers.promptedWith)
        assertEquals(0, answers.chooserCalls)
        assertEquals("Project scan complete", statusOf(tw))
        assertTrue(
            fileNamesOf(tw).containsAll(setOf("src/SqlInjectionVulnerable.kt", "src/CertificateVulnerable.kt", "src/PromptLoginActivity.java"))
        )
    }

    // ==========================================================
    // 10. After Choose Another File: real-time detection still flags the
    // chosen file, the existing Quick Fix still applies, and the next
    // Scan Current File of it (the now-active file) no longer reports CWE-89.
    // ==========================================================
    fun testQuickFixAndRealTimeDetectionStillWorkOnTheChosenFile() {
        checkBackendReachable()
        myFixture.openFileInEditor(writeSource("Main.kt", mainKotlin))
        val sql = writeSource("SqlInjectionVulnerable.kt", sqlKotlin)
        val tw = toolWindowAnswering(Answers(ScanFileChoice.CHOOSE_FILE, chosen = sql))
        clickScanFile(tw)
        assertTrue(findingsOf(tw).any { it.view.cwe == "CWE-89" })

        myFixture.openFileInEditor(sql) // already the active tab; hands the fixture its PSI/editor
        val psiFile = myFixture.file
        val annotator = CodeSentinelAnnotator()
        val realTime = annotator.doAnnotate(annotator.collectInformation(psiFile, myFixture.editor, false)) ?: emptyList()
        val sqlFinding = realTime.firstOrNull { it.vulnerabilityType == "SQL Injection" }
        assertNotNull("Real-time detection must still flag the SQL injection", sqlFinding)

        val fix = SqlFixLocator.tryBuildFix(psiFile, sqlFinding!!, "SqlInjectionVulnerable.kt")
        assertNotNull("The existing Quick Fix must still be offered", fix)
        val call = PsiTreeUtil.findChildrenOfType(psiFile, KtCallExpression::class.java).first { it.text.contains("rawQuery") }
        WriteCommandAction.runWriteCommandAction(project) { fix!!.invoke(project, psiFile, myFixture.editor, call, call) }

        tw.scanFilePrompt = { ScanFileChoice.SCAN_CURRENT_FILE }
        clickScanFile(tw)
        assertEquals(setOf<String>(), fileNamesOf(tw).filter { it != "src/SqlInjectionVulnerable.kt" }.toSet())
        assertFalse("After the Quick Fix, the rescan must no longer report CWE-89", findingsOf(tw).any { it.view.cwe == "CWE-89" })
    }
}
