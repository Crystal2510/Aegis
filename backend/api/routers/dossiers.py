"""
api/routers/dossiers.py (v2)

Returns complete DossierOut with all computed fields:
math_findings, plausibility_findings, primary_evidence, pipeline_telemetry,
legal_timeline_checks, entity_graph, fused risk scores.
"""

import csv
import io
import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from dataset import compute_srm_residual

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from db import get_db
from db.crud import get_dossier, list_dossiers
from db.models import Dossier
from api.schemas import (
    DossierListOut, DossierOut, DossierSummary, DocumentOut, MismatchOut,
    PipelineTelemetryOut, LegalTimelineCheckOut, EntityGraphOut, GraphNodeOut, GraphEdgeOut,
    MathFindingOut, PlausibilityFindingOut, PrimaryEvidenceOut,
)
from metadata_extract import extract_document_metadata
from cross_doc_check import (
    find_cross_doc_mismatches,
    verify_legal_and_property_timelines,
    build_entity_network_graph,
    build_pipeline_telemetry,
    verify_intra_document_math,
    verify_plausibility_metrics,
    compute_fused_risk_score,
    MathFinding, PlausibilityFinding, FieldMismatch,
)

router = APIRouter()


def _risk_level(risk_score: float) -> str:
    if risk_score >= 0.70: return "CRITICAL"
    if risk_score >= 0.50: return "HIGH"
    if risk_score >= 0.30: return "MEDIUM"
    return "LOW"


def _extract_ocr(d: Dossier, field: str) -> str | None:
    for doc in d.documents:
        fields = json.loads(doc.ocr_fields or "{}")
        entry = fields.get(field)
        if isinstance(entry, dict):
            v = entry.get("value")
        else:
            v = entry
        if v:
            return v
    return None


def _to_summary(d) -> DossierSummary:
    return DossierSummary(
        dossier_id=d.dossier_id,
        fraudulent=d.fraudulent,
        risk_score=d.risk_score,
        n_documents=d.n_documents,
        n_flagged=d.n_flagged,
        analyzed_at=d.analyzed_at,
    )


def _flatten_fields(fields: dict) -> dict:
    out = {}
    for k, v in fields.items():
        if k.startswith("__"):
            out[k] = v
        elif isinstance(v, dict) and "value" in v:
            out[k] = v["value"]
        else:
            out[k] = v
    return out


