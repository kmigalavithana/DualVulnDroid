"""
Phase 7, Part C: SQLAlchemy ORM models for the MySQL-backed persistence
layer. Every String column has an explicit length (MySQL requires this
for indexed VARCHAR columns, unlike SQLite - the previous implicit
"TEXT" columns wouldn't be valid, indexable MySQL DDL as-is).

Status/risk/recommendation fields are plain VARCHAR + Python-side enums
(below) rather than native SQL ENUM columns - adding a new value later
is then a simple deploy, not a schema ALTER, which matters for a still-
evolving research project.

developer_projects / developer_scan_results are deliberately NOT created
here: nothing in the current system (real-time /predict, /developer/scan)
persists anything - the plugin's workflow is stateless by design today.
Adding those tables now would be new functionality speculatively ahead
of any actual requirement ("do not create unnecessary tables").
"""

import enum

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, ForeignKey, UniqueConstraint, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .session import Base


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class RecommendationDecision(str, enum.Enum):
    SAFE_TO_INSTALL = "SAFE_TO_INSTALL"
    INSTALL_WITH_CAUTION = "INSTALL_WITH_CAUTION"
    AVOID_INSTALLING = "AVOID_INSTALLING"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class VulnerabilityStatus(str, enum.Enum):
    OPEN = "OPEN"
    FIXED = "FIXED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    ACCEPTED_RISK = "ACCEPTED_RISK"
    REVIEW = "REVIEW"


