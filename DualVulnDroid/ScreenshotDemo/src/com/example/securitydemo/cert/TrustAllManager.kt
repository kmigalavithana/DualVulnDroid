package com.example.securitydemo.cert

import java.security.cert.X509Certificate
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManager
import javax.net.ssl.X509TrustManager

// DEMO 6 - Certificate Validation (CWE-295), Kotlin.
// An X509TrustManager with empty checks accepts every certificate chain.
// Quick Fix: "Use default certificate validation" passes null to init()
// (the platform's real trust managers) and removes the trust-all array.
class TrustAllManager {

    fun insecureContext(): SSLContext {
        val trustAllCerts = arrayOf<TrustManager>(
            object : X509TrustManager {
                override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {}
                override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {}
                override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
            }
        )
        val context = SSLContext.getInstance("TLS")
        context.init(null, trustAllCerts, null)
        return context
    }
}
