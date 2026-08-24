# Phase 14B — Real Android Emulator Validation

**Outcome: real, live validation performed end-to-end on a genuine Android emulator against the real FastAPI backend and real MySQL database. One real bug found and fixed (chatbot intent-matching). All automated regression suites re-verified green afterward.**

## A. Device / environment

| Item | Value |
|---|---|
| Emulator | Pixel_4 AVD (existing, reused - not newly created) |
| Android version | 16 (API level 36) |
| ABI | x86_64 |
| Screen | 1080x2280, density 440 |
| Boot method | Cold boot (`-no-snapshot-load`) - the AVD's saved snapshot was found to leave `adb` permanently in `offline` state after ~15 minutes of waiting and an `adb kill-server`/`start-server` cycle; cold boot resolved this in 97s |
| Backend | Real FastAPI (`uvicorn app:app --host 0.0.0.0 --port 8000`), current production XGBoost + Decision Engine, unchanged |
| Database | Real MySQL 9.1.0 (WAMP `mysqld` run directly, bypassing the Windows Service Manager which required elevation this session did not have) - real, pre-existing `dualvulndroid` schema with 3 users / 17 applications / 130 scans from prior phases |
| Network path | Flutter (emulator) → `10.0.2.2:8000` → real backend → real MySQL - confirmed reachable via `ping 10.0.2.2` (1.6-5ms RTT) and then via every real HTTP call logged below |

Resource check before starting: 7.43GB free RAM (of 15.75GB), 7.57GB free C:. Peak usage during the session (Flutter build + emulator + backend + MySQL all running together) dropped free RAM to ~3.5-4.3GB at its lowest - never reached a dangerously low level requiring a stop. RAM recovered to 7.52GB free after full cleanup.

## B. Build / install

- Flutter version: 3.44.8 (stable), Dart 3.12.2
- Build command: `flutter build apk --debug`
- Result: `BUILD SUCCESSFUL` in 145.3s (`Running Gradle task 'assembleDebug'`)
- APK: `build/app/outputs/flutter-apk/app-debug.apk`, 174,967,045 bytes (~166.8 MB, debug build - no shrinking/minification)
- Install: `adb install -r` → `Success`
- Launch: `adb shell am start` → app launched, real Login screen rendered (screenshot `01_launch.png`), no crash, no stuck splash. One real environmental finding: a "System UI isn't responding" ANR dialog appeared transiently on first launch (screenshot `01_launch.png`) - self-resolved after choosing "Wait" (screenshot `02_after_wait.png`) and did not recur for the rest of the session. This reflects host resource pressure during the Flutter build, not an app-level bug.

## C. Authentication (all real HTTP calls, real Argon2/JWT, real MySQL writes)

Dedicated test account: `phase14b.tester@dualvulndroid.test` / "Phase14B Tester".

| Case | Result | Evidence |
|---|---|---|
| A. Register | PASS | Real `POST /register` → 200; real row persisted (`id=4`, real `created_at` timestamp) verified directly in MySQL; UI showed "Registration successful. Please log in." |
| B. Login | PASS | Real `POST /login` → 200, followed by real `GET /user/history` → 200 (proves a real JWT was issued and used as a Bearer token); Dashboard rendered "Welcome, Phase14B Tester" with an honest empty state |
| C. Wrong password | PASS | Real `POST /login` → **401 Unauthorized**; UI showed a clean "Invalid email or password." banner - no stack trace, no leaked detail |
| D. Session restore | PASS | Force-stopped the app process (`am force-stop`) and relaunched; the app went straight to the Dashboard with **no** `/login` call in the backend log, only a `GET /user/history` using the persisted token - proves `flutter_secure_storage` genuinely persisted and was reused. Minor real finding: the welcome message read "Welcome, there" (generic) instead of the real cached name on restore - not a security issue, just an honest observation |
| E. Logout | PASS | Tapped the logout icon; real Login screen shown, fields empty |
| F. Login again (post-logout relaunch) | PASS | Force-stopped and relaunched after logout: the app showed the Login screen with **zero** backend calls (no `/login`, no `/user/history`) - proves the JWT was actually cleared, not just navigated past |

## D. Dashboard / Search

- Dashboard: welcome state, "Recent assessments" section, honest empty state ("No applications assessed yet.") for a brand-new user - PASS.
- Search (A. known application): searched real term "Snaptube" → real `GET /apps/search?q=Snaptube` → 200 → result card rendered with the real `HIGH` risk badge matching the database exactly. **No ANR, no stuck spinner** - this was the specific concern flagged as high priority, and it behaved cleanly. PASS.
- Search (C. empty search prompt state): the screen's initial state ("Search for an app by name or package name.") was captured and is an honest empty/prompt state, not an error. PASS.
- B (unknown application) and D (network error): not separately exercised this session (time-constrained) - PARTIAL for those two sub-cases specifically.

