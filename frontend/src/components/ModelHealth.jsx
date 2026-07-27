/**
 * ModelHealth.jsx
 *
 * Ops-only page — aggregate model performance metrics.
 * AUC / Precision / Recall / F1 / per-tier recall BELONG HERE,
 * not on individual applicant review screens.
 *
 * Accessible via Header nav "Model Health" tab.
 */

import React, { useState, useEffect } from 'react';

const API = 'http://127.0.0.1:8000';

const MetricCard = ({ label, value, sub, color }) => (
    <div className="bg-white border border-[#e5e7eb] rounded-lg p-4 text-center">
        <div className="text-[22px] font-black" style={{ color: color || '#111' }}>{value ?? '—'}</div>
        <div className="text-[10px] font-bold uppercase tracking-wider text-[#374151] mt-1">{label}</div>
        {sub && <div className="text-[9px] text-[#9ca3af] mt-0.5">{sub}</div>}
    </div>
);

const Bar = ({ label, value, color }) => (
    <div className="flex items-center gap-2 mb-2">
        <div className="w-[170px] text-[10px] text-[#6b7280] truncate">{label}</div>
        <div className="flex-1 bg-[#f3f4f6] rounded-full h-[6px]">
            <div
                className="h-full rounded-full"
                style={{ width: `${Math.round((value || 0) * 100)}%`, background: color }}
            />
        </div>
        <div className="w-[36px] text-right text-[10px] font-bold" style={{ color }}>
            {Math.round((value || 0) * 100)}%
        </div>
    </div>
);

