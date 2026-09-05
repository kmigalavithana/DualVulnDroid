package com.dualvulndroid.dualvulndroid

import com.intellij.openapi.application.ApplicationManager
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

// Phase 5A: "Scan Project" now sends ONE batch request to
// POST /developer/scan instead of one /predict call per file (see
// APIClient.scanProjectBatch). This tool window remains the existing
// details-panel architecture from Phase 4, extended with a findings
// list so a project-level scan (many findings) is browsable, not just
// "stop at the first vulnerable file" like the old per-file loop did.
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

        private val testButton = JButton("Scan Project")

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
            emptyText.text = "Click “Scan Project” to begin"
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
            add(testButton.alignLeft())
            add(javax.swing.Box.createVerticalStrut(4))
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

                testButton.addActionListener { startScan(project) }
            }

        fun getContent(): JBPanel<JBPanel<*>> = content

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

        private fun startScan(project: Project) {
            if (isScanning) {
                return // section 15: prevent duplicate simultaneous scans
            }
            val basePath = project.basePath
            if (basePath == null) {
                setStatus("Ready", STATUS_ERROR, "Project path not found")
                return
            }

            // Plugin-fix task, root cause #2 (STEP 6): used to hard-require
            // "$basePath/app/src/main/java" to exist before even attempting
            // to collect files - failing with "Source folder not found!"
            // for any project that isn't laid out like a standard Android
            // Gradle module. Whether any usable source exists is now
            // determined by actually trying to collect files
            // (discoverSourceRoots()/mergeCollect() below), never by
            // checking one hardcoded path in advance.
            isScanning = true
            testButton.isEnabled = false
            testButton.text = "Scanning..."
            listModel.clear()
            findingsList.emptyText.text = "Scanning..."
            setStatus("Scanning...", STATUS_SCANNING)
            setSummary(readySummaryHtml())

            ProgressManagerCompat.runBackgroundable(project, "DualVulnDroid: Scanning Project") { indicator ->
                runScan(project, basePath, indicator)
            }
        }

        private fun runScan(project: Project, basePath: String, indicator: ProgressIndicator) {
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
                    setStatus("Scan complete", STATUS_COMPLETE)
                    setEmptyText("No supported Java/Kotlin source files found", null, 0)
                    setSummary(readySummaryHtml())
                    return
                }

                val batches = ProjectFileCollector.chunk(collected.files)
                val allFindings = mutableListOf<FindingEntry>()
                // STEP 9/item 10 (of the UI task): a stable finding identity
                // - normalized relative path + canonical CWE + line - so a
                // detection that legitimately appears more than once (e.g.
                // present in overlapping evidence) is never listed twice.
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
                    // P0 Step 6: lets the IDE's own progress-bar Cancel
                    // button actually abort a hung/in-flight batch request
                    // immediately, instead of the button silently staying
                    // disabled for up to scanProjectBatch's full read
                    // timeout - see APIClient.scanProjectBatch's own
                    // comment for the full investigation.
                    val response = api.scanProjectBatch(request) { indicator.isCanceled }

                    if (response == null) {
                        val message = api.lastBatchError ?: "Unknown error contacting backend."
                        println("[CodeSentinel] Batch ${batchIndex + 1} failed: $message")
                        // UI task, item 8: preserve whatever earlier batches
                        // already found rather than discarding it - only the
                        // REMAINING (unscanned) files are lost to this failure.
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

                        // UI-presentation task, item 2: the SAME shared
                        // classification rule the real-time annotator uses
                        // (see FindingModel.kt's classify(DeveloperScanResult)
                        // for the full rationale).
                        val classification = classify(result)
                        if (classification == FindingClassification.NONE) continue

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
                        // present in the same file's response.
                        //
                        // One FindingEntry per (file, CWE type) - never per
                        // individual evidentiary line - is what makes "Total
                        // findings" mathematically equal to
                        // sqlCount+certCount by construction: each type-group
                        // increments exactly one of those two counts AND
                        // adds exactly one entry.
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
                // UI task, item 5: group findings by CWE type, then file,
                // then line, so related findings read together rather than
                // in arbitrary batch-arrival order.
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

                setStatus("Scan complete", STATUS_COMPLETE)
                setSummary(
                    projectSummaryHtml(
                        filesScanned = filesScanned,
                        filesFailed = filesFailed,
                        sqlCount = sqlCount,
                        certCount = certCount,
                        reviewCount = reviewCount,
                        totalFindings = allFindings.size
                    )
                )

                // Existing local network-security check (unrelated to the
                // batch endpoint, preserved exactly as before) - technical
                // detail, logged rather than shown in the compact status row.
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
                println("[CodeSentinel] Scan failed: ${e.message}")
                e.printStackTrace()
            } finally {
                ApplicationManager.getApplication().invokeLater {
                    isScanning = false
                    testButton.isEnabled = true
                    testButton.text = "Scan Project"
                }
            }
        }

        // Plugin-fix task, STEP 6: layered source-root discovery.
        //   1. IntelliJ's own registered module content/source roots
        //      (covers standard Gradle/Android/Maven-synced projects -
        //      whatever layout the IDE itself already resolved).
        //   2. If that yields nothing (e.g. a plain project with no
        //      recognized build system, or a bare content root that
        //      IntelliJ hasn't marked as a dedicated source folder - the
        //      exact "untitled16/src/ss.java" case this task's live
        //      verification target is built from), fall back to the whole
        //      project base directory: ProjectFileCollector.collect()
        //      already walks it recursively and excludes build/.gradle/
        //      .idea/target/generated/out/node_modules/etc., so this is
        //      safe even for a large, real Android checkout.
        // Only ever reported as "no source files found" (see runScan
        // above) if this actually finds zero matching files - never
        // because one hardcoded path didn't exist.
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

        // Collects from every discovered root and merges the results,
        // de-duplicating by project-relative path (roots can legitimately
        // overlap, e.g. a module root and one of its own subdirectories).
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
    totalFindings: Int
): String {
    val base = summaryCardsHtml(sqlCount, certCount, totalFindings)
    val filesLine = "Files scanned: $filesScanned" + if (filesFailed > 0) " ($filesFailed failed to scan)" else ""
    val reviewNote = if (reviewCount > 0) {
        "<p style='font-size:11px'><i>$reviewCount of $totalFindings finding(s) are SUSPICIOUS_REVIEW-level " +
            "(flagged for manual review, not auto-confirmed).</i></p>"
    } else ""
    return base.replace(
        "</body></html>",
        "<p style='font-size:11px'>$filesLine</p>$reviewNote</body></html>"
    )
}

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
