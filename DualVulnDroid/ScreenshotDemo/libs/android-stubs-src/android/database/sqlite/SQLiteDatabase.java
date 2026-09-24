package android.database.sqlite;

import android.database.Cursor;

/** Minimal stand-in for Android's SQLiteDatabase (signatures only). */
public abstract class SQLiteDatabase {
    public abstract Cursor rawQuery(String sql, String[] selectionArgs);

    public abstract void execSQL(String sql);

    public abstract void execSQL(String sql, Object[] bindArgs);
}