const ModelHealth = () => {
    const [stats, setStats]   = useState(null);
    const [live, setLive]     = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError]   = useState(null);

    useEffect(() => {
        const fetchAll = async () => {
            setLoading(true);
            setError(null);
            try {
                const [advRes, statsRes] = await Promise.all([
                    fetch(`${API}/adversarial_stats`),
                    fetch(`${API}/stats`),
                ]);
                if (!advRes.ok) throw new Error(`/adversarial_stats → ${advRes.status}`);
                const adv  = await advRes.json();
                const stat = statsRes.ok ? await statsRes.json() : null;
                setStats(adv);
                setLive(stat);
            } catch (e) {
                setError(e.message);
            } finally {
                setLoading(false);
            }
        };
        fetchAll();
    }, []);

    const h = stats?.held_out;
    const m = stats?.model;
    const lv = stats?.live || {};

    return (
        <div
            className="w-full h-full overflow-y-auto bg-[#f9fafb] p-6"
            style={{ fontFamily: "'Inter', sans-serif" }}
        >
            <div className="max-w-3xl mx-auto space-y-6">

                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-[18px] font-black text-[#111] uppercase tracking-tight">
                            Model Health Dashboard
                        </h1>
                        <p className="text-[11px] text-[#6b7280] mt-1">
                            Aggregate model performance — internal ops view only.
                            These metrics are <strong>not shown</strong> on individual applicant screens.
                        </p>
                    </div>
                    <div className="text-[9px] text-[#9ca3af] text-right font-mono">
                        <div>Model: AegisForgeryNet</div>
                        {m?.parameters && <div>{m.parameters.toLocaleString()} params</div>}
                    </div>
                </div>

                {loading && (
                    <div className="text-center py-12 text-[#9ca3af] text-[12px]">
                        Loading model metrics...
                    </div>
                )}
                {error && (
                    <div className="bg-[#fef2f2] border border-[#fecaca] rounded p-4 text-[12px] text-[#ef4444]">
                        Failed to load metrics: {error}
                    </div>
                )}

                {stats && (
                    <>
                        {/* Held-out test metrics */}
                        <div className="bg-white border border-[#e5e7eb] rounded-lg overflow-hidden">
                            <div className="px-4 py-3 bg-[#fafafa] border-b border-[#e5e7eb]">
                                <h2 className="text-[11px] font-bold uppercase tracking-wider text-[#374151]">
                                    Held-Out Test Performance
                                    {h?.n_samples && (
                                        <span className="ml-2 font-normal text-[#9ca3af]">
                                            n = {h.n_samples} · threshold: {h.threshold}
                                        </span>
                                    )}
                                </h2>
                            </div>
                            <div className="p-4">
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                                    <MetricCard
                                        label="AUC"
                                        value={h?.auc?.toFixed(3)}
                                        sub="Area under ROC"
                                        color="#1a3db5"
                                    />
                                    <MetricCard
                                        label="Precision"
                                        value={h?.precision != null ? `${(h.precision * 100).toFixed(1)}%` : null}
                                        sub="True flags / all flags"
                                        color="#f59e0b"
                                    />
                                    <MetricCard
                                        label="Recall"
                                        value={h?.recall != null ? `${(h.recall * 100).toFixed(1)}%` : null}
                                        sub="Caught / all forgeries"
                                        color="#10b981"
                                    />
                                    <MetricCard
                                        label="F1"
                                        value={h?.f1?.toFixed(3)}
                                        sub="Harmonic mean"
                                        color="#8b5cf6"
                                    />
                                </div>

                                {/* Honest interpretation */}
                                <div className="bg-[#fffbeb] border border-[#fde68a] rounded p-3 text-[10px] text-[#374151]">
                                    At threshold {h?.threshold}: the model flags approximately{' '}
                                    <strong>{h?.recall != null ? `${(h.recall * 100).toFixed(0)}%` : '—'} of genuine forgeries</strong> (recall),
                                    with <strong>{h?.precision != null ? `${(h.precision * 100).toFixed(0)}%` : '—'} precision</strong> —
                                    meaning roughly 1 in {h?.precision ? Math.round(1 / h.precision) : '?'} flagged documents is a genuine forgery.
                                    Threshold can be raised to improve precision at the cost of recall.
                                </div>
                            </div>
                        </div>

                        {/* Per-tier recall */}
                        {h?.per_tier_recall && (
                            <div className="bg-white border border-[#e5e7eb] rounded-lg overflow-hidden">
                                <div className="px-4 py-3 bg-[#fafafa] border-b border-[#e5e7eb]">
                                    <h2 className="text-[11px] font-bold uppercase tracking-wider text-[#374151]">
                                        Per-Tier Recall
                                    </h2>
                                    <p className="text-[9px] text-[#9ca3af] mt-0.5">
                                        How well the model detects each forgery type in adversarial tests
                                    </p>
                                </div>
                                <div className="p-4">
                                    <Bar
                                        label="Tier A — Semantic forgery (name/DOB swap, no pixel change)"
                                        value={h.per_tier_recall.tier_a}
                                        color="#ef4444"
                                    />
                                    <Bar
                                        label="Tier B — Structural forgery (field splice / copy-paste)"
                                        value={h.per_tier_recall.tier_b}
                                        color="#f59e0b"
                                    />
                                    <Bar
                                        label="Tier D — Physical damage / hard-copy artifacts"
                                        value={h.per_tier_recall.tier_d}
                                        color="#10b981"
                                    />
                                    <div className="mt-3 text-[9px] text-[#9ca3af] border-t border-[#f3f4f6] pt-2">
                                        Tier A (semantic) recall is lowest by design — pixel-level models cannot catch
                                        content-level forgeries. Cross-document coherence checking (Model 2) is the
                                        primary defence against Tier A.
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Mask IoU */}
                        {h?.mean_mask_iou != null && (
                            <div className="bg-white border border-[#e5e7eb] rounded-lg p-4 flex items-center gap-4">
                                <div className="text-center">
                                    <div className="text-[22px] font-black text-[#1a3db5]">
                                        {h.mean_mask_iou.toFixed(3)}
                                    </div>
                                    <div className="text-[9px] font-bold uppercase tracking-wider text-[#374151] mt-0.5">
                                        Mean Mask IoU
                                    </div>
                                </div>
                                <div className="text-[10px] text-[#6b7280] leading-relaxed">
                                    Forgery <strong>localization</strong> quality — how well the decoder's predicted
                                    mask overlaps with the ground-truth tampered region.
                                    0.664 is the test-set result on our 1,400-dossier dataset.
                                    IoU &gt; 0.5 is generally considered a useful localization.
                                </div>
                            </div>
                        )}

                        {/* Architecture */}
                        {m && (
                            <div className="bg-white border border-[#e5e7eb] rounded-lg overflow-hidden">
                                <div className="px-4 py-3 bg-[#fafafa] border-b border-[#e5e7eb]">
                                    <h2 className="text-[11px] font-bold uppercase tracking-wider text-[#374151]">
                                        Model Architecture
                                    </h2>
                                </div>
                                <div className="p-4 text-[11px] text-[#374151] space-y-1.5">
                                    <div><span className="font-semibold">Architecture:</span> {m.architecture}</div>
                                    <div><span className="font-semibold">Parameters:</span> {m.parameters?.toLocaleString()}</div>
                                    <div><span className="font-semibold">Training samples:</span> {m.training_samples?.toLocaleString()}</div>
                                    <div><span className="font-semibold">Device:</span> {m.device}</div>
                                </div>
                            </div>
                        )}

                        {/* Limitations */}
                        {stats.limitations?.length > 0 && (
                            <div className="bg-white border border-[#e5e7eb] rounded-lg overflow-hidden">
                                <div className="px-4 py-3 bg-[#fafafa] border-b border-[#e5e7eb]">
                                    <h2 className="text-[11px] font-bold uppercase tracking-wider text-[#374151]">
                                        Known Limitations
                                    </h2>
                                </div>
                                <div className="p-4">
                                    <ul className="space-y-2">
                                        {stats.limitations.map((l, i) => (
                                            <li key={i} className="flex items-start gap-2 text-[11px] text-[#374151]">
                                                <span className="mt-1 w-1.5 h-1.5 rounded-full bg-[#f59e0b] flex-shrink-0" />
                                                {l}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </div>
                        )}
                    </>
                )}

                {/* Live database stats */}
                {live && (
                    <div className="bg-white border border-[#e5e7eb] rounded-lg overflow-hidden">
                        <div className="px-4 py-3 bg-[#fafafa] border-b border-[#e5e7eb]">
                            <h2 className="text-[11px] font-bold uppercase tracking-wider text-[#374151]">
                                Live Database Stats
                            </h2>
                        </div>
                        <div className="p-4 grid grid-cols-3 gap-3 text-center">
                            <MetricCard label="Total Analyzed" value={live.total_count} color="#111" />
                            <MetricCard label="Flagged" value={live.risked_count} color="#ef4444" />
                            <MetricCard
                                label="Flag Rate"
                                value={live.total_count > 0
                                    ? `${((live.risked_count / live.total_count) * 100).toFixed(1)}%`
                                    : '—'}
                                color="#f59e0b"
                            />
                        </div>
                    </div>
                )}

            </div>
        </div>
    );
};

export default ModelHealth;
