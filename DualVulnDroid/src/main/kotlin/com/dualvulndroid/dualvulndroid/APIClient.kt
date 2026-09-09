package com.dualvulndroid.dualvulndroid

import com.google.gson.Gson
import com.google.gson.annotations.SerializedName
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

data class Detection(
    val line: Int,
    val code: String,
    val type: String,
    val risk_weight: Double? = null,
    val critical_words: List<String>? = null,
    val source_to_sink_path: List<String>? = null,
    val dataflow_explanation: String? = null,
    val dataflow_verdict: String? = null
)

data class DataFlowFinding(
    val line: Int,
    val explanation: String,
    val path: List<String>? = null,
    val verdict: String? = null,
    val vulnerabilityType: String? = null
)

// Phase 4: one entry in the Hybrid Decision Engine's evidence trail
// (decision_engine.py's `reasons` list) - source of the signal, a
// human-readable detail, and its signed contribution to the final
// decision. See decision_engine.py for the exact documented weights.
data class DecisionReason(
    val source: String,
    val detail: String,
    val contribution: Double
)

// Real per-request SHAP contribution for one feature (predictor.py's
// `shapTopFeatures`) - not a static/precomputed value.
data class ShapFeature(
    val feature: String,
    val shapValue: Double
)

data class ScanResponse(
    val prediction: String,
    val vulnerable: Boolean,
    val vulnerabilityType: String,
    val confidence: Double,
    val explanation: String,
    val detections: List<Detection>,
    val dataFlow: List<DataFlowFinding>? = null,
    // Phase 4 additions - all nullable so responses from an older backend
    // (or /predict's guard-clause "no code provided" branch) still parse.
    val predictionModel: String? = null,
    val decision: String? = null,
    val decisionEvidence: List<DecisionReason>? = null,
    val securityFeatures: Map<String, Double>? = null,
    val severity: String? = null,
    val shapTopFeatures: List<ShapFeature>? = null
)

data class ScanRequest(
    val code: String,
    val fileName: String
)

// =====================================================
// Phase 5A: POST /developer/scan (batch project scan)
//
// Request/response shapes below mirror the EXISTING backend contract
// exactly (backend/app.py's BatchScanFile/BatchScanRequest, and
// predictor.to_developer_response()'s nested shape) - nothing here was
// invented; see the Phase 5A audit notes for the exact fields checked
// against app.py before writing these classes.
// =====================================================

data class BatchScanFileRequest(
    val code: String,
    val fileName: String
)

data class BatchScanRequest(
    val files: List<BatchScanFileRequest>
)

data class DeveloperModelInfo(
    val name: String,
    val version: String
)

data class DeveloperDataFlowEntry(
    val source: String?,
    val sink: String?,
    val path: List<String>? = null,
    val verdict: String? = null
)

data class DeveloperDecision(
    val riskLevel: String,
    val recommendation: String,
    val decisionConfidence: Double,
    val evidence: List<DecisionReason>? = null
)

// Matches predictor.to_developer_response()'s shape exactly (also the
// body of POST /developer/predict) - reused as-is for each file's result
// inside a batch response so the plugin has one shape to render for both
// single-file and project-level results.
data class DeveloperScanResult(
    val vulnerable: Boolean,
    val vulnerabilityType: String,
    val cwe: String? = null,
    val confidence: Double,
    val severity: String,
    val model: DeveloperModelInfo,
    val dataFlow: List<DeveloperDataFlowEntry>? = null,
    val securityFeatures: Map<String, Double>? = null,
    val decision: DeveloperDecision,
    val explanation: List<String>? = null,
    val detections: List<Detection>? = null
)

data class BatchFileResult(
    val fileName: String,
    val result: DeveloperScanResult? = null,
    // Present instead of `result` when this one file failed (e.g. it
    // exceeded the backend's per-file size limit) - the rest of the
    // batch still succeeds; see app.py's developer_scan().
    val error: String? = null
)

data class BatchScanResponse(
    val files: List<BatchFileResult>
)

// Latency-measurement experiment task: mirrors backend/predictor.py's
// optional "timing" response block exactly (see app.py's /predict,
// gated behind the X-Benchmark-Timing header). shapAndRuleDetectionMs is
// nullable only so an older/mismatched backend response missing that one
// sub-field still parses instead of failing the whole object.
data class BenchmarkTiming(
    @SerializedName("backend_total_ms") val backendTotalMs: Double,
    @SerializedName("prediction_ms") val predictionMs: Double,
    @SerializedName("shap_and_rule_detection_ms") val shapAndRuleDetectionMs: Double? = null,
    @SerializedName("dataflow_ms") val dataflowMs: Double,
    @SerializedName("decision_ms") val decisionMs: Double,
)

