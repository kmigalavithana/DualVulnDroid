package com.dualvulndroid.dualvulndroid

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.fileEditor.OpenFileDescriptor
import com.intellij.openapi.progress.ProcessCanceledException
import com.intellij.openapi.progress.ProgressIndicator
import com.intellij.openapi.progress.Task
import com.intellij.openapi.project.Project
import com.intellij.openapi.application.ReadAction
import com.intellij.openapi.roots.ProjectRootManager
import com.intellij.openapi.ui.Messages
import com.intellij.openapi.vfs.LocalFileSystem
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.openapi.wm.ToolWindowManager
import com.intellij.ui.JBColor
import com.intellij.ui.components.JBLabel
import com.intellij.ui.components.JBList
import com.intellij.ui.components.JBPanel
import com.intellij.ui.components.JBScrollPane
import com.intellij.ui.content.ContentFactory
import com.intellij.util.ui.JBUI
import com.intellij.util.ui.UIUtil
import java.awt.BorderLayout
import java.awt.Component
import java.awt.Font
import java.awt.event.MouseAdapter
import java.awt.event.MouseEvent
import java.io.File
import javax.swing.BorderFactory
import javax.swing.BoxLayout
import javax.swing.DefaultListModel
import javax.swing.JButton
import javax.swing.JLabel
import javax.swing.JList
import javax.swing.JPanel
import javax.swing.JSeparator
import javax.swing.ListCellRenderer
import javax.swing.SwingConstants

const val DUALVULNDROID_TOOL_WINDOW_ID = "DualVulnDroid"

class MyToolWindowFactory : ToolWindowFactory {

    override fun shouldBeAvailable(project: Project) = true

    override fun createToolWindowContent(
        project: Project,
        toolWindow: ToolWindow
    ) {
        val myToolWindow = MyToolWindow(project)
        MyToolWindow.registry[project] = myToolWindow

        val content = ContentFactory.getInstance()
            .createContent(
                myToolWindow.getContent(),
                null,
                false
            )

        toolWindow.contentManager.addContent(content)
    }
}

