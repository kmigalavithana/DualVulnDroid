package com.dualvulndroid.dualvulndroid

import com.intellij.codeInsight.daemon.DaemonCodeAnalyzer
import com.intellij.lang.annotation.AnnotationHolder
import com.intellij.lang.annotation.ExternalAnnotator
import com.intellij.lang.annotation.HighlightSeverity
import com.intellij.openapi.editor.Document
import com.intellij.openapi.editor.markup.EffectType
import com.intellij.openapi.editor.markup.TextAttributes
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.project.ProjectManager
import com.intellij.openapi.util.TextRange
import com.intellij.psi.PsiFile
import com.intellij.ui.JBColor
import java.awt.Color
import java.awt.Font
import java.util.concurrent.ConcurrentHashMap

// Tooltips are rendered as HTML - code/explanation text can contain
// '<', '>', '&' (e.g. generics like List<String>) which must be escaped
// or they silently break the tooltip's HTML rendering.
private fun String.escapeHtml(): String =
    this.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

// UI-presentation task, items 1/10: the exact inline annotation message -
// a distinct "CodeSentinel —" branded prefix (never just re-using
// IntelliJ's own error/warning wording) so it is visually AND textually
// unmistakable as a CodeSentinel security finding rather than a compiler
// diagnostic. Top-level (not private) so tests can assert against the
// REAL message-building logic instead of a separately-maintained
// duplicate of the format, which is exactly how that duplicate silently
// went stale once before (see FindingModelTest's "stays short" test).
// Editor visualization: a finding is drawn as a wavy UNDERLINE under the
// vulnerable statement only. The attributes are enforced on the annotation
// so the color scheme's default WARNING style (a yellow background fill in
// the light theme) is never applied, and no foreground/background is set,
// so normal syntax highlighting underneath stays exactly as it was.
internal object VulnerabilityUnderline {
    val ERROR_COLOR = JBColor(Color(0xD6, 0x2D, 0x2D), Color(0xF7, 0x54, 0x64))
    val REVIEW_COLOR = JBColor(Color(0xD9, 0x7A, 0x00), Color(0xF2, 0xB1, 0x3C))

    fun attributesFor(isReviewLevel: Boolean): TextAttributes {
        val color = if (isReviewLevel) REVIEW_COLOR else ERROR_COLOR
        return TextAttributes(null, null, color, EffectType.WAVE_UNDERSCORE, Font.PLAIN).apply {
            errorStripeColor = color
        }
    }

    // The finding's own line range with leading indentation and trailing
    // whitespace trimmed - i.e. exactly the statement on the line the
    // backend reported, never the whole editor row. Null if nothing but
    // whitespace remains (nothing real to underline).
    fun rangeFor(text: CharSequence, startOffset: Int, endOffset: Int): TextRange? {
        var start = startOffset
        var end = endOffset
        while (start < end && text[start].isWhitespace()) start++
        while (end > start && text[end - 1].isWhitespace()) end--
        return if (start < end) TextRange(start, end) else null
    }
}

fun buildAnnotationMessage(result: LineScanResult): String {
    val cwe = canonicalVulnerability(result.vulnerabilityType)?.second
    val cwePrefix = cwe?.let { "$it " } ?: ""
    return if (result.isReviewLevel) {
        "CodeSentinel — $cwePrefix${result.vulnerabilityType} (needs review, confidence: ${"%.0f".format(result.confidence)}%)"
    } else {
        "CodeSentinel — $cwePrefix${result.vulnerabilityType} detected (confidence: ${"%.0f".format(result.confidence)}%)"
    }
}

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
    val shapTopFeatures: List<ShapFeature>? = null,
    // UI-presentation task: true for a finding surfaced from a
    // SUSPICIOUS_REVIEW-level response with real corroborating evidence
    // (see doAnnotate()'s classification below), false for a confirmed
    // decision=="VULNERABLE" (response.vulnerable==true) finding.
    val isReviewLevel: Boolean = false
)

class CodeSentinelAnnotator : ExternalAnnotator<FileScanData, List<LineScanResult>>() {

