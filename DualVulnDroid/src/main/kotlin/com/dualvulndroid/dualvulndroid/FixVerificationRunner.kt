package com.dualvulndroid.dualvulndroid

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.application.ModalityState
import com.intellij.openapi.progress.ProgressIndicator
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.psi.PsiFile

/**
 * Phase 6, sections 11-13: after a fix is applied, re-runs the SAME
 * backend analysis (not a local guess) on the current file text and
 * compares against the original finding. Never claims success just
 * because a PSI edit happened - "resolved" is only ever set from a real
 * re-scan result. No numeric security score is shown (the backend
 * doesn't provide one for a single-file scan) - only detected/not
 * detected, per section 13.
 */
object FixVerificationRunner {

    fun runAsync(project: Project, psiFile: PsiFile, fileName: String, before: LineScanResult) {
        ProgressManagerCompat.runBackgroundable(project, "DualVulnDroid: Verifying fix") { indicator ->
            indicator.text = "Re-scanning after fix..."

            val currentText = ApplicationManager.getApplication().runReadAction<String> {
                psiFile.text
            }

            val api = APIClient()
            val response = api.scanCode(currentText, fileName)

            val verification = if (response == null) {
                FixVerification(
                    vulnerabilityType = before.vulnerabilityType,
                    cwe = null,
                    beforeDetected = true,
                    beforeConfidence = before.confidence,
                    afterDetected = true, // unknown - conservatively NOT claimed resolved
                    afterConfidence = 0.0,
                    resolved = false,
                    message = "Could not verify: ${api.lastError ?: "backend unavailable"}"
                )
            } else {
                val stillDetected = response.vulnerable
                FixVerification(
                    vulnerabilityType = before.vulnerabilityType,
                    cwe = null,
                    beforeDetected = true,
                    beforeConfidence = before.confidence,
                    afterDetected = stillDetected,
                    afterConfidence = response.confidence,
                    resolved = !stillDetected,
                    message = if (!stillDetected) "Vulnerability appears resolved" else "Fix applied, but vulnerability remains."
                )
            }

            RemediationLog.record(
                project,
                RemediationLogEntry(
                    timestampEpochMillis = System.currentTimeMillis(),
                    vulnerabilityType = before.vulnerabilityType,
                    cwe = null,
                    fixAvailable = true,
                    fixApplied = true,
                    beforeDetected = verification.beforeDetected,
                    afterDetected = verification.afterDetected,
                    resolved = verification.resolved
                )
            )

            ApplicationManager.getApplication().invokeLater({
                if (project.isDisposed) return@invokeLater
                if (verification.resolved) {
                    Messages.showInfoMessage(project, verification.toDisplayString(), "DualVulnDroid")
                } else {
                    Messages.showWarningDialog(project, verification.toDisplayString(), "DualVulnDroid")
                }
            }, ModalityState.NON_MODAL)
        }
    }
}
