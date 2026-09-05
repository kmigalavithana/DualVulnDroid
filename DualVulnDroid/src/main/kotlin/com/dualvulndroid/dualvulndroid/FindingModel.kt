package com.dualvulndroid.dualvulndroid

// =====================================================
// Phase 5B: the ONE shared internal representation of a finding, used by
// BOTH the real-time /predict path (CodeSentinelAnnotator) and the
// project-scan /developer/scan path (MyToolWindow), rendered by the ONE
// shared renderDetailHtml() below. Neither call site builds its own
// detail HTML anymore.
//
// Field-availability note (section 5): /predict's flat response has no
// "cwe" field and no per-file securityFeatures/SHAP breakdown consistent
// with /developer/scan's shape in every respect; /developer/scan's
// response has no SHAP contributions (only /developer/explain computes
// those). Rather than fabricate either, missing fields stay null here
// and renderDetailHtml() prints "Not available" for them - see the two
// adapters below for exactly which fields each source can and can't supply.
// =====================================================

// A small, deterministic, publicly-known CWE-name mapping - the same one
// predictor.py's CWE_BY_TYPE already applies server-side for
// /developer/scan. Used ONLY as a fallback when a response (namely
// /predict's flat ScanResponse) doesn't carry "cwe" directly; never
// overrides a real value the backend provided.
private val CWE_BY_VULNERABILITY_TYPE = mapOf(
    "SQL Injection" to "CWE-89",
    "Certificate Validation" to "CWE-295"
)

// UI-presentation task, item 7: the backend (predictor.py's TYPE_INFO /
// CWE_BY_TYPE) only ever actually returns the two canonical strings above
// today - this is a defensive normalization layer only, for common naming
// variants a future backend response could plausibly use, so grouping/
// counting in the ToolWindow doesn't silently miss a finding just because
// of a casing/punctuation difference. It never invents a NEW vulnerability
// category - anything that doesn't match either known family returns null
// and is left exactly as reported (see canonicalDisplayName below).
private fun normalizeForMatching(s: String): String =
    s.lowercase().replace(Regex("[ _-]"), "")

private val SQL_INJECTION_ALIASES = setOf(
    "sqlinjection", "sqli", "cwe89"
)
private val CERTIFICATE_VALIDATION_ALIASES = setOf(
    "certificatevalidation", "certvalidation", "sslvalidation",
    "impropercertificatevalidation", "hostnameverification", "cwe295"
)

/**
 * Canonical (displayName, cwe) for a raw `vulnerabilityType` string,
 * tolerant of common casing/punctuation variants. Returns null for
 * anything outside DualVulnDroid's two known families - callers must
 * fall back to displaying the raw type as-is rather than mis-classifying it.
 */
fun canonicalVulnerability(rawType: String): Pair<String, String>? {
    val normalized = normalizeForMatching(rawType)
    return when {
        normalized in SQL_INJECTION_ALIASES -> "SQL Injection" to "CWE-89"
        normalized in CERTIFICATE_VALIDATION_ALIASES -> "Certificate Validation" to "CWE-295"
        else -> null
    }
}

// =====================================================
// UI-presentation task, item 2: shared, pure, independently-testable
// classification of a backend result into what the UI should do with it.
//
// decision_engine.py's own documented rationale: ONLY its "VULNERABLE"
// decision maps to vulnerable=true - "SAFE" and "SUSPICIOUS_REVIEW" both
// report vulnerable=false BY DESIGN, specifically so a merely-average ML
// score doesn't paint a red warning on most scanned files (~65% of files
// are NOT auto-decided). The plugin was previously built strictly around
// `vulnerable==true`, so a real SUSPICIOUS_REVIEW result - like ss.java's
// (decision=SUSPICIOUS_REVIEW, confidence 60%, WITH a real static_rule
// signal in decisionEvidence) - never produced any annotation or finding
// at all, even though real corroborating evidence was present.
//
// FindingClassification.REVIEW exists for exactly that gap: it is used
// ONLY when there is a SUSPICIOUS_REVIEW-equivalent decision AND at least
// one non-"ml_model" decisionEvidence entry that itself argues
// "vulnerable" (a real static/data-flow signal, not just a middling ML
// score) AND at least one detection to anchor a location on. This keeps
// the fix from reintroducing the exact "red warning on nearly every file"
// problem decision_engine.py's own comment warns about - it is presented
// at a lower severity (WARNING, not ERROR) and clearly labeled "needs
// review" wherever it is shown (see CodeSentinelAnnotator.apply()/
// buildAnnotationMessage() and MyToolWindow's FindingEntry rendering).
// =====================================================
enum class FindingClassification { DEFINITE, REVIEW, NONE }