// Phase 5A: sends ONE batch request to POST /developer/scan (see
// APIClient.scanProjectBatch) rather than one /predict call per file. This
// tool window remains the existing details-panel architecture from Phase 4,
// extended with a findings list so multiple findings are browsable, not
// just "stop at the first vulnerable line" like the old flow did.
//
// Scan-scope task: "Scan Project" was renamed to "Scan Current File" and
// now sends ONLY the file currently open/selected in the editor
// (FileEditorManager.selectedFiles) as a batch of one - never
// ProjectFileCollector's whole-project walk. Every click clears listModel
// first (see startScan()), so the list and summary counters only ever
// reflect the CURRENT file's latest scan, never a previous file's leftover
// findings. The underlying /developer/scan endpoint, classification
// (classify()), per-detection-type grouping (groupDetectionsByType()), and
// finding presentation (toDetailView()/renderDetailHtml()) are unchanged -
// only the scan's file scope changed.
//
// Two-mode task: the tool window now has BOTH buttons. "Scan File"
// (testButton/startScan/runScan - the current-file implementation above,
// kept as-is) scans only the active editor file; "Scan Project"
// (scanProjectButton/startProjectScan/runProjectScan) is the original
// whole-project scan restored from the pre-rename code - ProjectFileCollector
// walk, chunked /developer/scan batches, same classification/grouping. Both
// share one isScanning guard and one findings list, and each clears the list
// before it starts so the two modes never mix stale findings.
//
// Scan-target prompt: clicking "Scan File" no longer scans immediately - it
// opens ScanFileDialog (Scan Current File / Choose Another File / Cancel; the
// current open file is shown only there - never in the tool window). The
// current file, or the file the user chooses (opened and made active), is
// passed to the SAME file-scan path (startScanOfFile -> runScan).
//
// Phase 5B: also the single "detail view" surface for the real-time
// /predict path - ShowFindingDetailsIntention (attached to editor
// annotations by CodeSentinelAnnotator) calls MyToolWindow.showFinding()
// to add a real-time finding to this SAME list, rendered with the SAME
// renderDetailHtml() (now surfaced as a hover tooltip - see
// FindingListCellRenderer below - rather than a separate fixed panel).
//
// UI-presentation task: dashboard-style redesign (header/status/summary
// cards/grouped compact rows/empty state) - detection, classification,
// deduplication, grouping, and navigation logic are UNCHANGED; only how
// the same underlying data is presented changed. `startScan`,
// `isScanning`, `listModel`, and `summaryLabel` keep their exact names/
// types since existing tests access them by reflection.
//
// Promoted to a top-level class (was nested in MyToolWindowFactory) so
// ShowFindingDetailsIntention, in a different file, can reference
// MyToolWindow.showFinding() directly.
class MyToolWindow(
        private val project: Project
) {

        companion object {
            // One MyToolWindow instance is created per project (see
            // MyToolWindowFactory.createToolWindowContent) - this registry
            // lets a real-time editor action reach that same instance
            // instead of building a second, disconnected UI.
            val registry = java.util.concurrent.ConcurrentHashMap<Project, MyToolWindow>()

            fun showFinding(project: Project, view: FindingDetailView) {
                ToolWindowManager.getInstance(project).getToolWindow(DUALVULNDROID_TOOL_WINDOW_ID)?.activate(null)
                registry[project]?.showFindingInstance(view)
            }

            private val STATUS_READY = JBColor.GRAY
            private val STATUS_SCANNING = JBColor(0x3592C4, 0x548AF7)
            private val STATUS_COMPLETE = JBColor(0x369650, 0x59A869)
            private val STATUS_ERROR = JBColor(0xC1282D, 0xFF6B68)

            const val SCAN_FILE_LABEL = "Scan File"
            const val SCAN_PROJECT_LABEL = "Scan Project"
            const val NO_FILE_OPEN_MESSAGE = "No file is currently open."
            const val UNSUPPORTED_FILE_MESSAGE = "Only Kotlin (.kt) and Java (.java) files can be scanned."
        }

        private val titleLabel = JBLabel("DualVulnDroid").apply {
            font = font.deriveFont(Font.BOLD, font.size2D + 2f)
        }
        private val subtitleLabel = JBLabel("CodeSentinel").apply {
            font = font.deriveFont(Font.BOLD)
            foreground = JBColor.namedColor("Label.infoForeground", JBColor.GRAY)
        }
        private val captionLabel = JBLabel("Android source security analysis").apply {
            font = font.deriveFont(font.size2D - 1f)
            foreground = JBColor.namedColor("Label.infoForeground", JBColor.GRAY)
        }

        // "Scan File": the existing current-file scan (startScan/runScan).
        private val testButton = JButton(SCAN_FILE_LABEL)

        // "Scan Project": the restored whole-project scan.
        private val scanProjectButton = JButton(SCAN_PROJECT_LABEL)

        // Item 1: a concise "● <state>" status row instead of long
        // technical progress text - the dot's color also carries the
        // state (grey/blue/green/red), all via JBColor so it stays
        // correct in both IntelliJ themes.
        private val statusDot = JBLabel("●")
        private val statusLabel = JBLabel("Ready")

        // Item 2/12: kept as ONE JBLabel (existing tests read its .text
        // for the exact "SQL Injection (CWE-89): N" / "Total findings: N"
        // / "Files scanned: N" substrings) - now rendered as a compact
        // 3-card HTML table instead of a single ad hoc paragraph.
        private val summaryLabel = JBLabel(readySummaryHtml()).apply {
            verticalAlignment = SwingConstants.TOP
        }

        private val findingsSectionLabel = JBLabel("SECURITY FINDINGS").apply {
            font = font.deriveFont(Font.BOLD)
            border = JBUI.Borders.empty(8, 4, 4, 4)
        }

        private val listModel = DefaultListModel<FindingEntry>()

        // Item 4/6: a custom renderer (below) draws each row compactly and
        // inserts a CWE section header whenever the group changes (item 5)
        // - the underlying model stays a flat DefaultListModel<FindingEntry>
        // (existing tests iterate it directly), only its ON-SCREEN
        // presentation is grouped. A single click navigates immediately
        // via the SAME, unchanged navigateToFinding() (item 4); hovering a
        // row shows the existing rich renderDetailHtml() detail as a
        // tooltip instead of a separate always-visible panel.
        private val findingsList = object : JBList<FindingEntry>(listModel) {
            override fun getToolTipText(event: MouseEvent): String? {
                val index = locationToIndex(event.point)
                if (index < 0) return null
                return renderDetailHtml(model.getElementAt(index).view)
            }
        }.apply {
            selectionMode = javax.swing.ListSelectionModel.SINGLE_SELECTION
            cellRenderer = FindingListCellRenderer()
            emptyText.text = "Click “Scan Project” or “Scan File” to begin"
            addMouseListener(object : MouseAdapter() {
                override fun mouseClicked(e: MouseEvent) {
                    val index = locationToIndex(e.point)
                    if (index < 0) return
                    val entry = model.getElementAt(index)
                    selectedIndex = index
                    navigateToFinding(project, entry)
                }
            })
        }

        @Volatile
        private var isScanning = false

        private val headerPanel = JBPanel<JBPanel<*>>().apply {
            layout = BoxLayout(this, BoxLayout.Y_AXIS)
            border = JBUI.Borders.empty(8, 8, 4, 8)
            alignmentX = Component.LEFT_ALIGNMENT

            add(titleLabel.alignLeft())
            add(subtitleLabel.alignLeft())
            add(captionLabel.alignLeft())
            add(javax.swing.Box.createVerticalStrut(6))
            add(JBPanel<JBPanel<*>>().apply {
                layout = BoxLayout(this, BoxLayout.X_AXIS)
                alignmentX = Component.LEFT_ALIGNMENT
                add(scanProjectButton)
                add(javax.swing.Box.createHorizontalStrut(6))
                add(testButton)
            })
            add(javax.swing.Box.createVerticalStrut(8))
            add(JBPanel<JBPanel<*>>().apply {
                layout = BoxLayout(this, BoxLayout.X_AXIS)
                alignmentX = Component.LEFT_ALIGNMENT
                statusDot.foreground = STATUS_READY
                add(statusDot)
                add(javax.swing.Box.createHorizontalStrut(4))
                add(statusLabel)
            })
            add(javax.swing.Box.createVerticalStrut(8))
            add(summaryLabel.alignLeft())
            add(javax.swing.Box.createVerticalStrut(4))
            add(findingsSectionLabel.alignLeft())
        }

        private val content: JBPanel<JBPanel<*>> =
            JBPanel<JBPanel<*>>().apply {
                layout = BorderLayout()
                add(headerPanel, BorderLayout.NORTH)
                // Item 6: only the findings area scrolls - the header
                // (title/button/status/summary cards) stays visible.
                add(JBScrollPane(findingsList), BorderLayout.CENTER)

                testButton.addActionListener { onScanFileClicked(project) }
                scanProjectButton.addActionListener { startProjectScan(project) }
            }

        // "Scan File" never scans straight away - it first asks which file
        // (ScanFileDialog). Both hooks are swappable so tests can answer
        // the dialog/chooser without a real modal.
        internal var scanFilePrompt: (ScanFilePromptInfo) -> ScanFileChoice = { showScanFileDialog(project, it) }
        internal var sourceFileChooser: () -> VirtualFile? = { chooseSourceFileToScan(project) }

        fun getContent(): JBPanel<JBPanel<*>> = content

        private fun activeEditorFile(): VirtualFile? =
            FileEditorManager.getInstance(project).selectedFiles.firstOrNull()

        private fun setScanButtonsEnabled(enabled: Boolean) {
            testButton.isEnabled = enabled
            scanProjectButton.isEnabled = enabled
        }

        // Phase 5B, section 7: entry point used by ShowFindingDetailsIntention
        // (attached to real-time editor annotations) - adds this ONE
        // real-time finding to the SAME list this tool window renders,
        // scrolling/selecting it so it's immediately visible.
        fun showFindingInstance(view: FindingDetailView, navigableFile: File? = null) {
            ApplicationManager.getApplication().invokeLater {
                val entry = FindingEntry(view, navigableFile)
                listModel.addElement(entry)
                findingsList.setSelectedValue(entry, true)
            }
        }

        // REQUIRED BEHAVIOR item 2/10: the ONLY source of "what to scan" is
        // the file currently open/selected in the editor - FileEditorManager's
        // own selectedFiles, never ProjectFileCollector's whole-project walk.
        private sealed class CurrentFileSelection {
            object NoFileSelected : CurrentFileSelection()
            object UnsupportedFile : CurrentFileSelection()
            data class Supported(
                val virtualFile: VirtualFile,
                val relativePath: String,
                val fileText: String
            ) : CurrentFileSelection()
        }

        // Resolves the file to scan straight from the live in-memory
        // Document (never disk) - so an unsaved Quick Fix edit
        // (SafeSqlQuickFixKotlin/Java, SafeHostnameVerifierQuickFixKotlin/
        // Java mutate the PSI/Document in memory but never write to disk
        // themselves) is picked up on the very next click, exactly like the
        // real-time annotator already does (item 7).
        private fun resolveFileSelection(project: Project, target: VirtualFile?): CurrentFileSelection {
            val virtualFile = target ?: return CurrentFileSelection.NoFileSelected

            if (!isScannableSourceFile(virtualFile)) {
                return CurrentFileSelection.UnsupportedFile
            }

            val fileText = FileDocumentManager.getInstance().getDocument(virtualFile)?.text
                ?: return CurrentFileSelection.UnsupportedFile

            return CurrentFileSelection.Supported(
                virtualFile = virtualFile,
                relativePath = relativeFilePath(project.basePath, virtualFile.path),
                fileText = fileText
            )
        }

        // "Scan File" click: shows the dialog, then either
        // [Scan Current File] -> scan exactly the active editor VirtualFile, or
        // [Choose Another File]/[Choose File] -> native chooser -> open the
        // chosen file as the active tab -> scan exactly that VirtualFile.
        // Nothing is scanned without one of those explicit clicks. Cancel - of
        // the dialog or of the chooser - changes nothing: no scan, no editor
        // switch, findings and status left exactly as they were.
        private fun onScanFileClicked(project: Project) {
            if (isScanning) return

            val editorFile = activeEditorFile()
            val info = when {
                editorFile == null -> ScanFilePromptInfo(null, null, CurrentFileStatus.NONE)
                else -> ScanFilePromptInfo(
                    editorFile.name,
                    relativeFilePath(project.basePath, editorFile.path),
                    if (isScannableSourceFile(editorFile)) CurrentFileStatus.SUPPORTED else CurrentFileStatus.UNSUPPORTED
                )
            }

            when (scanFilePrompt(info)) {
                ScanFileChoice.CANCEL -> return
                // The active editor VirtualFile, straight into the SAME
                // file-scan path - no chooser, never the whole project.
                ScanFileChoice.SCAN_CURRENT_FILE -> {
                    if (!info.canScanCurrentFile) return // not offered for unsupported/no file
                    startScanOfFile(project, editorFile)
                }
                ScanFileChoice.CHOOSE_FILE -> chooseAndScanFile(project)
            }
        }

        // The file-selection step of Scan File -> [Choose (Another) File]: native
        // chooser (.kt/.java) -> open + activate -> scan exactly that
        // VirtualFile. Cancelling the chooser changes nothing.
        private fun chooseAndScanFile(project: Project) {
            if (isScanning) return
            val chosen = sourceFileChooser() ?: return
            // Open the chosen file the normal IntelliJ way (reuses its tab if
            // already open) and make it the active editor - the scan uses
            // this same `chosen` file, never whatever tab was active before.
            FileEditorManager.getInstance(project).openFile(chosen, true)
            startScanOfFile(project, chosen)
        }

        private fun startScanOfFile(project: Project, target: VirtualFile?) {
            if (isScanning) {
                return // section 15: prevent duplicate simultaneous scans
            }

            // REQUIRED BEHAVIOR item 10: the ONE chosen file -> read its
            // current Document -> scan ONLY this file -> existing backend
            // -> existing finding parser -> Tool Window results.
            val selection = ReadAction.compute<CurrentFileSelection, Exception> {
                resolveFileSelection(project, target)
            }

            when (selection) {
                is CurrentFileSelection.NoFileSelected -> {
                    listModel.clear()
                    setStatus("Ready", STATUS_ERROR)
                    setEmptyText(NO_FILE_OPEN_MESSAGE, null, null)
                    setSummary(readySummaryHtml())
                }
                is CurrentFileSelection.UnsupportedFile -> {
                    listModel.clear()
                    setStatus("Ready", STATUS_ERROR)
                    setEmptyText(UNSUPPORTED_FILE_MESSAGE, null, null)
                    setSummary(readySummaryHtml())
                }
                is CurrentFileSelection.Supported -> {
                    isScanning = true
                    setScanButtonsEnabled(false)
                    testButton.text = "Scanning..."
                    listModel.clear()
                    findingsList.emptyText.text = "Scanning..."
                    setStatus("Scanning...", STATUS_SCANNING)
                    setSummary(readySummaryHtml())

                    ProgressManagerCompat.runBackgroundable(project, "DualVulnDroid: Scanning ${selection.relativePath}") { indicator ->
                        runScan(project, selection, indicator)
                    }
                }
            }
        }

        // REQUIRED BEHAVIOR item 4: sends ONLY the current file's source to
        // the EXISTING /developer/scan endpoint (APIClient.scanProjectBatch,
        // as a batch of exactly one file) and reuses the EXACT SAME
        // classification/grouping/finding-parsing logic project-wide
        // scanning already used (classify(), groupDetectionsByType(),
        // toDetailView()) - no second, parallel scanning architecture, and
        // no change to the backend contract itself.
        private fun runScan(project: Project, selection: CurrentFileSelection.Supported, indicator: ProgressIndicator) {
            val startedAt = System.nanoTime()
            try {
                indicator.text = "Checking backend availability..."
                val availability = APIClient().checkBackendAvailability()
                if (availability.status != APIClient.BackendAvailability.AVAILABLE) {
                    println("[CodeSentinel] Backend not available: ${availability.detail}")
                    setStatus("Backend unavailable", STATUS_ERROR)
                    setEmptyText("Backend unavailable", availability.detail, null)
                    setSummary(errorSummaryHtml(availability.detail))
                    return
                }

                indicator.text = "Analyzing ${selection.relativePath}..."
                val api = APIClient()
                val request = listOf(BatchScanFileRequest(selection.fileText, selection.relativePath))
                // P0 Step 6: lets the IDE's own progress-bar Cancel button
                // actually abort a hung/in-flight request immediately - see
                // APIClient.scanProjectBatch's own comment for the full
                // investigation.
                val response = api.scanProjectBatch(request) { indicator.isCanceled }

                if (response == null) {
                    val message = api.lastBatchError ?: "Unknown error contacting backend."
                    println("[CodeSentinel] Scan failed: $message")
                    setStatus("Scan failed", STATUS_ERROR)
                    setEmptyText("Scan failed", message, null)
                    setSummary(errorSummaryHtml(message))
                    return
                }

                indicator.text = "Analyzing results..."
                val fileResult = response.files.firstOrNull()
                if (fileResult?.error != null) {
                    println("[CodeSentinel] ${fileResult.fileName}: ${fileResult.error}")
                    setStatus("Scan failed", STATUS_ERROR)
                    setEmptyText("Scan failed", fileResult.error, null)
                    setSummary(errorSummaryHtml(fileResult.error))
                    return
                }

                // REQUIRED BEHAVIOR item 5: previous findings were already
                // cleared in startScan() before this background task was
                // queued - listModel only ever holds THIS file's findings.
                val findings = mutableListOf<FindingEntry>()
                // STEP 9/item 10 (of the UI task): a stable finding identity
                // - normalized relative path + canonical CWE + line - so a
                // detection that legitimately appears more than once (e.g.
                // present in overlapping evidence) is never listed twice.
                val seenFindingKeys = HashSet<String>()
                var sqlCount = 0
                var certCount = 0
                var reviewCount = 0

                val result = fileResult?.result
                if (result != null) {
                    // UI-presentation task, item 2: the SAME shared
                    // classification rule the real-time annotator uses (see
                    // FindingModel.kt's classify(DeveloperScanResult) for
                    // the full rationale).
                    val classification = classify(result)
                    if (classification != FindingClassification.NONE) {
                        // Critical bug fix: a single response describes ONE
                        // file's fused, file-level verdict, but predict_code()
                        // always runs BOTH the SQL and certificate analyzers,
                        // so `detections` can legitimately contain BOTH
                        // types even though the response's own
                        // vulnerabilityType/cwe names only one (confirmed
                        // against a real live /developer/scan response - see
                        // FindingModel.kt's groupDetectionsByType() comment).
                        // Grouping by each DETECTION's own type - never the
                        // response-level one - is what keeps a CWE-295
                        // detection from ever being mislabeled CWE-89 (or
                        // vice versa) merely because the OTHER type was also
                        // present in this same file's response.
                        val typeGroups = groupDetectionsByType(result.detections, classification)
                        for (group in typeGroups) {
                            if (classification == FindingClassification.REVIEW) reviewCount++
                            val canonicalType = canonicalVulnerability(group.vulnerabilityType)?.first ?: group.vulnerabilityType
                            if (canonicalType == "SQL Injection") sqlCount++
                            if (canonicalType == "Certificate Validation") certCount++

                            val anchorLine = group.anchorDetections.maxByOrNull { it.line }?.line
                            val key = findingKey(selection.relativePath, canonicalType, anchorLine)
                            if (seenFindingKeys.add(key)) {
                                findings.add(
                                    FindingEntry(
                                        result.toDetailView(selection.relativePath, group, classification == FindingClassification.REVIEW),
                                        File(selection.virtualFile.path)
                                    )
                                )
                            }
                        }
                    }
                }

                println("[CodeSentinel] Receiving security results... done.")
                // UI task, item 5: group findings by CWE type, then line, so
                // related findings read together rather than in arbitrary
                // detection-arrival order.
                findings
                    .sortedWith(compareBy({ it.view.cwe ?: it.view.vulnerabilityType }, { it.view.line ?: -1 }))
                    .forEach { listModel.addElement(it) }

                if (findings.isEmpty()) {
                    setEmptyText("No security findings detected", "${selection.relativePath} scanned successfully.", 1)
                }

                val durationMillis = (System.nanoTime() - startedAt) / 1_000_000
                setStatus("Scan complete", STATUS_COMPLETE)
                setSummary(
                    projectSummaryHtml(
                        filesScanned = 1,
                        filesFailed = 0,
                        sqlCount = sqlCount,
                        certCount = certCount,
                        reviewCount = reviewCount,
                        totalFindings = findings.size,
                        durationMillis = durationMillis
                    )
                )
            } catch (e: ProcessCanceledException) {
                setStatus("Scan cancelled", STATUS_ERROR)
                throw e
            } catch (e: Exception) {
                setStatus("Scan failed", STATUS_ERROR)
                println("[CodeSentinel] Scan failed: ${e.message}")
                e.printStackTrace()
            } finally {
                ApplicationManager.getApplication().invokeLater {
                    isScanning = false
                    setScanButtonsEnabled(true)
                    testButton.text = SCAN_FILE_LABEL
                }
            }
        }

        // ---- Scan Project: the original whole-project scan, restored from
        // the pre-rename implementation. Same backend contract
        // (/developer/scan via APIClient.scanProjectBatch), same
        // ProjectFileCollector walk/chunking, same classify()/
        // groupDetectionsByType()/toDetailView() - only the entry point
        // and final status text ("Project scan complete") are new. ----
        private fun startProjectScan(project: Project) {
            if (isScanning) {
                return // shared guard: never a project scan and a file scan at once
            }
            val basePath = project.basePath
            if (basePath == null) {
                setStatus("Ready", STATUS_ERROR, "Project path not found")
                return
            }

            // ProjectFileCollector reads file contents from disk, so flush
            // every open document first - an applied-but-unsaved Quick Fix
            // is then scanned as the CURRENT editor content.
            FileDocumentManager.getInstance().saveAllDocuments()

            isScanning = true
            setScanButtonsEnabled(false)
            scanProjectButton.text = "Scanning..."
            listModel.clear()
            findingsList.emptyText.text = "Scanning project..."
            setStatus("Scanning project...", STATUS_SCANNING)
            setSummary(readySummaryHtml())

            ProgressManagerCompat.runBackgroundable(project, "DualVulnDroid: Scanning Project") { indicator ->
                runProjectScan(project, basePath, indicator)
            }
        }

        private fun runProjectScan(project: Project, basePath: String, indicator: ProgressIndicator) {
            val startedAt = System.nanoTime()
            try {
                indicator.text = "Checking backend availability..."
                val availability = APIClient().checkBackendAvailability()
                if (availability.status != APIClient.BackendAvailability.AVAILABLE) {
                    println("[CodeSentinel] Backend not available: ${availability.detail}")
                    setStatus("Backend unavailable", STATUS_ERROR)
                    setEmptyText("Backend unavailable", availability.detail, null)
                    setSummary(errorSummaryHtml(availability.detail))
                    return
                }

                indicator.text = "Collecting source files..."
                val sourceRoots = discoverSourceRoots(project, basePath)
                val collected = mergeCollect(basePath, sourceRoots)
                println(
                    "[CodeSentinel] Files collected: ${collected.files.size} " +
                        "(skipped: ${collected.skippedEmpty} empty, ${collected.skippedDuplicate} duplicate, ${collected.skippedOversized} oversized)"
                )

                if (collected.files.isEmpty()) {
                    setStatus("Project scan complete", STATUS_COMPLETE)
                    setEmptyText("No supported Java/Kotlin source files found", null, 0)
                    setSummary(readySummaryHtml())
                    return
                }

                val batches = ProjectFileCollector.chunk(collected.files)
                val allFindings = mutableListOf<FindingEntry>()
                val seenFindingKeys = HashSet<String>()
                var filesScanned = 0
                var filesFailed = 0
                var sqlCount = 0
                var certCount = 0
                var reviewCount = 0

                for ((batchIndex, batch) in batches.withIndex()) {
                    indicator.checkCanceled()
                    println("[CodeSentinel] Uploading batch ${batchIndex + 1}/${batches.size} (${batch.size} files) for analysis...")

                    val request = batch.map { BatchScanFileRequest(it.content, it.relativePath) }
                    val api = APIClient()
                    val response = api.scanProjectBatch(request) { indicator.isCanceled }

                    if (response == null) {
                        val message = api.lastBatchError ?: "Unknown error contacting backend."
                        println("[CodeSentinel] Batch ${batchIndex + 1} failed: $message")
                        // Preserve whatever earlier batches already found -
                        // only the remaining, unscanned files are lost.
                        allFindings.forEach { listModel.addElement(it) }
                        setStatus("Scan failed", STATUS_ERROR)
                        if (allFindings.isEmpty()) setEmptyText("Scan failed", message, null)
                        setSummary(errorSummaryHtml(message, filesScanned, allFindings.size))
                        return
                    }

                    indicator.text = "Analyzing results..."
                    val byPath = batch.associateBy { it.relativePath }

                    for (fileResult in response.files) {
                        val collectedFile = byPath[fileResult.fileName]
                        if (fileResult.error != null) {
                            filesFailed++
                            println("[CodeSentinel] ${fileResult.fileName}: ${fileResult.error}")
                            continue
                        }
                        val result = fileResult.result ?: continue
                        filesScanned++

                        val classification = classify(result)
                        if (classification == FindingClassification.NONE) continue

                        // Group by each DETECTION's own type (see
                        // groupDetectionsByType) so a CWE-295 detection is
                        // never mislabeled CWE-89 or vice versa; one entry
                        // per (file, CWE type) keeps Total = SQL + Cert.
                        val typeGroups = groupDetectionsByType(result.detections, classification)
                        for (group in typeGroups) {
                            if (classification == FindingClassification.REVIEW) reviewCount++
                            val canonicalType = canonicalVulnerability(group.vulnerabilityType)?.first ?: group.vulnerabilityType
                            if (canonicalType == "SQL Injection") sqlCount++
                            if (canonicalType == "Certificate Validation") certCount++

                            val anchorLine = group.anchorDetections.maxByOrNull { it.line }?.line
                            val key = findingKey(fileResult.fileName, canonicalType, anchorLine)
                            if (seenFindingKeys.add(key)) {
                                allFindings.add(
                                    FindingEntry(
                                        result.toDetailView(fileResult.fileName, group, classification == FindingClassification.REVIEW),
                                        collectedFile?.absoluteFile
                                    )
                                )
                            }
                        }
                    }
                }

                println("[CodeSentinel] Receiving security results... done.")
                allFindings
                    .sortedWith(
                        compareBy(
                            { it.view.cwe ?: it.view.vulnerabilityType },
                            { it.view.fileName },
                            { it.view.line ?: -1 }
                        )
                    )
                    .forEach { listModel.addElement(it) }

                if (allFindings.isEmpty()) {
                    setEmptyText("No security findings detected", "Project scan completed successfully.", filesScanned)
                }

                val durationMillis = (System.nanoTime() - startedAt) / 1_000_000
                setStatus("Project scan complete", STATUS_COMPLETE)
                setSummary(
                    projectSummaryHtml(
                        filesScanned = filesScanned,
                        filesFailed = filesFailed,
                        sqlCount = sqlCount,
                        certCount = certCount,
                        reviewCount = reviewCount,
                        totalFindings = allFindings.size,
                        durationMillis = durationMillis
                    )
                )

                // Existing local network-security check, preserved as before
                // (logged, not shown in the compact status row).
                val networkIssues = NetworkSecurityScanner.scan(basePath)
                if (networkIssues.isNotEmpty()) {
                    val issue = networkIssues.first()
                    println("[CodeSentinel] Also found a network security issue in ${issue.file}: ${issue.message}")
                }
            } catch (e: ProcessCanceledException) {
                setStatus("Scan cancelled", STATUS_ERROR)
                throw e
            } catch (e: Exception) {
                setStatus("Scan failed", STATUS_ERROR)
                println("[CodeSentinel] Project scan failed: ${e.message}")
                e.printStackTrace()
            } finally {
                ApplicationManager.getApplication().invokeLater {
                    isScanning = false
                    setScanButtonsEnabled(true)
                    scanProjectButton.text = SCAN_PROJECT_LABEL
                }
            }
        }

        // Layered source-root discovery (restored): IntelliJ's registered
        // content source roots first; if none, the project base directory
        // (ProjectFileCollector already excludes build/.gradle/.idea/etc.).
        private fun discoverSourceRoots(project: Project, basePath: String): List<File> {
            val ideRoots = try {
                ReadAction.compute<List<File>, Exception> {
                    ProjectRootManager.getInstance(project).contentSourceRoots
                        .mapNotNull { it.canonicalPath }
                        .map { File(it) }
                        .filter { it.exists() }
                }
            } catch (e: Exception) {
                println("[CodeSentinel] Could not read IntelliJ source roots, falling back to project base directory: ${e.message}")
                emptyList()
            }
            return ideRoots.ifEmpty { listOf(File(basePath)) }
        }

        // Collects from every discovered root, de-duplicating by
        // project-relative path (roots can legitimately overlap).
        private fun mergeCollect(basePath: String, roots: List<File>): ProjectFileCollector.CollectionResult {
            val seenRelativePaths = HashSet<String>()
            val files = mutableListOf<ProjectFileCollector.CollectedFile>()
            var skippedEmpty = 0
            var skippedDuplicate = 0
            var skippedOversized = 0

            for (root in roots) {
                if (!root.exists()) continue
                val result = ProjectFileCollector.collect(basePath, root)
                for (file in result.files) {
                    if (seenRelativePaths.add(file.relativePath)) {
                        files.add(file)
                    } else {
                        skippedDuplicate++
                    }
                }
                skippedEmpty += result.skippedEmpty
                skippedDuplicate += result.skippedDuplicate
                skippedOversized += result.skippedOversized
            }

            return ProjectFileCollector.CollectionResult(files, skippedEmpty, skippedDuplicate, skippedOversized)
        }

        // Project-relative, forward-slash path for the currently selected
        // file (e.g. "src/SqlInjectionVulnerable.kt") - mirrors
        // ProjectFileCollector's own relativize() convention (section 6) so
        // findings display a real project-relative path, never an absolute
        // local filesystem path, falling back to the bare file name only
        // when no project base directory is available.
        private fun relativeFilePath(basePath: String?, absolutePath: String): String {
            if (basePath == null) return File(absolutePath).name
            return try {
                val base = File(basePath).canonicalFile.toPath()
                val file = File(absolutePath).canonicalFile.toPath()
                base.relativize(file).toString().replace(File.separatorChar, '/')
            } catch (e: Exception) {
                File(absolutePath).name
            }
        }

        // Item 1/7/8: ONE concise status string plus a JBColor-driven dot -
        // never the old verbose per-batch technical text (that detail now
        // only ever goes to println/log, see runScan above).
        private fun setStatus(text: String, color: JBColor, detail: String? = null) {
            ApplicationManager.getApplication().invokeLater {
                statusLabel.text = text
                statusDot.foreground = color
                if (detail != null) statusLabel.toolTipText = detail
            }
        }

        private fun setSummary(html: String) {
            ApplicationManager.getApplication().invokeLater { summaryLabel.text = html }
        }

        // Item 3/12: replaces the platform's own generic "Nothing to show"
        // with a clear, centered explanation of WHY the list is empty -
        // never a giant unexplained blank panel.
        private fun setEmptyText(primary: String, secondary: String?, filesScanned: Int?) {
            ApplicationManager.getApplication().invokeLater {
                findingsList.emptyText.apply {
                    clear()
                    appendText(primary)
                    if (secondary != null) {
                        appendSecondaryText(secondary, com.intellij.ui.SimpleTextAttributes.REGULAR_ATTRIBUTES, null)
                    }
                    if (filesScanned != null) {
                        appendSecondaryText(
                            "Files scanned: $filesScanned",
                            com.intellij.ui.SimpleTextAttributes.GRAYED_ATTRIBUTES, null
                        )
                    }
                }
            }
        }
    }

