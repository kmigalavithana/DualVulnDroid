package com.dualvulndroid.dualvulndroid

import com.intellij.testFramework.fixtures.BasePlatformTestCase
import java.io.File
import java.time.Instant
import java.time.format.DateTimeFormatter

/**
 * Latency-measurement experiment task, Parts 4/11: the actual controlled
 * benchmark. Drives the REAL, registered CodeSentinelAnnotator through
 * IntelliJ's REAL daemon highlighting pipeline (myFixture.doHighlighting()
 * - not a direct collectInformation()/doAnnotate() call, so apply() -
 * and therefore T7/T8 - genuinely runs too, with a real AnnotationHolder
 * supplied by the platform) against the REAL running FastAPI backend
 * (no mocks, no simulated API - see checkBackendReachable()).
 *
 * What is automated here: every one of the 5 warm-up + 50 measured
 * "edit events" (a fresh file with different/representative code,
 * standing in for a developer's edit) and the resulting real annotator
 * pass, exactly as the live IDE would trigger on that edit.
 *
 * What is NOT automated / a documented limitation (Part 11's own escape
 * valve: "if the full IDE automation cannot reliably generate real
 * user-edit events, create a clearly documented controlled benchmark
 * harness and state exactly which part is automated and which part is
 * manually triggered"): this runs inside a headless IntelliJ Platform
 * test instance (JUnit + BasePlatformTestCase), not a visible, rendered
 * IDE window with actual keystrokes typed by a human or a UI-automation
 * tool. No pixels are rendered or captured. This is the same escalation
 * in rigor LiveAnnotatorIntegrationTest already documents for its own,
 * smaller-scale real-backend tests - genuine PSI/document state, a real
 * registered ExternalAnnotator, a real HTTP round trip, a real
 * AnnotationHolder - just not a human typing in a visible window.
 *
 * Each measured event is fully sequential (Part 4C): this is a single
 * JUnit test method with a plain for-loop, so event N+1's
 * configureByText()+doHighlighting() call only starts after event N's
 * has returned - there is no concurrency and therefore no artificial
 * queueing.
 */
class LatencyExperimentTest : BasePlatformTestCase() {

    companion object {
        const val WARMUP_COUNT = 5
        const val MEASURED_COUNT = 50
    }

    private fun checkBackendReachable() {
        val probe = APIClient().scanCode("int x = 1;", "ReachabilityProbe.java")
        if (probe == null) {
            fail(
                "Real backend not reachable at ${APIClient.BACKEND_URL} - the latency experiment " +
                    "requires the real FastAPI backend running (never simulated/mocked for the final " +
                    "benchmark, per Part 11). Start it and re-run."
            )
        }
    }

    // ---- Representative Java snippets, drawn from/matching the patterns
    // already used and verified against the real backend in
    // LiveAnnotatorIntegrationTest.kt - not invented for this experiment. ----

    private data class Template(val codeType: String, val expectedCwe: String, val code: String)

    private val cwe89Vulnerable = Template(
        "cwe89_vulnerable", "CWE-89",
        """
        public class LoginActivity {
            public void onCreate() {
                String username = getIntent().getStringExtra("username");
                String query = "SELECT * FROM users WHERE name=" + username;
                db.rawQuery(query, null);
            }
        }
        """.trimIndent()
    )

    private val cwe89Safe = Template(
        "cwe89_safe", "SAFE",
        """
        public class LoginActivity {
            public void login(String userId) {
                db.rawQuery("SELECT * FROM users WHERE id=?", new String[]{userId});
            }
        }
        """.trimIndent()
    )

    private val cwe295Vulnerable = Template(
        "cwe295_vulnerable", "CWE-295",
        """
        import javax.net.ssl.HostnameVerifier;
        import javax.net.ssl.SSLSession;
        public class NetworkConfig {
            HostnameVerifier hv = new HostnameVerifier() {
                public boolean verify(String hostname, SSLSession session) {
                    return true;
                }
            };
        }
        """.trimIndent()
    )

