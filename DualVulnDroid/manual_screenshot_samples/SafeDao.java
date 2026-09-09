package com.dualvulndroid.fixture.cwe89safe;

import android.database.sqlite.SQLiteDatabase;
import android.database.Cursor;

// DELIBERATELY SAFE TEST FIXTURE - NOT A REAL APPLICATION.
// The counterpart to cwe89_vulnerable: the same query shape, but properly
// parameterized (a '?' placeholder with a separate selectionArgs array),
// so no CWE-89 finding should ever be produced for this class.
public class SafeDao {
    private SQLiteDatabase db;

    public Cursor findUserByName(String userInput) {
        return db.rawQuery("SELECT * FROM users WHERE name = ?", new String[]{userInput});
    }
}