def _to_out(d) -> DossierOut:
    docs_out = []
    extracted_fields_by_doc = {}
    for doc in d.documents:
        fields = json.loads(doc.ocr_fields or "{}")
        if "__metadata__" not in fields and doc.image_path:
            try:
                fields["__metadata__"] = extract_document_metadata(doc.image_path)
            except Exception:
                pass
        fields = _flatten_fields(fields)
        docs_out.append(DocumentOut(
            doc_name=doc.doc_name,
            delivery_mode=doc.delivery_mode,
            forged_prob=doc.forged_prob or 0.0,
            visual_flagged=bool(doc.visual_flagged),
            tier_a_flagged=bool(getattr(doc, 'tier_a_flagged', False)),
            tier_bd_flagged=bool(getattr(doc, 'tier_bd_flagged', False)),
            ocr_fields=fields,
            flagged=bool(doc.flagged),
            mask_url=(
                f"/masks/{Path(doc.mask_path).name}"
                if doc.mask_path and Path(doc.mask_path).exists()
                else None
            ),
        ))
        doc_key = doc.doc_name if doc.delivery_mode == "soft_copy" else f"{doc.doc_name}_hard_copy"
        extracted_fields_by_doc[doc_key.lower()] = fields

    clean_mismatches = find_cross_doc_mismatches(extracted_fields_by_doc)
    legal_checks_raw = verify_legal_and_property_timelines(extracted_fields_by_doc)
    math_findings_raw = verify_intra_document_math(extracted_fields_by_doc)
    plausibility_findings_raw = verify_plausibility_metrics(extracted_fields_by_doc)

    fusion = compute_fused_risk_score(
        visual_model_probability=d.visual_model_probability or 0.0,
        math_findings=math_findings_raw,
        plausibility_findings=plausibility_findings_raw,
        cross_doc_mismatches=clean_mismatches,
        legal_timeline_checks=legal_checks_raw,
        n_nri_failures=d.n_nri_failures or 0,
        n_date_failures=d.n_date_failures or 0,
        n_physical_tamper_failures=d.n_physical_tamper_failures or 0,
        n_company_failures=d.n_company_failures or 0,
        n_property_failures=d.n_property_failures or 0,
    )

    graph_raw = build_entity_network_graph(extracted_fields_by_doc, clean_mismatches)
    telemetry_raw = build_pipeline_telemetry(d.processing_time_ms or 0.0, d.n_documents or 1)

    legal_checks_out = [
        LegalTimelineCheckOut(
            check_type=lc["check_type"], pass_verdict=lc["pass_verdict"],
            label=lc["label"], detail=lc["detail"],
            confidence=lc.get("confidence", 1.0),
            formula=lc.get("formula"), doc_a=lc.get("doc_a"), doc_b=lc.get("doc_b"),
            val_a=lc.get("val_a"), val_b=lc.get("val_b"),
        ) for lc in legal_checks_raw
    ]

    entity_graph_out = EntityGraphOut(
        nodes=[GraphNodeOut(**n) for n in graph_raw["nodes"]],
        edges=[GraphEdgeOut(**e) for e in graph_raw["edges"]],
    )

    return DossierOut(
        dossier_id=d.dossier_id,
        fraudulent=d.fraudulent,
        risk_score=fusion["fused_score"],
        n_documents=d.n_documents,
        n_flagged=d.n_flagged,
        techniques=json.loads(d.techniques or "[]"),
        processing_time_ms=d.processing_time_ms or 0.0,
        analyzed_at=d.analyzed_at,
        ground_truth_fraudulent=d.ground_truth_fraudulent,
        documents=docs_out,
        mismatches=[
            MismatchOut(
                field=m.field, doc_a=m.doc_a, doc_b=m.doc_b,
                value_a=m.value_a, value_b=m.value_b,
                confidence=m.confidence,
                confidence_a=getattr(m, 'confidence_a', 1.0),
                confidence_b=getattr(m, 'confidence_b', 1.0),
                mismatch_type=getattr(m, 'mismatch_type', 'value_mismatch'),
            ) for m in clean_mismatches
        ],
        pipeline_telemetry=PipelineTelemetryOut(**telemetry_raw),
        legal_timeline_checks=legal_checks_out,
        entity_graph=entity_graph_out,
        math_findings=[MathFindingOut(**vars(mf)) for mf in math_findings_raw],
        plausibility_findings=[PlausibilityFindingOut(**vars(pf)) for pf in plausibility_findings_raw],
        primary_evidence=[PrimaryEvidenceOut(**pe) for pe in fusion["primary_evidence"]],
        logic_severity=fusion["logic_severity"],
        visual_model_probability=fusion["visual_model_probability"],
        math_severity=fusion["math_severity"],
        plausibility_severity=fusion["plausibility_severity"],
        mismatch_severity=fusion["mismatch_severity"],
        timeline_severity=fusion["timeline_severity"],
        n_math_failures=fusion["n_math_failures"],
        n_plausibility_failures=fusion["n_plausibility_failures"],
        n_cross_doc_mismatches=fusion["n_cross_doc_mismatches"],
        n_timeline_failures=fusion["n_timeline_failures"],
        clause_findings=json.loads(getattr(d, 'clause_findings', '[]')),
        signature_findings=json.loads(getattr(d, 'signature_findings', '[]')),
        quality_findings=json.loads(getattr(d, 'quality_findings', '[]')),
        micr_findings=json.loads(getattr(d, 'micr_findings', '[]')),
        metadata_forensics=json.loads(getattr(d, 'metadata_forensics', '[]')),
        n_signature_failures=getattr(d, 'n_signature_failures', 0),
        n_clause_failures=getattr(d, 'n_clause_failures', 0),
        n_quality_failures=getattr(d, 'n_quality_failures', 0),
        physical_tamper_findings=json.loads(getattr(d, 'physical_tamper_findings', '[]')),
        date_forensic_findings=json.loads(getattr(d, 'date_forensic_findings', '[]')),
        nri_forensic_findings=json.loads(getattr(d, 'nri_forensic_findings', '[]')),
        company_forensic_findings=json.loads(getattr(d, 'company_forensic_findings', '[]')),
        property_forensic_findings=json.loads(getattr(d, 'property_forensic_findings', '[]')),
        n_physical_tamper_failures=getattr(d, 'n_physical_tamper_failures', 0),
        n_date_failures=getattr(d, 'n_date_failures', 0),
        n_nri_failures=getattr(d, 'n_nri_failures', 0),
        n_company_failures=getattr(d, 'n_company_failures', 0),
        n_property_failures=getattr(d, 'n_property_failures', 0),
    )


