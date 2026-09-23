package com.example.securitydemo.sql

import android.database.Cursor
import android.database.sqlite.SQLiteDatabase

// DEMO 1 - SQL Injection (CWE-89), Kotlin - Quick Fix available.
// User input is concatenated straight into the SQL string passed to rawQuery().
class UserRepository(private val db: SQLiteDatabase) {

    fun findUser(userId: String): Cursor {
        val query = "SELECT * FROM users WHERE id=" + userId
        return db.rawQuery(query, null)
    }
}
