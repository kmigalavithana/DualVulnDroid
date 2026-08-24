# Phase 14C — Chat History Read-Path Fix

**Outcome: the real gap (write-only chat history) is fixed with a minimal, additive read endpoint and Flutter load path. Implementation: PASS. Automated tests (backend + Flutter): PASS. Live Android UI validation: NOT VALIDATED — not attempted this run, per explicit instruction, because the emulator's stability after Phase 14C's failure has not yet been re-confirmed.**

## 1. Original problem

`POST /ai-chat` has always called `database.save_chat_message()`, which writes every exchange to the real `chat_history` table. No `GET` endpoint for chat history existed anywhere in `app.py`, and neither `chat_repository.dart`, `chat_api_service.dart`, nor `security_chat_screen.dart` referenced chat history at all. The chat screen's message list was in-memory `State` only. Confirmed by direct code inspection (not a live-device observation) during Phase 14C.

## 2. Root cause

A write path was built (Phase 12, for audit/future use) without ever building the corresponding read path. Not a security bug, not a data-loss bug — the data was safely persisted the whole time — simply a missing feature.

## 3. Existing schema and mechanisms confirmed before changing anything

- `db/models.py`: `ChatHistory` table — `id`, `user_id` (FK → `users.id`, nullable, indexed), `question` (Text), `answer` (Text), `created_at` (server-default now). No schema change was needed or made.
- `db/crud.py`: `save_chat_message(db, user_id, question, answer)` — unchanged, still the only write path.
- `app.py`: `get_current_user()` — the existing JWT dependency (`Authorization: Bearer`, decodes the token, loads the real `User` row, raises 401 on missing/malformed/expired/invalid token or a deleted user). This is the exact same dependency already protecting `GET /user/history`; **no second authentication mechanism was introduced.**
- `GET /user/history` (Part M) was used as the direct structural template for the new endpoint, since it already solves the identical problem (return only the authenticated caller's own rows, id derived from the JWT, never from client input) for scan history.

## 4. What was implemented

**Backend:**
- `db/crud.py` — added `get_user_chat_history(db, user_id, limit=200)`: queries `ChatHistory` filtered by `user_id`, ordered **chronologically** (oldest first — a conversation transcript, unlike `get_user_history()`'s newest-first event list), returns `{id, question, answer, created_at}` per row.
- `app.py` — added `GET /user/chat-history`, guarded by `Depends(get_current_user)` + `Depends(get_db)`, calling `crud.get_user_chat_history(db, current_user.id)`. The user id is **never** taken from the request — only from the verified JWT, exactly like `/user/history`.

**Flutter:**
- `lib/services/chat_api_service.dart` — added `getHistory()`, calling `GET /user/chat-history` and expanding each `{question, answer}` row into two ordered `ChatMessage`s (user turn, then bot turn).
- `lib/repositories/chat_repository.dart` — added a thin `getHistory()` passthrough.
- `lib/screens/security_chat_screen.dart` — added `initState()` → `_loadHistory()`: if a user is authenticated, fetches and displays their real history before the chat screen becomes interactive-empty; on no session or a fetch error, silently falls back to the existing empty-suggestions state (never blocks the chat feature, never fabricates a transcript). Added a loading spinner state (`_isLoadingHistory`) shown only during this fetch.

No change was made to `decision_engine.py`, `predictor.py`, the XGBoost model, or any unrelated backend logic.

## 5. Security verification

| Requirement | How it's enforced | Verified by |
|---|---|---|
| Only the authenticated user's own history is returned | `current_user.id` from the verified JWT is the only value ever passed to the query — no user id is accepted from the request | `test_authenticated_user_can_retrieve_own_history_in_order` |
| Another user cannot see it | Same mechanism — a second real user, real JWT, real different account | `test_another_user_cannot_see_a_different_users_chat_history` (asserts an empty result, not an error) |
| No second auth system | Reuses `get_current_user` verbatim, the same dependency already on `/user/history` | Code review; both endpoints share the identical dependency |
| Unauthenticated/invalid requests rejected | `get_current_user` raises 401 for a missing header, a malformed header, and an invalid/garbage token | `test_missing_authorization_header_is_rejected`, `test_malformed_authorization_header_is_rejected`, `test_invalid_token_is_rejected` |

## 6. Tests added and exact results

**Backend — `backend/tests/test_chat_history.py` (new file, 7 tests, all real HTTP calls through `TestClient` with a real register → login → JWT flow — the first test file in this project to exercise that flow end-to-end rather than calling `db/crud.py` directly):**

```
tests/test_chat_history.py::test_chat_message_is_stored_for_the_sending_user PASSED
tests/test_chat_history.py::test_authenticated_user_can_retrieve_own_history_in_order PASSED
tests/test_chat_history.py::test_another_user_cannot_see_a_different_users_chat_history PASSED
tests/test_chat_history.py::test_empty_history_returns_an_empty_list_not_an_error PASSED
tests/test_chat_history.py::test_missing_authorization_header_is_rejected PASSED
tests/test_chat_history.py::test_malformed_authorization_header_is_rejected PASSED
tests/test_chat_history.py::test_invalid_token_is_rejected PASSED

7 passed in 9.69s
```

**Full backend regression** (`python -m pytest -v`): **323 passed, 2 skipped** (up from the prior baseline of 316 passed/2 skipped by exactly the 7 new tests; the 2 skips are unchanged — the same MySQL-test-database-specific integration tests, an honest skip, not a new failure).

**Flutter — 2 tests added to the existing `test/repositories/chat_repository_test.dart`:**

```
ChatRepository getHistory() expands each real {question, answer} row into two ordered messages ✓
ChatRepository getHistory() on an empty history returns an empty list, not an error ✓
```

**Full Flutter regression** (`flutter test`): **41 passed, 0 failed** (up from 39 by exactly the 2 new tests). `flutter analyze`: **0 errors**, the same 6 pre-existing style-level infos as before this change (none introduced by this change).

## 7. Live Android UI validation status

**NOT VALIDATED.** Per explicit instruction, the remaining live-emulator validations — including seeing this chat-history load on a real device — were **not** attempted in this run, because Phase 14C's emulator instability had not yet been re-confirmed as resolved. No screenshot or on-device observation is claimed for this feature. See `REMAINING_VALIDATION_ITEMS.md` for the current, honest list of what still needs a real device pass, which now includes chat-history UI display alongside the six items already carried over from Phase 14C.

A resource check (not a live validation attempt) was taken as input to the "is a retry worth attempting" question: with the emulator not running, free RAM is currently 4.83 GB (of 15.75 GB) — measurably better than the 2.79–2.87 GB present throughout Phase 14C's failed attempt, and better than the 4.01 GB recovered immediately after stopping the emulator that session. This suggests a retry is more likely to succeed than the last attempt, but this is an inference from headroom, not a confirmed live result — the emulator has not actually been relaunched to test it.