// UI-presentation task, item 9: a stable finding identity - normalized
// relative file path + canonical CWE/vulnerability type + line - so the
// SAME underlying finding is never counted or listed twice, whether it
// came from overlapping detections within one scan or (in principle) from
// two different call sites converging on the same file.
private fun findingKey(fileName: String, canonicalType: String, line: Int?): String =
    "${fileName.replace('\\', '/')}|$canonicalType|${line ?: -1}"

// One row in the findings list - wraps the shared FindingDetailView
// (see FindingModel.kt) with the extra bit only the plugin's local
// filesystem knowledge can supply: the actual File to navigate to.
// Real-time findings and project-scan findings are indistinguishable
// once wrapped here - both render via the SAME renderDetailHtml() (now
// shown as a hover tooltip - see FindingListCellRenderer below).
//
// toString() is kept as a plain-text fallback (logs/debug output only -
// FindingListCellRenderer, not toString(), is what actually paints the
// on-screen row; it uses real Swing components/JBColor so it stays
// correct in both IntelliJ themes, unlike a fixed hardcoded HTML color).
data class FindingEntry(
    val view: FindingDetailView,
    val navigableFile: File? = null
) {
    override fun toString(): String {
        val cwePrefix = view.cwe?.let { "[$it] " } ?: ""
        val statusText = if (view.reviewLevel) "NEEDS REVIEW" else "CONFIRMED"
        return "$cwePrefix${view.vulnerabilityType} @ ${view.location} - ${"%.0f".format(view.confidence)}% - $statusText"
    }
}