/** Classification for a /predict (or real-time annotator) ScanResponse. */
fun classify(response: ScanResponse): FindingClassification {
    if (response.vulnerable) return FindingClassification.DEFINITE
    val hasCorroboratingEvidence = response.decisionEvidence
        ?.any { it.source != "ml_model" && it.contribution > 0 } == true
    return if (response.decision == "SUSPICIOUS_REVIEW" && hasCorroboratingEvidence && response.detections.isNotEmpty()) {
        FindingClassification.REVIEW
    } else {
        FindingClassification.NONE
    }
}

/**
 * Classification for a /developer/scan (project batch) DeveloperScanResult.
 * This response shape has no raw 3-way `decision` string - the equivalent
 * signal is decision.recommendation == "MANUAL_REVIEW_RECOMMENDED"
 * (predictor.py's RECOMMENDATION_BY_DECISION, computed from that SAME
 * underlying decision string server-side).
 */
fun classify(result: DeveloperScanResult): FindingClassification {
    if (result.vulnerable) return FindingClassification.DEFINITE
    val hasCorroboratingEvidence = result.decision.evidence
        ?.any { it.source != "ml_model" && it.contribution > 0 } == true
    return if (result.decision.recommendation == "MANUAL_REVIEW_RECOMMENDED" &&
        hasCorroboratingEvidence && !result.detections.isNullOrEmpty()
    ) {
        FindingClassification.REVIEW
    } else {
        FindingClassification.NONE
    }
}

/**
 * Narrows a REVIEW-level result's detections down to the one(s) that
 * actually carry the strongest evidence (max risk_weight, or a real
 * traced source-to-sink/data-flow explanation) - "highlight the most
 * relevant vulnerable statement," not every incidental keyword match on
 * an unrelated line. A DEFINITE (confirmed) result keeps every detection,
 * matching the plugin's existing, already-tested behavior. Falls back to
 * the full list if the narrowing would otherwise leave nothing to show.
 */
fun selectRelevantDetections(detections: List<Detection>?, classification: FindingClassification): List<Detection> {
    if (detections.isNullOrEmpty()) return emptyList()
    if (classification == FindingClassification.DEFINITE) return detections
    val maxWeight = detections.mapNotNull { it.risk_weight }.maxOrNull() ?: 0.0
    val filtered = detections.filter { d ->
        (maxWeight > 0.0 && (d.risk_weight ?: 0.0) >= maxWeight) ||
            !d.source_to_sink_path.isNullOrEmpty() ||
            d.dataflow_explanation != null
    }
    return filtered.ifEmpty { detections }
}

// =====================================================
// Critical bug fix: a single /developer/scan (or /predict) response
// describes ONE file with ONE fused, file-level ML verdict
// (vulnerabilityType/cwe/confidence/decision) - decision_engine.py
// deliberately combines ML + static + data-flow evidence from BOTH CWE
// families into one score so strong evidence in either family can raise
// the file's overall risk (see decision_engine.py's own docstring).
// predict_code() ALWAYS runs analyze_sql_dataflow() AND
// analyze_cert_dataflow() on every file (predictor.py ~L348-369) and
// appends detections of BOTH types into the SAME `detections` list
// regardless of which single type the top-level verdict names - e.g. a
// file with both an unsafe concatenated query AND an unsafe
// HostnameVerifier can have `vulnerabilityType: "SQL Injection"` at the
// response level while `detections` legitimately contains entries with
// `type: "SQL Injection"` (the query/sink lines) AND separate entries
// with `type: "Certificate Validation"` (the HostnameVerifier line) -
// confirmed against a real live /developer/scan response during this fix.
//
// MyToolWindow.runScan() used to build every FindingEntry from the
// response-level vulnerabilityType/cwe, so a genuinely CWE-295 detection
// (e.g. the HostnameVerifier line) got mislabeled with whatever CWE-89/
// CWE-295 the file's OVERALL ML verdict happened to be. groupDetectionsByType()
// is the fix: it groups by each DETECTION's OWN `type` field (never the
// response-level one) and decides, independently per type-group, whether
// that group should be surfaced - so a CWE-295 detection can never become
// a CWE-89 finding just because another detection in the same response is
// SQL-related, and vice versa.
// =====================================================