@router.get("", response_model=DossierListOut, summary="List analyzed dossiers")
def list_all_dossiers(
    fraudulent: bool | None = Query(None, description="Filter by fraud verdict"),
    min_risk: float | None = Query(None, ge=0.0, le=1.0, description="Minimum risk_score"),
    doc_name: str | None = Query(None, description="Only dossiers containing this document type"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
):
    items, total = list_dossiers(db, fraudulent=fraudulent, min_risk=min_risk,
                                  doc_name=doc_name, limit=limit, offset=offset)
    return DossierListOut(total=total, items=[_to_summary(d) for d in items])


@router.get("/{dossier_id}", response_model=DossierOut, summary="Get full dossier analysis")
def get_one_dossier(dossier_id: str, db: Session = Depends(get_db)):
    d = get_dossier(db, dossier_id)
    if not d:
        raise HTTPException(status_code=404, detail=f"Dossier '{dossier_id}' not in database.")
    return _to_out(d)


@router.get("/{dossier_id}/mask/{doc_name}", response_class=FileResponse, summary="Get forgery localization mask")
def get_mask(dossier_id: str, doc_name: str, db: Session = Depends(get_db)):
    d = get_dossier(db, dossier_id)
    if not d:
        raise HTTPException(status_code=404, detail=f"Dossier '{dossier_id}' not found")

    preferred = next(
        (doc for doc in d.documents if doc.doc_name == doc_name and doc.delivery_mode == "soft_copy"), None)
    fallback = next((doc for doc in d.documents if doc.doc_name == doc_name), None)
    target_doc = preferred or fallback

    if target_doc and target_doc.mask_path:
        mp = Path(target_doc.mask_path)
        if mp.exists():
            return FileResponse(str(mp), media_type="image/png",
                                filename=f"{dossier_id}_{doc_name}_mask.png")
    raise HTTPException(status_code=404, detail=f"Mask for document '{doc_name}' not found in dossier '{dossier_id}'")


def _find_doc_image_file(dossier_id: str, doc_name: str, delivery_mode: str, dossier_path: str = None) -> Path | None:
    filename_patterns = [
        f"{dossier_id}_{doc_name}_{delivery_mode}.jpg", f"{dossier_id}_{doc_name}.jpg",
        f"{doc_name}_{delivery_mode}.jpg", f"{doc_name}.jpg",
        f"{dossier_id}_{doc_name}_{delivery_mode}.png", f"{doc_name}.png",
    ]
    candidate_dirs = []
    if dossier_path:
        candidate_dirs.append(Path(dossier_path))
    uploads_dir = Path(__file__).parent.parent.parent / "uploads"
    candidate_dirs.append(uploads_dir / dossier_id)
    candidate_dirs.append(uploads_dir)
    candidate_dirs.append(Path("D:/Programs/aegis-dataset/outputs/full_dataset_1400") / dossier_id)
    candidate_dirs.append(Path("D:/Programs/aegis-dataset/outputs") / dossier_id)
    for cdir in candidate_dirs:
        if not cdir.exists():
            continue
        for fname in filename_patterns:
            p = cdir / fname
            if p.exists():
                return p
        for f in cdir.glob("*"):
            if f.is_file() and doc_name.lower() in f.name.lower() and f.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                return f
    return None


def _generate_ela_map(img_rgb: np.ndarray) -> np.ndarray:
    img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    success, encoded_jpg = cv2.imencode('.jpg', img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not success:
        return img_rgb
    decompressed_bgr = cv2.imdecode(encoded_jpg, cv2.IMREAD_COLOR)
    diff_bgr = cv2.absdiff(img_bgr, decompressed_bgr).astype(np.float32)
    diff_gray = cv2.cvtColor(diff_bgr, cv2.COLOR_BGR2GRAY)
    ela_scaled = np.clip(diff_gray * 14.0, 0, 255).astype(np.uint8)
    lut = np.zeros((256, 1, 3), dtype=np.uint8)
    for i in range(256):
        v = i / 255.0
        b = int(np.clip(180 - v * 140, 10, 255))
        g = int(np.clip(v * 45, 0, 255))
        r = int(np.clip(v * 255 * 1.6, 0, 255))
        if v > 0.55:
            g = int(np.clip((v - 0.55) * 350, 0, 255))
        lut[i, 0] = [b, g, r]
    ela_bgr = cv2.LUT(cv2.cvtColor(ela_scaled, cv2.COLOR_GRAY2BGR), lut)
    return cv2.cvtColor(ela_bgr, cv2.COLOR_BGR2RGB)


def _generate_srm_map(img_rgb: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    kernel = np.array([
        [-1,  2, -2,  2, -1], [ 2, -6,  8, -6,  2],
        [-2,  8, -12, 8, -2], [ 2, -6,  8, -6,  2],
        [-1,  2, -2,  2, -1],
    ], dtype=np.float32) / 12.0
    residual = cv2.filter2D(gray, -1, kernel)
    srm_scaled = np.clip(np.abs(residual) * 20.0, 0, 255).astype(np.uint8)
    return cv2.cvtColor(srm_scaled, cv2.COLOR_GRAY2RGB)


@router.get("/{dossier_id}/image/{doc_name}/{delivery_mode}", response_class=FileResponse, summary="Serve original document image")
def get_document_image(dossier_id: str, doc_name: str, delivery_mode: str, db: Session = Depends(get_db)):
    d = get_dossier(db, dossier_id)
    if not d:
        raise HTTPException(status_code=404, detail=f"Dossier '{dossier_id}' not found")
    target_doc = next((doc for doc in d.documents if doc.doc_name == doc_name and doc.delivery_mode == delivery_mode), None)
    img_path = None
    if target_doc and target_doc.image_path:
        img_path = Path(target_doc.image_path)
    else:
        img_path = _find_doc_image_file(dossier_id, doc_name, delivery_mode, getattr(d, 'path', None))
    if img_path and img_path.exists():
        if img_path.suffix.lower() == ".pdf":
            try:
                from pdf2image import convert_from_path
                pages = convert_from_path(str(img_path), dpi=150, first_page=1, last_page=1)
                if pages:
                    buf = io.BytesIO()
                    pages[0].convert("RGB").save(buf, format="JPEG")
                    buf.seek(0)
                    return StreamingResponse(buf, media_type="image/jpeg")
            except Exception:
                pass
        return FileResponse(str(img_path), media_type="image/jpeg", filename=img_path.name)
    raise HTTPException(status_code=404, detail=f"Image not found for doc {doc_name} ({delivery_mode})")


@router.get("/{dossier_id}/srm/{doc_name}/{delivery_mode}", summary="Get SRM noise residual heatmap")
def get_srm_image(dossier_id: str, doc_name: str, delivery_mode: str, db: Session = Depends(get_db)):
    d = get_dossier(db, dossier_id)
    if not d:
        raise HTTPException(status_code=404, detail=f"Dossier '{dossier_id}' not found")
    target_doc = next((doc for doc in d.documents if doc.doc_name == doc_name and doc.delivery_mode == delivery_mode), None)
    img_path = None
    if target_doc and target_doc.image_path:
        img_path = Path(target_doc.image_path)
    else:
        img_path = _find_doc_image_file(dossier_id, doc_name, delivery_mode, getattr(d, 'path', None))
    if not img_path or not img_path.exists():
        raise HTTPException(status_code=404, detail=f"Image not found for SRM: {doc_name}")
    img_rgb = None
    if img_path.suffix.lower() == ".pdf":
        try:
            from pdf2image import convert_from_path
            pages = convert_from_path(str(img_path), dpi=150, first_page=1, last_page=1)
            if pages:
                img_rgb = np.array(pages[0].convert("RGB"))
        except Exception:
            pass
    else:
        img = cv2.imread(str(img_path))
        if img is not None:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    if img_rgb is None:
        raise HTTPException(status_code=500, detail="Could not read original image")
    srm_rgb = _generate_srm_map(img_rgb)
    success, encoded = cv2.imencode(".png", cv2.cvtColor(srm_rgb, cv2.COLOR_RGB2BGR))
    if not success:
        raise HTTPException(status_code=500, detail="Encoding failed")
    return StreamingResponse(io.BytesIO(encoded.tobytes()), media_type="image/png")


@router.get("/{dossier_id}/ela/{doc_name}/{delivery_mode}", summary="Get ELA heatmap")
def get_ela_image(dossier_id: str, doc_name: str, delivery_mode: str, db: Session = Depends(get_db)):
    d = get_dossier(db, dossier_id)
    if not d:
        raise HTTPException(status_code=404, detail=f"Dossier '{dossier_id}' not found")
    target_doc = next((doc for doc in d.documents if doc.doc_name == doc_name and doc.delivery_mode == delivery_mode), None)
    img_path = None
    if target_doc and target_doc.image_path:
        img_path = Path(target_doc.image_path)
    else:
        img_path = _find_doc_image_file(dossier_id, doc_name, delivery_mode, getattr(d, 'path', None))
    if not img_path or not img_path.exists():
        raise HTTPException(status_code=404, detail=f"Image not found for ELA: {doc_name}")
    img_rgb = None
    if img_path.suffix.lower() == ".pdf":
        try:
            from pdf2image import convert_from_path
            pages = convert_from_path(str(img_path), dpi=150, first_page=1, last_page=1)
            if pages:
                img_rgb = np.array(pages[0].convert("RGB"))
        except Exception:
            pass
    else:
        img = cv2.imread(str(img_path))
        if img is not None:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    if img_rgb is None:
        raise HTTPException(status_code=500, detail="Could not read original image")
    ela_rgb = _generate_ela_map(img_rgb)
    success, encoded = cv2.imencode(".png", cv2.cvtColor(ela_rgb, cv2.COLOR_RGB2BGR))
    if not success:
        raise HTTPException(status_code=500, detail="Encoding failed")
    return StreamingResponse(io.BytesIO(encoded.tobytes()), media_type="image/png")


@router.get("/database/list", summary="DatabaseView legacy endpoint")
def database_list(db: Session = Depends(get_db)):
    items, total = list_dossiers(db, limit=2000, offset=0)
    safe_count = sum(1 for d in items if not d.fraudulent)
    risked_count = total - safe_count
    records = []
    for d in items:
        name = _extract_ocr(d, "full_name") or "Unknown"
        pan = _extract_ocr(d, "pan") or "-"
        mismatch_flags = [f"{m.field}_mismatch" for m in d.mismatches]
        visual_flags = [
            f"{doc.doc_name}_visual_anomaly"
            for doc in d.documents
            if doc.visual_flagged and doc.delivery_mode == "soft_copy"
        ]
        fraud_flags = mismatch_flags + visual_flags
        records.append({
            "applicant_id": d.dossier_id, "name": name, "pan": pan,
            "doc_date": d.analyzed_at.strftime("%Y-%m-%d") if d.analyzed_at else "-",
            "risk_score": round(d.risk_score, 4), "risk_level": _risk_level(d.risk_score),
            "n_documents": d.n_documents, "n_flagged": d.n_flagged,
            "fraud_flags": fraud_flags, "fraudulent": d.fraudulent,
        })
    return {"records": records, "total": total, "safe_count": safe_count, "risked_count": risked_count}


@router.get("/report/{applicant_id}", summary="Download dossier report")
def download_report(applicant_id: str, db: Session = Depends(get_db)):
    d = get_dossier(db, applicant_id)
    if not d:
        raise HTTPException(404, f"Dossier '{applicant_id}' not found")
    name = _extract_ocr(d, "full_name") or "Unknown"
    pan = _extract_ocr(d, "pan") or "-"
    report = {
        "dossier_id": d.dossier_id, "applicant_name": name, "pan": pan,
        "analyzed_at": d.analyzed_at.isoformat() if d.analyzed_at else None,
        "fraudulent": d.fraudulent, "risk_score": round(d.risk_score, 4),
        "risk_level": _risk_level(d.risk_score),
        "n_documents": d.n_documents, "n_flagged": d.n_flagged,
        "techniques": json.loads(d.techniques or "[]"),
        "mismatches": [
            {"field": m.field, "doc_a": m.doc_a, "value_a": m.value_a,
             "doc_b": m.doc_b, "value_b": m.value_b}
            for m in d.mismatches
        ],
        "documents": [
            {"doc_name": doc.doc_name, "delivery_mode": doc.delivery_mode,
             "forged_prob": doc.forged_prob, "flagged": doc.flagged,
             "ocr_fields": _flatten_fields(json.loads(doc.ocr_fields or "{}"))}
            for doc in d.documents
        ],
        "generated_at": datetime.utcnow().isoformat(),
    }
    content = json.dumps(report, indent=2, ensure_ascii=False)
    return StreamingResponse(
        io.BytesIO(content.encode()), media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="AEGIS_Report_{applicant_id}.json"'},
    )


@router.get("/audit-trail/export", summary="Export all records as CSV")
def export_audit_trail(db: Session = Depends(get_db)):
    items, _ = list_dossiers(db, limit=10000, offset=0)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["dossier_id", "applicant_name", "pan", "analyzed_at",
                      "fraudulent", "risk_score", "risk_level", "n_documents",
                      "n_flagged", "techniques", "mismatch_count"])
    for d in items:
        writer.writerow([
            d.dossier_id, _extract_ocr(d, "full_name") or "", _extract_ocr(d, "pan") or "",
            d.analyzed_at.isoformat() if d.analyzed_at else "", d.fraudulent,
            round(d.risk_score, 4), _risk_level(d.risk_score),
            d.n_documents, d.n_flagged, json.loads(d.techniques or "[]"), len(d.mismatches),
        ])
    output.seek(0)
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="AEGIS_AuditTrail_{date_str}.csv"'},
    )


_feedback_log = []


@router.post("/submit-feedback", summary="Submit underwriter decision")
async def submit_feedback(request: Request):
    body = await request.json()
    dossier_id = body.get("dossier_id") or body.get("applicant_id")
    decision = body.get("decision")
    note = body.get("note", "")
    timestamp = body.get("timestamp") or datetime.utcnow().isoformat()
    corrected_label = body.get("corrected_label")
    if decision is None and corrected_label is not None:
        decision = "reject" if corrected_label == 1 else "approve"
    entry = {"dossier_id": dossier_id, "decision": decision, "note": note, "recorded_at": timestamp}
    _feedback_log.append(entry)
    print(f"[Feedback] {entry}")
    return {"status": "recorded", "message": f"Decision '{decision}' recorded for {dossier_id}."}


@router.get("/dossiers/{dossier_id}/export-pdf", summary="Export PDF memorandum")
def export_dossier_pdf(dossier_id: str, db: Session = Depends(get_db)):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    except ImportError:
        raise HTTPException(status_code=500, detail="ReportLab not installed.")
    d = get_dossier(db, dossier_id)
    if not d:
        raise HTTPException(status_code=404, detail=f"Dossier '{dossier_id}' not found")
    buffer = io.BytesIO()
    doc_pdf = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36,
                                 topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontName='Helvetica-Bold',
                                  fontSize=16, textColor=colors.HexColor('#0f172a'), spaceAfter=2)
    subtitle_style = ParagraphStyle('DocSubTitle', parent=styles['Normal'], fontName='Helvetica',
                                     fontSize=9, textColor=colors.HexColor('#64748b'), spaceAfter=10)
    heading2_style = ParagraphStyle('Heading2Custom', parent=styles['Heading2'], fontName='Helvetica-Bold',
                                     fontSize=10, textColor=colors.HexColor('#1e293b'), spaceBefore=8, spaceAfter=4)
    normal_style = ParagraphStyle('NormalCustom', parent=styles['Normal'], fontName='Helvetica',
                                   fontSize=8.5, textColor=colors.HexColor('#334155'), leading=11)
    elements = []
    elements.append(Paragraph("AEGIS FORENSIC FRAUD DETECTION SYSTEM", title_style))
    elements.append(Paragraph("OFFICIAL CREDIT SANCTION & FORENSIC AUDIT MEMORANDUM", subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0f172a'), spaceAfter=8))
    applicant_name = _extract_ocr(d, "full_name") or "Unknown"
    pan_no = _extract_ocr(d, "pan") or "-"
    analyzed_date = d.analyzed_at.strftime("%Y-%m-%d %H:%M:%S UTC") if d.analyzed_at else datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    risk_pct = f"{round(d.risk_score * 100)}%"
    verdict = "FLAGGED / HIGH RISK" if d.fraudulent else "APPROVED / LOW RISK"
    verdict_color = "#ef4444" if d.fraudulent else "#10b981"
    meta_data = [
        [Paragraph("<b>Dossier ID:</b>", normal_style), Paragraph(d.dossier_id, normal_style),
         Paragraph("<b>Audit Timestamp:</b>", normal_style), Paragraph(analyzed_date, normal_style)],
        [Paragraph("<b>Applicant Name:</b>", normal_style), Paragraph(applicant_name, normal_style),
         Paragraph("<b>PAN Number:</b>", normal_style), Paragraph(pan_no, normal_style)],
        [Paragraph("<b>Risk Score:</b>", normal_style), Paragraph(f"<b>{risk_pct}</b>", normal_style),
         Paragraph("<b>Verdict:</b>", normal_style), Paragraph(f"<font color='{verdict_color}'><b>{verdict}</b></font>", normal_style)]
    ]
    t_meta = Table(meta_data, colWidths=[100, 160, 100, 180])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(t_meta)
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("1. Document Telemetry & Visual Model Findings", heading2_style))
    doc_table_data = [
        [Paragraph("<b>Document</b>", normal_style), Paragraph("<b>Mode</b>", normal_style),
         Paragraph("<b>Forgery Prob.</b>", normal_style), Paragraph("<b>Status</b>", normal_style)]
    ]
    for doc_item in d.documents:
        prob_str = f"{round(doc_item.forged_prob * 100)}%"
        status_str = "FLAGGED" if doc_item.forged_prob >= 0.60 else "PASS"
        doc_table_data.append([
            Paragraph(doc_item.doc_name.replace('_', ' ').title(), normal_style),
            Paragraph(doc_item.delivery_mode.replace('_', ' ').title(), normal_style),
            Paragraph(prob_str, normal_style), Paragraph(f"<b>{status_str}</b>", normal_style)
        ])
    t_docs = Table(doc_table_data, colWidths=[170, 130, 120, 120])
    t_docs.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_docs)
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("2. Cross-Document Coherence Discrepancies", heading2_style))
    if d.mismatches:
        mm_table_data = [
            [Paragraph("<b>Field</b>", normal_style), Paragraph("<b>Doc A Value</b>", normal_style),
             Paragraph("<b>Doc B Value</b>", normal_style), Paragraph("<b>Status</b>", normal_style)]
        ]
        for mm_item in d.mismatches:
            mm_table_data.append([
                Paragraph(mm_item.field.replace('_', ' ').title(), normal_style),
                Paragraph(f"{mm_item.doc_a.upper()}: {mm_item.value_a}", normal_style),
                Paragraph(f"{mm_item.doc_b.upper()}: {mm_item.value_b}", normal_style),
                Paragraph("<font color='#ef4444'><b>MISMATCH</b></font>", normal_style)
            ])
        t_mm = Table(mm_table_data, colWidths=[130, 140, 140, 130])
        t_mm.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7f1d1d')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#fca5a5')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#fee2e2')),
            ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(t_mm)
    else:
        elements.append(Paragraph("<i>No cross-document mismatches detected.</i>", normal_style))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cbd5e1'), spaceAfter=8))
    sign_data = [
        [Paragraph("<b>Credit Risk Officer:</b> ___________________________", normal_style),
         Paragraph("<b>Date:</b> ______________", normal_style)],
    ]
    t_sign = Table(sign_data, colWidths=[360, 180])
    t_sign.setStyle(TableStyle([
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_sign)
    doc_pdf.build(elements)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="AEGIS_Report_{dossier_id}.pdf"'})
