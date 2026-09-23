package com.example.securitydemo.sql

import android.database.sqlite.SQLiteDatabase

// DEMO 3 - SQL Injection (CWE-89), Kotlin - detected, manual remediation.
// execSQL() is not covered by the automatic Quick Fix, so the tooltip explains
// the finding and the fix has to be applied by hand.
class NotesDao(private val db: SQLiteDatabase) {

    fun deleteNote(noteId: String) {
        db.execSQL("DELETE FROM notes WHERE id=" + noteId)
    }
}
