package android.database;

/** Minimal stand-in for Android's Cursor so the demo compiles without the Android SDK. */
public interface Cursor extends java.io.Closeable {
    boolean moveToNext();

    String getString(int columnIndex);
}
