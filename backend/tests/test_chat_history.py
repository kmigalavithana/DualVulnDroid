"""
Phase 14C: tests for the chat-history READ path (GET /user/chat-history).

/ai-chat has always WRITTEN every message to the chat_history table
(database.save_chat_message), but until this phase nothing ever read it
back - a user's own chat history was persisted but never actually
observable. These tests exercise the real HTTP layer end-to-end
(register -> login -> real JWT -> Authorization: Bearer), the same
security pattern GET /user/history already uses, rather than calling
crud functions directly - this is the first test file in this project to
drive the real login/JWT flow through TestClient rather than db/crud.py
directly, since no such HTTP-level auth test existed before this phase.
"""
import uuid

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def _register_and_login(name: str) -> tuple[int, str]:
    """Returns (user_id_unused_placeholder, jwt_token) for a freshly
    registered, unique test user. The real backend never returns the raw
    user id at login (Part M: JWT is opaque to the client), so callers
    that need the id for setup (e.g. to pass as /ai-chat's user_id) get
    it via the same real /login response's "user" field instead."""
    email = f"chathistory-{uuid.uuid4().hex}@example.com"
    password = "correct horse battery staple 42"
    reg = client.post("/register", json={"name": name, "email": email, "password": password})
    assert reg.status_code == 200, reg.text
    login = client.post("/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    body = login.json()
    return body["user"]["id"], body["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------
# 1. Chat message is stored
# ---------------------------------------------------------------------
def test_chat_message_is_stored_for_the_sending_user():
    user_id, token = _register_and_login("Chat History Tester A")

    r = client.post("/ai-chat", json={"message": "What is CWE-89?", "user_id": user_id})
    assert r.status_code == 200

    history = client.get("/user/chat-history", headers=_auth(token))
    assert history.status_code == 200
    rows = history.json()["history"]
    assert len(rows) == 1
    assert rows[0]["question"] == "What is CWE-89?"
    assert "SQL Injection" in rows[0]["answer"]
    assert rows[0]["created_at"] is not None


# ---------------------------------------------------------------------
# 2. Authenticated user can retrieve their own history
# ---------------------------------------------------------------------
def test_authenticated_user_can_retrieve_own_history_in_order():
    user_id, token = _register_and_login("Chat History Tester B")

    client.post("/ai-chat", json={"message": "What is CWE-89?", "user_id": user_id})
    client.post("/ai-chat", json={"message": "What is CWE-295?", "user_id": user_id})

    history = client.get("/user/chat-history", headers=_auth(token))
    assert history.status_code == 200
    rows = history.json()["history"]
    assert len(rows) == 2
    # Chronological (oldest first) - a conversation transcript, not a
    # newest-first event log (see db/crud.py get_user_chat_history docstring).
    assert rows[0]["question"] == "What is CWE-89?"
    assert rows[1]["question"] == "What is CWE-295?"


# ---------------------------------------------------------------------
# 3. Another authenticated user cannot retrieve that history
# ---------------------------------------------------------------------
def test_another_user_cannot_see_a_different_users_chat_history():
    user_a_id, token_a = _register_and_login("Chat History Tester C")
    _user_b_id, token_b = _register_and_login("Chat History Tester D")

    client.post("/ai-chat", json={"message": "Why is this app risky?", "user_id": user_a_id})

    # User A sees their own real message.
    history_a = client.get("/user/chat-history", headers=_auth(token_a))
    assert len(history_a.json()["history"]) == 1

    # User B, a completely different authenticated user, must not see it.
    history_b = client.get("/user/chat-history", headers=_auth(token_b))
    assert history_b.status_code == 200
    assert history_b.json()["history"] == []


# ---------------------------------------------------------------------
# 4. Empty history is handled correctly
# ---------------------------------------------------------------------
def test_empty_history_returns_an_empty_list_not_an_error():
    _user_id, token = _register_and_login("Chat History Tester E")

    history = client.get("/user/chat-history", headers=_auth(token))
    assert history.status_code == 200
    assert history.json() == {"history": []}


# ---------------------------------------------------------------------
# 5. Invalid/unauthenticated requests are rejected correctly
# ---------------------------------------------------------------------
def test_missing_authorization_header_is_rejected():
    r = client.get("/user/chat-history")
    assert r.status_code == 401


def test_malformed_authorization_header_is_rejected():
    r = client.get("/user/chat-history", headers={"Authorization": "NotBearer something"})
    assert r.status_code == 401


def test_invalid_token_is_rejected():
    r = client.get("/user/chat-history", headers={"Authorization": "Bearer this-is-not-a-real-jwt"})
    assert r.status_code == 401
