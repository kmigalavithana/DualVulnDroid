package com.example.securitydemo.cert;

import java.io.IOException;
import java.net.URL;
import javax.net.ssl.HostnameVerifier;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLSession;

// DEMO 5 - Certificate Validation (CWE-295), Java - Quick Fix available.
// Hostname verification is switched off with an always-true verifier.
public class ApiConnection {

    public HttpsURLConnection connect(URL url) throws IOException {
        HttpsURLConnection connection = (HttpsURLConnection) url.openConnection();
        connection.setHostnameVerifier(new HostnameVerifier() {
            @Override
            public boolean verify(String hostname, SSLSession session) {
                return true;
            }
        });
        return connection;
    }
}
