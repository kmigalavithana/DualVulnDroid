package com.dualvulndroid.fixture.cwe295vuln;

import javax.net.ssl.HostnameVerifier;
import javax.net.ssl.SSLSession;

// DELIBERATELY INSECURE TEST FIXTURE - NOT A REAL APPLICATION.
// Plants a real CWE-295 Improper Certificate Validation: the
// HostnameVerifier unconditionally accepts every hostname, disabling
// hostname checking entirely.
public class VulnCertClient {
    public HostnameVerifier buildVerifier() {
        return new HostnameVerifier() {
            public boolean verify(String hostname, SSLSession session) {
                return true;
            }
        };
    }
}
