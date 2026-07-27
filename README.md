# AEGIS v2 — Improved Forgery Detection Pipeline

## What Changed from v1

### 1. Cross-Doc Name Checks RE-ENABLED
`cross_doc_check.py:_values_match()` no longer has the blanket `return True` for `full_name` fields. Name mismatches across documents are now detected using token-set matching with configurable thresholds.

### 2. Confidence-Tracked OCR
`ocr_extract.py:extract_fields()` returns `{field_name: {value, confidence, failure_reason}}` dictionaries instead of raw values. Every extraction records WHY a field was not found (label_not_found, value_not_found, ocr_low_confidence).

### 3. UNVERIFIED Mismatch Reporting
When a field is extracted in one document but not another, an UNVERIFIED mismatch is recorded instead of silently skipping. Absence of data is itself suspicious.

### 4. Complete Fused Score at Analysis Time
`pipeline.py:analyze_dossier()` now computes the full fused risk score (math findings + plausibility + cross-doc mismatches + legal timelines) during analysis, not only when re-reading from the database.

### 5. Full API Response
All `DossierOut` responses include:
- `math_findings` — salary balance check, cheque figures-vs-words
- `plausibility_findings` — age check, ITR range, rent-to-income, 3-way income triangulation
- `primary_evidence` — list of items that triggered the fraud verdict
- `pipeline_telemetry` — per-stage timing breakdown
- `legal_timeline_checks` — death cert vs legal heir, construction timeline
- `entity_graph` — document-entity relationship graph
- Separate `tier_a_flagged` / `tier_bd_flagged` per document

### 6. NLP Clause Analysis (New)
`clause_analyzer.py` checks rent agreements, appointment letters, and ITR schedules for missing standard clauses — catching fabricated or abbreviated documents.

### 7. Database Stores Full Results
Dossier model has JSON columns for all computed findings, so re-reads don't need to recompute.

## How to Run

```bash
cd D:\Programs\aegis-model-v2\backend
pip install -r requirements_api.txt
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

## How to Train

```bash
cd D:\Programs\aegis-model-v2\backend
python train.py --root D:/Programs/aegis-dataset/outputs/full_dataset_1400 --epochs 30 --freeze-epochs 6
```

## Frontend Integration

The API returns the complete DossierOut shape. The frontend at `frontend/` should be updated to:
1. Read `math_findings`, `plausibility_findings`, `primary_evidence` from API response
2. Display `UNVERIFIED` badges for low-confidence OCR extractions
3. Show `tier_a_flagged` vs `tier_bd_flagged` separately
4. Remove all simulated/hardcoded forensic metadata
