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
    val explanation: List<String>
) {
    val location: String
        get() = if (line != null) "$fileName:${line + 1}" else fileName
}

// ---- Adapter: project scan (/developer/scan -> DeveloperScanResult) ----
// SHAP factors are not available from this endpoint (only
// /developer/explain computes them) - left null, rendered as
// "Not available", never invented.
fun DeveloperScanResult.toDetailView(fileName: String, line: Int?): FindingDetailView = FindingDetailView(
    fileName = fileName,
    line = line,
    vulnerabilityType = vulnerabilityType,
    cwe = cwe ?: CWE_BY_VULNERABILITY_TYPE[vulnerabilityType],
    severity = severity,
    confidence = confidence,
    decision = decision.riskLevel,
    recommendation = decision.recommendation,
    modelName = model.name,
    sourceToSinkPath = dataFlow?.firstOrNull()?.path,
    securityFeatures = securityFeatures,
    shapFactors = null,
    evidence = decision.evidence?.filter { it.source != "ml_model" }?.map { it.detail } ?: emptyList(),
    explanation = explanation ?: emptyList()
)

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
    cwe = CWE_BY_VULNERABILITY_TYPE[vulnerabilityType],
    severity = severity,
    confidence = confidence,
    decision = decision,
    recommendation = null, // /predict has no `decision.recommendation` equivalent field
    modelName = predictionModel,
    sourceToSinkPath = sourceToSinkPath,
    securityFeatures = securityFeatures,
    shapFactors = shapTopFeatures,
    evidence = decisionEvidence?.filter { it.source != "ml_model" }?.map { it.detail } ?: emptyList(),
    explanation = listOfNotNull(dataflowExplanation)
)

fun renderDetailHtml(view: FindingDetailView): String {
    val sb = StringBuilder()
    sb.append("<html><body style='width: 400px'>")

    val title = if (view.cwe != null) "${view.cwe} &mdash; ${view.vulnerabilityType}" else view.vulnerabilityType
    sb.append("<h2>⚠ ${escapeHtml(title)}</h2>")
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
