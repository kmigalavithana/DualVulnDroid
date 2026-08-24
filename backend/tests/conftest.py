"""
Test-harness-only DATABASE_URL/JWT_SECRET setup (Phase 7, Part V/M).

db/session.py reads DATABASE_URL at import time and never falls back to
SQLite silently in application code (Part T) - that rule is about
production runtime behavior. Here, in the test harness itself, we need
*some* real database for the DB-backed endpoints (/apps/*, /user/history,
etc.) to exercise their actual logic instead of always hitting the 503
"not configured" path. Since no MySQL server is reachable in this sandbox
(documented throughout Phase 7), tests run against a throwaway SQLite file
that is created fresh and torn down at the end of the session - this is
explicit test configuration, not a silent runtime fallback.

This module must set the environment variables before any test module
imports `app` (and therefore `db.session`), which is why the assignment
happens at conftest.py's top level - pytest imports conftest.py in a
directory before collecting/importing the test modules in it.
"""

import os
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix="dualvulndroid_test_")
_DB_PATH = os.path.join(_TMP_DIR, "test.db")

os.environ.setdefault("DATABASE_URL", f"sqlite:///{_DB_PATH}")
os.environ.setdefault("JWT_SECRET", "test-only-secret-not-for-production")

from db.session import create_all_tables  # noqa: E402

create_all_tables()