private data class ScanResponseWithTiming(val timing: BenchmarkTiming?)

class APIClient {

    companion object {
        // Default backend URL. Can be overridden without recompiling by
        // setting the DUALVULNDROID_BACKEND_URL environment variable
        // (e.g. if the backend is run on a different port or host).
        private const val DEFAULT_BACKEND_URL = "http://127.0.0.1:8000/predict"

        val BACKEND_URL: String =
            System.getenv("DUALVULNDROID_BACKEND_URL") ?: DEFAULT_BACKEND_URL

        // Derived from BACKEND_URL so overriding DUALVULNDROID_BACKEND_URL
        // (e.g. a different host/port) keeps both endpoints in sync;
        // independently overridable via DUALVULNDROID_DEVELOPER_SCAN_URL
        // for setups that genuinely need it to differ.
        private val DEFAULT_DEVELOPER_SCAN_URL: String =
            BACKEND_URL.removeSuffix("/predict").trimEnd('/') + "/developer/scan"

        val DEVELOPER_SCAN_URL: String =
            System.getenv("DUALVULNDROID_DEVELOPER_SCAN_URL") ?: DEFAULT_DEVELOPER_SCAN_URL

        // Matches backend/app.py's BatchScanRequest(files: ..., max_length=200) exactly.
        const val MAX_FILES_PER_BATCH = 200

        // Plugin-fix task, STEP 3's exact spec: connect=5s, write=10s,
        // read=30s, call=35s for the single-file /predict path.
        const val CONNECT_TIMEOUT_S = 5L
        const val WRITE_TIMEOUT_S = 10L
        const val READ_TIMEOUT_S = 30L
        const val CALL_TIMEOUT_S = 35L
        const val HEALTH_CHECK_TIMEOUT_S = 3L

        // STEP 3: "bounded retry only for transient connection
        // failures/timeouts (max 1 retry, small delay, never repeatedly
        // retry every keystroke)". Never applied to HTTP 4xx/5xx - those
        // are real backend answers, not transport failures.
        const val MAX_TRANSIENT_RETRIES = 1
        const val RETRY_DELAY_MS = 300L

        val BASE_URL: String = BACKEND_URL.removeSuffix("/predict").trimEnd('/')
    }

    enum class BackendAvailability { AVAILABLE, CONNECTION_REFUSED, TIMEOUT, HTTP_ERROR, UNKNOWN }

    data class BackendAvailabilityResult(val status: BackendAvailability, val detail: String)

    /**
     * STEP 2: a fast, cheap liveness probe against the backend's own "/"
     * route (returns {"message": "DualVulnDroid XGBoost Backend Running"})
     * so the plugin can tell a developer "the backend isn't running" in a
     * couple of seconds, distinctly from "the backend is running but this
     * particular request was slow" - the two symptoms the original single
     * generic timeout message conflated.
     */
    fun checkBackendAvailability(url: String = BASE_URL): BackendAvailabilityResult {
        val request = Request.Builder().url(url).get().build()
        return try {
            healthCheckClient.newCall(request).execute().use { response ->
                if (response.isSuccessful) {
                    BackendAvailabilityResult(BackendAvailability.AVAILABLE, "Backend reachable at $url")
                } else {
                    BackendAvailabilityResult(
                        BackendAvailability.HTTP_ERROR,
                        "Backend at $url responded with HTTP ${response.code}"
                    )
                }
            }
        } catch (e: java.net.SocketTimeoutException) {
            BackendAvailabilityResult(
                BackendAvailability.TIMEOUT,
                "Backend at $url did not respond within ${HEALTH_CHECK_TIMEOUT_S}s"
            )
        } catch (e: java.net.ConnectException) {
            BackendAvailabilityResult(
                BackendAvailability.CONNECTION_REFUSED,
                "Could not connect to $url - start the DualVulnDroid FastAPI backend (see backend/app.py)"
            )
        } catch (e: Exception) {
            BackendAvailabilityResult(BackendAvailability.UNKNOWN, "Unexpected error checking backend: ${e.message}")
        }
    }

