package com.dualvulndroid.dualvulndroid

/**
 * Phase 6, section 7: certificate-validation auto-fix is intentionally
 * limited to TWO unambiguous patterns:
 *   - a HostnameVerifier.verify() body that is nothing but `return true`;
 *   - SSLContext.init(km, <trust-all array>, random) where the array holds
 *     an X509TrustManager whose checkServerTrusted() is empty. Passing
 *     `null` instead makes SSLContext use the platform's default trust
 *     managers, i.e. real certificate validation.
 * Everything else (WebView handler.proceed(), a TrustManager with any real
 * logic in it) is NOT auto-fixed - "Safety is more important than fix
 * coverage."
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

    // ---- Trust-all X509TrustManager ----

    /** What replaces the trust-manager argument of SSLContext.init(). */
    const val DEFAULT_TRUST_MANAGERS_ARGUMENT = "null"

    private val COMMENTS = Regex("""//[^\n]*|/\*[\s\S]*?\*/""")

    // checkServerTrusted(...) [: Unit] [throws X] { }  - an empty body, i.e. no validation at all.
    private val EMPTY_CHECK_SERVER_TRUSTED = Regex("""\bcheckServerTrusted\s*\([^)]*\)[^{;=]*\{\s*}""")

    // The expression must BE the array - arrayOf(...)/arrayOf<TrustManager>(...) or
    // new TrustManager[]{...} / new X509TrustManager[]{...} - not a call that merely contains one.
    private val KOTLIN_ARRAY = Regex("""^arrayOf\s*(<[^>]*>)?\s*\([\s\S]*\)$""")
    private val JAVA_ARRAY = Regex("""^new\s+(javax\.net\.ssl\.)?(X509)?TrustManager\s*\[\s*]\s*\{[\s\S]*}$""")

    /**
     * True when [arrayExprText] is an array literal of trust managers that
     * contains an X509TrustManager whose checkServerTrusted() is empty -
     * the "trust every certificate" pattern. Comments inside the empty
     * body (`{ // trust all }`) still count as empty.
     */
    fun isTrustAllArray(arrayExprText: String, language: FixLanguage): Boolean {
        val text = arrayExprText.replace(COMMENTS, "").trim()
        val isArrayLiteral = when (language) {
            FixLanguage.KOTLIN -> KOTLIN_ARRAY.matches(text)
            FixLanguage.JAVA -> JAVA_ARRAY.matches(text)
        }
        return isArrayLiteral && text.contains("X509TrustManager") && EMPTY_CHECK_SERVER_TRUSTED.containsMatchIn(text)
    }
}
