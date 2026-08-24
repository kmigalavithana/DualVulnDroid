package com.dualvulndroid.dualvulndroid

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.fileEditor.OpenFileDescriptor
import com.intellij.openapi.progress.ProcessCanceledException
import com.intellij.openapi.progress.ProgressIndicator
import com.intellij.openapi.progress.Task
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.openapi.vfs.LocalFileSystem
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.openapi.wm.ToolWindowManager
import com.intellij.ui.components.JBLabel
import com.intellij.ui.components.JBList
import com.intellij.ui.components.JBPanel
import com.intellij.ui.components.JBScrollPane
import com.intellij.ui.content.ContentFactory
import java.io.File
import javax.swing.DefaultListModel
import javax.swing.JButton
import javax.swing.ListSelectionModel
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
// to add a real-time finding to this SAME list and render it with the
// SAME renderDetailHtml(), rather than duplicating the detail UI.
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
        }

        private val testButton = JButton("Scan Project")

        private val statusLabel = JBLabel(" ").apply {
            verticalAlignment = SwingConstants.TOP
        }

        private val summaryLabel = JBLabel("CodeSentinel Ready").apply {
            verticalAlignment = SwingConstants.TOP
        }

        private val listModel = DefaultListModel<FindingEntry>()
        private val findingsList = JBList(listModel).apply {
            selectionMode = ListSelectionModel.SINGLE_SELECTION
            visibleRowCount = 8
        }

        private val jumpButton = JButton("Jump to Source").apply {
            isEnabled = false
        }

        private val detailLabel = JBLabel(" ").apply {
            verticalAlignment = SwingConstants.TOP
        }

        @Volatile
        private var isScanning = false

        private val content: JBPanel<JBPanel<*>> =
            JBPanel<JBPanel<*>>().apply {
                layout = javax.swing.BoxLayout(this, javax.swing.BoxLayout.Y_AXIS)

                add(testButton)
                add(statusLabel)
                add(JBScrollPane(summaryLabel).apply { preferredSize = java.awt.Dimension(420, 90) })
                add(JBScrollPane(findingsList).apply { preferredSize = java.awt.Dimension(420, 140) })
                add(jumpButton)
                add(JBScrollPane(detailLabel).apply { preferredSize = java.awt.Dimension(420, 220) })

                findingsList.addListSelectionListener { e ->
                    if (!e.valueIsAdjusting) {
                        val selected = findingsList.selectedValue
                        jumpButton.isEnabled = selected?.navigableFile != null
                        detailLabel.text = selected?.let { renderDetailHtml(it.view) } ?: " "
                    }
                }

                jumpButton.addActionListener {
                    findingsList.selectedValue?.let { navigateToFinding(project, it) }
                }

                testButton.addActionListener { startScan(project) }
            }

        fun getContent(): JBPanel<JBPanel<*>> = content

        // Phase 5B, section 7: entry point used by ShowFindingDetailsIntention
        // (attached to real-time editor annotations) - adds this ONE
        // real-time finding to the SAME list/detail UI project scan uses,
        // and selects it so its detail is shown immediately.
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
                statusLabel.text = "Project path not found!"
                return
            }
            val sourceFolder = File("$basePath/app/src/main/java")
            if (!sourceFolder.exists()) {
                statusLabel.text = "Source folder not found!"
                return
            }

            isScanning = true
            testButton.isEnabled = false
            listModel.clear()
            summaryLabel.text = "Scanning..."
            detailLabel.text = " "
            statusLabel.text = "Scanning project..."

            ProgressManagerCompat.runBackgroundable(project, "DualVulnDroid: Scanning Project") { indicator ->
                runScan(project, basePath, sourceFolder, indicator)
            }
        }

        private fun runScan(project: Project, basePath: String, sourceFolder: File, indicator: ProgressIndicator) {
            try {
                indicator.text = "Collecting source files..."
                val collected = ProjectFileCollector.collect(basePath, sourceFolder)
                setStatus("Files collected: ${collected.files.size} " +
                    "(skipped: ${collected.skippedEmpty} empty, ${collected.skippedDuplicate} duplicate, ${collected.skippedOversized} oversized)")

                if (collected.files.isEmpty()) {
                    setStatus("No supported Java/Kotlin source files were found.")
                    setSummary("<html><b>No supported Java/Kotlin source files were found.</b></html>")
                    return
                }

                val batches = ProjectFileCollector.chunk(collected.files)
                val allFindings = mutableListOf<FindingEntry>()
                var filesScanned = 0
                var filesFailed = 0
                val vulnerableFiles = mutableSetOf<String>()
                var sqlCount = 0
                var certCount = 0
                var highestSeverityRank = -1
                var highestSeverity: String? = null

                for ((batchIndex, batch) in batches.withIndex()) {
                    indicator.checkCanceled()
                    setStatus("Uploading batch ${batchIndex + 1}/${batches.size} (${batch.size} files) for analysis...")

                    val request = batch.map { BatchScanFileRequest(it.content, it.relativePath) }
                    val api = APIClient()
                    val response = api.scanProjectBatch(request)

                    if (response == null) {
                        val message = api.lastBatchError ?: "Unknown error contacting backend."
                        setStatus("Batch ${batchIndex + 1} failed: $message")
                        setSummary(errorSummaryHtml(message))
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

                        if (result.vulnerable) {
                            vulnerableFiles.add(fileResult.fileName)
                            if (result.vulnerabilityType == "SQL Injection") sqlCount++
                            if (result.vulnerabilityType == "Certificate Validation") certCount++

                            val rank = SEVERITY_RANK[result.severity] ?: -1
                            if (rank > highestSeverityRank) {
                                highestSeverityRank = rank
                                highestSeverity = result.severity
                            }

                            val detections = result.detections
                            if (!detections.isNullOrEmpty()) {
                                detections.forEach { d ->
                                    allFindings.add(FindingEntry(result.toDetailView(fileResult.fileName, d.line), collectedFile?.absoluteFile))
                                }
                            } else {
                                allFindings.add(FindingEntry(result.toDetailView(fileResult.fileName, null), collectedFile?.absoluteFile))
                            }
                        }
                    }
                }

                setStatus("Receiving security results... done.")
                allFindings.forEach { listModel.addElement(it) }

                setSummary(
                    projectSummaryHtml(
                        filesScanned = filesScanned,
                        filesFailed = filesFailed,
                        vulnerableFileCount = vulnerableFiles.size,
                        sqlCount = sqlCount,
                        certCount = certCount,
                        highestSeverity = highestSeverity
                    )
                )

                // Existing local network-security check (unrelated to the
                // batch endpoint, preserved exactly as before).
                val networkIssues = NetworkSecurityScanner.scan(basePath)
                if (networkIssues.isNotEmpty()) {
                    val issue = networkIssues.first()
                    setStatus("Also found a network security issue in ${issue.file}: ${issue.message}")
                }

            } catch (e: ProcessCanceledException) {
                setStatus("Scan cancelled.")
                throw e
            } catch (e: Exception) {
                setStatus("Scan failed: ${e.message}")
                e.printStackTrace()
            } finally {
                ApplicationManager.getApplication().invokeLater {
                    isScanning = false
                    testButton.isEnabled = true
                }
            }
        }

        private fun setStatus(text: String) {
            ApplicationManager.getApplication().invokeLater { statusLabel.text = text }
        }

        private fun setSummary(html: String) {
            ApplicationManager.getApplication().invokeLater { summaryLabel.text = html }
        }
    }

