"""
Phase 7, Part B/T: engine/session setup for MySQL via SQLAlchemy + PyMySQL,
configured entirely from the DATABASE_URL environment variable - never a
hardcoded username/password/host, and never a silent SQLite fallback.

DATABASE_URL is read lazily and create_engine() itself does not open a
network connection (that's standard SQLAlchemy behavior - the pool
connects on first actual use). This means:
  - importing this module (and therefore app.py) never requires a live
    MySQL server, so ML-only endpoints/tests that never touch the
    database keep working even when MySQL isn't configured.
  - any DB-backed code path (get_db()) fails immediately and clearly the
    moment it's actually used without DATABASE_URL configured - it never
    substitutes SQLite behind the scenes.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

Base = declarative_base()

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600) if DATABASE_URL else None
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None


class DatabaseNotConfiguredError(RuntimeError):
    """DATABASE_URL is not set. Never caught silently anywhere in this
    codebase - see app.py's exception handler, which turns this into a
    clear 503 response instead of a stack trace or a quiet fallback."""
    pass


def get_db():
    """FastAPI dependency - yields a Session, always closes it."""
    if SessionLocal is None:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL is not configured. Copy backend/.env.example to backend/.env "
            "and set DATABASE_URL to a real MySQL connection string, e.g. "
            "mysql+pymysql://user:password@localhost:3306/dualvulndroid"
        )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_connection() -> tuple:
    """Best-effort startup health check (Part T) - logs loudly if MySQL
    is unreachable, but does not crash the whole process (endpoints that
    don't touch the database, like /predict, have nothing to do with
    this and should keep working). Returns (ok: bool, message: str)."""
    if engine is None:
        return False, "DATABASE_URL is not set - database-backed endpoints will return 503 until configured."
    try:
        with engine.connect():
            pass
        return True, "Database connection OK."
    except Exception as e:
        return False, f"DATABASE_URL is set but the database is unreachable: {e}"


def create_all_tables():
    """Dev/test convenience only - production deployments should use
    Alembic migrations (see alembic/), per Part S."""
    if engine is None:
        raise DatabaseNotConfiguredError("DATABASE_URL is not configured.")
    from . import models  # noqa: F401 - ensures models are registered on Base.metadata
    Base.metadata.create_all(bind=engine)
