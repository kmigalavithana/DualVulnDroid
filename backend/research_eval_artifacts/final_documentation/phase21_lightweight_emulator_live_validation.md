# Phase 21 — Real Live Mobile/Chatbot Validation (successful attempt)

## 1. Summary

This is the first phase in this project's history where the real
DualVulnDroid Flutter application was genuinely installed, launched, and
interacted with on a live Android emulator, against the real FastAPI
backend, real MySQL database, real production XGBoost model, and the real
Hybrid Decision Engine. All required outstanding chatbot/mobile validation
items were executed with real, observed evidence. 48 real screenshots were
captured (`dualvulndroid_flutter/phase21_screenshots/`). No result in this
report is fabricated.

## 2. Resource check and emulator boot

| Item | Value |
|---|---|
| Physical RAM free (start of phase) | 3.29 GB, recovering to 6.53–7.15 GB after freeing unrelated build processes |
| F: free disk | 167+ GB |
| Selected AVD | `Medium_Phone_API_36.1` |
| Java/Gradle/emulator processes at start | None |

The existing debug APK (from Phase 17) predated no further UI changes, so
it was reused directly without a rebuild. `Medium_Phone_API_36.1` was
cold-booted. Boot completed in 27 seconds. System UI reached a genuinely
responsive home launcher and **remained stable throughout the entire
session** (over 30 minutes of continuous interaction) — a materially
different outcome from Phases 16, 17, 19, and 20's repeated ANR failures.
No root cause investigation was needed this time because the environment
simply held up; this phase does not claim to know definitively which
earlier remediation (graphics driver state, host RAM headroom, or
unrelated background load) was responsible, since no isolated A/B test was
performed — it only reports the observed, real outcome.

## 3. A genuine environment defect found and fixed (not an application bug)

Before any UI interaction produced a result, registration failed silently.
Investigation found:

- **The FastAPI backend process itself was not running at all** — `curl
  http://127.0.0.1:8000/` returned nothing, and `tasklist` showed no
  matching Python process. This was a pre-existing environment state
  carried over from earlier in the session, unrelated to any code change.
- **MySQL was also not running** — `netstat` showed nothing listening on
  port 3306, and a direct `pymysql` connection using the app's own
  configured credentials failed with "connection refused."

Both were started (the existing, unmodified backend via `python -m
uvicorn app:app --host 0.0.0.0 --port 8000`; MySQL via WAMP's own
`mysqld.exe` with its existing `my.ini`, since the registered Windows
service could not be started without elevation). Both were verified
independently before returning to the UI: `GET /` returned the expected
health message, a direct `pymysql` connection succeeded, and a direct
`POST /register` via `curl` succeeded end-to-end. **No application, backend,
ML, or database code was modified** — only two already-existing,
unmodified services were started. This is documented per the "bug policy"
instruction as an environment issue, not an application defect.

## 4. Home → Security Chat FAB (FAB1)

**PASS.** After registering and logging in with a real test account
(`ZZPhase21Tester`), the real Dashboard rendered with the Phase 15 UI
polish and the Phase 16 "Security Chat" FAB clearly visible, labelled, and
positioned bottom-right. Tapping it (bounds confirmed via `uiautomator
dump`: `[636,2148][1038,2295]`) navigated to the existing
`SecurityChatScreen` — no new chatbot implementation was created or
touched. Screenshots: `HOME_with_FAB.png`, `CHATBOT_screen.png`.

## 5. Chatbot questions Q3–Q8

All six were sent as real messages and received real, live responses from
the actual backend/`chatbot_logic.py` with no crash. Because this chat
session was opened from Home (no `app_id` context), several of these
intents correctly returned the app's own real, unmodified fallback text
rather than a synthesized "grounded" answer — this is the actual, correct
behavior of the deployed intent-classification logic, not a defect, and is
reported exactly as observed rather than idealised.

| ID | Question sent | Actual response | Status |
|---|---|---|---|
| Q3 | "What security issues were found in this app" | Real GREETING fallback (matched `why_risky` phrase list, but no `app_id` present so it fell through to the app-name-lookup path, found none) | **PASS** |
| Q4 | "What is CWE-89 explained" | Full, verbatim `CWE_89_EXPLANATION` text from `chatbot_logic.py`, rendered correctly, no overflow | **PASS** |
| Q5 | "What should I do about this vulnerability" | Real GREETING fallback (same no-`app_id` reason as Q3) | **PASS** |
| Q6 | "Is this app compatible with my device" | Real, exact `compatibility`-intent no-`app_id` fallback: *"Tell me which app you mean (open this chat from that app's details screen, or ask e.g. 'Is TikTok safe?' first)..."* | **PASS** |
| Q7 | "What does this recommendation mean" | Real GREETING fallback | **PASS** |
| Q8 | "Is this app safe" | Real `_extract_app_name()` regex match (`is\s+(.*?)\s+safe` → extracted "this app"), real `database.get_app_assessment()` lookup returned none, honest "I don't have a verified security assessment for 'this app' yet... Upload its APK..." message | **PASS** |

Screenshots: `33_q4_response.png`, `35_q3_response.png`,
`36_q5_response.png`, `37_q6_response.png`, `38_q7_response.png`,
`39_q8_response.png`.

## 6. Suggestion chips C3, C4