    // Plugin-fix task, root cause #1: this client backs scanCode() - the
    // single-file POST /predict call used by BOTH the real-time
    // ExternalAnnotator on every edit AND "Rescan Current File". A real
    // /predict call runs feature extraction, XGBoost, a SHAP
    // TreeExplainer pass, and data-flow analysis server-side
    // (backend/predictor.py) - measured in the 70-300ms range when the
    // backend is idle, but predict() is a synchronous FastAPI route
    // (backend/app.py) served from Starlette's finite threadpool with a
    // single uvicorn worker, so a burst of near-simultaneous requests
    // (e.g. every keystroke, before debouncing was added below) queues up
    // and can easily push an individual request's real latency past a
    // couple of seconds even though the backend is healthy. The previous
    // connectTimeout=2s/readTimeout=2s (with no callTimeout, so a slow
    // response could also hang past both individually) turned that
    // ordinary queuing delay into a hard, misleading "Backend did not
    // respond in time (timeout)" failure. Widened to the same order of
    // magnitude as scanProjectBatch's already-correct batchClient below,
    // scaled down for a single file.
    private val client = OkHttpClient.Builder()
        .connectTimeout(CONNECT_TIMEOUT_S, TimeUnit.SECONDS)
        .writeTimeout(WRITE_TIMEOUT_S, TimeUnit.SECONDS)
        .readTimeout(READ_TIMEOUT_S, TimeUnit.SECONDS)
        .callTimeout(CALL_TIMEOUT_S, TimeUnit.SECONDS)
        .build()

    // Short-lived client for checkBackendAvailability()'s liveness probe -
    // deliberately much shorter than `client` above since it exists only
    // to answer "is anything listening at all," not to wait out a real
    // prediction.
    private val healthCheckClient = OkHttpClient.Builder()
        .connectTimeout(HEALTH_CHECK_TIMEOUT_S, TimeUnit.SECONDS)
        .readTimeout(HEALTH_CHECK_TIMEOUT_S, TimeUnit.SECONDS)
        .build()

