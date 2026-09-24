package com.example.securitydemo.safe

import android.database.Cursor
import android.database.sqlite.SQLiteDatabase

// DEMO 7 - SAFE: parameterized query. The user input is passed as a bound
// argument, never concatenated into the SQL text.
class SafeUserRepository(private val db: SQLiteDatabase) {

    fun findUser(userId: String): Cursor {
        return db.rawQuery("SELECT * FROM users WHERE id = ?", arrayOf(userId))
    }
}
