import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from inference import predict_document
from ocr_extract import extract_fields
from field_templates import FIELD_TEMPLATES
from cross_doc_check import (
    find_cross_doc_mismatches,
    FieldMismatch,
    verify_legal_and_property_timelines,
    verify_intra_document_math,
    MathFinding,
    verify_plausibility_metrics,
    PlausibilityFinding,
    compute_fused_risk_score,
    build_entity_network_graph,
    build_pipeline_telemetry,
)
from metadata_extract import extract_document_metadata
from clause_analyzer import analyze_all_clauses, ClauseFinding
from signature_analyzer import analyze_signature_quality, cross_doc_signature_match, SignatureFinding
from image_quality import analyze_all_quality, QualityFinding
from micr_analyzer import analyze_micr_cheque_number, analyze_micr_code, analyze_amount_consistency, MICRFinding
from physical_tamper import analyze_physical_tamper, PhysicalTamperFinding
from date_forensics import analyze_all_dates, DateForensicFinding
from nri_forensics import analyze_nri_documents, NriForensicFinding
from company_forensics import analyze_company_documents, CompanyForensicFinding
from property_forensics import analyze_property_documents, PropertyForensicFinding

VISUAL_THRESHOLD = 0.6


@dataclass
class DocumentResult:
    doc_name: str
    delivery_mode: str
    image_path: str
    forged_prob: float
    visual_flagged: bool
    tier_a_flagged: bool
    tier_bd_flagged: bool
    ocr_fields: dict
    flagged: bool
    mask: np.ndarray


@dataclass
class DossierResult:
    dossier_id: str
    dossier_path: str
    fraudulent: bool
    risk_score: float
    n_documents: int
    n_flagged: int
    documents: list
    mismatches: list
    processing_time_ms: float
    ground_truth_fraudulent: object
    techniques: list
    math_findings: list = field(default_factory=list)
    plausibility_findings: list = field(default_factory=list)
    primary_evidence: list = field(default_factory=list)
    pipeline_telemetry: dict = field(default_factory=dict)
    legal_timeline_checks: list = field(default_factory=list)
    entity_graph: dict = field(default_factory=dict)
    logic_severity: float = 0.0
    visual_model_probability: float = 0.0
    math_severity: float = 0.0
    plausibility_severity: float = 0.0
    mismatch_severity: float = 0.0
    timeline_severity: float = 0.0
    special_severity: float = 0.0
    n_math_failures: int = 0
    n_plausibility_failures: int = 0
    n_cross_doc_mismatches: int = 0
    n_timeline_failures: int = 0
    clause_findings: list = field(default_factory=list)
    signature_findings: list = field(default_factory=list)
    quality_findings: list = field(default_factory=list)
    micr_findings: list = field(default_factory=list)
    metadata_forensics: list = field(default_factory=list)
    n_signature_failures: int = 0
    n_clause_failures: int = 0
    n_quality_failures: int = 0
    physical_tamper_findings: list = field(default_factory=list)
    date_forensic_findings: list = field(default_factory=list)
    nri_forensic_findings: list = field(default_factory=list)
    company_forensic_findings: list = field(default_factory=list)
    property_forensic_findings: list = field(default_factory=list)
    n_physical_tamper_failures: int = 0
    n_date_failures: int = 0
    n_nri_failures: int = 0
    n_company_failures: int = 0
    n_property_failures: int = 0


def _load_image_rgb(path: Path):
    img = cv2.imread(str(path))
    if img is None:
        return None
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def _load_pdf_as_rgb(path: Path):
    try:
        from pdf2image import convert_from_path
        pages = convert_from_path(str(path), dpi=150, first_page=1, last_page=1)
        if pages:
            return np.array(pages[0].convert("RGB"))
    except Exception:
        pass
    return None


BOX_KEY_MAP = {
    "kyc": "kyc_boxes",
    "salary": "salary_boxes",
    "cheque": "cheque_boxes",
    "itr": "itr_boxes",
    "rent": "rent_boxes",
    "appointment": "appointment_boxes",
    "idcard": "idcard_boxes",
    "plan_approval": "plan_approval_boxes",
    "occupancy_cert": "oc_boxes",
    "ca_certificate": "ca_boxes",
    "roc_certificate": "roc_boxes",
    "nri_salary": "nri_salary_boxes",
    "nri_bank": "nri_bank_boxes",
    "death_certificate": "death_cert_boxes",
    "legal_heir": "legal_heir_boxes",
    "rera": "rera_boxes",
}