    companion object {
        // Bug fix (real-time annotation debugging task): `cache` used to be
        // keyed on path alone, and a separate `scanning: Set<String>` guard
        // made doAnnotate() return the (possibly-null, possibly-stale) cached
        // result whenever ANY request for this path was still in flight -
        // including one started for OLDER text. IntelliJ's daemon restarts
        // highlighting on every edit, often faster than a round trip to the
        // backend completes, so while actively typing a multi-line snippet
        // the LATEST keystroke's pass would frequently lose this race: it
        // would see `scanning.add(path) == false` (an earlier pass's request
        // for the previous, already-superseded text was still in flight) and
        // return early with that earlier pass's (or, on a brand-new file,
        // simply no) cached results - showing stale or empty annotations for
        // the CURRENT, correct code until a further, unrelated edit happened
        // to land while no request was in flight. Keying both the cache and
        // the in-flight guard on (path, exact file text) fixes this: a scan
        // for genuinely new text is never suppressed by an older in-flight
        // request for different text, while a redundant re-invocation for
        // text that is already cached, or already being fetched, still avoids
        // an unnecessary duplicate backend call.
        private val cache = ConcurrentHashMap<String, List<LineScanResult>>()
        private val scanning = ConcurrentHashMap.newKeySet<String>()

        private fun cacheKey(path: String, fileText: String): String = "$path::${fileText.hashCode()}"

        // Plugin-fix task, STEP 4/12: the single source of truth for
        // "what is the MOST RECENT edit's key for this path" - updated at
        // the top of every doAnnotate() call (the daemon invokes
        // collectInformation()/doAnnotate() again on every keystroke, so
        // whichever call started last holds the truly current text).
        // Anything that later notices its own key no longer matches this
        // map's entry for its path knows a newer edit has superseded it,
        // and bails out rather than caching or returning a stale result.
        private val latestKeyForPath = ConcurrentHashMap<String, String>()

        // STEP 4: 400-700ms debounce window. A pass that gets superseded
        // while still inside this sleep aborts BEFORE ever making a
        // network call, so a burst of keystrokes collapses into one real
        // backend request for the text the user actually settles on,
        // instead of one request per keystroke queuing up server-side.
        private const val DEBOUNCE_MS = 500L

        /**
         * STEP 8/9: manual "Rescan Current File" must never be short-
         * circuited by a stale cached result for this path - clears every
         * cache/in-flight/latest-key entry belonging to `path` so the next
         * real-time pass (and any concurrently-running manual rescan) is
         * guaranteed to hit the backend fresh.
         */
        fun forceRescan(path: String) {
            val prefix = "$path::"
            cache.keys.removeIf { it.startsWith(prefix) }
            scanning.removeIf { it.startsWith(prefix) }
            latestKeyForPath.remove(path)
        }
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

        // Latency-measurement experiment task: T0 = "code edit event
        // received". This architecture has no separate DocumentListener -
        // IntelliJ's own daemon detects the edit and re-invokes this
        // ExternalAnnotator, so collectInformation() entry is the
        // earliest point OUR code observes it. Guarded so this is the
        // only extra work done when telemetry is disabled: one boolean
        // check, nothing else.
        if (LatencyTelemetry.enabled) {
            LatencyTelemetry.markT0(cacheKey(path, fileText))
        }

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
        val key = cacheKey(path, collectedData.fileText)
        latestKeyForPath[path] = key

        // Only skip if THIS EXACT text is already cached or already being
        // fetched - never suppress a scan just because a request for some
        // OLDER text on the same path is still in flight (see the fix note
        // on `cache`/`scanning` above).
        cache[key]?.let { return it }

        // STEP 4 debounce: wait briefly before ever touching the network.
        // If a newer edit lands on this same path during the wait, this
        // pass is now for stale text - abort without making a request at
        // all, rather than adding to the backend's queue for a result
        // nobody will see.
        Thread.sleep(DEBOUNCE_MS)
        if (latestKeyForPath[path] != key) return null

        // Latency-measurement experiment task: T1 = "debounce period
        // completed and scan actually starts" - this pass has survived
        // the staleness check right above, so it is genuinely proceeding
        // (a cache hit above never reaches here at all, and correctly
        // produces no telemetry event for what wasn't a real scan).
        if (LatencyTelemetry.enabled) LatencyTelemetry.markT1(key)

        if (!scanning.add(key)) return cache[key]

        val api = APIClient()
        val results = mutableListOf<LineScanResult>()

        try {
            // T2 = "HTTP request sent" / T6 = "HTTP response received by
            // plugin" - bracket the exact real network call, nothing else.
            if (LatencyTelemetry.enabled) LatencyTelemetry.markT2(key)
            val response = api.scanCode(collectedData.fileText, collectedData.path.substringAfterLast('/'))
            if (LatencyTelemetry.enabled) LatencyTelemetry.markT6(key)

            // STEP 12: a slow request for now-superseded text must never
            // overwrite (via `cache[key] = results` below, or by being
            // returned to apply()) whatever a newer, faster pass already
            // produced or is about to produce.
            if (latestKeyForPath[path] != key) return null

            if (response == null) {
                // Section 12: never crash or go silent - log a specific,
                // useful reason so a developer looking at the IDE log
                // knows why no annotations appeared for this file.
                if (api.lastError != null) {
                    println("[CodeSentinel] Scan failed for $path: ${api.lastError}")
                }
            } else {
                // UI-presentation task, item 2: see FindingModel.kt's
                // classify(ScanResponse) for the full rationale - a plain
                // response.vulnerable==true check silently dropped every
                // SUSPICIOUS_REVIEW result (like ss.java's own: decision=
                // SUSPICIOUS_REVIEW, confidence 60%, WITH real
                // corroborating evidence), which is why no annotation ever
                // appeared for it.
                val classification = classify(response)

                if (classification != FindingClassification.NONE) {
                    println("Detected: ${response.vulnerabilityType} ($classification)")

                    if (classification == FindingClassification.DEFINITE) {
                        // Bug fix (duplicate-finding / missing-Quick-Fix task):
                        // predictor.py's rule/SHAP keyword scan and its
                        // dataflow analyzer both independently emit their own
                        // "SQL Injection"/"Certificate Validation" detection
                        // entries for the SAME underlying vulnerability - e.g.
                        // one incidental keyword hit on the `val query = ...`
                        // declaration line (matches "select ") AND a second,
                        // real traced-dataflow hit on the `db.rawQuery(...)`
                        // sink line. selectRelevantDetections() never narrows
                        // a DEFINITE response (by design - "every type
                        // actually detected is surfaced", see FindingModel.kt),
                        // so the OLD one-annotation-per-raw-detection loop
                        // below created a SEPARATE, real annotation for each
                        // of those - including one anchored on the
                        // declaration line, where SqlFixLocator's sink search
                        // (restricted to that ONE annotation's own text
                        // range) can never find the rawQuery(...) call that
                        // lives on a different line, so Alt+Enter on THAT
                        // annotation legitimately never offered a fix.
                        //
                        // groupDetectionsByType() already exists precisely
                        // for this - it's the SAME consolidation MyToolWindow
                        // uses for its one-row-per-type findings list - and
                        // reusing it here gives exactly ONE annotation per
                        // vulnerability TYPE actually detected (SQL and Cert
                        // both still surfaced if both are present - nothing
                        // is suppressed), anchored on the group's own
                        // strongest/last-line detection - the SAME "anchor on
                        // max line" convention DeveloperScanResult.toDetailView
                        // already uses (and existing tests already depend on:
                        // a keyword hit on a real sink/pattern line is always
                        // the LAST line in these detection groups, e.g.
                        // "db.rawQuery(...)" or "return true;"), so a Quick
                        // Fix locator's exact-range search now always has a
                        // real chance to find its target.
                        val typeGroups = groupDetectionsByType(response.detections, classification)
                        typeGroups.forEach { group ->
                            val anchorDetection = group.anchorDetections.maxByOrNull { it.line } ?: return@forEach
                            val line = collectedData.lines.find { it.index == anchorDetection.line } ?: return@forEach
                            // The richest dataflow evidence isn't always on
                            // the anchor line itself (e.g. a HostnameVerifier
                            // is traced at its declaration, not its "return
                            // true;" statement) - pulled in separately here
                            // so the tooltip stays as informative as before,
                            // independent of which line the annotation itself
                            // is anchored on.
                            val dataflowDetection = group.anchorDetections.firstOrNull { !it.source_to_sink_path.isNullOrEmpty() }
                            val criticalWords = group.anchorDetections.flatMap { it.critical_words ?: emptyList() }.distinct()
                            results.add(
                                LineScanResult(
                                    lineText = line.text,
                                    vulnerabilityType = group.vulnerabilityType,
                                    confidence = response.confidence,
                                    startOffset = line.startOffset,
                                    endOffset = line.endOffset,
                                    riskWeight = anchorDetection.risk_weight,
                                    criticalWords = criticalWords,
                                    sourceToSinkPath = dataflowDetection?.source_to_sink_path,
                                    dataflowExplanation = dataflowDetection?.dataflow_explanation,
                                    severity = response.severity,
                                    predictionModel = response.predictionModel,
                                    decision = response.decision,
                                    decisionEvidence = response.decisionEvidence,
                                    lineNumber = anchorDetection.line,
                                    securityFeatures = response.securityFeatures,
                                    shapTopFeatures = response.shapTopFeatures,
                                    isReviewLevel = false
                                )
                            )
                        }
                    } else {
                        // REVIEW: unchanged - selectRelevantDetections()
                        // already narrows a SUSPICIOUS_REVIEW response down
                        // to just its strongest-evidence detection(s), which
                        // can legitimately still be more than one distinct
                        // line (see FinalUIStateVerificationTest's real
                        // ss.java case, lines 6 and 8 both survive on merit) -
                        // every surviving detection keeps its own annotation
                        // exactly as before.
                        val relevantDetections = selectRelevantDetections(response.detections, classification)

                        relevantDetections.forEach { detection ->
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
                                        shapTopFeatures = response.shapTopFeatures,
                                        isReviewLevel = true
                                    )
                                )
                            }
                        }
                    }
                }
            }

            cache[key] = results
            return results
        } catch (e: Exception) {
            e.printStackTrace()
            return cache[key]
        } finally {
            scanning.remove(key)
        }
    }

    override fun apply(
        file: PsiFile,
        annotationResult: List<LineScanResult>?,
        holder: AnnotationHolder
    ) {
        println("========== APPLY START ==========")
        val path = file.virtualFile?.path ?: return
        // `cache` is now keyed by (path, exact text) - not by path alone -
        // so it can no longer be used here as a plain fallback. That's fine:
        // doAnnotate() only returns null for a pass whose own request truly
        // failed or raced with an identical in-flight one, in which case
        // showing nothing for THIS pass (rather than a possibly-unrelated
        // cached result for different text) is the correct behavior; the
        // next highlighting pass will pick up cleanly since it is no longer
        // blocked by the old (path-only) staleness bug.

        // Latency-measurement experiment task: T7 = "IDE annotation
        // processing starts". apply() only receives (file, result) - not
        // the FileScanData/key doAnnotate() used - so the same cacheKey()
        // is recomputed from file.text here. The IntelliJ platform only
        // calls apply() with a result that is still current for `file`'s
        // present text (a superseded pass is cancelled by the platform
        // before apply() runs), so this recomputed key is expected to
        // match the one T0/T1/T2/T6 were recorded under; if it doesn't
        // (e.g. a very fast subsequent edit raced apply() itself), T8
        // below simply never finds a matching in-progress entry and no
        // event is recorded for this pass - never a mismatched/corrupted
        // measurement.
        val telemetryKey = if (LatencyTelemetry.enabled) cacheKey(path, file.text) else null
        if (telemetryKey != null) LatencyTelemetry.markT7(telemetryKey)

        val results = annotationResult ?: return

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
            val highlightSeverity = if (result.isReviewLevel) HighlightSeverity.WARNING else HighlightSeverity.ERROR
            // Underline only the statement itself (indentation trimmed); the
            // locators above still get the finding's original line offsets.
            val underlineRange = VulnerabilityUnderline.rangeFor(file.text, result.startOffset, result.endOffset) ?: continue

            val builder = holder.newAnnotation(highlightSeverity, buildAnnotationMessage(result))
                .range(underlineRange)
                .enforcedTextAttributes(VulnerabilityUnderline.attributesFor(result.isReviewLevel))
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

        // T8 = "IDE annotation/finding creation completes" - marked here
        // regardless of whether `results` was empty (a genuine safe/
        // no-finding scan still completes real apply() processing and is
        // a valid, real measurement, not a failure).
        if (telemetryKey != null) LatencyTelemetry.markT8(telemetryKey)
    }

    // Phase 4, section 8: a more informative but still readable tooltip -
    // severity/confidence up top, the real source->sink flow (not a
    // hardcoded 3-tier example), the decision engine's actual evidence
    // bullets, and which model produced the verdict. Every value here
    // comes from the backend response for THIS scan, nothing is static.
    private fun buildTooltip(result: LineScanResult, hasAutomaticFix: Boolean): String {
        val sb = StringBuilder()
        sb.append("<html>")
        val cwe = canonicalVulnerability(result.vulnerabilityType)?.second
        val title = if (cwe != null) "$cwe &mdash; ${result.vulnerabilityType}" else result.vulnerabilityType
        sb.append("<b>CodeSentinel &mdash; ⚠ ${title.escapeHtml()}</b><br><br>")

        // UI-presentation task, item 2/10: make a review-level finding
        // (SUSPICIOUS_REVIEW + real corroborating evidence, see
        // doAnnotate()) visually and textually distinct from a confirmed
        // one right at the top of the tooltip, not just via color.
        if (result.isReviewLevel) {
            sb.append("<b><font color=\"#B08800\">NEEDS REVIEW</font></b> - flagged by the Hybrid Decision " +
                "Engine as SUSPICIOUS_REVIEW with corroborating evidence below, not an auto-confirmed vulnerability.<br><br>")
        }

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