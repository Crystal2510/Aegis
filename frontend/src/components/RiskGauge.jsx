/**
 * RiskGauge.jsx
 *
 * Animated half-circle gauge showing dossier risk score.
 * Only shows real data — no fake confidence or model-mode fields.
 * Sub-label explains what the score means in plain language.
 */

import React, { useEffect, useState } from 'react';

const RiskGauge = ({ score, nFlagged, nDocuments }) => {
    const [animatedScore, setAnimatedScore] = useState(0);

    useEffect(() => {
        let start = 0;
        const end = Math.round((score || 0) * 100);
        if (end === 0) { setAnimatedScore(0); return; }

        const duration = 1200;
        const increment = end / (duration / 16);
        const timer = setInterval(() => {
            start += increment;
            if (start >= end) {
                clearInterval(timer);
                setAnimatedScore(end);
            } else {
                setAnimatedScore(Math.floor(start));
            }
        }, 16);

        return () => clearInterval(timer);
    }, [score]);

    const getColor = (s) => {
        if (s >= 65) return '#ef4444';
        if (s >= 45) return '#f59e0b';
        if (s >= 30) return '#f59e0b';
        return '#10b981';
    };

    const getLabel = (s) => {
        if (s >= 65) return 'Elevated — escalate for review';
        if (s >= 45) return 'Moderate — underwriter review';
        return 'Within range — standard KYC';
    };

    const radius = 80;
    const circumference = Math.PI * radius;
    const strokeDashoffset = circumference - (animatedScore / 100) * circumference;
    const color = getColor(animatedScore);

    return (
        <div className="flex flex-col items-center justify-center p-5 border-b border-[#e5e7eb] bg-white">
            <div className="relative w-[180px] h-[100px] overflow-hidden flex justify-center">
                <svg width="180" height="100" viewBox="0 0 200 120" className="rotate-180">
                    <circle
                        cx="100" cy="10" r={radius}
                        fill="none"
                        stroke="#e5e7eb"
                        strokeWidth="14"
                        strokeDasharray={circumference}
                        strokeDashoffset="0"
                    />
                    <circle
                        cx="100" cy="10" r={radius}
                        fill="none"
                        stroke={color}
                        strokeWidth="14"
                        strokeDasharray={circumference}
                        strokeDashoffset={strokeDashoffset}
                        style={{ transition: 'stroke-dashoffset 75ms linear' }}
                    />
                </svg>
                <div className="absolute bottom-1 text-center">
                    <div
                        className="text-[42px] font-black font-mono leading-none"
                        style={{ color }}
                    >
                        {animatedScore}
                    </div>
                    <div className="text-[9px] font-bold uppercase tracking-widest mt-0.5 text-[#6b7280]">
                        Risk Score
                    </div>
                </div>
            </div>

            <div
                className="mt-3 text-center text-[10px] font-semibold"
                style={{ color }}
            >
                {getLabel(animatedScore)}
            </div>

            {nDocuments != null && (
                <div className="mt-2 text-[9px] text-[#6b7280] text-center">
                    {nFlagged ?? 0} of {nDocuments} documents flagged
                </div>
            )}
        </div>
    );
};

export default RiskGauge;
