






package com.dualvulndroid.fixture.cwe295safe;

import javax.net.ssl.HostnameVerifier;
import javax.net.ssl.SSLSession;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.X509TrustManager;
import java.security.cert.X509Certificate;
import java.security.cert.CertificateException;

// DELIBERATELY SAFE TEST FIXTURE - NOT A REAL APPLICATION.
// The counterpart to cwe295_vulnerable: a HostnameVerifier that delegates
// to a real hostname check, and a TrustManager that actually validates
// (can throw CertificateException) - no CWE-295 finding should ever be
// produced for this class.
public class SafeCertClient {
    public HostnameVerifier buildVerifier() {
        return new HostnameVerifier() {
            public boolean verify(String hostname, SSLSession session) {
                return HttpsURLConnection.getDefaultHostnameVerifier().verify(hostname, session);
            }
        };
    }

    public X509TrustManager buildTrustManager() {
        return new X509TrustManager() {
            public void checkClientTrusted(X509Certificate[] chain, String authType) throws CertificateException {
                throw new CertificateException("real validation would happen here");
            }

            public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
                throw new CertificateException("real validation would happen here");
            }

            public X509Certificate[] getAcceptedIssuers() {
                return new X509Certificate[0];
            }
        };
    }
}
