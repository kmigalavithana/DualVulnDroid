package com.dualvulndroid.dualvulndroid

/**
 * Phase 6, section 7: certificate-validation auto-fix is intentionally
 * limited to ONE unambiguous pattern - a HostnameVerifier.verify() body
 * that is nothing but `return true`. Everything else (WebView
 * handler.proceed(), custom X509TrustManager logic) is explicitly NOT
 * auto-fixed per the phase's own instructions - "Safety is more
 * important than fix coverage."
 */
object CertificateFixAnalyzer {

    const val MANUAL_REMEDIATION_MESSAGE =
        "Automatic fix unavailable. Manual certificate validation review recommended."

    data class HostnameVerifierMatch(
        val hostnameParam: String,
        val sessionParam: String,
        val language: FixLanguage
    ) {
        // Only the RETURNED EXPRESSION, not a whole method body - the fix
        // replaces `true` with this, leaving the `return` statement (and
        // everything else about the method) untouched. Fully-qualified
        // so it's valid without needing to add/manage an import.
        fun replacementExpression(): String =
            "javax.net.ssl.HttpsURLConnection.getDefaultHostnameVerifier().verify($hostnameParam, $sessionParam)"
    }

    /**
     * bodyStatements: the verify() method body with ONLY real statements
     * (no comments/whitespace-only entries) - the SAME "single statement,
     * literally `return true`" check dataflow.py's own
     * certificate_return_true feature already uses, re-expressed here
     * independently for the fix's own validation (never trusts the prior
     * finding blindly - see section 9).
     */
    fun matchReturnTrueOnly(bodyStatements: List<String>, hostnameParam: String?, sessionParam: String?, language: FixLanguage): HostnameVerifierMatch? {
        if (bodyStatements.size != 1) return null
        if (bodyStatements[0].trim().replace(" ", "") != "returntrue") return null
        if (hostnameParam.isNullOrBlank() || sessionParam.isNullOrBlank()) return null
        return HostnameVerifierMatch(hostnameParam, sessionParam, language)
    }
}