class User(Base):
    __tablename__ = "users"
    # Explicit InnoDB (Part Y follow-up): this project's target MySQL
    # servers have shown a non-InnoDB default_storage_engine (MyISAM),
    # which silently drops FOREIGN KEY clauses instead of enforcing them.
    # Every table here pins InnoDB explicitly so relationships declared
    # in db/models.py are actually enforced regardless of server config.
    __table_args__ = {"mysql_engine": "InnoDB"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True)
    # 191, not 255: utf8mb4 uses up to 4 bytes/char, and this column is
    # indexed+unique. 255*4=1020 bytes exceeds this MySQL server's key
    # length limit (MyISAM's fixed 1000-byte cap; also safely under
    # InnoDB's 767-byte COMPACT-row limit). 191*4=764 bytes fits both.
    email = Column(String(191), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    scans = relationship("Scan", back_populates="user")
    chat_messages = relationship("ChatHistory", back_populates="user")


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = {"mysql_engine": "InnoDB"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 191, not 255 - see User.email above for why (indexed utf8mb4 column,
    # key-length limit).
    package_name = Column(String(191), nullable=True, unique=True, index=True)
    app_name = Column(String(191), nullable=False, index=True)
    developer = Column(String(255), nullable=True)
    category = Column(String(100), nullable=True)
    icon_url = Column(String(1024), nullable=True)
    # How this record came to exist - "apk_upload", "trusted_metadata", etc.
    # Never fabricated: always reflects the actual real source.
    source = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    versions = relationship("AppVersion", back_populates="application", cascade="all, delete-orphan")
    scans = relationship("Scan", back_populates="application")


class AppVersion(Base):
    __tablename__ = "app_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    # Both nullable (Part F): never assume version info that wasn't
    # actually present in the analysed APK/metadata.
    version_name = Column(String(100), nullable=True)
    version_code = Column(Integer, nullable=True)
    # Phase 8B: real AndroidManifest.xml facts about this specific
    # compiled build. All four placed here on AppVersion, not
    # Application - unlike version_name, these can only meaningfully
    # change between different compiled builds (a new version could
    # raise minSdkVersion, or a debug build could accidentally ship with
    # debuggable=true), so they're per-build facts like version_name/
    # version_code, not stable per-app facts. Nullable: None means the
    # manifest genuinely didn't yield this value, never a guess. debuggable/
    # allow_backup are the RAW manifest attribute (see apk_scanner.py's
    # extract_apk_metadata) - None means the attribute was absent from
    # the manifest, which is NOT the same as Android's effective runtime
    # default for a missing attribute.
    min_sdk_version = Column(Integer, nullable=True)
    target_sdk_version = Column(Integer, nullable=True)
    debuggable = Column(Boolean, nullable=True)
    allow_backup = Column(Boolean, nullable=True)
    # Phase 8C: real <uses-feature> declarations and real lib/<abi>/
    # directories found in this exact compiled build - same per-build
    # placement reasoning as the four columns above. JSON (same pattern
    # already used by MLPrediction.shap_summary), not a separate table
    # per feature: there's no query need to filter/join on individual
    # feature names yet, and one JSON column per build avoids a table
    # with an unbounded, sparse row-per-feature shape for no current
    # benefit. features_json holds a list of {feature_name, gl_es_version,
    # required, required_explicit} dicts (see apk_scanner.py's
    # _extract_uses_features docstring); abis_json holds a plain list of
    # ABI name strings (e.g. ["arm64-v8a", "armeabi-v7a"]). Both default
    # to an empty list, never null-vs-empty ambiguity for "no features/
    # ABIs found" vs "not yet analyzed" - see get_or_create_app_version.
    features_json = Column(JSON, nullable=True)
    abis_json = Column(JSON, nullable=True)
    analyzed_at = Column(DateTime, server_default=func.now())

    application = relationship("Application", back_populates="versions")
    scans = relationship("Scan", back_populates="app_version")

    __table_args__ = (
        UniqueConstraint("application_id", "version_name", "version_code", name="uq_app_version"),
        {"mysql_engine": "InnoDB"},
    )


class Scan(Base):
    __tablename__ = "scans"
    __table_args__ = {"mysql_engine": "InnoDB"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=True, index=True)
    app_version_id = Column(Integer, ForeignKey("app_versions.id"), nullable=True)
    scan_type = Column(String(50), nullable=False)  # "apk_upload" | "chat_lookup" | ...
    scan_status = Column(String(50), nullable=False, default="COMPLETED")
    # NULL, never fabricated, when the backend cannot legitimately
    # calculate a score for this scan (Part G).
    security_score = Column(Integer, nullable=True)
    risk_level = Column(String(20), nullable=True)
    recommendation = Column(String(50), nullable=True)
    confidence = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)

    user = relationship("User", back_populates="scans")
    application = relationship("Application", back_populates="scans")
    app_version = relationship("AppVersion", back_populates="scans")
    vulnerabilities = relationship("Vulnerability", back_populates="scan", cascade="all, delete-orphan")
    ml_predictions = relationship("MLPrediction", back_populates="scan", cascade="all, delete-orphan")
    recommendations = relationship("RecommendationRecord", back_populates="scan", cascade="all, delete-orphan")


class Vulnerability(Base):
    __tablename__ = "vulnerabilities"
    __table_args__ = {"mysql_engine": "InnoDB"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_id = Column(Integer, ForeignKey("scans.id"), nullable=False, index=True)
    cwe = Column(String(20), nullable=True, index=True)
    type = Column(String(100), nullable=True)
    severity = Column(String(20), nullable=True)
    confidence = Column(Integer, nullable=True)
    file_name = Column(String(500), nullable=True)
    line_number = Column(Integer, nullable=True)
    source = Column(String(255), nullable=True)
    sink = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    # Never auto-set to a confident status for an uncertain finding -
    # defaults to OPEN, matching the decision engine's own "don't guess"
    # behavior; SUSPICIOUS_REVIEW-derived findings should be persisted as
    # REVIEW, not OPEN (see db/crud.py).
    status = Column(String(30), nullable=False, default=VulnerabilityStatus.OPEN.value)
    created_at = Column(DateTime, server_default=func.now())

    scan = relationship("Scan", back_populates="vulnerabilities")


class MLPrediction(Base):
    __tablename__ = "ml_predictions"
    __table_args__ = {"mysql_engine": "InnoDB"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_id = Column(Integer, ForeignKey("scans.id"), nullable=False, index=True)
    model_name = Column(String(100), nullable=True)
    model_version = Column(String(50), nullable=True)
    predicted_class = Column(String(20), nullable=True)
    confidence = Column(Integer, nullable=True)
    # Structured JSON (Part I) - top SHAP features, never raw source code.
    shap_summary = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    scan = relationship("Scan", back_populates="ml_predictions")


class RecommendationRecord(Base):
    __tablename__ = "recommendations"
    __table_args__ = {"mysql_engine": "InnoDB"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_id = Column(Integer, ForeignKey("scans.id"), nullable=False, index=True)
    risk_level = Column(String(20), nullable=True)
    recommendation = Column(String(50), nullable=True)
    reason = Column(Text, nullable=True)
    confidence = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    scan = relationship("Scan", back_populates="recommendations")


class AlternativeApp(Base):
    """An explicit, real link between two REAL Application rows (Part N).
    Never auto-populated with invented apps - rows only exist once both
    applications are real records, added by a curator or (in a future
    phase) a ranking process over real assessed applications."""
    __tablename__ = "alternative_apps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    alternative_application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("application_id", "alternative_application_id", name="uq_alternative_pair"),
        {"mysql_engine": "InnoDB"},
    )


class ChatHistory(Base):
    __tablename__ = "chat_history"
    __table_args__ = {"mysql_engine": "InnoDB"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="chat_messages")


class SecurityTip(Base):
    __tablename__ = "security_tips"
    __table_args__ = {"mysql_engine": "InnoDB"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