private fun <T : javax.swing.JComponent> T.alignLeft(): T = apply { alignmentX = Component.LEFT_ALIGNMENT }

// UI-presentation task, item 5/6: groups consecutive same-CWE rows under a
// bold section header ("SQL INJECTION (CWE-89)") and renders each finding
// as a compact 3-line row - "[CWE-89] SQL Injection", "file : line N",
// "Confidence: NN%   STATUS" - using ONLY real Swing components/JBColor
// (never hardcoded RGB literals baked into HTML) so both the section
// headers and the CONFIRMED/NEEDS REVIEW status color stay correct in
// both light and dark IntelliJ themes. The underlying list model is
// untouched (still one FindingEntry per finding, sorted by CWE/file/line
// in runScan above) - this renderer only decides, per row, whether to
// also draw a header above it by comparing to the PREVIOUS row's CWE.
// internal (not private) so presentation tests can exercise the real
// renderer directly rather than reaching into Swing internals via
// reflection.
internal class FindingListCellRenderer : ListCellRenderer<FindingEntry> {

    val statusConfirmedColor = JBColor(0xC1282D, 0xFF6B68)
    val statusReviewColor = JBColor(0xB08800, 0xE8BF6A)

    override fun getListCellRendererComponent(
        list: JList<out FindingEntry>,
        value: FindingEntry,
        index: Int,
        isSelected: Boolean,
        cellHasFocus: Boolean
    ): Component {
        val background = if (isSelected) UIUtil.getListSelectionBackground(true) else UIUtil.getListBackground()
        val foreground = if (isSelected) UIUtil.getListSelectionForeground(true) else UIUtil.getListForeground()

        val panel = JPanel().apply {
            layout = BoxLayout(this, BoxLayout.Y_AXIS)
            isOpaque = true
            this.background = background
        }

        val previousCwe = if (index > 0) list.model.getElementAt(index - 1).view.let { it.cwe ?: it.vulnerabilityType } else null
        val thisCwe = value.view.cwe ?: value.view.vulnerabilityType
        if (thisCwe != previousCwe) {
            val groupTitle = value.view.cwe?.let { "${value.view.vulnerabilityType.uppercase()} ($it)" }
                ?: value.view.vulnerabilityType.uppercase()
            panel.add(JBLabel(groupTitle).apply {
                font = font.deriveFont(Font.BOLD, font.size2D - 1f)
                this.foreground = if (isSelected) foreground else JBColor.namedColor("Label.infoForeground", JBColor.GRAY)
                border = JBUI.Borders.empty(if (index == 0) 2 else 8, 6, 2, 6)
                alignmentX = Component.LEFT_ALIGNMENT
            })
            panel.add(JSeparator().apply { alignmentX = Component.LEFT_ALIGNMENT })
        }

        val rowPanel = JPanel().apply {
            layout = BoxLayout(this, BoxLayout.Y_AXIS)
            isOpaque = false
            border = JBUI.Borders.empty(4, 10, 6, 6)
            alignmentX = Component.LEFT_ALIGNMENT
        }
        val cwePrefix = value.view.cwe?.let { "[$it] " } ?: ""
        rowPanel.add(JBLabel("$cwePrefix${value.view.vulnerabilityType}").apply {
            font = font.deriveFont(Font.BOLD)
            this.foreground = foreground
            alignmentX = Component.LEFT_ALIGNMENT
        })
        rowPanel.add(JBLabel(value.view.location).apply {
            this.foreground = foreground
            alignmentX = Component.LEFT_ALIGNMENT
        })
        rowPanel.add(JBPanel<JBPanel<*>>().apply {
            layout = BoxLayout(this, BoxLayout.X_AXIS)
            isOpaque = false
            alignmentX = Component.LEFT_ALIGNMENT
            add(JBLabel("Confidence: ${"%.0f".format(value.view.confidence)}%").apply { this.foreground = foreground })
            add(javax.swing.Box.createHorizontalStrut(12))
            val statusText = if (value.view.reviewLevel) "NEEDS REVIEW" else "CONFIRMED"
            val statusColor = if (value.view.reviewLevel) statusReviewColor else statusConfirmedColor
            add(JBLabel(statusText).apply {
                font = font.deriveFont(Font.BOLD)
                this.foreground = if (isSelected) foreground else statusColor
            })
        })
        panel.add(rowPanel)
        panel.add(JSeparator().apply { alignmentX = Component.LEFT_ALIGNMENT; this.foreground = JBColor.border() })

        return panel
    }
}

