package com.example.securitydemo.sql

import android.database.sqlite.SQLiteDatabase

// DEMO 3 - SQL Injection (CWE-89) through execSQL(), Kotlin.
// Quick Fix: "Use parameterized query (execSQL)" adds the bind-args argument.
class NotesDao(private val db: SQLiteDatabase) {

    fun deleteNote(noteId: String) {
        db.execSQL("DELETE FROM notes WHERE id=" + noteId)
    }
}
