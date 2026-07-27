# AEGIS v2 — Project Rules for AI Coding Agents

## Key Invariants

1. **`cross_doc_check.py`**: `_values_match()` for `full_name` fields MUST use `_names_match()` (re-enabled, no blanket return True). Never disable name cross-doc comparison again.

2. **`ocr_extract.py`**: `extract_fields()` MUST return dict of `{field_name: {"value": ..., "confidence": ..., "failure_reason": ...}}`. Raw value strings are legacy format only.

3. **`pipeline.py`**: `analyze_dossier()` MUST compute `compute_fused_risk_score()` and include math_findings, plausibility_findings, primary_evidence, pipeline_telemetry in the DossierResult. The fused score is computed at analysis time, NOT only on DB read.

4. **`cross_doc_check.py`**: When a field is extracted in one document but not another, record an UNVERIFIED mismatch instead of silently skipping.

5. **Database**: Dossier model stores all computed findings (math_findings, plausibility_findings, etc.) as JSON columns. upsert_dossier saves them; _to_out reads them.

6. **Frontend contract**: The API always returns the full DossierOut with all evidence fields. Frontend should never simulate or hardcode forensic metadata.
