import React from 'react';
import RiskGauge from './RiskGauge';

const probTier = (p, flagged = false) => {
    if (p >= 0.60) return { label: 'Elevated concern', color: '#ef4444' };
    if (p >= 0.40) return { label: 'Warrants attention', color: '#f59e0b' };
    if (flagged) return { label: 'Logic flag — anomaly detected', color: '#f59e0b' };
    return { label: 'Likely clean', color: '#10b981' };
};

const Row = ({ label, value, mono }) => (
    <div className="flex justify-between items-start py-1 border-b border-[#e5e7eb] last:border-0 gap-2">
        <span className="text-[10px] text-[#6b7280] shrink-0">{label}</span>
        <span className={`text-[10px] font-semibold text-[#111111] text-right ${mono ? 'font-mono' : ''}`}>
            {value ?? '—'}
        </span>
    </div>
);

const Section = ({ title, children, danger }) => (
    <div className={`border ${danger ? 'border-[#fca5a5]' : 'border-[#e5e7eb]'} rounded p-3 ${danger ? 'bg-[#fef2f2]' : 'bg-white'}`}>
        <div className="text-[10px] font-bold uppercase tracking-wider text-[#374151] mb-2">
            {danger && <span className="text-[#dc2626] mr-1">&#9654;</span>}
            {title}
        </div>
        {children}
    </div>
);

const ThreatEngine = ({ backendData }) => {
    const docs = backendData?.documents || [];
    const mismatches = backendData?.mismatches || [];
    const score = backendData?.risk_score || 0;
    const dossierId = backendData?.dossier_id || backendData?.applicant_id;

    const softDocs = docs.filter(d => d.delivery_mode === 'soft_copy');
    const docTypes = [...new Set(docs.map(d => d.doc_name || d.type).filter(Boolean))];
    const primaryEvidence = backendData?.primary_evidence || [];
    const mathFindings = backendData?.math_findings || [];
    const plausFindings = backendData?.plausibility_findings || [];
    const telemetry = backendData?.pipeline_telemetry || {};
    const entityGraph = backendData?.entity_graph || {};
    const insight = backendData?.llm_insight;

    const mathFails = mathFindings.filter(m => !m.passed);
    const plausFails = plausFindings.filter(p => !p.passed);
    const nFails = mathFails.length + plausFails.length + mismatches.length
        + (backendData?.n_timeline_failures || 0)
        + (backendData?.n_signature_failures || 0)
        + (backendData?.n_clause_failures || 0)
        + (backendData?.n_quality_failures || 0)
        + (backendData?.n_physical_tamper_failures || 0)
        + (backendData?.n_date_failures || 0)
        + (backendData?.n_nri_failures || 0)
        + (backendData?.n_company_failures || 0)
        + (backendData?.n_property_failures || 0);

    const maxProb = Math.max(...softDocs.map(d => d.forged_prob || 0), 0);
    const reviewPriority = score >= 0.60 ? 'Needs Review' : score >= 0.35 ? 'Elevated Concern' : 'Likely Clean';
    const priorityColor = score >= 0.60 ? '#ef4444' : score >= 0.35 ? '#f59e0b' : '#10b981';

    const highestSeverity = Math.max(
        backendData?.logic_severity || 0,
        backendData?.math_severity || 0,
        backendData?.plausibility_severity || 0,
        backendData?.mismatch_severity || 0,
        backendData?.timeline_severity || 0,
    );

    const flagSummary = () => {
        const parts = [];
        if (nFails > 0) parts.push(`${nFails} signal(s) across ${[...new Set([
            ...(mathFails.length ? ['math'] : []),
            ...(plausFails.length ? ['plausibility'] : []),
            ...(mismatches.length ? ['cross-doc'] : []),
            ...(backendData?.n_timeline_failures ? ['timeline'] : []),
            ...(backendData?.n_signature_failures ? ['signature'] : []),
            ...(backendData?.n_clause_failures ? ['clause'] : []),
            ...(backendData?.n_quality_failures ? ['quality'] : []),
            ...(backendData?.n_physical_tamper_failures ? ['physical'] : []),
            ...(backendData?.n_date_failures ? ['date'] : []),
            ...(backendData?.n_nri_failures ? ['nri'] : []),
            ...(backendData?.n_company_failures ? ['company'] : []),
            ...(backendData?.n_property_failures ? ['property'] : []),
        ])].join(', ')}`);
        if (softDocs.some(d => d.forged_prob >= 0.60)) parts.push('visual model flagged');
        return parts.join('; ') || 'no signals detected';
    };

    return (
        <div className="w-full flex flex-col bg-[#f9fafb] overflow-y-auto">

            <RiskGauge
                score={score}
                nFlagged={backendData?.n_flagged}
                nDocuments={backendData?.n_documents}
            />

            <div className="p-3 space-y-3">

                {/* Review Priority */}
                <div className="border border-[#e5e7eb] rounded p-3 text-center bg-white">
                    <div className="text-[9px] font-bold uppercase tracking-widest text-[#6b7280] mb-1">
                        Review Priority
                    </div>
                    <div className="text-[13px] font-black" style={{ color: priorityColor }}>
                        {reviewPriority}
                    </div>
                    <div className="text-[9px] text-[#6b7280] mt-1">
                        Fused risk score: {Math.round(score * 100)}%
                    </div>
                </div>

                {/* Severity Breakdown */}
                <Section title="Severity Breakdown">
                    <Row label="Visual Model" value={backendData?.visual_model_probability != null ? `${Math.round(backendData.visual_model_probability * 100)}%` : '0%'} />
                    <Row label="Math Integrity" value={backendData?.math_severity != null ? `${Math.round(backendData.math_severity * 100)}%` : '0%'} />
                    <Row label="Plausibility" value={backendData?.plausibility_severity != null ? `${Math.round(backendData.plausibility_severity * 100)}%` : '0%'} />
                    <Row label="Cross-Doc Mismatch" value={backendData?.mismatch_severity != null ? `${Math.round(backendData.mismatch_severity * 100)}%` : '0%'} />
                    <Row label="Timeline / Legal" value={backendData?.timeline_severity != null ? `${Math.round(backendData.timeline_severity * 100)}%` : '0%'} />
                    <Row label="Logic (fused)" value={backendData?.logic_severity != null ? `${Math.round(backendData.logic_severity * 100)}%` : '0%'} />
                </Section>

                {/* Primary Evidence */}
                {primaryEvidence.length > 0 && (
                    <Section title={`Primary Evidence (${primaryEvidence.length})`} danger>
                        <div className="space-y-1.5">
                            {primaryEvidence.map((ev, i) => (
                                <div key={i} className="text-[9.5px] bg-[#fef2f2] border border-[#fca5a5] text-[#374151] p-2 rounded leading-relaxed">
                                    {ev.type === 'cross_doc_mismatch' && (
                                        <div>
                                            <span className="font-bold uppercase text-[#991b1b] mr-1">MISMATCH ({ev.field.replace(/_/g, ' ')}):</span>
                                            {ev.doc_a.replace(/_/g, ' ').toUpperCase()} &ldquo;{ev.value_a}&rdquo; vs {ev.doc_b.replace(/_/g, ' ').toUpperCase()} &ldquo;{ev.value_b}&rdquo;
                                        </div>
                                    )}
                                    {ev.type === 'math_failure' && (
                                        <div><span className="font-bold uppercase text-[#991b1b] mr-1">MATH:</span> {ev.detail}</div>
                                    )}
                                    {ev.type === 'plausibility_failure' && (
                                        <div><span className="font-bold uppercase text-[#991b1b] mr-1">PLAUSIBILITY:</span> {ev.detail}</div>
                                    )}
                                    {ev.type === 'timeline_failure' && (
                                        <div><span className="font-bold uppercase text-[#991b1b] mr-1">TIMELINE:</span> {ev.detail}</div>
                                    )}
                                    {ev.type === 'metadata_poisoning' && (
                                        <div><span className="font-bold uppercase text-action-orange mr-1">METADATA:</span> {ev.detail}</div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </Section>
                )}

                {/* Dossier Summary */}
                <Section title="Dossier Summary">
                    <Row label="Dossier ID" value={dossierId} mono />
                    <Row label="Documents" value={`${backendData?.n_documents || 0} (${backendData?.n_flagged || 0} flagged)`} />
                    <Row label="Types" value={docTypes.map(d => d.replace(/_/g, ' ')).join(', ') || '—'} />
                    <Row label="Cross-doc mismatches" value={mismatches.length > 0 ? `${mismatches.length}` : 'None'} />
                    <Row label="Math failures" value={mathFails.length > 0 ? `${mathFails.length}` : 'None'} />
                    <Row label="Plausibility flags" value={plausFails.length > 0 ? `${plausFails.length}` : 'None'} />
                    <Row label="Processing" value={backendData?.processing_time_ms ? `${(backendData.processing_time_ms / 1000).toFixed(1)}s` : '—'} />
                </Section>

                {/* Pipeline Telemetry */}
                {Object.keys(telemetry).length > 0 && (
                    <Section title="Pipeline Telemetry">
                        <Row label="Total" value={`${telemetry.total_ms || '—'} ms`} />
                        <Row label="Vision" value={`${telemetry.vision_ms || '—'} ms`} />
                        <Row label="OCR" value={`${telemetry.ocr_ms || '—'} ms`} />
                        <Row label="Alignment" value={`${telemetry.alignment_ms || '—'} ms`} />
                        {telemetry.clause_ms != null && <Row label="Clause" value={`${telemetry.clause_ms} ms`} />}
                        {telemetry.per_doc_ms != null && <Row label="Per document" value={`${telemetry.per_doc_ms} ms`} />}
                    </Section>
                )}

                {/* Entity Graph */}
                {entityGraph?.nodes?.length > 0 && (
                    <Section title="Entity Graph">
                        <Row label="Entities" value={entityGraph.nodes.length} />
                        <Row label="Relations" value={entityGraph.edges?.length || 0} />
                        {entityGraph.nodes.length > 0 && (
                            <div className="mt-1.5 text-[8px] text-[#6b7280]">
                                {entityGraph.nodes.slice(0, 6).map(n => n.label || n.id || n.name).filter(Boolean).join(', ')}
                                {entityGraph.nodes.length > 6 ? ` +${entityGraph.nodes.length - 6} more` : ''}
                            </div>
                        )}
                    </Section>
                )}

                {/* Analysis Insight — data-driven, replaces hardcoded Model Operating Mode */}
                <Section title="Analysis">
                    <div className="text-[9.5px] text-[#374151] leading-relaxed space-y-1.5">
                        {insight ? (
                            <div>
                                <span className="font-bold text-[#111111]">Insight: </span>
                                {insight}
                            </div>
                        ) : (
                            <div>
                                <span className="font-bold text-[#111111]">Signal summary: </span>
                                {flagSummary()}
                            </div>
                        )}
                        <div>
                            <span className="font-bold text-[#111111]">Recommendation: </span>
                            {highestSeverity >= 0.60 || nFails > 2
                                ? 'Escalate for senior risk underwriter review — multiple deterministic signals detected.'
                                : highestSeverity >= 0.30 || nFails > 0
                                ? 'Perform manual document verification — signals warrant human review.'
                                : 'Proceed with standard approval workflow — no significant signals detected.'}
                        </div>
                    </div>
                </Section>

            </div>
        </div>
    );
};

export default ThreatEngine;