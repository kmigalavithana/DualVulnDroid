# Manual smoke-test script, NOT a pytest test - run it by hand against a
# separately, manually started server (e.g. `uvicorn app:app --port 8000`).
# Named to avoid pytest's default collection patterns (test_*.py, *_test.py)
# so it's never imported/executed by `pytest`, only run directly with
# `python manual_predict_smoke.py`. Not run in CI.
# For the automated equivalent (same /predict + vulnerable-SQL scenario,
# via FastAPI TestClient with real assertions, no live server needed),
# see tests/test_api.py::test_predict_traced_sql_detects_vulnerable.
import requests

url = "http://127.0.0.1:8000/predict"
payload = {
    "code": """import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;

public class SecurityTest {
    public Cursor getUser(SQLiteDatabase db, String userId) {
        return db.rawQuery("SELECT * FROM users WHERE id = '" + userId + "'", null);
    }
}
"""
}
response = requests.post(url, json=payload)
print(response.json())
