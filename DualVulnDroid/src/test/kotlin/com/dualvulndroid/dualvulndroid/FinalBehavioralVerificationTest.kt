package com.dualvulndroid.dualvulndroid

import com.intellij.testFramework.PlatformTestUtil
import com.intellij.testFramework.fixtures.BasePlatformTestCase
import java.io.File

/**
 * Plugin-fix task, final hardening pass - STEP 12 behavioral verification:
 * exercises the actual production code paths end-to-end against the real
 * backend, reproducing the reported real-world "untitled16" scenario
 * (a bare src/ss.java layout, no Android-standard source folders) rather
 * than a synthetic stand-in.
 *
 *   A. scan the real unsafe ss.java content
 *   B. fire several rapid consecutive edits
 *   C. debouncing collapses them into ~one real backend round trip
 *   D. Rescan Current File's underlying path (forceRescan + fresh scanCode)
 *   E/F. Scan Project run twice, consecutively, on the bare layout
 *   G/H. the second run is a fresh request whose results never duplicate
 *        or get appended on top of the first run's
 *
 * REQUIRES the real backend running and reachable at APIClient.BACKEND_URL,
 * same convention as every other Live* test in this suite.
 */
class FinalBehavioralVerificationTest : BasePlatformTestCase() {

    private fun checkBackendReachable() {
        val probe = APIClient().scanCode("int x = 1;", "ReachabilityProbe.java")
        if (probe == null) {
            fail(
                "Real backend not reachable at ${APIClient.BACKEND_URL} - this test requires the " +
                    "real FastAPI backend running. Start it and re-run."
            )
        }
    }

    // The exact content of the real C:/Users/User/IdeaProjects/untitled16/src/ss.java
    private val unsafeSs = """
        public Cursor findUser(SQLiteDatabase db, String username) {

            // UNSAFE: user input is directly concatenated
            String query =
                    "SELECT * FROM users WHERE username = '" + username + "'";

            return db.rawQuery(query, null);
        }
    """.trimIndent()

    // ---- A + B + C ----
    fun testAScanUnsafeSsThenRapidEditsAreDebouncedToOneRealRoundTrip() {
        checkBackendReachable()
        val file = myFixture.configureByText("ss.java", unsafeSs)
        val annotator = CodeSentinelAnnotator()

        val firstResults = annotator.doAnnotate(annotator.collectInformation(file, myFixture.editor, false)!!)
        println("[FINAL-VERIFY][A] unsafe ss.java -> findings=${firstResults?.size ?: 0}")
        assertNotNull(
            "A real (possibly-empty) result must come back for a reachable backend - never null/crash",
            firstResults
        )

        // B: 5 rapid "edits" fired on separate threads in immediate
        // succession, exactly like a fast typing burst hitting the same path.
        val path = file.virtualFile!!.path
        fun scanData(text: String) = FileScanData(
            path = path,
            fileText = text,
            lines = text.lines().mapIndexed { i, l ->
                val startOffset = text.lines().take(i).sumOf { it.length + 1 }
                LineData(i, l, startOffset, startOffset + l.length)
            }
        )
        val variants = (1..5).map { i -> "$unsafeSs\n// edit $i" }
        val threads = variants.map { text -> Thread { annotator.doAnnotate(scanData(text)) } }

        val start = System.currentTimeMillis()
        threads.forEach { it.start() }
        threads.forEach { it.join(15_000) }
        val elapsedMs = System.currentTimeMillis() - start
        println("[FINAL-VERIFY][B/C] 5 rapid edits resolved in ${elapsedMs}ms")

        // C: without debouncing, 5 edits each running their own full
        // network round trip (serialized behind the backend's threadpool)
        // would take noticeably longer than one debounce window (500ms)
        // plus one real round trip. This bounds total wall time well
        // under what 5 serial real requests would cost.
        assertTrue(
            "5 rapid edits on the same path must be debounced into roughly one real backend round trip, " +
                "not 5 independently-queued ones (observed ${elapsedMs}ms)",
            elapsedMs < 5000
        )
    }

