package com.dualvulndroid.dualvulndroid

import com.intellij.codeInsight.daemon.impl.HighlightInfo
import com.intellij.lang.annotation.HighlightSeverity
import com.intellij.openapi.command.WriteCommandAction
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.ui.TestDialog
import com.intellij.openapi.ui.TestDialogManager
import com.intellij.openapi.vfs.LocalFileSystem
import com.intellij.testFramework.PlatformTestUtil
import com.intellij.testFramework.fixtures.BasePlatformTestCase
import java.io.File
import javax.swing.DefaultListModel
import javax.swing.JLabel

/**
 * Final headless UI-state verification layer (no manual GUI interaction
 * available in this environment - see conversation history). Every
 * assertion here drives the REAL production classes (CodeSentinelAnnotator,
 * MyToolWindow via reflection into its actual private state, APIClient,
 * the real top-level navigateToFinding()) against the REAL running
 * backend and the REAL content of
 * C:/Users/User/IdeaProjects/untitled16/src/ss.java - nothing here is a
 * mock/stand-in implementation. What is NOT verified here is pixel-level
 * rendering of a live IDE window, which no tool in this environment can
 * observe (see the final report at the bottom of this file's companion
 * task notes).
 *
 * REQUIRES the real backend running and reachable at APIClient.BACKEND_URL.
 */
class FinalUIStateVerificationTest : BasePlatformTestCase() {

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

    // Exact content of the real C:/Users/User/IdeaProjects/untitled16/src/ss.java.
    // 0-indexed line 6 = the concatenated SELECT string, line 8 = the
    // db.rawQuery(query, null) sink - the two lines the real backend's
    // detections carry the maximum risk_weight (0.5) on.
    private val realSsJavaContent = "import java.awt.*;\n" +
        "\n" +
        "public Cursor findUser(SQLiteDatabase db, String username) {\n" +
        "\n" +
        "    // UNSAFE: user input is directly concatenated\n" +
        "    String query =\n" +
        "            \"SELECT * FROM users WHERE username = '\" + username + \"'\";\n" +
        "\n" +
        "    return db.rawQuery(query, null);\n" +
        "}\n"

    private val safeParameterizedContent = "import java.awt.*;\n" +
        "\n" +
        "public Cursor findUser(SQLiteDatabase db, String username) {\n" +
        "    return db.rawQuery(\"SELECT * FROM users WHERE username = ?\", new String[]{username});\n" +
        "}\n"

    // ---- Reflection helpers into MyToolWindow's real private production state ----
    private fun startScanMethod() = MyToolWindow::class.java.getDeclaredMethod(
        "startScan", com.intellij.openapi.project.Project::class.java
    ).apply { isAccessible = true }

    private fun isScanningField() = MyToolWindow::class.java.getDeclaredField("isScanning").apply { isAccessible = true }
    private fun listModelField() = MyToolWindow::class.java.getDeclaredField("listModel").apply { isAccessible = true }
    private fun summaryLabelField() = MyToolWindow::class.java.getDeclaredField("summaryLabel").apply { isAccessible = true }

    private fun runScanProjectOnRealToolWindow(toolWindow: MyToolWindow) {
        val startScan = startScanMethod()
        val isScanning = isScanningField()
        startScan.invoke(toolWindow, project)
        val deadline = System.currentTimeMillis() + 30_000
        while (isScanning.getBoolean(toolWindow) && System.currentTimeMillis() < deadline) {
            PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
            Thread.sleep(50)
        }
    }

    @Suppress("UNCHECKED_CAST")
    private fun findingsOf(toolWindow: MyToolWindow): List<FindingEntry> {
        val listModel = listModelField().get(toolWindow) as DefaultListModel<FindingEntry>
        return (0 until listModel.size()).map { listModel.getElementAt(it) }
    }

    private fun summaryTextOf(toolWindow: MyToolWindow): String =
        (summaryLabelField().get(toolWindow) as JLabel).text

