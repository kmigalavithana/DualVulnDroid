"""
Real automated tests for the limited source-to-sink data-flow analyzer
(dataflow.py). These promote the ad-hoc verification snippets used
during development into a permanent regression suite.

Run from backend/:  python -m pytest tests/ -v
"""

from dataflow import analyze_sql_dataflow, analyze_cert_dataflow, sql_sink_safety_summary


# ---------------------------------------------------------------------
# SQL Injection (CWE-89)
# ---------------------------------------------------------------------

def test_sql_vulnerable_concatenation_spec_example():
    code = '''
String query = "SELECT * FROM users WHERE id=" + userId;
db.rawQuery(query, null);
'''
    findings = analyze_sql_dataflow(code)
    assert len(findings) == 1
    assert findings[0]["sink"] == "rawQuery()"


def test_sql_safe_parameterized_spec_example():
    code = '''
db.rawQuery(
    "SELECT * FROM users WHERE id=?",
    new String[]{userId}
);
'''
    assert analyze_sql_dataflow(code) == []
    safety = sql_sink_safety_summary(code)
    assert safety["sinks_found"] == 1
    assert safety["all_parameterized"] is True


def test_sql_traced_intent_to_rawquery():
    code = '''
public class LoginActivity extends Activity {
    public void onCreate() {
        String username = getIntent().getStringExtra("username");
        String query = "SELECT * FROM users WHERE name='" + username + "'";
        db.rawQuery(query, null);
    }
}
'''
    findings = analyze_sql_dataflow(code)
    assert len(findings) == 1
    f = findings[0]
    assert f["detection_basis"] == "traced-source"
    assert f["path"][0] == "Intent.getStringExtra()"
    assert f["path"][-1] == "rawQuery()"


def test_sql_edittext_source_to_rawquery():
    code = '''
public class SearchActivity extends Activity {
    public void search() {
        String term = searchBox.getText().toString();
        String query = "SELECT * FROM items WHERE name='" + term + "'";
        db.rawQuery(query, null);
    }
}
'''
    findings = analyze_sql_dataflow(code)
    assert len(findings) == 1
    assert findings[0]["path"][0] == "EditText.getText().toString()"


def test_sql_method_parameter_reaching_sink():
    code = '''
public void search(String userId) {
    String q = "SELECT * FROM users WHERE id=" + userId;
    db.rawQuery(q, null);
}
'''
    findings = analyze_sql_dataflow(code)
    assert len(findings) == 1
    assert findings[0]["detection_basis"] == "unparameterized-concatenation"


def test_sql_interprocedural_one_hop():
    code = '''
public class UserDao {
    public void search(String userId) {
        String q = "SELECT * FROM users WHERE id=" + userId;
        runQuery(q);
    }
    public void runQuery(String sql) {
        db.rawQuery(sql, null);
    }
}
'''
    findings = analyze_sql_dataflow(code)
    assert len(findings) == 1
    assert findings[0]["detection_basis"] == "traced-source-interprocedural"


def test_sql_unrelated_code_is_clean():
    code = '''
public class MainActivity extends Activity {
    public void onCreate() {
        Log.d("TAG", "hello world");
        int x = 5 + 3;
    }
}
'''
    assert analyze_sql_dataflow(code) == []


# ---------------------------------------------------------------------
# Certificate Validation (CWE-295)
# ---------------------------------------------------------------------

def test_cert_hostname_verifier_return_true_is_vulnerable():
    code = '''
val hv = object : HostnameVerifier {
    override fun verify(hostname: String, session: SSLSession): Boolean {
        return true
    }
}
'''
    findings = analyze_cert_dataflow(code)
    assert any(f["component"] == "HostnameVerifier" and f["verdict"] == "VULNERABLE" for f in findings)


def test_cert_hostname_verifier_default_delegate_is_safe():
    code = '''
val hv = object : HostnameVerifier {
    override fun verify(hostname: String, session: SSLSession): Boolean {
        return HttpsURLConnection.getDefaultHostnameVerifier().verify(hostname, session)
    }
}
'''
    findings = analyze_cert_dataflow(code)
    assert any(f["component"] == "HostnameVerifier" and f["verdict"] == "SAFE" for f in findings)


def test_cert_empty_trust_manager_is_vulnerable():
    code = '''
TrustManager[] trustAllCerts = new TrustManager[]{
    new X509TrustManager() {
        public void checkClientTrusted(X509Certificate[] chain, String authType) {}
        public void checkServerTrusted(X509Certificate[] chain, String authType) {}
        public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[]{}; }
    }
};
'''
    findings = analyze_cert_dataflow(code)
    vulnerable = [f for f in findings if f["verdict"] == "VULNERABLE"]
    assert len(vulnerable) == 2  # checkClientTrusted + checkServerTrusted


def test_cert_delegating_trust_manager_is_safe():
    code = '''
class RealTrustManager implements X509TrustManager {
    public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
        if (chain == null || chain.length == 0) {
            throw new CertificateException("Empty chain");
        }
        defaultTrustManager.checkServerTrusted(chain, authType);
    }
}
'''
    findings = analyze_cert_dataflow(code)
    assert any(f["component"] == "X509TrustManager.checkServerTrusted" and f["verdict"] == "SAFE" for f in findings)


def test_cert_webview_proceed_is_vulnerable():
    code = '''
client = new WebViewClient() {
    @Override
    public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
        handler.proceed();
    }
};
'''
    findings = analyze_cert_dataflow(code)
    assert any(f["component"] == "WebViewClient.onReceivedSslError" and f["verdict"] == "VULNERABLE" for f in findings)


def test_cert_webview_cancel_is_safe():
    code = '''
client = new WebViewClient() {
    @Override
    public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
        handler.cancel();
    }
};
'''
    findings = analyze_cert_dataflow(code)
    assert any(f["component"] == "WebViewClient.onReceivedSslError" and f["verdict"] == "SAFE" for f in findings)


def test_cert_unrelated_code_is_clean():
    code = 'System.out.println("hello world");'
    assert analyze_cert_dataflow(code) == []