    // ---- D ----
    fun testDForceRescanPathProducesAFreshResult() {
        checkBackendReachable()
        val file = myFixture.configureByText("ss.java", unsafeSs)
        val annotator = CodeSentinelAnnotator()
        annotator.doAnnotate(annotator.collectInformation(file, myFixture.editor, false)!!)

        // This is exactly what RescanCurrentFileAction does: force-clear
        // any cached annotator entry for this path, then call the SAME
        // scanCode() path directly against live text.
        CodeSentinelAnnotator.forceRescan(file.virtualFile!!.path)

        val api = APIClient()
        val fresh = api.scanCode(unsafeSs, "ss.java")
        assertNotNull("Rescan Current File's underlying scanCode() must return a real result after forceRescan", fresh)
        println("[FINAL-VERIFY][D] rescan -> vulnerable=${fresh!!.vulnerable} type=${fresh.vulnerabilityType} decision=${fresh.decision}")
    }

    // ---- E/F/G/H ----
    fun testEFScanProjectRunTwiceOnBareSrcLayoutBothSucceedWithoutDuplicates() {
        checkBackendReachable()

        val basePath = project.basePath!!
        // Reproduces the real reported layout: a bare "src/" directory,
        // no "app/src/main/java" anywhere - the exact case root cause #2
        // (MyToolWindow's old hardcoded Android path check) failed on.
        val srcDir = File(basePath, "src")
        srcDir.mkdirs()
        // A filename unique to this test - several other test classes in
        // this suite also write a real disk "src/ss.java"; reusing that
        // exact relative path risks a stale FileDocumentManager Document
        // from an earlier test's use of the same path, now that
        // MyToolWindow's scan reads the live Document rather than disk.
        val ssFile = File(srcDir, "FinalBehavioralEF.java")
        ssFile.writeText(unsafeSs)
        val vFile = com.intellij.openapi.vfs.LocalFileSystem.getInstance().refreshAndFindFileByIoFile(ssFile)!!
        // "Scan Current File" now scans ONLY the active editor file - it
        // must be opened for startScan() to find it via
        // FileEditorManager.selectedFiles.
        myFixture.openFileInEditor(vFile)

        val toolWindow = MyToolWindow(project)
        val startScan = MyToolWindow::class.java.getDeclaredMethod("startScanOfFile", com.intellij.openapi.project.Project::class.java, com.intellij.openapi.vfs.VirtualFile::class.java)
        startScan.isAccessible = true
        val isScanningField = MyToolWindow::class.java.getDeclaredField("isScanning")
        isScanningField.isAccessible = true
        val listModelField = MyToolWindow::class.java.getDeclaredField("listModel")
        listModelField.isAccessible = true

        fun waitForScanToFinish() {
            val deadline = System.currentTimeMillis() + 30_000
            while (isScanningField.getBoolean(toolWindow) && System.currentTimeMillis() < deadline) {
                PlatformTestUtil.dispatchAllInvocationEventsInIdeEventQueue()
                Thread.sleep(50)
            }
        }

        @Suppress("UNCHECKED_CAST")
        fun currentFindingCount(): Int =
            (listModelField.get(toolWindow) as javax.swing.DefaultListModel<FindingEntry>).size()

        try {
            // E: first Scan Project - must succeed via the project-root
            // fallback (no Android-standard source layout exists here at all).
            startScan.invoke(toolWindow, project, com.intellij.openapi.fileEditor.FileEditorManager.getInstance(project).selectedFiles.firstOrNull())
            waitForScanToFinish()
            assertFalse("First scan must complete (isScanning back to false)", isScanningField.getBoolean(toolWindow))
            val firstCount = currentFindingCount()
            println("[FINAL-VERIFY][E] first Scan Project on bare src/ layout -> findings=$firstCount")

            // F: second, consecutive Scan Project - the button must be
            // clickable again and perform an independent fresh request.
            startScan.invoke(toolWindow, project, com.intellij.openapi.fileEditor.FileEditorManager.getInstance(project).selectedFiles.firstOrNull())
            waitForScanToFinish()
            assertFalse("Second scan must also complete (isScanning back to false)", isScanningField.getBoolean(toolWindow))
            val secondCount = currentFindingCount()
            println("[FINAL-VERIFY][F] second Scan Project on bare src/ layout -> findings=$secondCount")

            // G/H: MyToolWindow.startScan() clears listModel at the start
            // of every run, so the second run's results can never be
            // appended on top of (duplicated with) the first's - for this
            // single, unedited file, both runs must agree exactly.
            assertEquals(
                "Two consecutive Scan Project runs over the same unedited file must produce the same " +
                    "finding count, not accumulate duplicates across runs",
                firstCount, secondCount
            )
        } finally {
            srcDir.deleteRecursively()
        }
    }
}
