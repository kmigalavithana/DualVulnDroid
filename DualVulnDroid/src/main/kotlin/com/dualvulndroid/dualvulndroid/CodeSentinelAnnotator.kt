package com.dualvulndroid.dualvulndroid

import com.intellij.codeInsight.daemon.DaemonCodeAnalyzer
import com.intellij.lang.annotation.AnnotationHolder
import com.intellij.lang.annotation.ExternalAnnotator
import com.intellij.lang.annotation.HighlightSeverity
import com.intellij.openapi.editor.Document
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.project.ProjectManager
import com.intellij.openapi.util.TextRange
import com.intellij.psi.PsiFile
import java.util.concurrent.ConcurrentHashMap

// Tooltips are rendered as HTML - code/explanation text can contain
// '<', '>', '&' (e.g. generics like List<String>) which must be escaped
// or they silently break the tooltip's HTML rendering.
private fun String.escapeHtml(): String =
    this.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

// 1. collectInformation එකෙන් doAnnotate එකට Data පාස් කරන්න හදන Class එක
data class FileScanData(
    val path: String,
    val fileText: String,
    val lines: List<LineData>
)

data class LineData(
    val index: Int,
    val text: String,
    val startOffset: Int,
    val endOffset: Int
)

// 2. ඩිටෙක්ට් වෙන රිසල්ට් එක
data class LineScanResult(
    val lineText: String,
    val vulnerabilityType: String,
    val confidence: Double,
    val startOffset: Int,
    val endOffset: Int,
    val riskWeight: Double? = null,
    val criticalWords: List<String>? = null,
    val sourceToSinkPath: List<String>? = null,
    val dataflowExplanation: String? = null,
    // Phase 4: whole-scan context attached to every line result so the
    // tooltip can show severity/model/evidence without a second request.
    val severity: String? = null,
    val predictionModel: String? = null,
    val decision: String? = null,
    val decisionEvidence: List<DecisionReason>? = null,
    // Phase 5B: the raw 0-indexed backend line number (distinct from the
    // editor character offsets above) plus the two fields /predict has
    // but this data class didn't previously surface, so the shared
    // FindingDetailView (see FindingModel.kt) can show real-time findings
    // with the same richness as project-scan findings.
    val lineNumber: Int? = null,
    val securityFeatures: Map<String, Double>? = null,
    val shapTopFeatures: List<ShapFeature>? = null
)

class CodeSentinelAnnotator : ExternalAnnotator<FileScanData, List<LineScanResult>>() {

    companion object {
        private val cache = ConcurrentHashMap<String, List<LineScanResult>>()
        private val scanning = ConcurrentHashMap.newKeySet<String>()
    }

    override fun collectInformation(
        file: PsiFile,
        editor: com.intellij.openapi.editor.Editor,
        hasErrors: Boolean
    ): FileScanData? {
        val lang = file.language.id.lowercase()
        if (lang != "java" && lang != "kotlin" && lang != "xml") return null

        val path = file.virtualFile?.path ?: file.name
        val fileName = file.name

        // Only scan specific XML files for Network Security
        if (lang == "xml" && fileName != "AndroidManifest.xml" && fileName != "network_security_config.xml") {
            return null
        }

        val fileText = editor.document.text
        println("Scanning file: $path | Length: ${fileText.length}")

        val linesData = mutableListOf<LineData>()
        val lineCount = editor.document.lineCount
        for (i in 0 until lineCount) {
            val startOffset = editor.document.getLineStartOffset(i)
            val endOffset = editor.document.getLineEndOffset(i)
            val lineText = editor.document.getText(TextRange(startOffset, endOffset))
            linesData.add(LineData(i, lineText, startOffset, endOffset))
        }

        return FileScanData(path, fileText, linesData)
    }

    override fun doAnnotate(collectedData: FileScanData?): List<LineScanResult>? {
        println("ANNOTATOR RUNNING BACKGROUND API CALLS")
        if (collectedData == null) return null

        val path = collectedData.path
        if (!scanning.add(path)) return cache[path]

        val api = APIClient()
        val results = mutableListOf<LineScanResult>()

        try {
            val response = api.scanCode(collectedData.fileText, collectedData.path.substringAfterLast('/'))

            if (response == null) {
                // Section 12: never crash or go silent - log a specific,
                // useful reason so a developer looking at the IDE log
                // knows why no annotations appeared for this file.
                if (api.lastError != null) {
                    println("[CodeSentinel] Scan failed for $path: ${api.lastError}")
                }
            } else if (response.vulnerable) {
                println("Detected: ${response.vulnerabilityType}")
                response.detections.forEach { detection ->
                    val line = collectedData.lines.find {
                        it.index == detection.line
                    }
                    if (line != null) {
                        results.add(
                            LineScanResult(
                                lineText = line.text,
                                vulnerabilityType = detection.type,
                                confidence = response.confidence,
                                startOffset = line.startOffset,
                                endOffset = line.endOffset,
                                riskWeight = detection.risk_weight,
                                criticalWords = detection.critical_words,
                                sourceToSinkPath = detection.source_to_sink_path,
                                dataflowExplanation = detection.dataflow_explanation,
                                severity = response.severity,
                                predictionModel = response.predictionModel,
                                decision = response.decision,
                                decisionEvidence = response.decisionEvidence,
                                lineNumber = detection.line,
                                securityFeatures = response.securityFeatures,
                                shapTopFeatures = response.shapTopFeatures
                            )
                        )
                    }
                }
            }

            cache[path] = results
            return results
        } catch (e: Exception) {
            e.printStackTrace()
            return cache[path]
        } finally {
            scanning.remove(path)
        }
    }

