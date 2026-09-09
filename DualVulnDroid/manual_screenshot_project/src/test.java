package com.example.securitytest

import android.database.Cursor
import android.database.sqlite.SQLiteDatabase

class UserDatabase {

    fun findUser(db: SQLiteDatabase, userInput: String): Cursor {

        // User-controlled input is directly concatenated into SQL
        val query = "SELECT * FROM users WHERE username = '$userInput'"

        return db.rawQuery(query, null)
    }

    fun getUserById(db: SQLiteDatabase, id: String): Cursor {

        // Vulnerable SQL Injection
        val sql = "SELECT * FROM users WHERE id = $id"

        return db.rawQuery(sql, null)
    }
}