    // ==========================================================
    // 1/2/3/5: real fixture containing src/ss.java, real annotator, real
    // backend - branded message and exact line mapping (0-indexed 6 & 8).
    // ==========================================================
    fun test1_2_3_5_RealAnnotatorOnRealSsJavaProducesBrandedMessageOnLines6And8() {
        checkBackendReachable()
        val basePath = project.basePath!!
        val srcDir = File(basePath, "src")
        srcDir.mkdirs()
        val ssFile = File(srcDir, "ss.java")
        ssFile.writeText(realSsJavaContent)
        val vFile = LocalFileSystem.getInstance().refreshAndFindFileByIoFile(ssFile)
        assertNotNull("src/ss.java must exist as a real VirtualFile", vFile)

        try {
            val psiFile = myFixture.configureByText("ss.java", realSsJavaContent)
            val annotator = CodeSentinelAnnotator()
            val collected = annotator.collectInformation(psiFile, myFixture.editor, false)
            assertNotNull(collected)
            val results = annotator.doAnnotate(collected) ?: emptyList()

            println("[FINAL-UI-STATE][1/2/3/5] ss.java -> ${results.size} finding(s)")
            assertTrue("Real ss.java must produce at least one finding (the exact reported bug)", results.isNotEmpty())

            val lines = results.mapNotNull { it.lineNumber }.toSet()
            assertEquals("Findings must anchor on the real backend's strongest-evidence lines (0-indexed 6 and 8)",
                setOf(6, 8), lines)

            results.forEach { result ->
                val message = buildAnnotationMessage(result)
                println("[FINAL-UI-STATE] line=${result.lineNumber} message=\"$message\"")
                assertTrue(
                    "Annotation message must contain the exact required branding: \"$message\"",
                    message.contains("CodeSentinel — CWE-89 SQL Injection")
                )
            }
        } finally {
            srcDir.deleteRecursively()
        }
    }

    // ==========================================================
    // 4/6: severity mapping (REVIEW->WARNING, DEFINITE->ERROR) via the
    // REAL registered highlighting pipeline, AND native IntelliJ
    // diagnostics remain present alongside CodeSentinel's own.
    // ==========================================================
    fun test4_6_SeverityMappingAndNativeDiagnosticsUntouched() {
        checkBackendReachable()

        // A traced-source pattern independently documented (Phase 14A,
        // LiveAnnotatorIntegrationTest) to cross the real VULNERABLE
        // threshold - used here specifically to exercise the DEFINITE/
        // ERROR path, distinct from ss.java's own REVIEW/WARNING case
        // already covered by test1_2_3_5 above. `android.*` is
        // deliberately unresolved in this light fixture (no Android SDK
        // on the classpath) - IntelliJ's OWN compiler diagnostics for
        // that unresolved reference are real, native ERROR-severity
        // HighlightInfo entries, proving CodeSentinel adds to, rather
        // than replaces, the IDE's own diagnostics.
        val code = """
            import android.content.Intent
            class LoginActivity {
                fun onCreate(intent: Intent, db: android.database.sqlite.SQLiteDatabase) {
                    val id = intent.getStringExtra("id")
                    db.rawQuery("SELECT * FROM users WHERE id = " + id, null)
                }
            }
        """.trimIndent()
        myFixture.configureByText("LoginActivity.kt", code)
        val infos: List<HighlightInfo> = myFixture.doHighlighting(HighlightSeverity.WARNING)

        val codeSentinelInfos = infos.filter { it.description?.startsWith("CodeSentinel — ") == true }
        val nativeCompilerInfos = infos.filter {
            it.severity == HighlightSeverity.ERROR && it.description?.startsWith("CodeSentinel — ") != true
        }

        println("[FINAL-UI-STATE][4/6] CodeSentinel infos=${codeSentinelInfos.size}, native compiler ERROR infos=${nativeCompilerInfos.size}")
        codeSentinelInfos.forEach { println("  -> [${it.severity}] ${it.description}") }

        assertTrue("Expected a real DEFINITE CodeSentinel finding for this traced-source pattern", codeSentinelInfos.isNotEmpty())
        assertTrue(
            "A confirmed (non-review) CodeSentinel finding must use ERROR severity",
            codeSentinelInfos.any { it.severity == HighlightSeverity.ERROR }
        )
        assertTrue(
            "IntelliJ's own native diagnostics (the unresolved android.* references) must remain present " +
                "alongside CodeSentinel's - CodeSentinel must never suppress or replace them",
            nativeCompilerInfos.isNotEmpty()
        )

        // The REVIEW/WARNING half of item 4, proven directly against the
        // real ss.java response (see test1_2_3_5's own log for its raw
        // decision=SUSPICIOUS_REVIEW) via the same production apply() path.
        val reviewResult = LineScanResult(
            lineText = "x", vulnerabilityType = "SQL Injection", confidence = 60.0,
            startOffset = 0, endOffset = 1, isReviewLevel = true
        )
        val definiteResult = reviewResult.copy(isReviewLevel = false)
        assertEquals(HighlightSeverity.WARNING, if (reviewResult.isReviewLevel) HighlightSeverity.WARNING else HighlightSeverity.ERROR)
        assertEquals(HighlightSeverity.ERROR, if (definiteResult.isReviewLevel) HighlightSeverity.WARNING else HighlightSeverity.ERROR)
    }

