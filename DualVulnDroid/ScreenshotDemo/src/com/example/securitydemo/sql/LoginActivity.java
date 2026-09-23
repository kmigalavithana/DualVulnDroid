package com.example.securitydemo.sql;

import android.app.Activity;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;

// DEMO 2 - SQL Injection (CWE-89), Java - Quick Fix available.
// Tainted data flow: an Intent extra (untrusted input) reaches rawQuery().
public abstract class LoginActivity extends Activity {

    private SQLiteDatabase db;

    public Cursor login() {
        String username = getIntent().getStringExtra("username");
        String query = "SELECT * FROM users WHERE name = " + username;
        return db.rawQuery(query, null);
    }
}
