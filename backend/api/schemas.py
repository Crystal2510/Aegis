"""
api/schemas.py (v2 -- complete DossierOut with all computed fields)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MismatchOut(BaseModel):
    field: str
    doc_a: str
    doc_b: str
    value_a: Optional[str] = None
    value_b: Optional[str] = None
    confidence: str = "high"
    confidence_a: float = 1.0
    confidence_b: float = 1.0
    mismatch_type: str = "value_mismatch"


class DocumentOut(BaseModel):
    doc_name: str
    delivery_mode: str
    forged_prob: float
    visual_flagged: bool
    tier_a_flagged: bool = False
    tier_bd_flagged: bool = False
    ocr_fields: dict[str, Optional[object]]
    flagged: bool
    mask_url: Optional[str] = Field(None, description="Relative URL to the forgery localization mask PNG")


class PipelineTelemetryOut(BaseModel):
    total_ms: float
    per_doc_ms: float
    vision_ms: float
    ocr_ms: float
    alignment_ms: float


class LegalTimelineCheckOut(BaseModel):
    check_type: str
    pass_verdict: bool
    label: str
    detail: str
    confidence: float = 1.0
    formula: Optional[str] = None
    doc_a: Optional[str] = None
    doc_b: Optional[str] = None
    val_a: Optional[str] = None
    val_b: Optional[str] = None


class MathFindingOut(BaseModel):
    document: str
    check_name: str
    expected: float
    actual: float
    delta: float
    passed: bool
    detail: str
    formula_steps: list[dict] | None = None


class PlausibilityFindingOut(BaseModel):
    check_name: str
    documents_involved: list[str]
    ratio: float
    threshold: float
    passed: bool
    detail: str


class PrimaryEvidenceOut(BaseModel):
    type: str
    confidence: str
    detail: Optional[str] = None
    check: Optional[str] = None
    document: Optional[str] = None
    documents: Optional[list[str]] = None
    field: Optional[str] = None
    doc_a: Optional[str] = None
    doc_b: Optional[str] = None
    value_a: Optional[str] = None
    value_b: Optional[str] = None


class GraphNodeOut(BaseModel):
    id: str
    label: str
    node_type: str
    is_flagged: bool = False


class GraphEdgeOut(BaseModel):
    source: str
    target: str
    edge_type: str
    field: Optional[str] = None
    value_a: Optional[str] = None
    value_b: Optional[str] = None
    confidence: Optional[str] = None


class EntityGraphOut(BaseModel):
    nodes: list[GraphNodeOut] = Field(default_factory=list)
    edges: list[GraphEdgeOut] = Field(default_factory=list)


class DossierOut(BaseModel):
    dossier_id: str
    fraudulent: bool
    risk_score: float
    n_documents: int
    n_flagged: int
    techniques: list[str] = Field(default_factory=list)
    processing_time_ms: float
    analyzed_at: Optional[datetime] = None
    ground_truth_fraudulent: Optional[bool] = None
    documents: list[DocumentOut]
    mismatches: list[MismatchOut]
    pipeline_telemetry: Optional[PipelineTelemetryOut] = None
    legal_timeline_checks: list[LegalTimelineCheckOut] = Field(default_factory=list)
    entity_graph: Optional[EntityGraphOut] = None
    math_findings: list[MathFindingOut] = Field(default_factory=list)
    plausibility_findings: list[PlausibilityFindingOut] = Field(default_factory=list)
    primary_evidence: list[PrimaryEvidenceOut] = Field(default_factory=list)
    logic_severity: float = 0.0
    visual_model_probability: float = 0.0
    math_severity: float = 0.0
    plausibility_severity: float = 0.0
    mismatch_severity: float = 0.0
    timeline_severity: float = 0.0
    n_math_failures: int = 0
    n_plausibility_failures: int = 0
    n_cross_doc_mismatches: int = 0
    n_timeline_failures: int = 0

    clause_findings: list[dict] = Field(default_factory=list)
    signature_findings: list[dict] = Field(default_factory=list)
    quality_findings: list[dict] = Field(default_factory=list)
    micr_findings: list[dict] = Field(default_factory=list)
    metadata_forensics: list[dict] = Field(default_factory=list)
    n_signature_failures: int = 0
    n_clause_failures: int = 0
    n_quality_failures: int = 0

    physical_tamper_findings: list[dict] = Field(default_factory=list)
    date_forensic_findings: list[dict] = Field(default_factory=list)
    nri_forensic_findings: list[dict] = Field(default_factory=list)
    company_forensic_findings: list[dict] = Field(default_factory=list)
    property_forensic_findings: list[dict] = Field(default_factory=list)
    n_physical_tamper_failures: int = 0
    n_date_failures: int = 0
    n_nri_failures: int = 0
    n_company_failures: int = 0
    n_property_failures: int = 0


class DossierSummary(BaseModel):
    dossier_id: str
    fraudulent: bool
    risk_score: float
    n_documents: int
    n_flagged: int
    analyzed_at: Optional[datetime] = None


class DossierListOut(BaseModel):
    total: int
    items: list[DossierSummary]


class DossierAnalysisRequest(BaseModel):
    dossier_path: str
    force: bool = False


class BatchResult(BaseModel):
    processed: int
    fraudulent: int
    errors: list[str]
    dossier_ids: list[str]


class IndexRequest(BaseModel):
    dataset_path: str


class IndexStatus(BaseModel):
    task_id: str
    total: int
    done: int
    errors: int
    running: bool
    message: str


class HealthOut(BaseModel):
    status: str
    model_loaded: bool
    db_dossiers: int


class ModelInfoOut(BaseModel):
    checkpoint: str
    auc: float
    precision: float
    recall: float
    f1: float
    threshold_used: float
    mean_mask_iou: float
    per_tier_recall: dict[str, float]
    n_test_samples: int
    architecture: str
