package com.dualvulndroid.dualvulndroid

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * Phase 6, section 18: certificate-validation Quick Fix is deliberately
 * limited to ONE pattern. Items 3-6 below are not "expected to fail" -
 * they document that CertificateFixAnalyzer never even offers a match
 * for those shapes, by design ("Safety is more important than fix
 * coverage").
 */
class CertificateFixAnalyzerTest {

    // ---- 1. HostnameVerifier returning true - the one supported case ----
    @Test
    fun `single return-true statement is matched`() {
        val match = CertificateFixAnalyzer.matchReturnTrueOnly(
            listOf("return true"), "hostname", "session", FixLanguage.JAVA
        )
        assertNotNull(match)
        assertEquals(
            "javax.net.ssl.HttpsURLConnection.getDefaultHostnameVerifier().verify(hostname, session)",
            match!!.replacementExpression()
        )
    }

    @Test
    fun `parameter names are preserved exactly, never assumed`() {
        val match = CertificateFixAnalyzer.matchReturnTrueOnly(
            listOf("return true"), "host", "sslSession", FixLanguage.KOTLIN
        )
        assertNotNull(match)
        assertEquals(
            "javax.net.ssl.HttpsURLConnection.getDefaultHostnameVerifier().verify(host, sslSession)",
            match!!.replacementExpression()
        )
    }

    // ---- 2. Default hostname verifier (already safe) - no match, no fix needed ----
    @Test
    fun `a body that already delegates is not matched (nothing to fix)`() {
        val match = CertificateFixAnalyzer.matchReturnTrueOnly(
            listOf("return HttpsURLConnection.getDefaultHostnameVerifier().verify(hostname, session)"),
            "hostname", "session", FixLanguage.JAVA
        )
        assertNull(match)
    }

    // ---- More than one statement: even if it ends in `return true`, not confidently safe ----
    @Test
    fun `multi-statement bodies are never matched even if they end in return true`() {
        val match = CertificateFixAnalyzer.matchReturnTrueOnly(
            listOf("log(hostname)", "return true"), "hostname", "session", FixLanguage.JAVA
        )
        assertNull(match)
    }

    @Test
    fun `missing parameter names never produce a match`() {
        val match = CertificateFixAnalyzer.matchReturnTrueOnly(listOf("return true"), null, "session", FixLanguage.JAVA)
        assertNull(match)
    }

    // ---- 3. WebView handler.proceed() - out of scope by design: this
    // analyzer has no function that could ever match WebView code, so
    // there is no code path capable of offering a fix for it. ----
    @Test
    fun `WebView proceed-style text is never treated as the HostnameVerifier pattern`() {
        val match = CertificateFixAnalyzer.matchReturnTrueOnly(
            listOf("handler.proceed()"), "view", "handler", FixLanguage.JAVA
        )
        assertNull(match)
    }

    // ---- 5. Empty TrustManager - out of scope by design: an empty body
    // is not a single "return true" statement. ----
    @Test
    fun `empty method bodies (TrustManager-style) are never matched`() {
        val match = CertificateFixAnalyzer.matchReturnTrueOnly(emptyList(), "chain", "authType", FixLanguage.JAVA)
        assertNull(match)
    }

    // ---- 6. Safe TrustManager delegation - out of scope by design: a
    // throw/delegate body is not a single "return true" statement. ----
    @Test
    fun `throwing or delegating bodies (safe TrustManager) are never matched`() {
        val match = CertificateFixAnalyzer.matchReturnTrueOnly(
            listOf("throw new CertificateException()"), "chain", "authType", FixLanguage.JAVA
        )
        assertNull(match)
    }
}