    override fun apply(
        file: PsiFile,
        annotationResult: List<LineScanResult>?,
        holder: AnnotationHolder
    ) {
        println("========== APPLY START ==========")
        val path = file.virtualFile?.path ?: return
        val results = annotationResult ?: cache[path] ?: return

        for (result in results) {
            if (result.startOffset < 0 || result.endOffset > file.textLength || result.startOffset >= result.endOffset) {
                continue
            }

            // Phase 6, section 14: a Quick Fix is registered ONLY when a
            // locator confidently matches one of the small set of safe
            // patterns. No locator match -> no automatic fix, ever -
            // the tooltip says so explicitly instead of staying silent.
            val safeFix = SqlFixLocator.tryBuildFix(file, result, file.name)
                ?: CertificateFixLocator.tryBuildFix(file, result, file.name)

            val tooltip = buildTooltip(result, hasAutomaticFix = safeFix != null)
            val severityPrefix = result.severity?.let { "$it - " } ?: ""

            val builder = holder.newAnnotation(
                HighlightSeverity.ERROR,
                "$severityPrefix${result.vulnerabilityType} (${"%.2f".format(result.confidence)}%)"
            )
                .range(TextRange(result.startOffset, result.endOffset))
                .tooltip(tooltip)
                // Phase 5B, section 7: Alt+Enter opens the full detail
                // view in the existing tool window (same renderer project
                // scan uses) - a real IntelliJ action, not an HTML button
                // inside the tooltip that wouldn't actually do anything.
                .withFix(ShowFindingDetailsIntention(file.name, result))

            if (safeFix != null) {
                builder.withFix(safeFix)
            }
            builder.create()
        }
    }

    // Phase 4, section 8: a more informative but still readable tooltip -
    // severity/confidence up top, the real source->sink flow (not a
    // hardcoded 3-tier example), the decision engine's actual evidence
    // bullets, and which model produced the verdict. Every value here
    // comes from the backend response for THIS scan, nothing is static.
    private fun buildTooltip(result: LineScanResult, hasAutomaticFix: Boolean): String {
        val sb = StringBuilder()
        sb.append("<html>")
        sb.append("<b>⚠ ${result.vulnerabilityType}</b><br><br>")

        val severity = result.severity ?: "UNKNOWN"
        sb.append("<b>Severity:</b> $severity &nbsp;&nbsp; <b>Confidence:</b> ${"%.0f".format(result.confidence)}%<br>")
        if (result.decision != null) {
            sb.append("<b>Decision:</b> ${result.decision}<br>")
        }

        if (!result.sourceToSinkPath.isNullOrEmpty()) {
            sb.append("<br><b>Why was this flagged?</b><br>")
            sb.append(result.sourceToSinkPath.joinToString(" &rarr; ") { it.escapeHtml() })
            sb.append("<br>")
        } else if (result.dataflowExplanation != null) {
            sb.append("<br><b>Why was this flagged?</b><br>${result.dataflowExplanation.escapeHtml()}<br>")
        }

        if (!result.decisionEvidence.isNullOrEmpty()) {
            sb.append("<br><b>Evidence:</b><ul style=\"margin-top:2px;margin-bottom:2px\">")
            result.decisionEvidence
                .filter { it.source != "ml_model" }
                .forEach { sb.append("<li>${it.detail.escapeHtml()}</li>") }
            sb.append("</ul>")
        }

        if (!result.criticalWords.isNullOrEmpty()) {
            sb.append("<br><b>AI-flagged tokens:</b> ${result.criticalWords.joinToString(", ")}<br>")
        }

        sb.append("<br><b>ML model:</b> ${result.predictionModel ?: "XGBoost"} " +
            "&nbsp;&nbsp; <b>Confidence:</b> ${"%.2f".format(result.confidence)}%<br>")

        sb.append("<br><i>Press Alt+Enter for the full detail view (security features, SHAP factors, mitigation).</i><br>")

        // Phase 6, section 3/7: be explicit when NO automatic fix is
        // offered rather than silently doing nothing - the developer
        // shouldn't have to guess whether a fix exists.
        if (!hasAutomaticFix && (result.vulnerabilityType == "SQL Injection" || result.vulnerabilityType == "Certificate Validation")) {
            val message = if (result.vulnerabilityType == "SQL Injection")
                SqlConcatenationAnalyzer.MANUAL_REMEDIATION_MESSAGE else CertificateFixAnalyzer.MANUAL_REMEDIATION_MESSAGE
            sb.append("<br><i>$message</i><br>")
        }

        sb.append("<br><b>Line:</b><pre>${result.lineText.trim().escapeHtml()}</pre>")
        sb.append("</html>")
        return sb.toString()
    }

    object ProjectManagerHelper {
        fun clearCache() {
            cache.clear()
            println("✅ CodeSentinel cache cleared")
        }

        fun restartDaemon() {
            ProjectManager.getInstance().openProjects.forEach {
                DaemonCodeAnalyzer.getInstance(it).restart()
            }
        }
    }
}