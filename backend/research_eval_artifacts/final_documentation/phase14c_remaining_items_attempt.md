# Phase 14C — Remaining Validation Items: Attempt Record

**Outcome: attempt made on a real Android emulator; blocked by a genuine, sustained host resource constraint before any of the 6 remaining items could be exercised. Not a DualVulnDroid bug. No result fabricated.**

## 1. Scope (from `REMAINING_VALIDATION_ITEMS.md`)

Only items explicitly marked PARTIAL/NOT VALIDATED in `phase14b_android_validation.md` were in scope. All previously-PASS items (Login, Registration, Session restore, Logout, Dashboard, Search-known-app, Application Details, Security assessment, Compatibility-COMPATIBLE case, Alternatives, History isolation, chatbot mechanism + 2 questions, both regression suites, 61 screenshots) were **not** touched or rerun, per instruction, and remain PASS as recorded in Phase 14B.

## 2. Environment brought up (real, not simulated)

- MySQL 9.1.0 (direct `mysqld`, same as Phase 14B) — up, `Database connection OK.`
- FastAPI backend (`uvicorn app:app`) — up, production XGBoost loaded (`rounds=103/123`), SHAP `TreeExplainer` initialized, 7,610 features cached
- Android emulator: Pixel_4 AVD, cold boot (`-no-snapshot-load`) — booted in 30s, `adb devices` showed `device` (online), API 36, x86_64
- App already installed from Phase 14B (`com.example.dualvulndroid_flutter`) — launched via `am start`

## 3. What happened

The app launched and rendered a real, correct Login screen (`remaining_02_after_wait_tap.png`) after dismissing one transient "System UI isn't responding" dialog — the same class of transient ANR Phase 14B documented and which self-resolved there after one "Wait" tap.

This time it did not self-resolve. Attempting to navigate to the Register screen (needed because Phase 14B's test-account password was not recorded anywhere accessible, so a fresh dedicated test account was going to be created rather than guessing a password) retriggered the same ANR. It was dismissed and re-observed **five times** across increasing wait intervals (immediate, 6s, 10s, 18s, 30s) and was still present after the final, full 30-second settle — a materially different, non-resolving pattern compared to Phase 14B's single transient occurrence.

## 4. Root cause: measured, not assumed

Free RAM was checked directly: **2.79–2.87 GB free** (of 15.75 GB total) throughout the stuck period, essentially flat despite the waits — i.e. not recovering on its own. A process listing showed this was **not** caused primarily by DualVulnDroid's own components (MySQL ≈280 MB combined, backend Python ≈270 MB) but by a combination of the emulator itself plus substantial pre-existing load already on this host before this session started: two `claude` processes (≈870 MB combined), three VSCode windows (≈1 GB combined), multiple Chrome processes, and WhatsApp — none of which this task has any authority or reason to close. Stopping only the emulator (a resource fully within this task's own scope) immediately recovered RAM to **4.01 GB free**, confirming the emulator was the specific marginal factor pushing an already-loaded host over the threshold where `system_server`/SystemUI stops responding promptly, not a defect in the emulator, the AVD image, or the DualVulnDroid app.

## 5. Decision

Per the standing instruction across every phase of this validation effort ("if host memory becomes dangerously low / the system becomes unstable, stop cleanly and report the exact limitation" — not force through it), the attempt was stopped after five non-resolving dismiss cycles rather than continuing indefinitely or working around the dialog in a way that couldn't produce trustworthy evidence. The emulator was cleanly killed (`adb emu kill` + process cleanup, RAM confirmed recovered to 4.01 GB). The backend and MySQL were left running (lightweight, not implicated in the instability) so a retry does not need to re-pay their startup cost.

## 6. Result for each remaining item

| # | Item | Result | Evidence |
|---|---|---|---|
| 1 | Search — unknown/no-match application | **NOT VALIDATED** | Blocked before reaching the Search screen |
| 2 | Search — network-error state | **NOT VALIDATED** | Blocked before reaching the Search screen |
| 3 | Compatibility — INCOMPATIBLE scenario | **NOT VALIDATED** | Blocked before reaching the Compatibility screen |
| 4 | Compatibility — NOT_AVAILABLE scenario | **NOT VALIDATED** | Blocked before reaching the Compatibility screen |
| 5 | Chatbot — 6 remaining required questions | **NOT VALIDATED** | Blocked before reaching the Chatbot screen |
| 6 | Chat history persistence | **NOT VALIDATED (design-level finding available — see §7)** | Blocked before live re-check; code inspection completed |
| 7 | APK upload | **NOT VALIDATED — unchanged, not applicable** (no UI entry point exists) | Carried forward from Phase 14B, not reattempted |

No item above is reported as PASS. None of Phase 14B's existing PASS results were altered.

## 7. One real finding, established by code inspection (not live-device evidence)

While preparing item 6, the actual code path was traced: `POST /ai-chat` calls `database.save_chat_message()`, which writes to the real `chat_history` table (`db/crud.py`) — but **no `GET` endpoint for chat history exists anywhere in `app.py`**, and neither `security_chat_screen.dart` nor `chat_repository.dart` reference chat history at all. Chat messages are persisted server-side (write-only, presumably for audit/future use) but are never read back and redisplayed to the user. This means chat history, as a user-facing feature, does not currently exist — the chat screen's message list is in-memory `State` only and will not survive navigating away and back. This is stated as a **verified code-level fact**, not a live-device observation (the live re-check to visually confirm this on-device was itself blocked by §4–5 above), and is not treated as a bug to fix under this task's constraints (no backend change was made).

## 8. Recommendation for a future retry

Retry when more host RAM is available — closing some of the pre-existing, unrelated applications (extra browser windows/tabs, one of the several open VSCode windows) before starting the emulator would likely be sufficient, based on the ≈1.2 GB recovered from stopping the emulator alone landing right at the edge of stability observed here. No change to the DualVulnDroid system itself is indicated or recommended.
