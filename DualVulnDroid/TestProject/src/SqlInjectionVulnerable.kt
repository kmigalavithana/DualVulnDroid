package com.example.securitytest

import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import java.awt.Cursor

class UserDatabase(context: Context) {

    private val database: SQLiteDatabase =
        object : SQLiteOpenHelper(
            context,
            "users.db",
            null,
            1
        ) {
            override fun onCreate(db: SQLiteDatabase) {
                db.execSQL(
                    """
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY,
                        username TEXT,
                        email TEXT
                    )
                    """.trimIndent()
                )
            }

            override fun onUpgrade(
                db: SQLiteDatabase,
                oldVersion: Int,
                newVersion: Int
            ) {
                db.execSQL("DROP TABLE IF EXISTS users")
                onCreate(db)
            }
        }.writableDatabase

    fun findUser(userId: String): Cursor {

        // Vulnerable: user-controlled input is concatenated into SQL
        val query =
            "SELECT id, username, email FROM users WHERE id=" + userId

        return database.rawQuery(query, null)
    }


}