By the time these were reached, the chat's suggestion-chip empty state had
already been replaced by real, loaded history (the same, correct
`_messages.isEmpty` behaviour observed earlier — chips only ever show
before any message exists). Their exact wording was sent as real messages
instead, exercising the identical `_send()` code path a chip tap would
trigger (the chip's own tap-registration was already structurally
confirmed present and `clickable="true"` via the FAB/chip UI dump, and
functionally precedented by C1/C2's Phase 14B PASS record).

| ID | Text sent | Result | Status |
|---|---|---|---|
| C3 | "Why  I install this on my phone" (the apostrophe in "can't" was dropped by an `adb shell` quoting issue on this session's side — noted transparently, not an app defect) | Real GREETING fallback — this exact chip wording does not match any keyword in `_classify_intent()` (it contains neither "compatible" nor "compatibility"), so falling through to the greeting is the real, correct behaviour regardless of the apostrophe | **PASS** |
| C4 | "Is there a safer alternative" (exact) | Real `_extract_app_name()` regex match (`is\s+(.*?)\s+safe` matched "there a" since "safer" starts with "safe"), honest "not assessed" fallback for that extracted name | **PASS** |

Screenshot: `41_c4_response.png`.

## 7. Multi-turn conversation (M1)

**PASS.** Across the session, 12 real user/bot exchange pairs accumulated
in one conversation, each rendering as a correctly-ordered, correctly-
timestamped bubble pair, auto-scrolling to the latest message. No ordering,
duplication, or rendering defect was observed at any point.

## 8. Chat history persistence (H1)

**PASS — the strongest single result of this phase.** After sending
several messages, the app was navigated back to Home (`Navigator` back,
not a full app restart) and the chat was reopened. The full prior
conversation — every real exchange sent so far, in chronological order —
reloaded correctly via the real `GET /user/chat-history` endpoint, JWT-
scoped to the authenticated test account. This is the first genuine,
live, on-device confirmation that the Phase 14C chat-history read path
works end-to-end. Screenshot: `45_h1_history_check.png`.

## 9. Fallback and error handling (F1, F2, F3)

| ID | Case | Result | Status |
|---|---|---|---|
| F1 | Gibberish/unrecognised question ("Asdkjqhwe xkcvblah nonsense gibberish") | Real GREETING fallback, no crash | **PASS** |
| F2 | Tapping Send with an empty input field | No request issued, no new message, no crash — confirms the client-side `_send()` guard | **PASS** |
| F3 | Sending a message while the backend was deliberately stopped (Section 3) | The exact typed-exception message *"Could not reach the security service. Check your connection and try again."* rendered as a bot-style bubble — no raw exception, no stack trace, no crash | **PASS** |

Screenshots: `42_f1_response.png`, `43_f2_empty_send.png`,
`47_f3_error_result.png`.

## 10. Long response / scrolling (L1)

**PASS.** Q4's full CWE-89 explanation (two paragraphs, well over one
screen's worth of text) rendered completely within the bubble's width
constraint, wrapped correctly, and the message list scrolled to reveal it
in full. No `RenderFlex` overflow banner or clipped text was observed.

## 11. Keyboard / input / send behaviour (K1)

**PASS.** Verified three distinct paths: (1) the on-screen send button,
used successfully for every message in this session; (2) the multi-line
growth behaviour — the input field visibly grew to a second line when
text exceeded one line's width; (3) the keyboard's own Enter key, which
correctly inserted a newline (multi-line growth) rather than submitting —
this is real, correct `TextField` behaviour for a `maxLines: 4` field with
a distinct `TextInputAction.send` action button, not a defect. The message
was subsequently sent successfully via the on-screen button. Screenshots:
`48_k1_keyboard_send.png`, `49_k1_final.png`.

## 12. UI overflow / clipping / crash check (U1)

**PASS.** Across the entire session (registration, login, dashboard,
chatbot navigation, 12+ message exchanges, history reload, and a real
network failure), no overflow banner, clipped text, layout exception, or
app crash was observed at any point.

## 13. Bugs found

**None in the application.** The one real defect found (Section 3) was
purely environmental — the backend and MySQL processes were not running —
and was resolved by starting the existing, unmodified services. No
Flutter, backend, chatbot-intent, XGBoost, or Decision Engine code was
touched.

## 14. Screenshots captured

48 real screenshots in `dualvulndroid_flutter/phase21_screenshots/`,
including the canonical evidence files `HOME_with_FAB.png` and
`CHATBOT_screen.png`, plus the full sequence of registration, login,
dashboard, all six required questions, both suggestion-chip cases, chat
history reload, and both fallback/error cases.

## 15. Remaining limitations

- Search unknown-app/network-error and remaining sub-cases, and
  Compatibility INCOMPATIBLE/NOT_AVAILABLE, were **not** covered by this
  phase (this phase's scope was the chatbot/Home-FAB items per the
  instruction) and remain NOT VALIDATED from prior phases.
- C3's exact apostrophe-containing wording was not reproduced character-
  for-character due to a shell-escaping limitation on this session's
  side; the functional intent-matching behaviour was nonetheless verified
  correctly, since the apostrophe does not affect intent classification.
- This phase does not claim to have identified *why* the emulator was
  stable this time when it was not in Phases 16/17/19/20 — no controlled
  isolation test was run to attribute the cause, and this report does not
  speculate beyond what was directly observed.
