package com.example.securitydemo.cert

import java.net.URL
import javax.net.ssl.HostnameVerifier
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.SSLSession

// DEMO 4 - Certificate Validation (CWE-295), Kotlin - Quick Fix available.
// The HostnameVerifier accepts every host, so a man-in-the-middle certificate
// for any domain is trusted.
class InsecureHttpsClient {

    private val trustAllHosts = object : HostnameVerifier {
        override fun verify(hostname: String, session: SSLSession): Boolean {
            return true
        }
    }

    fun open(url: URL): HttpsURLConnection {
        val connection = url.openConnection() as HttpsURLConnection
        connection.hostnameVerifier = trustAllHosts
        return connection
    }
}