// UI-presentation task, item 1/12: the initial ("before any scan")
// summary state - same compact card layout, all zeros, no misleading claim.
private fun readySummaryHtml(): String = summaryCardsHtml(sqlCount = 0, certCount = 0, totalFindings = 0)

// Section 17 / UI-presentation task items 2/12: a compact 3-card summary
// - SQL INJECTION (CWE-89), CERTIFICATE VALIDATION (CWE-295), TOTAL
// FINDINGS - built as an HTML <table> (reliably supported by Swing's
// built-in HTML renderer, unlike CSS flexbox/inline-block) inside the
// SAME JBLabel existing tests already read via reflection. No background
// color is specified anywhere in this HTML - only the JBLabel's own
// (theme-correct) foreground/background show through, and the only
// explicit color is the table border, computed from the CURRENT theme's
// real border color (JBColor.border()) so it never breaks light mode
// with a color hardcoded for dark mode or vice versa.
private fun summaryCardsHtml(sqlCount: Int, certCount: Int, totalFindings: Int): String {
    val borderColor = JBColor.border().toHtmlHex()
    fun card(title: String, cwe: String?, count: Int): String =
        "<td style='border:1px solid $borderColor; padding:6px 10px; text-align:center'>" +
            "<b style='font-size:9px'>$title</b><br>" +
            (cwe?.let { "<span style='font-size:9px'>$it</span><br>" } ?: "") +
            "<span style='font-size:16px'><b>$count</b></span>" +
            "</td>"

    return "<html><body>" +
        "<h3 style='margin-bottom:4px'>CodeSentinel Scan Complete</h3>" +
        "<table cellspacing='0' cellpadding='0'><tr>" +
        card("SQL INJECTION", "CWE-89", sqlCount) +
        card("CERTIFICATE VALIDATION", "CWE-295", certCount) +
        card("TOTAL FINDINGS", null, totalFindings) +
        "</tr></table>" +
        // Exact substrings preserved for backward-compatible parsing
        // (SQL Injection (CWE-89): N / Certificate Validation (CWE-295): N /
        // Total findings: N) - kept as a visually-hidden line rather than
        // duplicated visible text, since the cards above already show the
        // same numbers to the user.
        "<p style='font-size:1px; color:$borderColor'>" +
        "SQL Injection (CWE-89): $sqlCount &nbsp; " +
        "Improper Certificate Validation (CWE-295): $certCount &nbsp; " +
        "Total findings: $totalFindings" +
        "</p>" +
        "</body></html>"
}

