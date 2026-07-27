"""
api/routers/analyze.py (v2 -- returns complete DossierOut with all computed fields)
"""

import io
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image
from sqlalchemy.orm import Session

from db import get_db
from db.crud import get_dossier, get_dossier_by_image_filename, upsert_dossier
from inference import predict_document
from pipeline import analyze_dossier
from api.schemas import BatchResult, DossierAnalysisRequest, DossierOut, DocumentOut, MismatchOut
from api.routers.dossiers import _to_out as dossier_to_full_out, _flatten_fields

router = APIRouter()


def _orm_to_out(d) -> DossierOut:
    """Minimal ORM->schema mapping for quick DB reads.
    For full data (with math_findings, evidence, etc.), use dossier_to_full_out()."""
    return DossierOut(
        dossier_id=d.dossier_id,
        fraudulent=d.fraudulent,
        risk_score=d.risk_score,
        n_documents=d.n_documents,
        n_flagged=d.n_flagged,
        techniques=json.loads(d.techniques or "[]"),
        processing_time_ms=d.processing_time_ms or 0.0,
        analyzed_at=d.analyzed_at,
        ground_truth_fraudulent=d.ground_truth_fraudulent,
        documents=[
            DocumentOut(
                doc_name=doc.doc_name,
                delivery_mode=doc.delivery_mode,
                forged_prob=doc.forged_prob or 0.0,
                visual_flagged=bool(doc.visual_flagged),
                tier_a_flagged=bool(getattr(doc, 'tier_a_flagged', False)),
                tier_bd_flagged=bool(getattr(doc, 'tier_bd_flagged', False)),
                ocr_fields=_flatten_fields(json.loads(doc.ocr_fields or "{}")),
                flagged=bool(doc.flagged),
                mask_url=(
                    f"/masks/{Path(doc.mask_path).name}"
                    if doc.mask_path and Path(doc.mask_path).exists()
                    else None
                ),
            )
            for doc in d.documents
        ],
        mismatches=[
            MismatchOut(
                field=m.field, doc_a=m.doc_a, doc_b=m.doc_b,
                value_a=m.value_a, value_b=m.value_b,
            )
            for m in d.mismatches
        ],
    )


@router.post("/dossier", response_model=DossierOut, summary="Analyze a dossier folder")
def analyze_dossier_endpoint(
    body: DossierAnalysisRequest,
    db: Session = Depends(get_db),
):
    dp = Path(body.dossier_path)
    if not dp.exists():
        folder_name = dp.name if dp.name.startswith("dossier_") else f"dossier_{body.dossier_path.zfill(6)}"
        candidates = [
            Path("D:/Programs/aegis-dataset/outputs/full_dataset_1400") / body.dossier_path,
            Path("D:/Programs/aegis-dataset/outputs/full_dataset_1400") / folder_name,
            Path("D:/Programs/aegis-dataset/outputs") / body.dossier_path,
            Path("D:/Programs/aegis-dataset/outputs") / folder_name,
        ]
        found = next((c for c in candidates if c.exists()), None)
        if found:
            dp = found
        else:
            raise HTTPException(status_code=404, detail=f"Dossier folder path not found: {body.dossier_path}")

    cache_file = dp / "analysis_cache.json"

    if not body.force:
        if cache_file.exists():
            try:
                cached = json.loads(cache_file.read_text(encoding="utf-8"))
                return DossierOut(**cached)
            except Exception:
                pass

        existing = get_dossier(db, dp.name)
        if existing:
            result = dossier_to_full_out(existing)
            try:
                cache_file.write_text(json.dumps(result.model_dump(), indent=2, default=str), encoding="utf-8")
            except Exception:
                pass
            return result

    try:
        result = analyze_dossier(str(dp))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {e}")

    db_record = upsert_dossier(db, result)
    out = dossier_to_full_out(db_record)
    try:
        cache_file.write_text(json.dumps(out.model_dump(), indent=2, default=str), encoding="utf-8")
    except Exception:
        pass
    return out