    private val cwe295Safe = Template(
        "cwe295_safe", "SAFE",
        """
        import java.security.cert.X509Certificate;
        import java.security.cert.CertificateException;
        public class RealTrustManager implements javax.net.ssl.X509TrustManager {
            public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
                if (chain == null || chain.length == 0) {
                    throw new CertificateException("Empty chain");
                }
            }
            public void checkClientTrusted(X509Certificate[] chain, String authType) throws CertificateException {
                if (chain == null || chain.length == 0) {
                    throw new CertificateException("Empty chain");
                }
            }
            public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
        }
        """.trimIndent()
    )

    // 50 measured events: 20 CWE-89 vulnerable, 10 CWE-89 safe,
    // 10 CWE-295 vulnerable, 10 CWE-295 safe (Part 4B: include both CWE
    // categories plus safe examples, keep code sizes representative).
    private fun buildMeasuredPlan(): List<Template> {
        val plan = mutableListOf<Template>()
        repeat(20) { plan.add(cwe89Vulnerable) }
        repeat(10) { plan.add(cwe89Safe) }
        repeat(10) { plan.add(cwe295Vulnerable) }
        repeat(10) { plan.add(cwe295Safe) }
        return plan
    }

    private fun buildWarmupPlan(): List<Template> =
        listOf(cwe89Vulnerable, cwe89Safe, cwe295Vulnerable, cwe295Safe, cwe89Vulnerable)

    private var globalFileCounter = 0

    /** Drives ONE real edit-to-annotation cycle through the real,
     * registered annotator via the real IntelliJ highlighting pipeline.
     * Returns the newly completed LatencyTelemetry event for this run, or
     * null if none completed (a documented, non-fabricated miss - see
     * Part 12's "unless a documented environment failure prevents this"). */
    private fun runOneEvent(template: Template): Pair<LatencyTelemetry.LatencyEvent, String>? {
        globalFileCounter++
        val fileName = "LatencyRun${globalFileCounter}_${template.codeType}.java"
        val before = LatencyTelemetry.snapshot().size

        myFixture.configureByText(fileName, template.code)
        val highlights = myFixture.doHighlighting()

        val after = LatencyTelemetry.snapshot()
        if (after.size != before + 1) {
            // Documented miss (Part 12) - never fabricate a row for a run
            // that didn't produce exactly one completed measurement.
            println("[LatencyExperiment] WARNING: run for $fileName did not produce exactly one completed event (before=$before, after=${after.size})")
            return null
        }
        val event = after.last()

        val prediction = when {
            highlights.any { it.description?.contains("SQL Injection") == true } -> "SQL Injection"
            highlights.any { it.description?.contains("Certificate Validation") == true } -> "Certificate Validation"
            else -> "None"
        }
        return event to prediction
    }