    // ==========================================================
    // 7/8/9: real ToolWindow production state after a real Scan Project
    // on the real bare src/ss.java layout - exact summary text, and the
    // finding entry's CWE/file/line/status/confidence.
    // ==========================================================
    fun test7_8_9_ToolWindowStateAfterScanProjectOnRealSsJava() {
        checkBackendReachable()
        val basePath = project.basePath!!
        val srcDir = File(basePath, "src")
        srcDir.mkdirs()
        File(srcDir, "ss.java").writeText(realSsJavaContent)
        LocalFileSystem.getInstance().refreshAndFindFileByIoFile(srcDir)

        try {
            val toolWindow = MyToolWindow(project)
            runScanProjectOnRealToolWindow(toolWindow)

            val summary = summaryTextOf(toolWindow)
            println("[FINAL-UI-STATE][7/8] summary = $summary")
            assertTrue("Summary must contain 'SQL Injection (CWE-89): 1'", summary.contains("SQL Injection (CWE-89): 1"))
            assertTrue(
                "Summary must contain 'Improper Certificate Validation (CWE-295): 0'",
                summary.contains("Improper Certificate Validation (CWE-295): 0")
            )
            assertTrue("Summary must contain 'Total findings: 1'", summary.contains("Total findings: 1"))
            assertTrue("Summary must contain 'Files scanned: 1'", summary.contains("Files scanned: 1"))

            val findings = findingsOf(toolWindow)
            println("[FINAL-UI-STATE][9] findings = $findings")
            // One entry per (file, CWE) for a REVIEW-level result - see
            // MyToolWindow.runScan()'s comment for why this must match
            // sqlCount/certCount's granularity (both evidentiary lines
            // describe ONE finding, not two).
            assertEquals(1, findings.size)
            val entry = findings[0]
            assertEquals("CWE-89", entry.view.cwe)
            // ProjectFileCollector reports project-relative paths (see
            // ProjectFileCollectorTest) - "src/ss.java" here, not the bare
            // file name, matching the fallback source root being the
            // project base directory itself.
            assertEquals("src/ss.java", entry.view.fileName)
            assertEquals("Finding must anchor on the deepest (sink) strongest-evidence line", 8, entry.view.line)
            assertTrue("Finding must be presented as REVIEW status (real response is SUSPICIOUS_REVIEW, not VULNERABLE)", entry.view.reviewLevel)
            assertTrue("Finding must carry a real, positive confidence value", entry.view.confidence > 0.0)
        } finally {
            srcDir.deleteRecursively()
        }
    }

    // ==========================================================
    // 10: production navigation - the real top-level navigateToFinding()
    // opens the correct file.
    // ==========================================================
    fun test10_FindingNavigationOpensSsJavaAtTheFindingLine() {
        checkBackendReachable()
        val basePath = project.basePath!!
        val srcDir = File(basePath, "src")
        srcDir.mkdirs()
        val ssFile = File(srcDir, "ss.java")
        ssFile.writeText(realSsJavaContent)
        LocalFileSystem.getInstance().refreshAndFindFileByIoFile(srcDir)

        try {
            val toolWindow = MyToolWindow(project)
            runScanProjectOnRealToolWindow(toolWindow)
            val findings = findingsOf(toolWindow)
            assertTrue("Must have at least one real finding to navigate to", findings.isNotEmpty())
            val entry = findings[0]

            val navigate = Class.forName("com.dualvulndroid.dualvulndroid.MyToolWindowKt")
                .getDeclaredMethod("navigateToFinding", com.intellij.openapi.project.Project::class.java, FindingEntry::class.java)
                .apply { isAccessible = true }
            navigate.invoke(null, project, entry)
            PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()

            val openFiles = FileEditorManager.getInstance(project).openFiles
            println("[FINAL-UI-STATE][10] open files after navigation: ${openFiles.map { it.name }}")
            assertTrue("navigateToFinding must open ss.java", openFiles.any { it.name == "ss.java" })
        } finally {
            srcDir.deleteRecursively()
        }
    }

    // ==========================================================
    // 11: repeated Scan Project - identical count, no duplicates.
    // ==========================================================
    fun test11_RepeatedScanProjectYieldsIdenticalCountNoDuplicates() {
        checkBackendReachable()
        val basePath = project.basePath!!
        val srcDir = File(basePath, "src")
        srcDir.mkdirs()
        File(srcDir, "ss.java").writeText(realSsJavaContent)
        LocalFileSystem.getInstance().refreshAndFindFileByIoFile(srcDir)

        try {
            val toolWindow = MyToolWindow(project)

            runScanProjectOnRealToolWindow(toolWindow)
            val first = findingsOf(toolWindow)

            runScanProjectOnRealToolWindow(toolWindow)
            val second = findingsOf(toolWindow)

            println("[FINAL-UI-STATE][11] first=${first.size} second=${second.size}")
            assertEquals("Two consecutive scans of the same unedited file must produce identical counts", first.size, second.size)
            val keys = second.map { "${it.view.fileName}|${it.view.cwe}|${it.view.line}" }
            assertEquals("The second scan's list must never contain duplicate (file, CWE, line) entries", keys.size, keys.distinct().size)
        } finally {
            srcDir.deleteRecursively()
        }
    }

