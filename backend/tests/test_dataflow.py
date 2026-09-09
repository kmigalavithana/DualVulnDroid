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


# ---------------------------------------------------------------------
# Variable-indirected parameterized queries (val sql = "...?..."; then
# db.rawQuery(sql, args) on a later line) - previously invisible to
# sql_sink_safety_summary()/analyze_sql_dataflow(), which only recognized
# a sink call as safely parameterized when the '?' literal was written
# inline as the sink's own first argument. This is the CodeSentinel
# false-positive fix: a variable is only resolved as a safe literal when
# its most recent assignment was a PURE '?'-literal with no concatenation
# and no tainted source - genuinely unsafe concatenation/interpolation
# reaching the same sink must still be caught (see the vulnerable cases
# below).
# ---------------------------------------------------------------------

def test_sql_safe_inline_parameterized_kotlin_arrayof():
    """(a) Inline literal, Kotlin arrayOf() args - still safe."""
    code = '''
val result = db.rawQuery(
    "SELECT * FROM users WHERE username = ? AND password = ?",
    arrayOf(username, password)
)
'''
    assert analyze_sql_dataflow(code) == []
    safety = sql_sink_safety_summary(code)
    assert safety["sinks_found"] == 1
    assert safety["all_parameterized"] is True


def test_sql_safe_parameterized_via_local_variable():
    """(b) The exact SqlInjectionSafe.kt pattern: the '?' literal lives in
    a separate `val sql = ...` assignment, not inline in the sink call."""
    code = '''
class LoginDatabase {
    fun login(db: SQLiteDatabase, username: String, password: String) {
        val sql = "SELECT * FROM users WHERE username = ? AND password = ?"
        val result = db.rawQuery(
            sql,
            arrayOf(username, password)
        )
    }
}
'''
    assert analyze_sql_dataflow(code) == []
    safety = sql_sink_safety_summary(code)
    assert safety["sinks_found"] == 1
    assert safety["all_parameterized"] is True


def test_sql_vulnerable_interpolated_string_via_local_variable():
    """(c) The SqlInjectionVulnerable.kt pattern: Kotlin string
    interpolation (not a '?' placeholder) embedded in a variable later
    passed to the sink. The new variable-resolution logic must NOT
    mistake this for a safe parameterized literal - there is no '?' in
    the literal at all, so it must never be credited as confirmed-safe."""
    code = '''
class LoginDatabase {
    fun login(db: SQLiteDatabase, username: String, password: String) {
        val sql = "SELECT * FROM users WHERE username = '$username' AND password = '$password'"
        val result = db.rawQuery(sql, null)
    }
}
'''
    safety = sql_sink_safety_summary(code)
    assert safety["sinks_found"] == 1
    assert safety["all_parameterized"] is False


def test_sql_vulnerable_concatenation_via_local_variable():
    """(d) A variable built via string concatenation (not a pure literal)
    reaching the sink - must still be traced as vulnerable, and must never
    be resolved as a safe literal by the new variable-indirection logic."""
    code = '''
fun search(db: SQLiteDatabase, userId: String) {
    val sql = "SELECT * FROM users WHERE id=" + userId
    val result = db.rawQuery(sql, null)
}
'''
    findings = analyze_sql_dataflow(code)
    assert len(findings) == 1
    assert findings[0]["detection_basis"] == "unparameterized-concatenation"

    safety = sql_sink_safety_summary(code)
    assert safety["sinks_found"] == 1
    assert safety["all_parameterized"] is False


def test_sql_reassignment_to_unsafe_is_not_masked_by_earlier_safe_literal():
    """A variable first bound to a safe literal, then reassigned to a
    concatenation before reaching the sink, must be flagged - a stale
    safe-literal binding must never suppress a real finding."""
    code = '''
fun search(db: SQLiteDatabase, userId: String) {
    var sql = "SELECT * FROM users WHERE id = ?"
    sql = "SELECT * FROM users WHERE id=" + userId
    val result = db.rawQuery(sql, null)
}
'''
    findings = analyze_sql_dataflow(code)
    assert len(findings) == 1
    assert findings[0]["detection_basis"] == "unparameterized-concatenation"


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


# ---------------------------------------------------------------------
# P0 Step 5 regression: fully package-qualified interface names.
#
# Real Android code very commonly writes `implements javax.net.ssl.X509TrustManager`
# / `implements javax.net.ssl.HostnameVerifier` without a separate simple-name
# import. TRUST_MANAGER_RE/HOSTNAME_VERIFIER_RE previously only matched the
# bare, unqualified name, so any code written this way was entirely invisible
# to analyze_cert_dataflow() - it silently returned [] instead of a SAFE or
# VULNERABLE verdict, in both directions (this is what let a genuinely
# vulnerable empty-body TrustManager slip through with zero dataflow_cert
# evidence, and separately let a genuinely safe one land on
# SUSPICIOUS_REVIEW purely from the static keyword rule + an
# unrelated-but-confident ML signal - see decision_engine.py's P0 Step 5
# evidence-combination fix for the second half of that).
# ---------------------------------------------------------------------

def test_cert_trust_manager_fully_qualified_name_safe_is_recognized():
    code = '''
public class RealTrustManager implements javax.net.ssl.X509TrustManager {
    public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
        if (chain == null || chain.length == 0) {
            throw new CertificateException("Empty chain");
        }
    }
}
'''
    findings = analyze_cert_dataflow(code)
    assert any(f["component"] == "X509TrustManager.checkServerTrusted" and f["verdict"] == "SAFE" for f in findings)


def test_cert_trust_manager_fully_qualified_name_vulnerable_is_recognized():
    code = '''
public class InsecureTrustManager implements javax.net.ssl.X509TrustManager {
    public void checkServerTrusted(X509Certificate[] chain, String authType) {
    }
}
'''
    findings = analyze_cert_dataflow(code)
    assert any(f["component"] == "X509TrustManager.checkServerTrusted" and f["verdict"] == "VULNERABLE" for f in findings)


def test_cert_hostname_verifier_fully_qualified_name_is_recognized():
    code = '''
public class NetworkConfig {
    HostnameVerifier hv = new javax.net.ssl.HostnameVerifier() {
        public boolean verify(String hostname, SSLSession session) {
            return true;
        }
    };
}
'''
    findings = analyze_cert_dataflow(code)
    assert any(f["component"] == "HostnameVerifier" and f["verdict"] == "VULNERABLE" for f in findings)
