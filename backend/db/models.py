"""
db/models.py (v2 -- Dossier model with JSON columns for computed findings)
"""

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Dossier(Base):
    __tablename__ = "dossiers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dossier_id = Column(String, unique=True, index=True, nullable=False)
    path = Column(String, nullable=False)

    fraudulent = Column(Boolean, nullable=False)
    risk_score = Column(Float, nullable=False)
    n_documents = Column(Integer, nullable=False)
    n_flagged = Column(Integer, nullable=False)

    techniques = Column(Text, default="[]")
    ground_truth_fraudulent = Column(Boolean, nullable=True)
    processing_time_ms = Column(Float, nullable=True)
    analyzed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    math_findings = Column(Text, default="[]")
    plausibility_findings = Column(Text, default="[]")
    primary_evidence = Column(Text, default="[]")
    pipeline_telemetry = Column(Text, default="{}")
    legal_timeline_checks = Column(Text, default="[]")
    entity_graph = Column(Text, default="{}")

    logic_severity = Column(Float, default=0.0)
    visual_model_probability = Column(Float, default=0.0)
    math_severity = Column(Float, default=0.0)
    plausibility_severity = Column(Float, default=0.0)
    mismatch_severity = Column(Float, default=0.0)
    timeline_severity = Column(Float, default=0.0)
    n_math_failures = Column(Integer, default=0)
    n_plausibility_failures = Column(Integer, default=0)
    n_cross_doc_mismatches = Column(Integer, default=0)
    n_timeline_failures = Column(Integer, default=0)

    clause_findings = Column(Text, default="[]")
    signature_findings = Column(Text, default="[]")
    quality_findings = Column(Text, default="[]")
    micr_findings = Column(Text, default="[]")
    metadata_forensics = Column(Text, default="[]")
    n_signature_failures = Column(Integer, default=0)
    n_clause_failures = Column(Integer, default=0)
    n_quality_failures = Column(Integer, default=0)

    physical_tamper_findings = Column(Text, default="[]")
    date_forensic_findings = Column(Text, default="[]")
    nri_forensic_findings = Column(Text, default="[]")
    company_forensic_findings = Column(Text, default="[]")
    property_forensic_findings = Column(Text, default="[]")

    n_physical_tamper_failures = Column(Integer, default=0)
    n_date_failures = Column(Integer, default=0)
    n_nri_failures = Column(Integer, default=0)
    n_company_failures = Column(Integer, default=0)
    n_property_failures = Column(Integer, default=0)

    documents = relationship(
        "Document", back_populates="dossier",
        cascade="all, delete-orphan", lazy="selectin",
    )
    mismatches = relationship(
        "Mismatch", back_populates="dossier",
        cascade="all, delete-orphan", lazy="selectin",
    )


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dossier_id = Column(String, ForeignKey("dossiers.dossier_id", ondelete="CASCADE"),
                        nullable=False, index=True)
    doc_name = Column(String, nullable=False)
    delivery_mode = Column(String, nullable=False)
    image_path = Column(String, nullable=True)

    forged_prob = Column(Float, nullable=True)
    visual_flagged = Column(Boolean, nullable=True)
    tier_a_flagged = Column(Boolean, default=False)
    tier_bd_flagged = Column(Boolean, default=False)
    ocr_fields = Column(Text, default="{}")
    flagged = Column(Boolean, nullable=True)
    mask_path = Column(String, nullable=True)

    dossier = relationship("Dossier", back_populates="documents")


class Mismatch(Base):
    __tablename__ = "mismatches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dossier_id = Column(String, ForeignKey("dossiers.dossier_id", ondelete="CASCADE"),
                        nullable=False, index=True)
    field = Column(String, nullable=False)
    doc_a = Column(String, nullable=False)
    doc_b = Column(String, nullable=False)
    value_a = Column(String, nullable=True)
    value_b = Column(String, nullable=True)
    confidence = Column(String, default="high")
    mismatch_type = Column(String, default="value_mismatch")

    dossier = relationship("Dossier", back_populates="mismatches")
