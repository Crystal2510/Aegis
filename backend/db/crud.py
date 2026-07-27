"""
db/crud.py (v2 -- stores complete DossierResult including computed findings)
"""

import json
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image
from sqlalchemy.orm import Session

from .models import Dossier, Document, Mismatch

MASKS_DIR = Path(__file__).parent.parent / "masks"
MASKS_DIR.mkdir(exist_ok=True)


def _save_mask_png(dossier_id: str, doc_name: str, delivery_mode: str, mask: np.ndarray) -> str:
    filename = f"{dossier_id}_{doc_name}_{delivery_mode}.png"
    path = MASKS_DIR / filename
    mask_uint8 = (mask * 255).clip(0, 255).astype(np.uint8)
    Image.fromarray(mask_uint8, mode="L").save(str(path))
    return str(path)


def upsert_dossier(db: Session, result) -> Dossier:
    existing = db.query(Dossier).filter_by(dossier_id=result.dossier_id).first()
    if existing:
        db.delete(existing)
        db.flush()

    dossier = Dossier(
        dossier_id=result.dossier_id,
        path=result.dossier_path,
        fraudulent=result.fraudulent,
        risk_score=result.risk_score,
        n_documents=result.n_documents,
        n_flagged=result.n_flagged,
        techniques=json.dumps(result.techniques),
        processing_time_ms=result.processing_time_ms,
        analyzed_at=datetime.utcnow(),
        ground_truth_fraudulent=result.ground_truth_fraudulent,
        math_findings=json.dumps([vars(mf) for mf in getattr(result, 'math_findings', [])]),
        plausibility_findings=json.dumps([vars(pf) for pf in getattr(result, 'plausibility_findings', [])]),
        primary_evidence=json.dumps(getattr(result, 'primary_evidence', [])),
        pipeline_telemetry=json.dumps(getattr(result, 'pipeline_telemetry', {})),
        legal_timeline_checks=json.dumps(getattr(result, 'legal_timeline_checks', [])),
        entity_graph=json.dumps(getattr(result, 'entity_graph', {})),
        logic_severity=getattr(result, 'logic_severity', 0.0),
        visual_model_probability=getattr(result, 'visual_model_probability', 0.0),
        math_severity=getattr(result, 'math_severity', 0.0),
        plausibility_severity=getattr(result, 'plausibility_severity', 0.0),
        mismatch_severity=getattr(result, 'mismatch_severity', 0.0),
        timeline_severity=getattr(result, 'timeline_severity', 0.0),
        n_math_failures=getattr(result, 'n_math_failures', 0),
        n_plausibility_failures=getattr(result, 'n_plausibility_failures', 0),
        n_cross_doc_mismatches=getattr(result, 'n_cross_doc_mismatches', 0),
        n_timeline_failures=getattr(result, 'n_timeline_failures', 0),
        clause_findings=json.dumps([vars(cf) for cf in getattr(result, 'clause_findings', [])]),
        signature_findings=json.dumps([vars(sf) for sf in getattr(result, 'signature_findings', [])]),
        quality_findings=json.dumps([vars(qf) for qf in getattr(result, 'quality_findings', [])]),
        micr_findings=json.dumps([vars(mf) for mf in getattr(result, 'micr_findings', [])]),
        metadata_forensics=json.dumps(getattr(result, 'metadata_forensics', [])),
        n_signature_failures=getattr(result, 'n_signature_failures', 0),
        n_clause_failures=getattr(result, 'n_clause_failures', 0),
        n_quality_failures=getattr(result, 'n_quality_failures', 0),
        physical_tamper_findings=json.dumps(getattr(result, 'physical_tamper_findings', [])),
        date_forensic_findings=json.dumps(getattr(result, 'date_forensic_findings', [])),
        nri_forensic_findings=json.dumps(getattr(result, 'nri_forensic_findings', [])),
        company_forensic_findings=json.dumps(getattr(result, 'company_forensic_findings', [])),
        property_forensic_findings=json.dumps(getattr(result, 'property_forensic_findings', [])),
        n_physical_tamper_failures=getattr(result, 'n_physical_tamper_failures', 0),
        n_date_failures=getattr(result, 'n_date_failures', 0),
        n_nri_failures=getattr(result, 'n_nri_failures', 0),
        n_company_failures=getattr(result, 'n_company_failures', 0),
        n_property_failures=getattr(result, 'n_property_failures', 0),
    )
    db.add(dossier)

    for dr in result.documents:
        mask_path = _save_mask_png(result.dossier_id, dr.doc_name, dr.delivery_mode, dr.mask)
        doc = Document(
            dossier_id=result.dossier_id,
            doc_name=dr.doc_name,
            delivery_mode=dr.delivery_mode,
            image_path=dr.image_path,
            forged_prob=dr.forged_prob,
            visual_flagged=dr.visual_flagged,
            tier_a_flagged=getattr(dr, 'tier_a_flagged', False),
            tier_bd_flagged=getattr(dr, 'tier_bd_flagged', False),
            ocr_fields=json.dumps(dr.ocr_fields),
            flagged=dr.flagged,
            mask_path=mask_path,
        )
        db.add(doc)

    for m in result.mismatches:
        mm = Mismatch(
            dossier_id=result.dossier_id,
            field=m.field, doc_a=m.doc_a, doc_b=m.doc_b,
            value_a=m.value_a, value_b=m.value_b,
            confidence=getattr(m, 'confidence', 'high'),
            mismatch_type=getattr(m, 'mismatch_type', 'value_mismatch'),
        )
        db.add(mm)

    db.commit()
    db.refresh(dossier)
    return dossier


def get_dossier(db: Session, dossier_id: str):
    return db.query(Dossier).filter_by(dossier_id=dossier_id).first()


def get_dossier_by_image_filename(db: Session, filename: str):
    parts = Path(filename).stem.split("_")
    if len(parts) >= 2 and parts[0] == "dossier":
        try:
            int(parts[1])
            dossier_id = f"dossier_{parts[1]}"
            return get_dossier(db, dossier_id)
        except ValueError:
            pass
    return None


def list_dossiers(
    db: Session,
    fraudulent=None,
    min_risk=None,
    doc_name=None,
    limit: int = 50,
    offset: int = 0,
):
    q = db.query(Dossier)
    if fraudulent is not None:
        q = q.filter(Dossier.fraudulent == fraudulent)
    if min_risk is not None:
        q = q.filter(Dossier.risk_score >= min_risk)
    if doc_name is not None:
        q = q.join(Dossier.documents).filter(Document.doc_name == doc_name).distinct()
    total = q.count()
    items = (
        q.order_by(Dossier.risk_score.desc())
        .offset(offset).limit(limit).all()
    )
    return items, total
