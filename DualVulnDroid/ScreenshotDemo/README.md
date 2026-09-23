# DualVulnDroid screenshot demo

A small IntelliJ project that exercises everything the DualVulnDroid plugin does,
for both vulnerability types:

- **CWE-89 SQL Injection**
- **CWE-295 Improper Certificate Validation**

Every file below was checked against the real backend and the real plugin code
(annotator + Quick Fix locators). The "Expected" column is what you should see.

## Files

| File | Vulnerability | Expected in the editor | Quick Fix (Alt+Enter) |
|---|---|---|---|
| `src/.../sql/UserRepository.kt` | CWE-89 (Kotlin) | Red underline on `db.rawQuery(query, null)` | **Use parameterized query (rawQuery)** |
| `src/.../sql/LoginActivity.java` | CWE-89 (Java), tainted data flow | Red underline; tooltip shows `Intent.getStringExtra() → username → query → rawQuery()` | **Use parameterized query (rawQuery)** |
| `src/.../sql/NotesDao.kt` | CWE-89 via `execSQL` | Red underline | None - manual remediation (explained in the tooltip) |
| `src/.../cert/InsecureHttpsClient.kt` | CWE-295 (Kotlin) | Red underline | **Use default hostname verifier** |
| `src/.../cert/ApiConnection.java` | CWE-295 (Java) | Red underline | **Use default hostname verifier** |
| `src/.../cert/TrustAllManager.kt` | CWE-295 via empty `X509TrustManager` | Red underline | None - manual remediation |
| `src/.../safe/SafeUserRepository.kt` | Safe (parameterized query) | No findings | - |
| `src/.../safe/SafeHttpsClient.java` | Safe code | **Amber "Needs Review"** underline - the model's keyword rule reacts to HTTPS connection code. Use it to show the review tier. | - |
| `src/Main.kt` | - | No findings | - |

`libs/android-stubs.jar` provides minimal `Cursor` / `SQLiteDatabase` / `Intent` / `Activity`
classes so the Android code resolves (no red errors) without the Android SDK. It is a library,
not a source folder, so the plugin never scans it. Its source is in `libs/android-stubs-src/`.

## Before you start

1. Start the backend: `uvicorn app:app --host 127.0.0.1 --port 8000` from `backend/`.
2. Start the plugin sandbox IDE: `./gradlew runIde` from `DualVulnDroid/`.
3. In the sandbox IDE: **File → Open → `DualVulnDroid/ScreenshotDemo`**.
   If IntelliJ asks for a JDK, pick any installed JDK (17+).
4. Open the **DualVulnDroid** tool window.

## Screenshot checklist

1. **Real-time detection** - open `UserRepository.kt`; wait a moment for the red underline.
2. **Tooltip** - hover the underline in `LoginActivity.java` (CWE, confidence, data-flow path).
3. **Quick Fix menu** - caret on the underline in `UserRepository.kt`, press **Alt+Enter**.
4. **Quick Fix result** - apply it; the fix-verification dialog shows before/after and the underline disappears.
5. **Certificate Quick Fix** - same in `InsecureHttpsClient.kt` (**Use default hostname verifier**).
6. **Manual remediation** - hover `NotesDao.kt` or `TrustAllManager.kt` (detected, no automatic fix).
7. **Needs Review tier** - `SafeHttpsClient.java` (amber underline).
8. **No false positive** - `SafeUserRepository.kt` (clean).
9. **Scan Project** - tool window → **Scan Project**: findings for both CWEs, grouped, with the summary cards.
10. **Scan File dialog** - tool window → **Scan File** (Scan Current File / Choose Another File / Cancel).
11. **Navigation** - click a finding in the tool window → the editor jumps to the line.
12. **Finding details** - Alt+Enter → **DualVulnDroid: Show finding details**.

## Resetting after a Quick Fix

Quick Fixes edit the demo files. To get the vulnerable versions back:

```
git restore DualVulnDroid/ScreenshotDemo/src
```

Applying a fix also writes a local log to `ScreenshotDemo/.dualvulndroid/`; it is safe to delete.
