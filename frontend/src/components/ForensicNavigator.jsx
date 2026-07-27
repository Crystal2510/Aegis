import React from 'react';

// 10 forensic modules
export const MODULES = [
    {
        id: 'mod-0',
        name: 'Document Viewer',
        desc: 'Original document images with forensic forgery annotation overlays',
    },
    {
        id: 'mod-1',
        name: 'Extracted Fields',
        desc: 'OCR output per document — extracted values, not-found, or failed',
    },
    {
        id: 'mod-2',
        name: 'Visual Forensics',
        desc: 'Per-document risk assessment — visual model, cross-doc mismatches, physical tampering, metadata anomalies',
    },
    {
        id: 'mod-3',
        name: 'Cross-Doc Coherence',
        desc: 'Match / Mismatch / Not Compared — full matrix across all documents',
    },
    {
        id: 'mod-4',
        name: 'Mathematical Integrity',
        desc: 'Salary, ITR, and cheque numeric verification — N/A stated explicitly for others',
    },
    {
        id: 'mod-5',
        name: 'Metadata Forensics',
        desc: 'PDF container metadata analysis — producer, creator, and editing software detection',
    },
    {
        id: 'mod-7',
        name: 'Evidence Summary',
        desc: 'Full dossier narrative — every clause traces to a real extracted value',
    },
    {
        id: 'mod-8',
        name: 'Decision & Audit',
        desc: 'Underwriter decision panel + timestamped audit trail',
    },
    {
        id: 'mod-9',
        name: 'Date Forensics',
        desc: 'Chronological order, future dates, death/registration/sanction/completion timeline checks',
    },
    {
        id: 'mod-10',
        name: 'Specialized Forensics',
        desc: 'NRI income/balance/employer, CA/ROC integrity, RERA/property consistency',
    },
];

// Derive status dot color from real backend data
const getModuleStatus = (modName, backendData) => {
    const docs     = backendData?.documents || [];
    const mm       = backendData?.mismatches || [];
    const flagged  = backendData?.fraudulent;
    const score    = backendData?.risk_score || 0;
    const softDocs = docs.filter(d => d.delivery_mode === 'soft_copy');

    switch (modName) {
        case 'Document Viewer': {
            const hasMask = docs.some(d => d.mask_url);
            const hasAnnotations = docs.some(d => d.visual_flagged || d.flagged);
            if ((hasMask || hasAnnotations) && flagged) return '#ef4444';
            if (hasMask || hasAnnotations) return '#f59e0b';
            return '#10b981';
        }
        case 'Extracted Fields': {
            const anyEmpty = docs.some(d => {
                const fields = d.ocr_fields || {};
                return Object.keys(fields).length === 0 || Object.values(fields).some(v => !v);
            });
            return anyEmpty ? '#f59e0b' : '#10b981';
        }
        case 'Visual Forensics': {
            const maxProb = Math.max(...softDocs.map(d => d.forged_prob || 0), 0);
            const anyFlagged = softDocs.some(d => d.flagged);
            const hasPhysicalFailure = (backendData?.physical_tamper_findings || []).some(p => p.passed === false);
            const hasMetaFlag = softDocs.some(d => d.ocr_fields?.__metadata__?.editing_software_detected);
            if (maxProb >= 0.60 || hasPhysicalFailure) return '#ef4444';
            if (maxProb >= 0.40 || anyFlagged || hasMetaFlag) return '#f59e0b';
            return '#10b981';
        }
        case 'Cross-Doc Coherence': {
            if (mm.length > 0) return '#ef4444';
            return '#10b981';
        }
        case 'Mathematical Integrity': {
            const mathFails = backendData?.math_findings?.some(m => m.passed === false);
            if (mathFails) return '#ef4444';
            const hasSalaryOrITR = docs.some(d =>
                (d.doc_name === 'salary' || d.doc_name === 'itr') &&
                Object.keys(d.ocr_fields || {}).length > 0
            );
            return hasSalaryOrITR ? '#6366f1' : '#9ca3af';
        }
        case 'Metadata Forensics': {
            // Red if any editing software detected
            const hasMetaFlag = softDocs.some(d => d.ocr_fields?.__metadata__?.editing_software_detected);
            if (hasMetaFlag) return '#ef4444';
            // Caution if any soft copy doc has metadata
            const hasMeta = softDocs.some(d => d.ocr_fields?.__metadata__);
            return hasMeta ? '#f59e0b' : '#9ca3af';
        }
        case 'Date Forensics': {
            const hasDateFailure = (backendData?.date_forensic_findings || []).some(d => d.passed === false);
            if (hasDateFailure) return '#ef4444';
            return '#10b981';
        }
        case 'Specialized Forensics': {
            const hasCompanyFailure = (backendData?.company_forensic_findings || []).some(c => c.passed === false);
            const hasNriFailure = (backendData?.nri_forensic_findings || []).some(n => n.passed === false);
            const hasPropertyFailure = (backendData?.property_forensic_findings || []).some(p => p.passed === false);
            if (hasCompanyFailure || hasNriFailure || hasPropertyFailure) return '#ef4444';
            return '#10b981';
        }
        case 'Evidence Summary':
            return flagged ? '#f59e0b' : '#10b981';
        case 'Decision & Audit':
            return '#9ca3af';
        default:
            return '#9ca3af';
    }
};