    // A batch of up to 200 files each running XGBoost+SHAP+data-flow
    // analysis genuinely takes longer than a single-file scan - reusing
    // the 2s single-file timeout here would make every non-trivial batch
    // fail by design. Built from the same client (same connection pool/
    // config) with only the timeouts widened for this specific call.
    private val batchClient = client.newBuilder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS)
        .build()

    private val gson = Gson()

    var lastBatchError: String? = null
        private set

    /**
     * Scans multiple files in ONE request to POST /developer/scan.
     * Feature extraction, data-flow analysis, XGBoost, SHAP, and the
     * decision engine all run server-side (predictor.py) exactly as for
     * /predict - this method only serializes the request and parses the
     * response, per Phase 5A section 4.
     */
    // P0 Step 6: without `isCancelled`, the IDE's own progress-indicator
    // Cancel button is powerless once this call starts - OkHttp's
    // synchronous execute() only returns when the call finishes or is
    // explicitly cancelled from another thread, and MyToolWindow.runScan()
    // only checks indicator.checkCanceled() BETWEEN batches, never during
    // one. If the backend disappears (killed/restarted) or hangs mid-
    // request, the "Scan Project" button stays disabled for up to the full
    // readTimeout (120s) with no way for the user to unstick it early -
    // this reads as "the button is broken" even though it silently
    // recovers on its own once the timeout elapses. Passing a cancellation
    // check here lets the caller's Cancel button abort the in-flight call
    // immediately instead. Default preserves the exact previous behavior
    // for any other caller.
    fun scanProjectBatch(files: List<BatchScanFileRequest>, isCancelled: () -> Boolean = { false }): BatchScanResponse? {
        lastBatchError = null

        if (files.isEmpty()) {
            lastBatchError = "No files to scan."
            return null
        }
        if (files.size > MAX_FILES_PER_BATCH) {
            lastBatchError = "Batch of ${files.size} files exceeds the backend's limit of $MAX_FILES_PER_BATCH per request."
            return null
        }

        val json = gson.toJson(BatchScanRequest(files))
        val body = json.toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url(DEVELOPER_SCAN_URL)
            .post(body)
            .build()

        val call = batchClient.newCall(request)
        val cancelWatcher = Thread {
            try {
                while (!call.isCanceled()) {
                    if (isCancelled()) {
                        call.cancel()
                        break
                    }
                    Thread.sleep(150)
                }
            } catch (_: InterruptedException) {
                // Normal shutdown path once the call below completes.
            }
        }.apply { isDaemon = true; name = "DualVulnDroid-batch-cancel-watcher"; start() }

        return try {
            call.execute().use { response ->
                val responseBody = response.body?.string()

                when {
                    response.isSuccessful && responseBody != null -> {
                        try {
                            gson.fromJson(responseBody, BatchScanResponse::class.java)
                        } catch (e: com.google.gson.JsonSyntaxException) {
                            lastBatchError = "Backend returned invalid JSON (HTTP ${response.code}): ${e.message}"
                            null
                        }
                    }
                    response.code == 400 -> {
                        lastBatchError = "Backend rejected the batch request (400): $responseBody"
                        null
                    }
                    response.code == 401 -> {
                        lastBatchError = "Backend requires authentication (401), which this plugin does not support yet."
                        null
                    }
                    response.code == 413 -> {
                        lastBatchError = "Batch request was too large for the backend to accept (413)."
                        null
                    }
                    response.code == 422 -> {
                        lastBatchError = "Backend could not validate the batch request (422): $responseBody"
                        null
                    }
                    response.code >= 500 -> {
                        lastBatchError = "Backend failed to process the batch scan (HTTP ${response.code}) - " +
                            "this usually means an ML prediction failure. Check backend logs."
                        null
                    }
                    else -> {
                        lastBatchError = "Backend returned HTTP ${response.code}: $responseBody"
                        null
                    }
                }
            }
        } catch (e: java.io.IOException) {
            if (call.isCanceled()) {
                lastBatchError = "Scan cancelled."
                null
            } else if (e is java.net.SocketTimeoutException) {
                lastBatchError = "Backend did not respond in time (timeout) for a batch of ${files.size} files."
                null
            } else if (e is java.net.ConnectException) {
                lastBatchError = "Unable to connect to DualVulnDroid backend at $DEVELOPER_SCAN_URL."
                null
            } else {
                lastBatchError = "Unexpected error contacting backend: ${e.message}"
                e.printStackTrace()
                null
            }
        } catch (e: Exception) {
            lastBatchError = "Unexpected error contacting backend: ${e.message}"
            e.printStackTrace()
            null
        } finally {
            cancelWatcher.interrupt()
        }
    }

    // Phase 4 (section 12): scanCode() keeps its existing ScanResponse?
    // return type so none of its 3 call sites need to change, but every
    // failure path now sets a specific, human-readable message here
    // instead of just logging a stack trace - callers that want to show
    // the developer *why* a scan failed (rather than silently doing
    // nothing) can read this right after a null result.
    var lastError: String? = null
        private set

    fun scanCode(code: String, fileName: String = ""): ScanResponse? {
        lastError = null

        // STEP 3: bounded single retry, ONLY for transient transport
        // failures (connect refused / timeout) - never for an HTTP 4xx/5xx,
        // which is a real answer from the backend, not a dropped request.
        var attempt = 0
        while (true) {
            val outcome = attemptScanCode(code, fileName)
            if (outcome !is ScanAttemptOutcome.TransientFailure || attempt >= MAX_TRANSIENT_RETRIES) {
                return when (outcome) {
                    is ScanAttemptOutcome.Success -> outcome.response
                    is ScanAttemptOutcome.TransientFailure -> null
                    is ScanAttemptOutcome.PermanentFailure -> null
                }
            }
            attempt++
            println("[CodeSentinel] Transient failure (${outcome.errorType}), retrying ($attempt/$MAX_TRANSIENT_RETRIES)...")
            Thread.sleep(RETRY_DELAY_MS)
        }
    }

    private sealed class ScanAttemptOutcome {
        data class Success(val response: ScanResponse) : ScanAttemptOutcome()
        data class TransientFailure(val errorType: String) : ScanAttemptOutcome()
        data class PermanentFailure(val errorType: String) : ScanAttemptOutcome()
    }

    // STEP 5's exact required diagnostic log format. Never logs `code`
    // itself (the source text) - only the URL, endpoint, status, timing,
    // and result/error classification.
    private fun attemptScanCode(code: String, fileName: String): ScanAttemptOutcome {
        val requestData = ScanRequest(code, fileName)
        val json = gson.toJson(requestData)
        val body = json.toRequestBody("application/json".toMediaType())

        val request = Request.Builder()
            .url(BACKEND_URL)
            .post(body)
            .build()

        println("[CodeSentinel] Backend request START")
        println("[CodeSentinel] Backend URL: $BASE_URL")
        println("[CodeSentinel] Endpoint: /predict")
        val start = System.currentTimeMillis()

        return try {
            client.newCall(request).execute().use { response ->
                val elapsedMs = System.currentTimeMillis() - start
                println("[CodeSentinel] HTTP status: ${response.code}")
                println("[CodeSentinel] Response received in $elapsedMs ms")
                val responseBody = response.body?.string()

                when {
                    response.isSuccessful && responseBody != null -> {
                        try {
                            val parsed = gson.fromJson(responseBody, ScanResponse::class.java)
                            println("[CodeSentinel] Result: vulnerable=${parsed.vulnerable} type=${parsed.vulnerabilityType}")
                            // A retry that succeeds must not leave the FIRST
                            // (failed) attempt's message sitting in lastError -
                            // a caller must never see a stale error alongside
                            // a genuinely successful response.
                            lastError = null
                            ScanAttemptOutcome.Success(parsed)
                        } catch (e: com.google.gson.JsonSyntaxException) {
                            lastError = "Backend returned invalid JSON (HTTP ${response.code}): ${e.message}"
                            println("[CodeSentinel] Error type: malformed-response")
                            ScanAttemptOutcome.PermanentFailure("malformed-response")
                        }
                    }
                    response.code == 400 -> {
                        lastError = "Backend rejected the request (400): $responseBody"
                        println("[CodeSentinel] Error type: http-400")
                        ScanAttemptOutcome.PermanentFailure("http-400")
                    }
                    response.code == 422 -> {
                        lastError = "Backend could not validate the scan request (422): $responseBody"
                        println("[CodeSentinel] Error type: http-422")
                        ScanAttemptOutcome.PermanentFailure("http-422")
                    }
                    response.code == 404 -> {
                        lastError = "Backend endpoint not found (404): $BACKEND_URL - is the plugin pointed at the right backend version?"
                        println("[CodeSentinel] Error type: http-404")
                        ScanAttemptOutcome.PermanentFailure("http-404")
                    }
                    response.code >= 500 -> {
                        lastError = "Backend failed to process the scan (HTTP ${response.code}) - " +
                            "this usually means an ML prediction failure. Check backend logs."
                        println("[CodeSentinel] Error type: http-5xx")
                        ScanAttemptOutcome.PermanentFailure("http-5xx")
                    }
                    else -> {
                        lastError = "Backend returned HTTP ${response.code}: $responseBody"
                        println("[CodeSentinel] Error type: http-other")
                        ScanAttemptOutcome.PermanentFailure("http-other")
                    }
                }
            }
        } catch (e: java.net.SocketTimeoutException) {
            lastError = "Backend did not respond within the ${READ_TIMEOUT_S}s timeout. " +
                "It may be under heavy load, or a batch/heavier request is still processing - check the backend log."
            println("[CodeSentinel] Error type: timeout")
            ScanAttemptOutcome.TransientFailure("timeout")
        } catch (e: java.net.ConnectException) {
            lastError = "Could not connect to the backend at $BASE_URL - start it with " +
                "'uvicorn app:app --host 127.0.0.1 --port 8000' from the backend/ directory (see backend/.env.example)."
            println("[CodeSentinel] Error type: connection-refused")
            ScanAttemptOutcome.TransientFailure("connection-refused")
        } catch (e: Exception) {
            lastError = "Unexpected error contacting backend: ${e.message}"
            println("[CodeSentinel] Error type: unexpected (${e.javaClass.simpleName})")
            e.printStackTrace()
            ScanAttemptOutcome.PermanentFailure("unexpected")
        }
    }

    /**
     * Latency-measurement experiment task, Part 3: a SEPARATE, clearly
     * opt-in-only call used ONLY by LatencyExperimentTest, to fetch the
     * backend's own internal timing breakdown for a piece of code already
     * measured (T0-T8) by the real-time pipeline above. scanCode()/
     * attemptScanCode() - the actual real-time production call path
     * CodeSentinelAnnotator uses - are completely unmodified and never
     * send this header, so normal plugin request timing/behavior is
     * entirely unaffected by this function's existence. Never retried,
     * never affects `lastError`/`lastBatchError` - a failure here just
     * means this experiment run's backend_total_ms/prediction_ms are
     * unavailable, never a fabricated fallback value.
     */
    fun fetchBenchmarkTiming(code: String, fileName: String = ""): BenchmarkTiming? {
        val requestData = ScanRequest(code, fileName)
        val json = gson.toJson(requestData)
        val body = json.toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url(BACKEND_URL)
            .header("X-Benchmark-Timing", "1")
            .post(body)
            .build()
        return try {
            client.newCall(request).execute().use { response ->
                val responseBody = response.body?.string()
                if (!response.isSuccessful || responseBody == null) return null
                gson.fromJson(responseBody, ScanResponseWithTiming::class.java).timing
            }
        } catch (e: Exception) {
            null
        }
    }
}