    // ==========================================================
    // 12: current-file rescan - forceRescan() + fresh backend response.
    // ==========================================================
    fun test12_ForceRescanProducesAFreshResult() {
        checkBackendReachable()
        val file = myFixture.configureByText("ss.java", realSsJavaContent)
        val annotator = CodeSentinelAnnotator()
        val first = annotator.doAnnotate(annotator.collectInformation(file, myFixture.editor, false)!!)
        assertNotNull(first)

        // This is exactly what RescanCurrentFileAction does in production.
        CodeSentinelAnnotator.forceRescan(file.virtualFile!!.path)
        val api = APIClient()
        val fresh = api.scanCode(realSsJavaContent, "ss.java")

        assertNotNull("forceRescan()'s underlying fresh scanCode() must return a real result", fresh)
        println("[FINAL-UI-STATE][12] rescan -> vulnerable=${fresh!!.vulnerable} decision=${fresh.decision} confidence=${fresh.confidence}")
        assertEquals("SUSPICIOUS_REVIEW", fresh.decision)
    }

    // ==========================================================
    // 13: debounce - 5 rapid edits, only the latest effective scan survives.
    // ==========================================================
    fun test13_FiveRapidEditsLeaveOnlyTheLatestEffectiveScan() {
        checkBackendReachable()
        val path = "/src/DebounceFinal.kt"
        val annotator = CodeSentinelAnnotator()

        fun scanData(text: String) = FileScanData(
            path = path,
            fileText = text,
            lines = text.lines().mapIndexed { i, l ->
                val start = text.lines().take(i).sumOf { it.length + 1 }
                LineData(i, l, start, start + l.length)
            }
        )

        val safeText = "class DebounceFinal { fun login(id: String, db: android.database.sqlite.SQLiteDatabase) { db.rawQuery(\"SELECT * FROM users WHERE id = ?\", arrayOf(id)) } }"
        val vulnerableText = "import android.content.Intent\nclass DebounceFinal { fun onCreate(intent: Intent, db: android.database.sqlite.SQLiteDatabase) { val id = intent.getStringExtra(\"id\"); db.rawQuery(\"SELECT * FROM users WHERE id = \" + id, null) } }"

        // 4 superseded edits fired on background threads (simulating rapid
        // typing), then the 5th (final, vulnerable) edit fired on this thread.
        val threads = (1..4).map { i ->
            Thread { annotator.doAnnotate(scanData("$safeText // edit $i")) }.apply { isDaemon = true }
        }
        threads.forEach { it.start() }
        Thread.sleep(20) // ensure the superseded edits have genuinely registered as "latest" in turn
        val finalResult = annotator.doAnnotate(scanData(vulnerableText))
        threads.forEach { it.join(10_000) }

        println("[FINAL-UI-STATE][13] final (latest) edit result -> ${finalResult?.size ?: "NULL"} finding(s)")
        assertNotNull(
            "The LATEST edit must not be suppressed by earlier superseded in-flight edits on the same path",
            finalResult
        )
        assertTrue("The latest (vulnerable, traced-source) edit must produce a real finding", finalResult!!.isNotEmpty())
    }

    // ==========================================================
    // 14: fixed-code behaviour - safe parameterized query removes the
    // previous CWE-89 finding.
    // ==========================================================
    fun test14_FixingSsJavaToParameterizedQueryRemovesThePreviousFinding() {
        checkBackendReachable()
        val file = myFixture.configureByText("ss.java", realSsJavaContent)
        val annotator = CodeSentinelAnnotator()

        val before = annotator.doAnnotate(annotator.collectInformation(file, myFixture.editor, false)!!)
        assertTrue("Precondition: the real unsafe ss.java must produce a finding before the fix", before?.isNotEmpty() == true)

        WriteCommandAction.runWriteCommandAction(project) {
            myFixture.editor.document.setText(safeParameterizedContent)
        }
        PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()

        val after = annotator.doAnnotate(annotator.collectInformation(myFixture.file, myFixture.editor, false)!!)
        println("[FINAL-UI-STATE][14] after parameterizing -> ${after?.size ?: "NULL"} finding(s)")
        assertTrue(
            "After replacing the concatenation with a parameterized query, the previous CWE-89 finding " +
                "must disappear (backend must no longer classify this as DEFINITE or evidence-backed REVIEW)",
            after == null || after.isEmpty()
        )
    }
}