    fun testRunLatencyExperiment() {
        checkBackendReachable()
        LatencyTelemetry.enabled = true
        LatencyTelemetry.reset()

        // ---- A. Warm-up (Part 4A): unrecorded, discarded ----
        var warmupCompleted = 0
        for (template in buildWarmupPlan()) {
            if (runOneEvent(template) != null) warmupCompleted++
        }
        println("[LatencyExperiment] Warm-up complete: $warmupCompleted/${WARMUP_COUNT} events produced a measurement (discarded).")
        LatencyTelemetry.reset() // discard warm-up measurements entirely

        // ---- B/C/D. Measured, sequential, recorded individually ----
        val measuredRuns = mutableListOf<MeasuredRun>()
        var runId = 0
        var missedRuns = 0
        for (template in buildMeasuredPlan()) {
            val result = runOneEvent(template)
            if (result == null) {
                missedRuns++
                continue
            }
            val (event, prediction) = result
            runId++
            val nanosToMs = { n: Long -> n / 1_000_000.0 }

            // Backend-internal breakdown for THIS SAME code, via a
            // separate, opt-in-only call (APIClient.fetchBenchmarkTiming) -
            // made AFTER the real measured pipeline above already
            // completed, so it cannot affect T0-T8 in any way. A miss
            // here (null) is recorded as 0.0 and is visible as such in
            // the raw data - never a fabricated estimate.
            val timing = APIClient().fetchBenchmarkTiming(template.code, template.codeType + ".java")

            measuredRuns.add(
                MeasuredRun(
                    runId = runId,
                    language = "java",
                    codeType = template.codeType,
                    expectedCwe = template.expectedCwe,
                    prediction = prediction,
                    debounceMs = nanosToMs(event.debounceNanos),
                    requestMs = nanosToMs(event.requestNanos),
                    backendTotalMs = timing?.backendTotalMs ?: 0.0,
                    predictionMs = timing?.predictionMs ?: 0.0,
                    pluginResponseMs = nanosToMs(event.pluginResponseProcessingNanos),
                    annotationMs = nanosToMs(event.annotationNanos),
                    pipelineMs = nanosToMs(event.pipelineNanos),
                    endToEndMs = nanosToMs(event.endToEndNanos),
                    timestamp = DateTimeFormatter.ISO_INSTANT.format(Instant.now()),
                )
            )
        }

        println("[LatencyExperiment] Measured phase complete: ${measuredRuns.size}/${MEASURED_COUNT} events produced a measurement ($missedRuns missed/documented).")

        // ---- Part 12 validation, asserted here so a broken experiment
        // fails the build loudly rather than silently producing bad data ----
        assertTrue("At least one measured run is required to produce a report", measuredRuns.isNotEmpty())
        val seenIds = mutableSetOf<Int>()
        for (r in measuredRuns) {
            assertTrue("Duplicate run_id: ${r.runId}", seenIds.add(r.runId))
            assertTrue("debounce_ms must not be negative", r.debounceMs >= 0)
            assertTrue("request_ms must not be negative", r.requestMs >= 0)
            assertTrue("plugin_response_ms must not be negative", r.pluginResponseMs >= 0)
            assertTrue("annotation_ms must not be negative", r.annotationMs >= 0)
            assertTrue("pipeline_ms must not be negative", r.pipelineMs >= 0)
            assertTrue("end_to_end_ms must not be negative", r.endToEndMs >= 0)
            assertTrue("end_to_end_ms must be >= pipeline_ms (T8-T0 >= T8-T1)", r.endToEndMs >= r.pipelineMs)
        }

        // ---- Part 5: raw data output, outside DualVulnDroid/backend/IEEE ----
        val outputDir = resolveExperimentOutputDir()
        val metadata = linkedMapOf<String, Any?>(
            "warmup_runs" to WARMUP_COUNT,
            "warmup_runs_completed" to warmupCompleted,
            "measured_runs_requested" to MEASURED_COUNT,
            "measured_runs_completed" to measuredRuns.size,
            "measured_runs_missed" to missedRuns,
            "plugin_build_identifier" to (System.getProperty("dualvulndroid.pluginVersion") ?: "1.0-SNAPSHOT"),
            "backend_url" to APIClient.BACKEND_URL,
            "debounce_setting_ms" to 500,
            "os_name" to System.getProperty("os.name"),
            "os_arch" to System.getProperty("os.arch"),
            "java_version" to System.getProperty("java.version"),
            "available_processors" to Runtime.getRuntime().availableProcessors(),
            "experiment_datetime_utc" to DateTimeFormatter.ISO_INSTANT.format(Instant.now()),
        )

        LatencyExperimentReport.writeCsv(measuredRuns, File(outputDir, "latency_results.csv"))
        LatencyExperimentReport.writeJson(measuredRuns, metadata, File(outputDir, "latency_results.json"))
        println("[LatencyExperiment] Wrote ${measuredRuns.size} measured runs to ${outputDir.absolutePath}")

        LatencyTelemetry.enabled = false
        LatencyTelemetry.reset()
    }

    /** DualVulnDroid/'s Gradle Test task working directory defaults to
     * the project directory itself - "../latency_experiment" therefore
     * resolves to <repo root>/latency_experiment, outside DualVulnDroid/,
     * backend/, and the IEEE workspace, matching Part 5's instruction. */
    private fun resolveExperimentOutputDir(): File {
        val dir = File(File(System.getProperty("user.dir")), "../latency_experiment").canonicalFile
        dir.mkdirs()
        return dir
    }
}