private fun projectSummaryHtml(
    filesScanned: Int,
    filesFailed: Int,
    sqlCount: Int,
    certCount: Int,
    reviewCount: Int,
    totalFindings: Int,
    durationMillis: Long? = null
): String {
    val base = summaryCardsHtml(sqlCount, certCount, totalFindings)
    val filesLine = "Files scanned: $filesScanned" +
        (if (filesFailed > 0) " ($filesFailed failed to scan)" else "") +
        (if (durationMillis != null) " · Scan time: ${formatScanDuration(durationMillis)}" else "")
    val reviewNote = if (reviewCount > 0) {
        "<p style='font-size:11px'><i>$reviewCount of $totalFindings finding(s) are SUSPICIOUS_REVIEW-level " +
            "(flagged for manual review, not auto-confirmed).</i></p>"
    } else ""
    return base.replace(
        "</body></html>",
        "<p style='font-size:11px'>$filesLine</p>$reviewNote</body></html>"
    )
}

/** Scan duration for the tool window: "850 ms" below one second, "2.4 s" above. */
internal fun formatScanDuration(millis: Long): String =
    if (millis < 1000) "$millis ms" else String.format(java.util.Locale.ROOT, "%.1f s", millis / 1000.0)

// UI-presentation task, item 8: "preserve any already-collected findings
// where appropriate" on failure - if earlier batches already produced
// real findings before this one failed, say so explicitly rather than
// just reporting the failure as if nothing had been found at all (those
// findings are still added to listModel by the caller before this is shown).
private fun errorSummaryHtml(message: String, filesScannedBeforeFailure: Int = 0, partialFindings: Int = 0): String {
    val sb = StringBuilder()
    sb.append("<html><body style='width: 400px'><h3>Scan failed</h3><p>${escapeHtml(message)}</p>")
    if (filesScannedBeforeFailure > 0) {
        sb.append(
            "<p><i>$filesScannedBeforeFailure file(s) were scanned before this failure, producing " +
                "$partialFindings finding(s) - shown below (partial results).</i></p>"
        )
    }
    sb.append("</body></html>")
    return sb.toString()
}