private val SEVERITY_RANK = mapOf("LOW" to 0, "MEDIUM" to 1, "HIGH" to 2, "CRITICAL" to 3)

// One row in the findings list - wraps the shared FindingDetailView
// (see FindingModel.kt) with the extra bit only the plugin's local
// filesystem knowledge can supply: the actual File to navigate to.
// Real-time findings and project-scan findings are indistinguishable
// once wrapped here - both render via the SAME renderDetailHtml().
data class FindingEntry(
    val view: FindingDetailView,
    val navigableFile: File? = null
) {
    override fun toString(): String =
        "⚠ ${view.vulnerabilityType} [${view.severity ?: "?"}, ${"%.0f".format(view.confidence)}%]  ${view.location}"
}

// Section 17: only ever describes what was actually found - never a
// fabricated "100% safe" claim, never an invented numeric score.
private fun projectSummaryHtml(
    filesScanned: Int,
    filesFailed: Int,
    vulnerableFileCount: Int,
    sqlCount: Int,
    certCount: Int,
    highestSeverity: String?
): String {
    val sb = StringBuilder()
    sb.append("<html><body style='width: 400px'>")
    sb.append("<h2>Project Security</h2>")
    sb.append("<p><b>Files scanned:</b> $filesScanned")
    if (filesFailed > 0) sb.append(" &nbsp; (<b>$filesFailed</b> failed to scan)")
    sb.append("</p>")

    if (vulnerableFileCount == 0) {
        sb.append("<p>No detected CWE-89 or CWE-295 vulnerabilities in the analysed files.</p>")
        sb.append("<p><b>Risk:</b> LOW</p>")
    } else {
        sb.append("<p><b>Risk:</b> ${highestSeverity ?: "UNKNOWN"}</p>")
        sb.append("<p><b>Files with findings:</b> $vulnerableFileCount</p>")
        sb.append("<p>CWE-89 SQL Injection: $sqlCount<br>CWE-295 Certificate Validation: $certCount</p>")
    }
    sb.append("</body></html>")
    return sb.toString()
}

private fun errorSummaryHtml(message: String): String =
    "<html><body style='width: 400px'><h2>Scan failed</h2><p>${escapeHtml(message)}</p></body></html>"

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