data class DetectionTypeGroup(
    val vulnerabilityType: String,
    val cwe: String?,
    val anchorDetections: List<Detection>
)

// Real-signal risk_weight values observed in production responses sit at
// 0.4 (STATIC_RULE_WEIGHT, matching decision_engine.py's own documented
// weight) or above (0.5 for a directly-matched sink/concatenation line,
// 1.0 for a traced data-flow finding); the only value below that is the
// ~0.08 incidental-keyword-token noise floor. Used only to decide whether
// a REVIEW-level type-group has earned its own finding, never to alter
// what the backend itself already decided.
private const val MEANINGFUL_RISK_WEIGHT = 0.4

/**
 * Groups a response's detections by their OWN `type` field and returns
 * one [DetectionTypeGroup] per distinct type actually present AND worth
 * surfacing, each anchored on that type's own strongest-evidence
 * detection(s) (via [selectRelevantDetections], scoped to just that
 * type's detections - never mixed with another type's).
 *
 * For a DEFINITE (confirmed) response every type actually detected is
 * surfaced - the file-level "vulnerable" verdict already applies, and a
 * detection is only ever added server-side when its own analyzer
 * (SQL or certificate) genuinely matched (see predictor.py).
 *
 * For a REVIEW-level response, a type-group is only surfaced if IT
 * independently carries real evidence (max risk_weight >= [MEANINGFUL_RISK_WEIGHT]
 * or a real traced source-to-sink/data-flow explanation) - the same
 * "not just middling noise" gate [classify] applies file-wide, scoped
 * down to one CWE family, so a response that's SUSPICIOUS_REVIEW purely
 * because of (say) SQL evidence doesn't also manufacture a phantom
 * Certificate Validation "needs review" finding with nothing behind it.
 */
fun groupDetectionsByType(
    detections: List<Detection>?,
    responseClassification: FindingClassification
): List<DetectionTypeGroup> {
    if (responseClassification == FindingClassification.NONE || detections.isNullOrEmpty()) return emptyList()

    return detections
        .groupBy { it.type }
        .toSortedMap()
        .mapNotNull { (type, groupDetections) ->
            val anchors = selectRelevantDetections(groupDetections, responseClassification)
            if (anchors.isEmpty()) return@mapNotNull null

            if (responseClassification == FindingClassification.REVIEW) {
                val hasMeaningfulEvidence = anchors.any { d ->
                    (d.risk_weight ?: 0.0) >= MEANINGFUL_RISK_WEIGHT ||
                        !d.source_to_sink_path.isNullOrEmpty() ||
                        d.dataflow_explanation != null
                }
                if (!hasMeaningfulEvidence) return@mapNotNull null
            }

            DetectionTypeGroup(
                vulnerabilityType = type,
                cwe = canonicalVulnerability(type)?.second ?: CWE_BY_VULNERABILITY_TYPE[type],
                anchorDetections = anchors
            )
        }
}

private val MITIGATION_BY_TYPE = mapOf(
    "SQL Injection" to "Use parameterized queries / selectionArgs instead of string concatenation.",
    "Certificate Validation" to "Perform proper hostname/certificate validation - do not accept all certificates or hostnames.",
    "Network Security" to "Disable cleartext traffic and remove permissive network security configuration overrides."
)

fun escapeHtml(s: String): String =
    s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