const ForensicNavigator = ({ backendData, activeModule, setActiveModule }) => {
    const hasDateFindings = (backendData?.date_forensic_findings || []).length > 0;
    const hasSpecializedFindings = (
        (backendData?.nri_forensic_findings || []).some(f => f.passed === false) ||
        (backendData?.company_forensic_findings || []).some(f => f.passed === false) ||
        (backendData?.property_forensic_findings || []).some(f => f.passed === false)
    );

    const visibleModules = MODULES.filter(mod => {
        if (mod.name === 'Date Forensics' && !hasDateFindings) return false;
        if (mod.name === 'Specialized Forensics' && !hasSpecializedFindings) return false;
        return true;
    });

    return (
        <div className="w-full h-full flex flex-col bg-[#fafafa]">
            <div className="h-[36px] px-4 border-b border-[#e5e7eb] flex justify-between items-center bg-[#f3f4f6] shrink-0">
                <div style={{
                    fontFamily: "'Inter', sans-serif",
                    fontWeight: 600, fontSize: '10px',
                    color: '#4b5563', letterSpacing: '0.1em'
                }}>
                    FORENSIC MODULES
                </div>
                <div style={{
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: '9px', color: '#9ca3af'
                }}>
                    {visibleModules.length} active
                </div>
            </div>

            <div className="flex-1 overflow-y-auto py-1">
                {visibleModules.map((mod) => {
                    const statusColor = getModuleStatus(mod.name, backendData);
                    const isActive = activeModule === mod.name;

                    return (
                        <div
                            key={mod.id}
                            onClick={() => setActiveModule && setActiveModule(mod.name)}
                            className={`px-4 py-2.5 cursor-pointer flex items-center justify-between transition-colors border-l-2 ${
                                isActive
                                    ? 'bg-[#f3f4f6] border-[#111111]'
                                    : 'border-transparent hover:bg-[#f9fafb]'
                            }`}
                        >
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-1.5">
                                    <span style={{
                                        fontFamily: "'Inter', sans-serif",
                                        fontSize: '10px',
                                        fontWeight: 600,
                                        color: isActive ? '#111111' : '#4b5563',
                                        letterSpacing: '0.08em',
                                        textTransform: 'uppercase',
                                    }}>
                                        {mod.name}
                                    </span>

                                </div>
                                {isActive && (
                                    <span style={{
                                        fontFamily: "'Inter', sans-serif",
                                        fontSize: '9px',
                                        color: '#9ca3af',
                                        display: 'block',
                                        marginTop: '2px',
                                    }}>
                                        {mod.desc}
                                    </span>
                                )}
                            </div>
                            <div style={{
                                width: '6px', height: '6px', borderRadius: '50%',
                                backgroundColor: statusColor, flexShrink: 0, marginLeft: '8px',
                                boxShadow: isActive ? `0 0 4px ${statusColor}` : 'none',
                            }} />
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

export default ForensicNavigator;