private fun java.awt.Color.toHtmlHex(): String = String.format("#%02x%02x%02x", red, green, blue)

// Section 13: resolve the finding's file relative to the CURRENT project
// state (we already hold the absolute File from collection time - we
// never trust a server-supplied path) and never crash if it moved/was
// deleted since the scan ran.
private fun navigateToFinding(project: Project, entry: FindingEntry) {
    val file = entry.navigableFile
    if (file == null || !file.exists()) {
        Messages.showWarningDialog(project, "Source file is no longer available.", "DualVulnDroid")
        return
    }
    val virtualFile = LocalFileSystem.getInstance().findFileByIoFile(file)
    if (virtualFile == null) {
        Messages.showWarningDialog(project, "Source file is no longer available.", "DualVulnDroid")
        return
    }
    ApplicationManager.getApplication().invokeLater {
        val line = entry.view.line
        val descriptor = if (line != null) {
            OpenFileDescriptor(project, virtualFile, line, 0)
        } else {
            OpenFileDescriptor(project, virtualFile)
        }
        FileEditorManager.getInstance(project).openTextEditor(descriptor, true)
    }
}

// Thin wrapper around Task.Backgroundable so the scan runs off the EDT
// (section 14) and integrates with the IDE's existing progress/cancel UI
// (section 15) without any custom cancellation infrastructure. Not
// private: FixVerificationRunner (Phase 6) reuses this same wrapper for
// its post-fix re-scan rather than duplicating it.
object ProgressManagerCompat {
    fun runBackgroundable(project: Project, title: String, work: (ProgressIndicator) -> Unit) {
        object : Task.Backgroundable(project, title, true) {
            override fun run(indicator: ProgressIndicator) {
                work(indicator)
            }
        }.queue()
    }
}
