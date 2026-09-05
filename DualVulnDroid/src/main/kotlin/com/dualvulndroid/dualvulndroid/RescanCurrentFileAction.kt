package com.dualvulndroid.dualvulndroid

import com.intellij.codeInsight.daemon.DaemonCodeAnalyzer
import com.intellij.openapi.actionSystem.ActionUpdateThread
import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.application.ReadAction
import com.intellij.openapi.ui.Messages

/**
 * Plugin-fix task, STEP 8: "Rescan Current File" - a manual, explicit
 * entry point that reuses CodeSentinelAnnotator's exact backend path
 * (APIClient.scanCode against the live in-editor Document text) instead
 * of duplicating it, and works even if the automatic real-time annotator
 * was disabled, cancelled, or is mid-debounce for this same file.
 *
 * Registered in plugin.xml under the editor popup menu and Tools menu.
 */
class RescanCurrentFileAction : AnAction() {

    override fun getActionUpdateThread(): ActionUpdateThread = ActionUpdateThread.BGT

    override fun update(e: AnActionEvent) {
        val file = e.getData(CommonDataKeys.PSI_FILE)
        val lang = file?.language?.id?.lowercase()
        e.presentation.isEnabledAndVisible = lang == "java" || lang == "kotlin"
    }

    private data class RescanInput(val path: String, val fileName: String, val fileText: String)

    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val psiFile = e.getData(CommonDataKeys.PSI_FILE) ?: return

        // All PSI/VirtualFile/Document access grouped under one read
        // action - `fileText` is psiFile.text, which always reflects the
        // CURRENT in-editor Document content (STEP 11), never a stale
        // on-disk copy, for an open, possibly-unsaved file.
        val input = ReadAction.compute<RescanInput?, Exception> {
            val lang = psiFile.language.id.lowercase()
            if (lang != "java" && lang != "kotlin") return@compute null
            RescanInput(
                path = psiFile.virtualFile?.path ?: psiFile.name,
                fileName = psiFile.name,
                fileText = psiFile.text
            )
        } ?: return
        val (path, fileName, fileText) = input

        // STEP 9: a manual rescan must never be short-circuited by a
        // stale cached annotation result for this exact path.
        CodeSentinelAnnotator.forceRescan(path)

        ProgressManagerCompat.runBackgroundable(project, "DualVulnDroid: Rescanning $fileName") {
            val api = APIClient()
            val response = api.scanCode(fileText, fileName)

            ApplicationManager.getApplication().invokeLater {
                if (project.isDisposed) return@invokeLater

                if (response == null) {
                    Messages.showErrorDialog(
                        project,
                        api.lastError ?: "Unknown error contacting the DualVulnDroid backend.",
                        "DualVulnDroid: Rescan Failed"
                    )
                    return@invokeLater
                }

                // Re-trigger the real-time annotator so the editor's inline
                // highlights reflect this fresh result immediately, rather
                // than waiting for the next unrelated highlighting pass.
                DaemonCodeAnalyzer.getInstance(project).restart(psiFile)

                val message = if (response.vulnerable) {
                    "${response.vulnerabilityType} detected (${"%.0f".format(response.confidence)}% confidence)."
                } else {
                    "No vulnerabilities detected."
                }
                Messages.showInfoMessage(project, "Rescan of $fileName complete.\n$message", "DualVulnDroid")
            }
        }
    }
}
