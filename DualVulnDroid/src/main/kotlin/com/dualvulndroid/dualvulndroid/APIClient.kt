package com.dualvulndroid.dualvulndroid

import com.google.gson.Gson
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
    }

    private val client = OkHttpClient.Builder()
        .connectTimeout(2, TimeUnit.SECONDS)
        .readTimeout(2, TimeUnit.SECONDS)
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
    fun scanProjectBatch(files: List<BatchScanFileRequest>): BatchScanResponse? {
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

        return try {
            batchClient.newCall(request).execute().use { response ->
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
        } catch (e: java.net.SocketTimeoutException) {
            lastBatchError = "Backend did not respond in time (timeout) for a batch of ${files.size} files."
            null
        } catch (e: java.net.ConnectException) {
            lastBatchError = "Unable to connect to DualVulnDroid backend at $DEVELOPER_SCAN_URL."
            null
        } catch (e: Exception) {
            lastBatchError = "Unexpected error contacting backend: ${e.message}"
            e.printStackTrace()
            null
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
        val requestData = ScanRequest(code, fileName)
        val json = gson.toJson(requestData)
        val body = json.toRequestBody("application/json".toMediaType())

        val request = Request.Builder()
            .url(BACKEND_URL)
            .post(body)
            .build()

        return try {
            client.newCall(request).execute().use { response ->
                val responseBody = response.body?.string()

                when {
                    response.isSuccessful && responseBody != null -> {
                        try {
                            gson.fromJson(responseBody, ScanResponse::class.java)
                        } catch (e: com.google.gson.JsonSyntaxException) {
                            lastError = "Backend returned invalid JSON (HTTP ${response.code}): ${e.message}"
                            null
                        }
                    }
                    response.code == 400 -> {
                        lastError = "Backend rejected the request (400): $responseBody"
                        null
                    }
                    response.code == 422 -> {
                        lastError = "Backend could not validate the scan request (422): $responseBody"
                        null
                    }
                    response.code == 404 -> {
                        lastError = "Backend endpoint not found (404): $BACKEND_URL"
                        null
                    }
                    response.code >= 500 -> {
                        lastError = "Backend failed to process the scan (HTTP ${response.code}) - " +
                            "this usually means an ML prediction failure. Check backend logs."
                        null
                    }
                    else -> {
                        lastError = "Backend returned HTTP ${response.code}: $responseBody"
                        null
                    }
                }
            }
        } catch (e: java.net.SocketTimeoutException) {
            lastError = "Backend did not respond in time (timeout). Is it under heavy load?"
            null
        } catch (e: java.net.ConnectException) {
            lastError = "Could not reach the backend at $BACKEND_URL - is it running?"
            null
        } catch (e: Exception) {
            lastError = "Unexpected error contacting backend: ${e.message}"
            e.printStackTrace()
            null
        }
    }

}