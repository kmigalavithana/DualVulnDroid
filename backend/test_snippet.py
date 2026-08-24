from predictor import predict_code
import json

code = """
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;

public class SecurityTest {

    // 1. ...
    public Cursor getUser(SQLiteDatabase db, String userId) {
        return db.rawQuery("SELECT * FROM users WHERE id = '" + userId + "'", null);
    }
}
"""

res = predict_code(code)
print(json.dumps(res, indent=2))
