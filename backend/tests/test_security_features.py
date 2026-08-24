from security_features import extract_security_features, FEATURE_NAMES


def test_feature_vector_is_deterministic():
    code = 'db.rawQuery("SELECT * FROM x WHERE id=" + userId, null);'
    assert dict(extract_security_features(code)) == dict(extract_security_features(code))


def test_all_feature_names_present():
    feats = extract_security_features('int x = 1;')
    assert list(feats.keys()) == FEATURE_NAMES


def test_unrelated_code_is_all_zero():
    feats = extract_security_features('System.out.println("hello world");')
    assert all(v == 0 for v in feats.values())


def test_empty_code_is_all_zero():
    feats = extract_security_features('')
    assert all(v == 0 for v in feats.values())


def test_vulnerable_sql_sets_expected_features():
    code = '''
String username = getIntent().getStringExtra("username");
String query = "SELECT * FROM users WHERE name=" + username;
db.rawQuery(query, null);
'''
    feats = extract_security_features(code)
    assert feats["sql_source_detected"] == 1
    assert feats["sql_sink_detected"] == 1
    assert feats["sql_source_to_sink"] == 1
    assert feats["sql_string_concatenation"] == 1
    assert feats["sql_parameterized_query"] == 0
    assert feats["sql_raw_query"] == 1


def test_safe_sql_sets_expected_features():
    code = 'db.rawQuery("SELECT * FROM users WHERE id=?", new String[]{userId});'
    feats = extract_security_features(code)
    assert feats["sql_parameterized_query"] == 1
    assert feats["sql_source_to_sink"] == 0
    assert feats["safe_flow_count"] >= 1


def test_vulnerable_cert_sets_expected_features():
    code = '''
val hv = object : HostnameVerifier {
    override fun verify(hostname: String, session: SSLSession): Boolean {
        return true
    }
}
'''
    feats = extract_security_features(code)
    assert feats["certificate_hostname_verifier"] == 1
    assert feats["certificate_return_true"] == 1
    assert feats["unsafe_flow_count"] >= 1