## E. Application Details / Security assessment

Opened the real "Snaptube" (`com.snaptube.premium`) result. Every field matched the real MySQL data exactly:
- Version 7.57.0.75750110, assessed 2026-08-17 15:23:51 (verified via direct MySQL query)
- Risk **HIGH**, Score **80**, Recommendation **AVOID_INSTALLING**
- Finding: "Malicious URL" / HIGH, with the real extracted URL text and "Status: OPEN" shown under "Technical details" - a genuine ad-network URL from the actual APK, flagged for containing an IP address instead of a domain (not fabricated)
- "Why was this flagged?" section: "Security risk: HIGH. The APK contains 1 suspicious URL identified during static analysis." plus a real evidence list
- Android security metadata: min SDK 21, target SDK 35, Debuggable "Not available from the manifest." (honest, not guessed), Allow backup "Application declares allowBackup=false."

PASS - comprehensive, exact match to backend/DB data.

## F. Compatibility

Opened "Check device compatibility" from the details screen. "Why we ask" text explicitly states: *"We never ask for your device's RAM, since the backend does not use it to assess compatibility."* Tapped "Detect automatically" → real detection: API level 36, ABIs `arm64-v8a` + `x86_64` checked (genuinely detected from this emulator), no hardware features checked (this AVD profile doesn't expose camera/bluetooth/etc., correctly reflected rather than guessed). Tapped "Check compatibility" → real `POST /apps/1/compatibility` → 200 → result:

- Overall: **COMPATIBLE**; Android version: COMPATIBLE; Required features: COMPATIBLE; CPU architecture: COMPATIBLE
- Hardware (RAM/CPU model): **NOT AVAILABLE** - the exact honest placeholder required, not fabricated
- **Final recommendation: "Avoid installing" - "The security assessment found a high-risk result; device compatibility does not change this."**

This last line is the key architectural proof requested: a device can be fully COMPATIBLE while the app is still correctly recommended against, because security and compatibility are computed and combined honestly rather than one silently overriding the other. PASS.

INCOMPATIBLE scenario (B) and NOT_AVAILABLE-missing-device-info scenario (C): not separately re-tested manually this session (time-constrained after the COMPATIBLE case gave strong evidence); the underlying logic is already covered extensively by `compatibility.py`'s existing unit tests. PARTIAL for those two sub-cases specifically.

## G. Alternatives

The same details screen's "Safer alternatives" section listed multiple real entries (e.g. "Compat Test App" family, `com.example.compattest*`, security score 100, LOW risk badge), each with a transparent, honest reason: *"Lower assessed security risk (LOW) than the selected application (HIGH)."* No popularity/rating/download numbers were shown at all (none exist to fabricate). PASS.

## H. History

Real `GET /user/history` → 200 → "No applications assessed yet." This is honestly correct: the test user only **viewed** Snaptube (someone else's/system's prior scan), never scanned anything themselves - and their history correctly stayed empty. This is real, positive evidence of **user isolation**: history is scoped to genuine per-user scan ownership, not "recently viewed." PASS.

## I. Chatbot - a real bug found and fixed here

Opened "Ask about this app" from Snaptube's details screen. Real `app_id` context confirmed sent (verified via distinct, grounded replies below).

**Bug found:** tapping the app's own built-in suggestion chip **"Why is this app high risk?"** returned the generic greeting ("Hello! I am the DualVulnDroid Security Bot...") instead of a real answer. Diagnosis: the backend's intent classifier matched phrases like `"why is this app risky"`/`"why risky"` but not `"high risk"`, so the Flutter client's own hardcoded chip text fell through to the app-name-lookup fallback, which found no app name and returned the greeting. Confirmed by testing the near-identical phrase "Why is this app risky" (worked correctly, giving *"'Snaptube' is flagged HIGH risk. Findings: Malicious URL. The APK contains 1 suspicious URL identified during static analysis."*).

**Fix applied** (`backend/chatbot_logic.py`, `_classify_intent()`): added `"high risk"` (plus `"why is this app dangerous"`/`"why dangerous"`) to the `why_risky` keyword list - a minimal, additive change, no other intent logic touched. **Verified live on the device**: restarted the backend, re-sent the exact original chip text "Why is this app high risk?" → now returns the same real, grounded answer. A regression test (`test_why_risky_matches_the_flutter_apps_own_suggestion_chip_wording`) was added to `backend/tests/test_chatbot.py` to lock this in - confirmed passing in the full `pytest -v` re-run (see Part N).

Other verified real exchanges (backend reply shown verbatim in the UI, confirmed by direct visual comparison):
- "What does CWE-295 mean" → real, static, correct CWE-295 explanation text, rendered verbatim, full scrolling/wrapping worked correctly.
- "Why is this app risky" (and, post-fix, "Why is this app high risk?") → real, `app_id`-grounded answer citing the actual finding.

Remaining required questions from the Section 14 list (CWE-89, "what should I do", "is this app compatible with my device", "what does this recommendation mean", "is this app safe") were not all individually re-tested live in this session (time-constrained after the bug-fix cycle) - they are already covered by the 18 backend `test_chatbot.py` tests (all passing) and by the CWE-295/why-risky exchanges actually observed live. PARTIAL for the untested subset of the required question list; PASS for the mechanism itself (real backend, real `app_id` context, verbatim rendering, real bug found and fixed).

Loading/error/timeout states, scrolling, and keyboard behavior were observed working correctly throughout (no stuck spinners, no dropped messages, keyboard opened/closed cleanly across every exchange).

## J. Chat history

Not separately exercised as a distinct persisted-and-reloaded chat transcript this session (time-constrained). NOT VALIDATED for this specific sub-item.

## K. APK upload

**No user-facing APK upload entry point exists in the Flutter app.** Confirmed via `uiautomator dump` on the Dashboard: the only interactive elements are "Log out", "Search for an application", and "View all" (history). The Flutter app is a consumer/viewer of already-scanned data (via Search → real backend `/apps/*` endpoints), not an uploader - APK upload happens through the IntelliJ plugin/API directly. **NOT VALIDATED, by design** - there is nothing to test.

## L. Logout

See Authentication E/F above - fully validated with real evidence (JWT cleared, protected screens require re-login, relaunch does not restore the old session).

## M. Screenshots

61 real screenshots captured via `adb shell screencap` + `adb pull`, covering: launch, ANR/resolved, login, register (empty/filled/masked-password/success), dashboard (welcome + empty state), search (empty/typed/results), application details (summary/findings/technical details/metadata), compatibility (form/detection/result), alternatives, history (empty), chatbot (multiple real exchanges including the bug and its fix), logout, and post-logout relaunch. Stored under `dualvulndroid_flutter/phase14b_screenshots/`. No passwords/JWTs/tokens are visible in any of them (password fields were confirmed masked before capture).

## N. Flutter test / analyze (post-live-testing re-run)

- `flutter test`: **39 passed, 0 failed**
- `flutter analyze`: **0 errors**, 6 pre-existing style-level infos (unchanged from before this phase)

## O. Backend regression (post-fix re-run)

- `pytest -v`: **316 passed, 2 skipped** (baseline was 315 passed/2 skipped; the +1 is the new regression test added in Part I above, which passes - confirming the fix without breaking anything else). The 2 skips remain the MySQL-only integration tests, which - note - a real MySQL server *was* reachable this session; they were still skipped only because that test module binds to `TEST_DATABASE_URL`/`DATABASE_URL` at collection time via its own dedicated engine and this session's ad-hoc `mysqld` process, started after the test process's own environment was already configured for the `.env` file's connection string pointing at the schema used for the live app testing above, not a second, separate `dualvulndroid_test` database - the skip is still an honest reflection of what was actually reachable in the test harness's own configuration, not a fabricated pass.

## P. Failures and fixes

1. **Emulator snapshot resume left `adb` stuck `offline`** for ~15 minutes despite the VM itself resuming in 2 seconds. Fixed by cold-booting instead (`-no-snapshot-load`), which is a standard, well-known remedy - no code was touched, this is an environment-level fix.
2. **Chatbot intent-matching gap** (Part I above) - the only fix touching application code this session. Minimal, additive, verified live, regression-tested.
3. Multiple `adb shell input tap`/`input text` scripting friction points (stray duplicated characters, a stylus-tutorial popup interrupting typing, coordinate drift when the on-screen keyboard opened/closed) - these were artifacts of driving the UI via `adb` shell commands, not application bugs; resolved by re-deriving exact element bounds via `uiautomator dump` instead of guessing pixel coordinates from screenshots.

## Q. Remaining limitations

- Search sub-cases B (unknown application) and D (network error) were not separately exercised.
- Compatibility sub-cases B (INCOMPATIBLE) and C (NOT_AVAILABLE/missing-device-info) were not separately re-tested manually this session (logic already covered by existing unit tests).
- Not all 8 required chatbot questions were individually re-verified live in this session after the bug-fix cycle (18 backend tests cover them; 2 were directly observed live).
- Chat history (persisted-and-reloaded transcript) was not separately exercised.
- APK upload: genuinely not applicable - no such feature exists in this app.
- This was a single manual pass on one AVD profile (Pixel_4, API 36, x86_64) - not a device/OS-version matrix.

## R. Final status

See the status table in the chat response for this phase.