data class FindingDetailView(
    val fileName: String,
    val line: Int?,
    val vulnerabilityType: String,
    val cwe: String?,
    val severity: String?,
    val confidence: Double,
    val decision: String?,
    val recommendation: String?,
    val modelName: String?,
    val sourceToSinkPath: List<String>?,
    val securityFeatures: Map<String, Double>?,
    val shapFactors: List<ShapFeature>?,
    val evidence: List<String>,
    val explanation: List<String>,
    // UI-presentation task: true when this finding was surfaced from a
    // SUSPICIOUS_REVIEW-level backend result with real corroborating
    // static/data-flow evidence (see CodeSentinelAnnotator.doAnnotate()
    // and MyToolWindow.runScan() for the exact classification rule) rather
    // than a confirmed decision=="VULNERABLE" result. Purely a client-side
    // presentation label - never sent to or invented on behalf of the
    // backend - so the UI can visibly distinguish "flag for manual review"
    // from "confirmed vulnerability" per the backend's own documented
    // decision_engine.py design intent.
    val reviewLevel: Boolean = false
) {
    val location: String
        get() = if (line != null) "$fileName:${line + 1}" else fileName
}

// ---- Adapter: project scan (/developer/scan -> DeveloperScanResult) ----
// SHAP factors are not available from this endpoint (only
// /developer/explain computes them) - left null, rendered as
// "Not available", never invented.
//
// Critical bug fix: vulnerabilityType/cwe/sourceToSinkPath now come from
// the CALLER-supplied DetectionTypeGroup (see groupDetectionsByType()) -
// this file's OWN detections for THIS specific type - never from the
// response's single file-level `vulnerabilityType`/`cwe`/`dataFlow[0]`,
// which describe the file's overall fused verdict and can legitimately
// name a DIFFERENT CWE family than a given detection actually belongs to.
// confidence/severity/decision/evidence remain response-level (the
// backend genuinely computes only one fused value per file for these,
// not one per detection-type - reusing the real value the backend
// returned, not inventing a fabricated per-type one).
fun DeveloperScanResult.toDetailView(
    fileName: String,
    group: DetectionTypeGroup,
    reviewLevel: Boolean = false
): FindingDetailView {
    val line = group.anchorDetections.maxByOrNull { it.line }?.line
    val dataflowDetection = group.anchorDetections.firstOrNull { !it.source_to_sink_path.isNullOrEmpty() }
    val dataflowExplanations = group.anchorDetections.mapNotNull { it.dataflow_explanation }.distinct()

    return FindingDetailView(
        fileName = fileName,
        line = line,
        vulnerabilityType = group.vulnerabilityType,
        cwe = group.cwe,
        severity = severity,
        confidence = confidence,
        decision = decision.riskLevel,
        recommendation = decision.recommendation,
        modelName = model.name,
        sourceToSinkPath = dataflowDetection?.source_to_sink_path,
        securityFeatures = securityFeatures,
        shapFactors = null,
        evidence = decision.evidence?.filter { it.source != "ml_model" }?.map { it.detail } ?: emptyList(),
        explanation = (dataflowExplanations + (explanation ?: emptyList())).distinct(),
        reviewLevel = reviewLevel
    )
}

// ---- Adapter: real-time inspection (/predict -> LineScanResult, the
// specific finding the developer invoked "Show details" on) ----
// /predict's flat response has no "explanation" list (it's a single
// string there, kept lightweight for the annotation) and no per-CWE
// field - filled in deterministically where possible, "Not available"
// otherwise. decisionEvidence/securityFeatures/shapTopFeatures ARE
// available here since predictor.py returns them on /predict too, and
// CodeSentinelAnnotator copies them onto every LineScanResult already.
fun LineScanResult.toDetailView(fileName: String): FindingDetailView = FindingDetailView(
    fileName = fileName,
    line = lineNumber,
    vulnerabilityType = vulnerabilityType,
    cwe = CWE_BY_VULNERABILITY_TYPE[vulnerabilityType] ?: canonicalVulnerability(vulnerabilityType)?.second,
    severity = severity,
    confidence = confidence,
    decision = decision,
    recommendation = null, // /predict has no `decision.recommendation` equivalent field
    modelName = predictionModel,
    sourceToSinkPath = sourceToSinkPath,
    securityFeatures = securityFeatures,
    shapFactors = shapTopFeatures,
    evidence = decisionEvidence?.filter { it.source != "ml_model" }?.map { it.detail } ?: emptyList(),
    explanation = listOfNotNull(dataflowExplanation),
    reviewLevel = isReviewLevel
)

