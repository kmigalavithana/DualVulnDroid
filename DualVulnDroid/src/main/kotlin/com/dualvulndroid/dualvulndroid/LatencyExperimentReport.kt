package com.dualvulndroid.dualvulndroid

import com.google.gson.FieldNamingPolicy
import com.google.gson.GsonBuilder
import java.io.File

/**
 * One completed, successfully measured edit-to-annotation cycle
 * (latency-measurement experiment task, Part 5). All *_ms fields are
 * plain milliseconds (Double), converted from LatencyTelemetry's raw
 * nanosecond values - never fabricated, always derived from a real
 * completed LatencyTelemetry.LatencyEvent plus the real backend
 * response/timing for that same request.
 */
data class MeasuredRun(
    val runId: Int,
    val language: String,
    val codeType: String,
    val expectedCwe: String,
    val prediction: String,
    val debounceMs: Double,
    val requestMs: Double,
    val backendTotalMs: Double,
    val predictionMs: Double,
    val pluginResponseMs: Double,
    val annotationMs: Double,
    val pipelineMs: Double,
    val endToEndMs: Double,
    val timestamp: String,
)

/**
 * Pure CSV/JSON serialization for a list of [MeasuredRun]s - no
 * IntelliJ Platform dependency, no backend call, so this is directly
 * unit-testable (Part 10, items 5/6).
 */
object LatencyExperimentReport {
    val CSV_HEADER = listOf(
        "run_id", "language", "code_type", "expected_cwe", "prediction",
        "debounce_ms", "request_ms", "backend_total_ms", "prediction_ms",
        "plugin_response_ms", "annotation_ms", "pipeline_ms", "end_to_end_ms", "timestamp",
    )

    private fun escapeCsvField(field: String): String =
        if (field.contains(",") || field.contains("\"") || field.contains("\n")) {
            "\"" + field.replace("\"", "\"\"") + "\""
        } else {
            field
        }

    private fun fmt(v: Double): String = "%.4f".format(v)

    fun toCsvRow(r: MeasuredRun): String = listOf(
        r.runId.toString(), r.language, r.codeType, r.expectedCwe, r.prediction,
        fmt(r.debounceMs), fmt(r.requestMs), fmt(r.backendTotalMs), fmt(r.predictionMs),
        fmt(r.pluginResponseMs), fmt(r.annotationMs), fmt(r.pipelineMs), fmt(r.endToEndMs),
        r.timestamp,
    ).joinToString(",") { escapeCsvField(it) }

    fun toCsv(runs: List<MeasuredRun>): String {
        val sb = StringBuilder()
        sb.append(CSV_HEADER.joinToString(","))
        sb.append("\n")
        runs.forEach { sb.append(toCsvRow(it)); sb.append("\n") }
        return sb.toString()
    }

    fun writeCsv(runs: List<MeasuredRun>, file: File) {
        file.parentFile?.mkdirs()
        file.writeText(toCsv(runs))
    }

    // snake_case field names in the JSON output, matching the CSV column
    // names above (run_id, expected_cwe, debounce_ms, ...) - MeasuredRun's
    // Kotlin properties stay idiomatic camelCase (runId, expectedCwe, ...).
    private val gson = GsonBuilder()
        .setPrettyPrinting()
        .setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES)
        .create()

    /** [metadata] is an arbitrary, JSON-serializable map (experiment
     * setup facts - warm-up count, plugin/backend version, etc. - see
     * Part 5). Kept generic here rather than a fixed data class so the
     * harness can freely add/omit fields without this module changing. */
    fun toJson(runs: List<MeasuredRun>, metadata: Map<String, Any?>): String {
        val payload = linkedMapOf<String, Any?>("metadata" to metadata, "runs" to runs)
        return gson.toJson(payload)
    }

    fun writeJson(runs: List<MeasuredRun>, metadata: Map<String, Any?>, file: File) {
        file.parentFile?.mkdirs()
        file.writeText(toJson(runs, metadata))
    }
}
