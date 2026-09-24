package com.example.securitydemo.safe;

import java.io.IOException;
import java.net.URL;
import javax.net.ssl.HttpsURLConnection;

// DEMO 8 - SAFE: the connection keeps the platform's default certificate and
// hostname checks - nothing overrides them.
public class SafeHttpsClient {

    public HttpsURLConnection connect(URL url) throws IOException {
        HttpsURLConnection connection = (HttpsURLConnection) url.openConnection();
        connection.setConnectTimeout(10_000);
        return connection;
    }
}
