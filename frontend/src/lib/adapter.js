/**
 * adapter.js (v2)
 *
 * Maps the v2 backend DossierOut shape to frontend component props.
 * v2 API returns ALL fields: math_findings, plausibility_findings,
 * primary_evidence, pipeline_telemetry, legal_timeline_checks,
 * entity_graph, tier_a_flagged, tier_bd_flagged.
 */

const API_BASE = 'http://127.0.0.1:8000';

function riskLevel(score) {
  if (score >= 0.70) return 'CRITICAL';
  if (score >= 0.50) return 'HIGH';
  if (score >= 0.30) return 'MEDIUM';
  return 'LOW';
}

function extractField(documents, fieldName) {
  const sorted = [...documents].sort((a, b) =>
    a.delivery_mode === 'soft_copy' ? -1 : 1
  );
  for (const doc of sorted) {
    const entry = doc.ocr_fields?.[fieldName];
    if (entry) {
      if (typeof entry === 'object' && entry.value) return entry.value;
      if (typeof entry === 'string') return entry;
    }
  }
  return null;
}

function buildFlags(documents, mismatches) {
  const flags = [];
  const reasons = {};

  for (const m of mismatches) {
    const key = `${m.field}_mismatch`;
    flags.push(key);
    reasons[key] =
      `${m.field}: ${m.doc_a}="${m.value_a ?? '?'}" vs ${m.doc_b}="${m.value_b ?? '?'}"`;
  }

  const seenDocs = new Set();
  for (const doc of documents) {
    if (!doc.visual_flagged) continue;
    if (seenDocs.has(doc.doc_name)) continue;
    if (doc.delivery_mode !== 'soft_copy' &&
        documents.find(d => d.doc_name === doc.doc_name && d.delivery_mode === 'soft_copy')) {
      continue;
    }
    seenDocs.add(doc.doc_name);
    const key = `${doc.doc_name}_visual_anomaly`;
    flags.push(key);
    reasons[key] =
      `${doc.doc_name}: visual model scored ${(doc.forged_prob * 100).toFixed(0)}% forgery probability (threshold: 60%)`;
  }

  return { flags, reasons };
}

function buildInsight(data, documents, mismatches, mathFindings, plausFindings, evidence) {
  const flaggedDocs = [...new Set(
    documents.filter(d => d.flagged && d.delivery_mode === 'soft_copy').map(d => d.doc_name)
  )];

  if (!data.fraudulent && evidence.length === 0) {
    return (
      `Analysis of ${data.dossier_id}: No forgery indicators detected across ` +
      `${data.n_documents} documents. Visual model, OCR, cross-document field ` +
      `comparison, and mathematical integrity checks all passed. ` +
      `Risk score: ${Math.round(data.risk_score * 100)}/100.`
    );
  }

  let insight = `Analysis of ${data.dossier_id}: ${data.n_flagged} of ` +
    `${data.n_documents} documents flagged. `;

  if (evidence.length > 0) {
    const evTypes = [...new Set(evidence.map(e => e.type))];
    insight += `Primary evidence: ${evTypes.join(', ')}. `;
  }

  if (mismatches.length > 0) {
    const mmParts = mismatches.slice(0, 3).map(m => `${m.field} (${m.doc_a} vs ${m.doc_b})`);
    insight += `Cross-document mismatches: ${mmParts.join('; ')}${mismatches.length > 3 ? ` +${mismatches.length - 3} more` : ''}. `;
  }

  if (flaggedDocs.length > 0) {
    insight += `Visual anomalies detected in: ${flaggedDocs.join(', ')}. `;
  }

  const mathFails = (mathFindings || []).filter(m => !m.passed);
  if (mathFails.length > 0) {
    insight += `Mathematical discrepancies found: ${mathFails.length}. `;
  }

  const plausFails = (plausFindings || []).filter(p => !p.passed);
  if (plausFails.length > 0) {
    insight += `Plausibility flags: ${plausFails.length}. `;
  }

  insight +=
    `Risk score: ${Math.round(data.risk_score * 100)}/100. ` +
    `Recommend ${data.risk_score >= 0.65 ? 'escalation to senior review' : 'manual underwriter review'}.`;

  return insight;
}