fun renderDetailHtml(view: FindingDetailView): String {
    val sb = StringBuilder()
    sb.append("<html><body style='width: 400px'>")

    val title = if (view.cwe != null) "${view.cwe} &mdash; ${view.vulnerabilityType}" else view.vulnerabilityType
    sb.append("<h2>⚠ ${escapeHtml(title)}</h2>")
    // UI-presentation task, item 10: make it visually unmistakable that
    // this is a CodeSentinel security finding, not an IntelliJ compiler
    // diagnostic, and (item 2) distinguish a confirmed VULNERABLE result
    // from a SUSPICIOUS_REVIEW-derived one that still had real
    // corroborating evidence.
    val statusHtml = if (view.reviewLevel) {
        "<p style='color:#B08800'><b>Status: NEEDS REVIEW</b> - flagged as SUSPICIOUS_REVIEW by the " +
            "Hybrid Decision Engine with corroborating static/data-flow evidence, not an auto-confirmed vulnerability.</p>"
    } else {
        "<p style='color:#C1282D'><b>Status: CONFIRMED FINDING</b></p>"
    }
    sb.append(statusHtml)
    sb.append("<p><b>Location:</b> ${escapeHtml(view.location)}</p>")
    sb.append("<p><b>Risk:</b> ${view.severity ?: "Not available"} &nbsp;&nbsp; " +
        "<b>Confidence:</b> ${"%.2f".format(view.confidence)}% &nbsp;&nbsp; " +
        "<b>Decision:</b> ${view.decision ?: "Not available"}</p>")
    sb.append("<p><b>Recommendation:</b> ${view.recommendation ?: "Not available"}</p>")
    sb.append("<p><b>Model:</b> ${view.modelName ?: "Not available"}</p>")

    sb.append("<h3>Source &rarr; Sink</h3>")
    if (!view.sourceToSinkPath.isNullOrEmpty()) {
        sb.append("<p>${view.sourceToSinkPath.joinToString(" &rarr; ") { escapeHtml(it) }}</p>")
    } else {
        sb.append("<p><i>Not available</i></p>")
    }

    sb.append("<h3>Evidence</h3>")
    if (view.evidence.isNotEmpty()) {
        sb.append("<ul>")
        view.evidence.forEach { sb.append("<li>${escapeHtml(it)}</li>") }
        sb.append("</ul>")
    } else {
        sb.append("<p><i>Not available</i></p>")
    }

    if (view.explanation.isNotEmpty()) {
        sb.append("<h3>Why was this flagged?</h3><ul>")
        view.explanation.forEach { sb.append("<li>${escapeHtml(it)}</li>") }
        sb.append("</ul>")
    }

    sb.append("<h3>Security features</h3>")
    val activeFeatures = view.securityFeatures?.filter { it.value != 0.0 }
    if (!activeFeatures.isNullOrEmpty()) {
        sb.append("<p>${activeFeatures.keys.joinToString(", ") { escapeHtml(it) }}</p>")
    } else {
        sb.append("<p><i>Not available</i></p>")
    }

    sb.append("<h3>Top contributing features (SHAP)</h3>")
    if (!view.shapFactors.isNullOrEmpty()) {
        sb.append("<ul>")
        view.shapFactors.take(5).forEach {
            sb.append("<li>${escapeHtml(it.feature)} (${"%.3f".format(it.shapValue)})</li>")
        }
        sb.append("</ul>")
    } else {
        sb.append("<p><i>Not available</i></p>")
    }

    val mitigation = MITIGATION_BY_TYPE[view.vulnerabilityType]
    sb.append("<h3>Recommended mitigation</h3>")
    sb.append("<p>${if (mitigation != null) escapeHtml(mitigation) else "Not available"}</p>")

    sb.append("</body></html>")
    return sb.toString()
}
