package com.dualvulndroid.dualvulndroid

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Phase 5A, section 20: pure serialization/parsing tests for the
 * /developer/scan batch contract - no IntelliJ platform fixture needed.
 */
class BatchScanParsingTest {

    private val gson = Gson()

    // ---- 1. Batch request serialization ----
    @Test
    fun `batch request serializes to the exact backend contract shape`() {
        val request = BatchScanRequest(
            files = listOf(
                BatchScanFileRequest(code = "db.rawQuery(x, null);", fileName = "app/src/main/java/A.kt"),
                BatchScanFileRequest(code = "int x = 1;", fileName = "app/src/main/java/B.java")
            )
        )
        val json = gson.toJson(request)

        // Must match backend/app.py's BatchScanRequest{files: [{code, fileName}]} exactly -
        // no "path"/"content" or any other invented field names.
        assertTrue(json.contains("\"files\""))
        assertTrue(json.contains("\"code\":\"db.rawQuery(x, null);\""))
        assertTrue(json.contains("\"fileName\":\"app/src/main/java/A.kt\""))
        assertTrue(!json.contains("\"path\""))
        assertTrue(!json.contains("\"content\""))
    }

    // ---- 2. Batch response parsing (single successful file) ----
    @Test
    fun `parses a batch response with one successful result`() {
        val json = """
        {
          "files": [
            {
              "fileName": "A.kt",
              "result": {
                "vulnerable": true,
                "vulnerabilityType": "SQL Injection",
                "cwe": "CWE-89",
                "confidence": 87.5,
                "severity": "HIGH",
                "model": {"name": "XGBoost-Hybrid", "version": "production"},
                "dataFlow": [{"source": "Intent.getStringExtra()", "sink": "rawQuery()", "path": ["Intent.getStringExtra()", "query", "rawQuery()"], "verdict": "VULNERABLE"}],
                "securityFeatures": {"sql_source_detected": 1.0},
                "decision": {"riskLevel": "HIGH", "recommendation": "REVIEW", "decisionConfidence": 0.9, "evidence": []},
                "explanation": ["User-controlled input reaches SQL execution."],
                "detections": [{"line": 4, "code": "db.rawQuery(query, null);", "type": "SQL Injection"}]
              }
            }
          ]
        }
        """.trimIndent()

        val response = gson.fromJson(json, BatchScanResponse::class.java)

        assertEquals(1, response.files.size)
        val fileResult = response.files[0]
        assertEquals("A.kt", fileResult.fileName)
        assertNull(fileResult.error)
        assertEquals("SQL Injection", fileResult.result?.vulnerabilityType)
        assertEquals("CWE-89", fileResult.result?.cwe)
        assertEquals("rawQuery()", fileResult.result?.dataFlow?.get(0)?.sink)
    }

    // ---- 3. Empty findings ----
    @Test
    fun `parses a batch response with zero vulnerable files`() {
        val json = """
        {
          "files": [
            {"fileName": "A.kt", "result": {"vulnerable": false, "vulnerabilityType": "SQL Injection", "confidence": 91.0, "severity": "LOW",
              "model": {"name": "XGBoost-Hybrid", "version": "production"}, "decision": {"riskLevel": "LOW", "recommendation": "NONE", "decisionConfidence": 0.1}}}
          ]
        }
        """.trimIndent()

        val response = gson.fromJson(json, BatchScanResponse::class.java)
        assertEquals(1, response.files.size)
        assertEquals(false, response.files[0].result?.vulnerable)
    }

    // ---- 4 & 5. Multiple findings, SQL + Certificate together ----
    @Test
    fun `parses multiple files with mixed SQL and certificate findings`() {
        val json = """
        {
          "files": [
            {"fileName": "Login.kt", "result": {"vulnerable": true, "vulnerabilityType": "SQL Injection", "cwe": "CWE-89", "confidence": 90.0, "severity": "HIGH",
              "model": {"name": "XGBoost-Hybrid", "version": "production"}, "decision": {"riskLevel": "HIGH", "recommendation": "REVIEW", "decisionConfidence": 0.9}}},
            {"fileName": "Net.kt", "result": {"vulnerable": true, "vulnerabilityType": "Certificate Validation", "cwe": "CWE-295", "confidence": 80.0, "severity": "HIGH",
              "model": {"name": "XGBoost-Hybrid", "version": "production"}, "decision": {"riskLevel": "HIGH", "recommendation": "REVIEW", "decisionConfidence": 0.8}}},
            {"fileName": "Main.kt", "result": {"vulnerable": false, "vulnerabilityType": "SQL Injection", "confidence": 95.0, "severity": "LOW",
              "model": {"name": "XGBoost-Hybrid", "version": "production"}, "decision": {"riskLevel": "LOW", "recommendation": "NONE", "decisionConfidence": 0.1}}}
          ]
        }
        """.trimIndent()

        val response = gson.fromJson(json, BatchScanResponse::class.java)
        assertEquals(3, response.files.size)

        val vulnerableTypes = response.files.mapNotNull { it.result }.filter { it.vulnerable }.map { it.vulnerabilityType }
        assertTrue(vulnerableTypes.contains("SQL Injection"))
        assertTrue(vulnerableTypes.contains("Certificate Validation"))
        assertEquals(1, response.files.count { it.result?.vulnerable == false })
    }

    // ---- 6. Backend error response (per-file error, not a whole-batch failure) ----
    @Test
    fun `parses a per-file error entry alongside successful results`() {
        val json = """
        {
          "files": [
            {"fileName": "Huge.kt", "error": "code exceeds the 200000 byte limit."},
            {"fileName": "Ok.kt", "result": {"vulnerable": false, "vulnerabilityType": "SQL Injection", "confidence": 88.0, "severity": "LOW",
              "model": {"name": "XGBoost-Hybrid", "version": "production"}, "decision": {"riskLevel": "LOW", "recommendation": "NONE", "decisionConfidence": 0.1}}}
          ]
        }
        """.trimIndent()

        val response = gson.fromJson(json, BatchScanResponse::class.java)
        assertEquals(2, response.files.size)
        assertNull(response.files[0].result)
        assertTrue(response.files[0].error!!.contains("200000 byte limit"))
        assertEquals("Ok.kt", response.files[1].fileName)
    }

    // ---- 7. Malformed response ----
    @Test(expected = com.google.gson.JsonSyntaxException::class)
    fun `malformed batch response throws instead of producing garbage`() {
        gson.fromJson("{\"files\": [not valid", BatchScanResponse::class.java)
    }

    @Test
    fun `response missing the files field parses to null list rather than crashing the caller`() {
        val response = gson.fromJson("{}", BatchScanResponse::class.java)
        // Gson leaves non-nullable Kotlin fields as null when absent from JSON -
        // callers (MyToolWindow) must treat a null/empty files list safely.
        assertNull(response.files)
    }
}