function buildLogicForensics(mismatches, mathFindings, plausFindings) {
  const mismatchedFields = new Set(mismatches.map(m => m.field));
  const mathFails = (mathFindings || []).filter(m => !m.passed);
  const plausFails = (plausFindings || []).filter(p => !p.passed);

  return {
    cross_doc_name_match: !mismatchedFields.has('full_name'),
    cross_doc_pan_match: !mismatchedFields.has('pan'),
    semantic_consistency: mismatches.length === 0,
    math_integrity: mathFails.length === 0,
    income_ratio_ok: !plausFails.some(p => p.check_name === 'rent_to_income_ratio' || p.check_name === 'three_way_income_triangulation'),
    wealth_ratio_ok: !plausFails.some(p => p.check_name === 'itr_plausibility_range'),
  };
}

export function adaptBackendResponse(raw) {
  const documents = (raw.documents || []).map(doc => ({
    ...doc,
    type: doc.doc_name,
    mask_url: doc.mask_url ? `${API_BASE}${doc.mask_url}` : null,
  }));

  const mismatches = raw.mismatches || [];
  const mathFindings = raw.math_findings || [];
  const plausFindings = raw.plausibility_findings || [];
  const evidence = raw.primary_evidence || [];
  const telemetry = raw.pipeline_telemetry || {};
  const legalChecks = raw.legal_timeline_checks || [];
  const graph = raw.entity_graph || {};

  const { flags, reasons } = buildFlags(documents, mismatches);

  return {
    applicant_id: raw.dossier_id,
    dossier_id: raw.dossier_id,
    applicant_name: extractField(documents, 'full_name') || raw.dossier_id,
    name: extractField(documents, 'full_name') || raw.dossier_id,
    pan: extractField(documents, 'pan'),

    risk_score: raw.risk_score,
    risk_level: riskLevel(raw.risk_score),
    fraudulent: raw.fraudulent,
    n_documents: raw.n_documents,
    n_flagged: raw.n_flagged,
    techniques: raw.techniques || [],
    ground_truth_fraudulent: raw.ground_truth_fraudulent,

    documents,

    fraud_flags: flags,
    fraud_reasons: reasons,
    mismatches,

    math_findings: mathFindings,
    plausibility_findings: plausFindings,
    primary_evidence: evidence,
    pipeline_telemetry: telemetry,
    legal_timeline_checks: legalChecks,
    entity_graph: graph,

    logic_severity: raw.logic_severity || 0,
    visual_model_probability: raw.visual_model_probability || 0,
    math_severity: raw.math_severity || 0,
    plausibility_severity: raw.plausibility_severity || 0,
    mismatch_severity: raw.mismatch_severity || 0,
    timeline_severity: raw.timeline_severity || 0,
    n_math_failures: raw.n_math_failures || 0,
    n_plausibility_failures: raw.n_plausibility_failures || 0,
    n_cross_doc_mismatches: raw.n_cross_doc_mismatches || 0,
    n_timeline_failures: raw.n_timeline_failures || 0,

    logic_forensics: buildLogicForensics(mismatches, mathFindings, plausFindings),

    llm_insight: buildInsight(raw, documents, mismatches, mathFindings, plausFindings, evidence),

    clause_findings: raw.clause_findings || [],
    signature_findings: raw.signature_findings || [],
    quality_findings: raw.quality_findings || [],
    micr_findings: raw.micr_findings || [],
    metadata_forensics: raw.metadata_forensics || [],
    n_clause_failures: raw.n_clause_failures || 0,
    n_signature_failures: raw.n_signature_failures || 0,
    n_quality_failures: raw.n_quality_failures || 0,
    physical_tamper_findings: raw.physical_tamper_findings || [],
    date_forensic_findings: raw.date_forensic_findings || [],
    nri_forensic_findings: raw.nri_forensic_findings || [],
    company_forensic_findings: raw.company_forensic_findings || [],
    property_forensic_findings: raw.property_forensic_findings || [],
    n_physical_tamper_failures: raw.n_physical_tamper_failures || 0,
    n_date_failures: raw.n_date_failures || 0,
    n_nri_failures: raw.n_nri_failures || 0,
    n_company_failures: raw.n_company_failures || 0,
    n_property_failures: raw.n_property_failures || 0,

    processing_time: raw.processing_time_ms / 1000,
    processing_time_ms: raw.processing_time_ms,
    analyzed_at: raw.analyzed_at,

    _raw: raw,
  };
}