def _get_boxes_for_doc(meta: dict, doc_name: str) -> dict:
    expected_key = BOX_KEY_MAP.get(doc_name)
    if expected_key:
        return meta.get(expected_key, {})
    return {}


def _build_fallback_meta(dp: Path, field_templates: dict):
    image_files = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.pdf"):
        image_files.extend(dp.glob(ext))
    doc_types = []
    outputs = {}
    for f in image_files:
        name = f.stem.lower()
        for dt in field_templates:
            if dt in name:
                doc_types.append(dt)
                outputs[f"{dt}_soft_copy"] = f.name
                break
    doc_types = list(dict.fromkeys(doc_types))
    meta = {
        "documents_rendered": doc_types,
        "outputs": outputs,
        "techniques": [],
        "fraudulent": False,
    }
    (dp / f"{dp.name}_metadata.json").write_text(json.dumps(meta, indent=2))


def analyze_dossier(dossier_path: str) -> DossierResult:
    t0 = time.time()
    dp = Path(dossier_path)
    dossier_id = dp.name

    meta_candidates = list(dp.glob("*_metadata.json"))
    if not meta_candidates:
        _build_fallback_meta(dp, FIELD_TEMPLATES)
        meta_candidates = list(dp.glob("*_metadata.json"))
    meta = json.loads(meta_candidates[0].read_text(encoding="utf-8-sig"))

    outputs = meta.get("outputs", {})
    techniques = meta.get("techniques", [])
    gt_fraudulent = meta.get("fraudulent", None)
    ocr_overrides = meta.get("ocr_overrides", {})
    delivery_mode_overrides = meta.get("delivery_modes", {})

    document_results = []
    extracted_fields_by_doc = {}
    document_images = {}
    metadata_cache = {}

    for doc_name in meta.get("documents_rendered", []):
        if doc_name not in FIELD_TEMPLATES:
            continue

        for mode in ("soft_copy", "hard_copy"):
            if doc_name in delivery_mode_overrides and delivery_mode_overrides[doc_name] != mode:
                continue
            out_key = f"{doc_name}_{mode}"
            if out_key not in outputs:
                continue
            image_path = dp / outputs[out_key]
            if not image_path.exists():
                continue

            suffix = image_path.suffix.lower()
            img_rgb = _load_pdf_as_rgb(image_path) if suffix == ".pdf" else _load_image_rgb(image_path)
            if img_rgb is None:
                continue

            vis = predict_document(img_rgb)
            forged_prob = vis["forged_prob"]
            mask = vis["mask"]
            visual_flagged = forged_prob >= VISUAL_THRESHOLD

            try:
                doc_boxes = _get_boxes_for_doc(meta, doc_name)
                ocr_fields = extract_fields(img_rgb, FIELD_TEMPLATES[doc_name], doc_type=doc_name, boxes=doc_boxes)
            except Exception:
                ocr_fields = {}

            if doc_name in ocr_overrides:
                for k, v in ocr_overrides[doc_name].items():
                    ocr_fields[k] = v

            boxes = _get_boxes_for_doc(meta, doc_name)
            ocr_fields = dict(ocr_fields)
            if boxes:
                ocr_fields["__boxes__"] = boxes

            try:
                metadata_overrides = meta.get("metadata_overrides", {})
                if doc_name in metadata_overrides:
                    raw_meta = metadata_overrides[doc_name]
                else:
                    raw_meta = extract_document_metadata(image_path, doc_type=doc_name)
                ocr_fields["__metadata__"] = raw_meta
            except Exception:
                raw_meta = {"producer": None, "severity": "N/A"}
                ocr_fields["__metadata__"] = raw_meta

            doc_key = doc_name if mode == "soft_copy" else f"{doc_name}_hard_copy"
            extracted_fields_by_doc[doc_key] = ocr_fields
            if mode == "soft_copy":
                document_images[doc_name] = img_rgb

            document_results.append(DocumentResult(
                doc_name=doc_name,
                delivery_mode=mode,
                image_path=str(image_path),
                forged_prob=forged_prob,
                visual_flagged=visual_flagged,
                tier_a_flagged=False,
                tier_bd_flagged=visual_flagged,
                ocr_fields=ocr_fields,
                flagged=visual_flagged,
                mask=mask,
            ))

    mismatches = find_cross_doc_mismatches(extracted_fields_by_doc)
    mismatch_targets = {m.doc_a for m in mismatches} | {m.doc_b for m in mismatches}

    high_conf_mm_docs = {
        m.doc_a for m in mismatches if m.confidence == "high"
    } | {m.doc_b for m in mismatches if m.confidence == "high"}

    for dr in document_results:
        dr_key = dr.doc_name if dr.delivery_mode == "soft_copy" else f"{dr.doc_name}_hard_copy"
        if dr_key in high_conf_mm_docs or dr.doc_name in high_conf_mm_docs:
            dr.flagged = True
            dr.tier_a_flagged = True

    n_flagged = sum(1 for dr in document_results if dr.flagged)
    risk_score = max((dr.forged_prob for dr in document_results), default=0.0)

    legal_checks = verify_legal_and_property_timelines(extracted_fields_by_doc)
    math_findings = verify_intra_document_math(extracted_fields_by_doc)
    plaus_findings = verify_plausibility_metrics(extracted_fields_by_doc)

    clause_findings = analyze_all_clauses(extracted_fields_by_doc)

    signature_findings = []
    for dr in document_results:
        if dr.delivery_mode == "hard_copy":
            continue
        img = document_images.get(dr.doc_name)
        if img is not None:
            signature_findings.extend(analyze_signature_quality(img, dr.doc_name))

    doc_names_list = list(document_images.keys())
    for i in range(len(doc_names_list)):
        for j in range(i + 1, len(doc_names_list)):
            da, db = doc_names_list[i], doc_names_list[j]
            img_a = document_images.get(da)
            img_b = document_images.get(db)
            if img_a is not None and img_b is not None:
                signature_findings.extend(cross_doc_signature_match(da, img_a, db, img_b))

    quality_findings = []
    for dr in document_results:
        if dr.delivery_mode == "hard_copy":
            continue
        img = document_images.get(dr.doc_name)
        if img is not None:
            qf = analyze_all_quality(img, dr.doc_name)
            for category in qf.values():
                quality_findings.extend(category)

    micr_findings = []
    cheque_img = document_images.get("cheque")
    if cheque_img is not None:
        cheque_fields = extracted_fields_by_doc.get("cheque", {})
        cheque_number = (
            cheque_fields.get("cheque_number", {}).get("value") if isinstance(cheque_fields.get("cheque_number"), dict)
            else cheque_fields.get("cheque_number")
        )
        if cheque_number:
            micr_findings.extend(analyze_micr_cheque_number(cheque_img, str(cheque_number)))

        amount_figures = (
            cheque_fields.get("amount_figures", {}).get("value") if isinstance(cheque_fields.get("amount_figures"), dict)
            else cheque_fields.get("amount_figures")
        )
        amount_words = (
            cheque_fields.get("amount_words", {}).get("value") if isinstance(cheque_fields.get("amount_words"), dict)
            else cheque_fields.get("amount_words")
        )
        if amount_figures and amount_words:
            micr_findings.extend(analyze_amount_consistency(str(amount_figures), str(amount_words)))

        micr_code = (
            cheque_fields.get("micr_code", {}).get("value") if isinstance(cheque_fields.get("micr_code"), dict)
            else cheque_fields.get("micr_code")
        )
        if micr_code:
            micr_findings.extend(analyze_micr_code(str(micr_code)))

    metadata_forensics = []
    for dr in document_results:
        md = dr.ocr_fields.get("__metadata__", {})
        if md and md.get("severity") not in (None, "N/A", "INFO", "OK"):
            metadata_forensics.append({
                "doc": dr.doc_name,
                "producer": md.get("producer"),
                "creator": md.get("creator"),
                "severity": md.get("severity"),
                "reason": md.get("reason"),
                "action": md.get("action"),
                "editing_software_detected": md.get("editing_software_detected", False),
                "flagged_software": md.get("flagged_software"),
            })

    n_signature_failures = sum(1 for f in signature_findings if not f.passed)
    n_clause_failures = sum(1 for f in clause_findings if not f.passed)
    n_quality_failures = sum(1 for f in quality_findings if not f.passed)

    physical_tamper_findings = []
    for dr in document_results:
        if dr.delivery_mode != "soft_copy":
            continue
        img = document_images.get(dr.doc_name)
        if img is not None:
            physical_tamper_findings.extend(analyze_physical_tamper(img, dr.doc_name))

    date_forensic_findings = analyze_all_dates(extracted_fields_by_doc)

    nri_forensic_findings = analyze_nri_documents(extracted_fields_by_doc)

    company_forensic_findings = analyze_company_documents(extracted_fields_by_doc)

    property_forensic_findings = analyze_property_documents(extracted_fields_by_doc)

    n_nri_failures = sum(1 for f in nri_forensic_findings if not f.passed)
    n_date_failures_val = sum(1 for f in date_forensic_findings if not f.passed)
    n_physical_tamper_failures_val = sum(1 for f in physical_tamper_findings if not f.passed)
    n_company_failures_val = sum(1 for f in company_forensic_findings if not f.passed)
    n_property_failures_val = sum(1 for f in property_forensic_findings if not f.passed)

    from copy import deepcopy
    augmented_mismatches = deepcopy(mismatches)
    for sf in signature_findings:
        if not sf.passed:
            augmented_mismatches.append(FieldMismatch(
                field="signature",
                doc_a=sf.document, doc_b=sf.document,
                value_a=sf.detail, value_b="",
                confidence=str(sf.confidence),
                mismatch_type="signature_anomaly",
            ))

    fusion = compute_fused_risk_score(
        visual_model_probability=risk_score,
        math_findings=math_findings,
        plausibility_findings=plaus_findings,
        cross_doc_mismatches=augmented_mismatches,
        legal_timeline_checks=legal_checks,
        n_nri_failures=n_nri_failures,
        n_date_failures=n_date_failures_val,
        n_physical_tamper_failures=n_physical_tamper_failures_val,
        n_company_failures=n_company_failures_val,
        n_property_failures=n_property_failures_val,
    )

    graph = build_entity_network_graph(extracted_fields_by_doc, mismatches)
    telemetry = build_pipeline_telemetry((time.time() - t0) * 1000, len(document_results))

    final_score = fusion["fused_score"]
    fraudulent = final_score >= 0.5

    return DossierResult(
        dossier_id=dossier_id,
        dossier_path=str(dp),
        fraudulent=fraudulent,
        risk_score=fusion["fused_score"],
        n_documents=len(document_results),
        n_flagged=n_flagged,
        documents=document_results,
        mismatches=mismatches,
        processing_time_ms=(time.time() - t0) * 1000,
        ground_truth_fraudulent=gt_fraudulent,
        techniques=techniques,
        math_findings=math_findings,
        plausibility_findings=plaus_findings,
        primary_evidence=fusion["primary_evidence"],
        pipeline_telemetry=telemetry,
        legal_timeline_checks=legal_checks,
        entity_graph=graph,
        logic_severity=fusion["logic_severity"],
        visual_model_probability=fusion["visual_model_probability"],
        math_severity=fusion["math_severity"],
        plausibility_severity=fusion["plausibility_severity"],
        mismatch_severity=fusion["mismatch_severity"],
        timeline_severity=fusion["timeline_severity"],
        special_severity=fusion.get("special_severity", 0),
        n_math_failures=fusion["n_math_failures"],
        n_plausibility_failures=fusion["n_plausibility_failures"],
        n_cross_doc_mismatches=fusion["n_cross_doc_mismatches"],
        n_timeline_failures=fusion["n_timeline_failures"],
        clause_findings=clause_findings,
        signature_findings=signature_findings,
        quality_findings=quality_findings,
        micr_findings=micr_findings,
        metadata_forensics=metadata_forensics,
        n_signature_failures=n_signature_failures,
        n_clause_failures=n_clause_failures,
        n_quality_failures=n_quality_failures,
        physical_tamper_findings=[vars(f) for f in physical_tamper_findings],
        date_forensic_findings=[vars(f) for f in date_forensic_findings],
        nri_forensic_findings=[vars(f) for f in nri_forensic_findings],
        company_forensic_findings=[vars(f) for f in company_forensic_findings],
        property_forensic_findings=[vars(f) for f in property_forensic_findings],
        n_physical_tamper_failures=n_physical_tamper_failures_val,
        n_date_failures=n_date_failures_val,
        n_nri_failures=n_nri_failures,
        n_company_failures=n_company_failures_val,
        n_property_failures=n_property_failures_val,
    )
