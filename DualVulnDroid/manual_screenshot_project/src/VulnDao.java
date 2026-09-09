package com.dualvulndroid.fixture.cwe89vuln;

import android.database.sqlite.SQLiteDatabase;
import android.database.Cursor;

// DELIBERATELY INSECURE TEST FIXTURE - NOT A REAL APPLICATION.
// Plants a real CWE-89 SQL Injection: the query is built by concatenating
// unsanitized input directly into the SQL string, then passed to
// rawQuery() with no parameterization.
public class VulnDao {
    private SQLiteDatabase db;

    public Cursor findUserByName(String userInput) {
        String query = "SELECT * FROM users WHERE name = '" + userInput + "'";
        return db.rawQuery(query, null);
    }
}
