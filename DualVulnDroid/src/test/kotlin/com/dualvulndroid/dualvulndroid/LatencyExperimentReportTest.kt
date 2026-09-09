package com.dualvulndroid.dualvulndroid

import com.google.gson.Gson
import com.google.gson.JsonObject
import junit.framework.TestCase
import java.io.File

/**
 * Latency-measurement experiment task, Part 10 items 5/6: CSV/JSON
 * serialization correctness. Pure data - no IDE fixture, no backend.
 */
class LatencyExperimentReportTest : TestCase() {

    private fun sampleRun(runId: Int = 1) = MeasuredRun(
        runId = runId, language = "java", codeType = "cwe89_vulnerable", expectedCwe = "CWE-89",
        prediction = "SQL Injection", debounceMs = 500.1234, requestMs = 42.5,
        backendTotalMs = 38.2, predictionMs = 6.4, pluginResponseMs = 3.1,
        annotationMs = 1.2, pipelineMs = 46.8, endToEndMs = 546.9, timestamp = "2026-01-01T00:00:00Z",
    )

    // ---- 5. CSV serialization ----
    fun testCsvHeaderMatchesRequiredColumns() {
        val header = LatencyExperimentReport.CSV_HEADER
        for (required in listOf(
            "run_id", "language", "code_type", "expected_cwe", "prediction",
            "debounce_ms", "request_ms", "backend_total_ms", "prediction_ms",
            "plugin_response_ms", "annotation_ms", "pipeline_ms", "end_to_end_ms", "timestamp",
        )) {
            assertTrue("missing required column: $required", header.contains(required))
        }
    }

    fun testCsvRowFieldCountMatchesHeaderCount() {
        val row = LatencyExperimentReport.toCsvRow(sampleRun())
        // Naive split is fine here since none of this sample's fields contain a comma.
        assertEquals(LatencyExperimentReport.CSV_HEADER.size, row.split(",").size)
    }

    fun testCsvRoundTripValuesAreCorrect() {
        val run = sampleRun(runId = 7)
        val row = LatencyExperimentReport.toCsvRow(run)
        val fields = row.split(",")
        assertEquals("7", fields[0])
        assertEquals("java", fields[1])
        assertEquals("CWE-89", fields[3])
        assertEquals("500.1234", fields[5])
    }

    fun testCsvFieldContainingCommaIsQuotedAndEscaped() {
        val run = sampleRun().copy(codeType = "has,comma\"and quote")
        val row = LatencyExperimentReport.toCsvRow(run)
        assertTrue(row.contains("\"has,comma\"\"and quote\""))
    }

    fun testWriteCsvProducesAReadableFileWithHeaderPlusOneLinePerRun(): Unit {
        val tmp = File.createTempFile("latency_test", ".csv")
        try {
            val runs = listOf(sampleRun(1), sampleRun(2), sampleRun(3))
            LatencyExperimentReport.writeCsv(runs, tmp)
            val lines = tmp.readLines()
            assertEquals(4, lines.size) // header + 3 rows
            assertEquals(LatencyExperimentReport.CSV_HEADER.joinToString(","), lines[0])
        } finally {
            tmp.delete()
        }
    }

    // ---- 6. JSON serialization ----
    fun testJsonContainsMetadataAndAllRuns() {
        val runs = listOf(sampleRun(1), sampleRun(2))
        val metadata = mapOf("warmup_runs" to 5, "measured_runs" to 50, "debounce_setting_ms" to 500)
        val json = LatencyExperimentReport.toJson(runs, metadata)

        val parsed = Gson().fromJson(json, JsonObject::class.java)
        assertTrue(parsed.has("metadata"))
        assertTrue(parsed.has("runs"))
        assertEquals(5, parsed.getAsJsonObject("metadata").get("warmup_runs").asInt)
        assertEquals(2, parsed.getAsJsonArray("runs").size())
        assertEquals("CWE-89", parsed.getAsJsonArray("runs")[0].asJsonObject.get("expected_cwe").asString)
    }

    fun testWriteJsonProducesValidParsableFile() {
        val tmp = File.createTempFile("latency_test", ".json")
        try {
            LatencyExperimentReport.writeJson(listOf(sampleRun()), mapOf("measured_runs" to 1), tmp)
            val parsed = Gson().fromJson(tmp.readText(), JsonObject::class.java)
            assertEquals(1, parsed.getAsJsonArray("runs").size())
        } finally {
            tmp.delete()
        }
    }
}