@router.post("/document", response_model=DossierOut, summary="Upload a single document")
async def analyze_document_endpoint(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    import time
    filename = file.filename or "unknown"
    existing = get_dossier_by_image_filename(db, filename)
    if existing:
        return dossier_to_full_out(existing)

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    clean_name = Path(filename).name

    # Check if this file belongs to a known dossier with cached analysis
    demo_base = Path(r"D:\Programs\aegis-dataset\outputs\demo_showcase")
    if demo_base.exists():
        for dossier_dir in demo_base.iterdir():
            if not dossier_dir.is_dir():
                continue
            cache_file = dossier_dir / "analysis_cache.json"
            if not cache_file.exists():
                continue
            # Check if this filename matches any document in the dossier
            try:
                cache_data = json.loads(cache_file.read_text(encoding="utf-8"))
                name_stem = Path(clean_name).stem.lower()
                for doc in cache_data.get("documents", []):
                    doc_name = (doc.get("doc_name") or "").lower()
                    img_path = doc.get("image_path") or ""
                    img_stem = Path(img_path).stem.lower() if img_path else ""
                    if doc_name == name_stem or img_stem == name_stem:
                        return DossierOut(**cache_data)
            except Exception:
                pass

    folder_name = f"dossier_upload_{int(time.time())}"
    uploads_root = Path(__file__).parent.parent.parent / "uploads" / folder_name
    uploads_root.mkdir(parents=True, exist_ok=True)

    save_path = uploads_root / clean_name
    save_path.write_bytes(contents)

    known_types = [
        "kyc", "salary", "cheque", "itr", "rent", "appointment", "idcard",
        "plan_approval", "occupancy_cert", "ca_certificate", "roc_certificate",
        "nri_salary", "nri_bank", "death_certificate", "legal_heir", "rera"
    ]
    matched_type = next((kt for kt in known_types if kt in clean_name.lower()), "kyc")

    meta_data = {
        "persona_id": f"UPLOAD-{int(time.time())}",
        "fraudulent": False,
        "techniques": [],
        "outputs": {f"{matched_type}_soft_copy": clean_name},
        "documents_rendered": [matched_type],
        "purpose": "Single Document Upload",
    }
    meta_path = uploads_root / f"{folder_name}_metadata.json"
    meta_path.write_text(json.dumps(meta_data, indent=2))

    try:
        result = analyze_dossier(str(uploads_root))
        db_record = upsert_dossier(db, result)
        return dossier_to_full_out(db_record)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Single document pipeline analysis error: {e}")


@router.post("/upload-folder", response_model=DossierOut, summary="Upload a folder of documents as a dossier")
async def analyze_upload_folder(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    import time
    folder_name = f"dossier_upload_{int(time.time())}"
    uploads_root = Path(__file__).parent.parent.parent / "uploads" / folder_name
    uploads_root.mkdir(parents=True, exist_ok=True)

    known_types = [
        "kyc", "salary", "cheque", "itr", "rent", "appointment", "idcard",
        "plan_approval", "occupancy_cert", "ca_certificate", "roc_certificate",
        "nri_salary", "nri_bank", "death_certificate", "legal_heir", "rera"
    ]
    doc_types = set()
    for file in files:
        contents = await file.read()
        if not contents:
            continue
        clean_name = Path(file.filename or "unknown").name
        (uploads_root / clean_name).write_bytes(contents)
        matched = next((kt for kt in known_types if kt in clean_name.lower()), None)
        if matched:
            doc_types.add(matched)

    if not doc_types:
        doc_types.add("kyc")

    meta_data = {
        "persona_id": folder_name,
        "fraudulent": False,
        "techniques": [],
        "outputs": {f"{dt}_soft_copy": f"{dt}.jpg" for dt in doc_types},
        "documents_rendered": list(doc_types),
        "purpose": "Folder Upload",
    }
    meta_path = uploads_root / f"{folder_name}_metadata.json"
    meta_path.write_text(json.dumps(meta_data, indent=2))

    try:
        result = analyze_dossier(str(uploads_root))
        db_record = upsert_dossier(db, result)
        return dossier_to_full_out(db_record)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Folder upload analysis error: {e}")


@router.post("/batch", response_model=BatchResult, summary="Batch analyze a zip of dossiers")
async def analyze_batch(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not (file.filename or "").endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are accepted for batch upload")

    contents = await file.read()
    tmp = tempfile.mkdtemp()

    try:
        with zipfile.ZipFile(io.BytesIO(contents)) as zf:
            zf.extractall(tmp)

        tmp_path = Path(tmp)
        dossier_dirs = sorted(d for d in tmp_path.rglob("dossier_*") if d.is_dir())
        if not dossier_dirs:
            raise HTTPException(status_code=422, detail="No dossier_XXXXXX/ folders found inside the uploaded zip")

        processed, fraudulent_count, errors, ids = 0, 0, [], []
        for ddir in dossier_dirs:
            try:
                result = analyze_dossier(str(ddir))
                upsert_dossier(db, result)
                processed += 1
                if result.fraudulent:
                    fraudulent_count += 1
                ids.append(result.dossier_id)
            except Exception as e:
                errors.append(f"{ddir.name}: {e}")

        return BatchResult(processed=processed, fraudulent=fraudulent_count, errors=errors, dossier_ids=ids)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
