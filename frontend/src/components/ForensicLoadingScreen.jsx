import React, { useState, useEffect } from 'react';

const FORENSIC_STAGES = [
    { ms: 0,     label: 'INITIALISING AEGIS MMFFN v2.0 ENGINE...',                   pct: 2  },
    { ms: 800,   label: 'Mounting document store — artefacts detected',               pct: 8  },
    { ms: 1600,  label: 'Decoding PDF container metadata headers...',                 pct: 13 },
    { ms: 2400,  label: 'OCR Pipeline: extracting text from documents...',            pct: 20 },
    { ms: 3300,  label: 'OCR field extraction — key-value pairs captured',            pct: 27 },
    { ms: 4200,  label: 'Error Level Analysis (ELA) — JPEG compression grid...',      pct: 34 },
    { ms: 5100,  label: 'Spatial Rich Model (SRM) noise residual filter...',          pct: 41 },
    { ms: 6000,  label: 'Neural visual model: localization mask inference...',        pct: 48 },
    { ms: 6900,  label: 'Benford Law digit-frequency analysis on numeric fields...',  pct: 55 },
    { ms: 7800,  label: 'Cross-document semantic coherence alignment...',              pct: 62 },
    { ms: 8700,  label: 'Mathematical integrity checks — salary, cheque, ITR...',     pct: 68 },
    { ms: 9600,  label: 'MICR E-13B character width measurement (CTS-2010)...',       pct: 74 },
    { ms: 10500, label: 'PDF metadata forensics — flagging non-standard producers...', pct: 80 },
    { ms: 11400, label: 'Timeline analysis — cross-document chronology...',           pct: 86 },
    { ms: 12300, label: 'Compiling evidence summary & risk score...',                 pct: 92 },
    { ms: 13200, label: 'Generating underwriter audit trail...',                      pct: 96 },
    { ms: 14000, label: 'ANALYSIS COMPLETE',                                          pct: 100 },
];

const ForensicLoadingScreen = ({ dossierName, onComplete }) => {
    const [stageIdx, setStageIdx] = useState(0);
    const [pct, setPct] = useState(0);
    const [log, setLog] = useState([]);
    const [done, setDone] = useState(false);

    useEffect(() => {
        const timers = FORENSIC_STAGES.map((stage, i) =>
            setTimeout(() => {
                setStageIdx(i);
                setPct(stage.pct);
                setLog(prev => [{ label: stage.label, pct: stage.pct }, ...prev].slice(0, 14));
                if (i === FORENSIC_STAGES.length - 1) {
                    setDone(true);
                    setTimeout(onComplete, 900);
                }
            }, stage.ms)
        );
        return () => timers.forEach(clearTimeout);
    }, [onComplete]);

    return (
        <div className="fixed inset-0 z-[9999] bg-white flex flex-col" style={{ fontFamily: "'IBM Plex Mono', monospace" }}>
            {/* Header bar */}
            <div className="h-[36px] border-b border-[#e5e7eb] flex items-center px-6 justify-between shrink-0">
                <div style={{ fontFamily: "'Cormorant Garamond', serif", fontWeight: 700, fontSize: '18px', color: '#111', letterSpacing: '0.12em' }}>AEGIS</div>
                <div className="text-[10px] text-[#9ca3af]" style={{ letterSpacing: '0.06em' }}>FORENSIC PIPELINE — RUNNING</div>
            </div>

            <div className="flex-1 flex flex-col items-center justify-center px-6 py-10">
                <div className="w-full max-w-[640px]">
                    {/* Dossier badge */}
                    <div className="flex items-center gap-3 mb-7">
                        <div
                            className="w-2 h-2 rounded-full"
                            style={{
                                background: done ? '#10b981' : '#1a3db5',
                                boxShadow: done ? '0 0 0 4px #d1fae5' : '0 0 0 4px #dbeafe'
                            }}
                        />
                        <div className="text-[11px] font-bold text-[#111] uppercase" style={{ letterSpacing: '0.1em' }}>
                            Analysing: {dossierName || 'Dossier'}
                        </div>
                        <div className="ml-auto text-[11px] text-[#9ca3af]">v2.0</div>
                    </div>

                    {/* Stage label */}
                    <div className="text-[12px] font-semibold min-h-[18px] mb-3" style={{ color: done ? '#10b981' : '#111', letterSpacing: '0.02em' }}>
                        {FORENSIC_STAGES[stageIdx]?.label || ''}
                    </div>

                    {/* Progress bar */}
                    <div className="h-[3px] bg-[#f3f4f6] rounded-[2px] overflow-hidden mb-7">
                        <div
                            className="h-full rounded-[2px]"
                            style={{
                                background: done ? '#10b981' : '#1a3db5',
                                width: pct + '%',
                                transition: 'width 0.7s ease-out'
                            }}
                        />
                    </div>

                    {/* Live pipeline log */}
                    <div className="border-t border-[#e5e7eb] pt-4">
                        <div className="text-[9px] font-semibold text-[#9ca3af] uppercase mb-2.5" style={{ letterSpacing: '0.1em' }}>
                            Pipeline Log
                        </div>
                        <div className="flex flex-col gap-1">
                            {log.map((l, i) => (
                                <div
                                    key={i}
                                    className="flex items-center gap-2.5"
                                    style={{ opacity: i === 0 ? 1 : Math.max(0.15, 1 - i * 0.075) }}
                                >
                                    <span
                                        className="text-[9px] font-bold shrink-0 text-right"
                                        style={{ color: i === 0 ? '#1a3db5' : '#d1d5db', width: '32px' }}
                                    >
                                        {l.pct}%
                                    </span>
                                    <span
                                        className="shrink-0"
                                        style={{ width: '1px', height: '10px', background: i === 0 ? '#1a3db5' : '#e5e7eb' }}
                                    />
                                    <span className="text-[10px]" style={{ color: i === 0 ? '#111' : '#9ca3af' }}>
                                        {l.label}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ForensicLoadingScreen;
