import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import Header from './components/Header';
import LandingPage from './components/LandingPage';
import ForensicWorkspace from './components/ForensicWorkspace';
import ForensicNavigator from './components/ForensicNavigator';
import ThreatEngine from './components/ThreatEngine';
import DatabaseView from './components/DatabaseView';
import ApplicantHistorySidebar from './components/ApplicantHistorySidebar';
import ForensicLoadingScreen from './components/ForensicLoadingScreen';
import { adaptBackendResponse } from './lib/adapter';
import { dossierPriority, dossierPurpose } from './components/ForensicWorkspace';

const API_BASE = 'http://127.0.0.1:8000';

function App() {
    const [currentRoute, setCurrentRoute] = useState('upload');
    const [applicants, setApplicants] = useState([]);
    const [activeApplicantId, setActiveApplicantId] = useState(null);
    const [showHistorySidebar, setShowHistorySidebar] = useState(false);
    const [activeModule, setActiveModule] = useState('Document Viewer');
    const [loadingDossierName, setLoadingDossierName] = useState(null);
    const [showLoadingScreen, setShowLoadingScreen] = useState(false);
    const loadingResolveRef = useRef(null);

    const prevApplicantId = useRef(null);
    useEffect(() => {
        if (activeApplicantId !== prevApplicantId.current) {
            prevApplicantId.current = activeApplicantId;
            setActiveModule('Document Viewer');
        }
    }, [activeApplicantId]);

    useEffect(() => {
        const handleKeyDown = (e) => {
            if (currentRoute !== 'upload' && currentRoute !== 'hub') return;
            if (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA') return;
            if (e.key.toLowerCase() === 'f') setCurrentRoute('hub');
            else if (e.key.toLowerCase() === 'd') setCurrentRoute('database');
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [currentRoute]);

    const handleSelectDossier = async (dossierId) => {
        try {
            const res = await axios.get(`${API_BASE}/dossiers/${dossierId}`);
            const adapted = adaptBackendResponse(res.data);
            setApplicants(prev => {
                const exists = prev.find(a => a.id === dossierId);
                if (exists) {
                    return prev.map(a => a.id === dossierId ? { ...a, data: adapted, status: 'done' } : a);
                }
                return [...prev, { id: dossierId, name: adapted.applicant_name || dossierId, status: 'done', data: adapted }];
            });
            setActiveApplicantId(dossierId);
            setCurrentRoute('hub');
        } catch (err) {
            console.error('Failed to load dossier:', err);
        }
    };

    const handleUpload = async (payload) => {
        const label =
            payload.mode === 'folder' ? (payload.path?.split(/[\/\\]/).pop() || 'Dossier')
          : payload.mode === 'batch'  ? (payload.file?.name || 'Batch')
          :                             (payload.file?.name || 'Document');

        const newApplicant = {
            id: `TEMP-${Date.now()}`,
            name: label,
            status: 'processing',
            data: null,
        };

        setApplicants(prev => [...prev, newApplicant]);
        setActiveApplicantId(newApplicant.id);

        // Show branded loading screen
        setLoadingDossierName(label);
        setShowLoadingScreen(true);

        // API call runs in parallel — store the resolve so we can finish loading screen after
        const loadPromise = new Promise((resolve) => {
            loadingResolveRef.current = resolve;
        });

        try {
            let raw;

            if (payload.mode === 'folder') {
                const res = await axios.post(`${API_BASE}/analyze/dossier`, {
                    dossier_path: payload.path,
                    force: false,
                });
                raw = res.data;

            } else if (payload.mode === 'upload-folder') {
                const form = new FormData();
                payload.files.forEach(file => {
                    form.append('files', file, file.webkitRelativePath || file.name);
                });
                const res = await axios.post(`${API_BASE}/analyze/upload-folder`, form, {
                    headers: { 'Content-Type': 'multipart/form-data' },
                });
                raw = res.data;

            } else if (payload.mode === 'single') {
                const form = new FormData();
                form.append('file', payload.file);
                const res = await axios.post(`${API_BASE}/analyze/document`, form, {
                    headers: { 'Content-Type': 'multipart/form-data' },
                });
                raw = res.data;

            } else {
                const form = new FormData();
                form.append('file', payload.file);
                const res = await axios.post(`${API_BASE}/analyze/batch`, form, {
                    headers: { 'Content-Type': 'multipart/form-data' },
                });
                raw = {
                    dossier_id: `batch-${Date.now()}`,
                    fraudulent: res.data.fraudulent > 0,
                    risk_score: 0,
                    n_documents: res.data.processed,
                    n_flagged: res.data.fraudulent,
                    techniques: [],
                    processing_time_ms: 0,
                    analyzed_at: null,
                    ground_truth_fraudulent: null,
                    documents: [],
                    mismatches: [],
                    _batchResult: res.data,
                };
            }

            const adapted = adaptBackendResponse(raw);
            setApplicants(prev => prev.map(app =>
                app.id === newApplicant.id
                    ? { ...app, name: adapted.applicant_name || label, status: 'done', data: adapted }
                    : app
            ));

            // Signal loading screen: API is done — it will finish its own animation then call onComplete
            if (loadingResolveRef.current) loadingResolveRef.current('done');

        } catch (error) {
            console.error('Upload failed:', error);
            const msg = error?.response?.data?.detail || error.message || 'Unknown error';
            setApplicants(prev => prev.map(app =>
                app.id === newApplicant.id
                    ? { ...app, status: 'error', errorMessage: msg }
                    : app
            ));
            // On error, skip loading screen
            setShowLoadingScreen(false);
        }
    };

    const handleLoadingComplete = useCallback(() => {
        setShowLoadingScreen(false);
        setLoadingDossierName(null);
        setCurrentRoute('hub');
    }, []);

    const activeApplicant = applicants.find(a => a.id === activeApplicantId)?.data;

    return (
        <div className="w-full h-screen flex flex-col bg-white text-[#111111] overflow-hidden">
            <Header
                currentRoute={currentRoute}
                setCurrentRoute={setCurrentRoute}
                applicantName={activeApplicant?.applicant_name || activeApplicant?.name}
                applicantId={activeApplicantId}
                onViewHistory={() => setShowHistorySidebar(prev => !prev)}
            />

            {currentRoute === 'database' && (
                <div className="flex-1 overflow-hidden bg-[#fafafa]">
                    <DatabaseView onSelectDossier={handleSelectDossier} />
                </div>
            )}

            {(currentRoute === 'upload' || (currentRoute === 'hub' && !activeApplicantId)) && (
                <LandingPage onUpload={handleUpload} />
            )}

            {currentRoute === 'hub' && activeApplicantId && (showLoadingScreen || activeApplicant) && (
                <div className="flex-1 flex overflow-hidden">
                    <div style={{ width: '220px', flexShrink: 0 }} className="bg-[#f9fafb] border-r border-[#e5e7eb] h-full flex flex-col">
                        <div className="flex flex-col" style={{ flex: '0 0 auto', maxHeight: '50%', minHeight: '120px', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                            <div className="h-[36px] px-4 border-b border-[#e5e7eb] flex justify-between items-center bg-[#f9fafb] shrink-0">
                                <div style={{ fontFamily: "'Inter', sans-serif", fontWeight: 600, fontSize: '10px', color: '#374151', letterSpacing: '0.1em' }}>APPLICATION QUEUE</div>
                                <button onClick={() => setCurrentRoute('upload')} style={{ fontSize: '16px', fontWeight: 'bold', color: '#374151' }}>+</button>
                            </div>
                            <div className="overflow-y-auto p-3 space-y-2" style={{ flex: 1 }}>
                                {applicants.map(app => (
                                    <div
                                        key={app.id}
                                        onClick={() => app.status === 'done' && setActiveApplicantId(app.id)}
                                        className={`p-2 border bg-white cursor-pointer transition-colors relative ${activeApplicantId === app.id ? 'border-[#111111]' : 'border-[#e5e7eb] hover:border-[#9ca3af]'}`}
                                    >
                                        <div className="flex justify-between items-start">
                                            <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '11px', fontWeight: 600, color: '#111111' }} className="truncate pr-6">{app.name}</div>
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    setApplicants(prev => prev.filter(a => a.id !== app.id));
                                                    if (activeApplicantId === app.id) setActiveApplicantId(null);
                                                }}
                                                style={{ color: '#64748b' }} className="hover:text-[#ef4444]"
                                                title="Remove Application"
                                            >×</button>
                                        </div>
                                        <div className="flex flex-wrap justify-between items-center mt-2 gap-1">
                                            {app.status === 'processing' && <span style={{ fontFamily: "'Inter', sans-serif", fontSize: '10px', color: '#60a5fa' }} className="animate-pulse uppercase font-semibold">Processing...</span>}
                                            {app.status === 'error' && <span style={{ fontFamily: "'Inter', sans-serif", fontSize: '10px', color: '#ef4444' }} className="uppercase font-semibold">Error</span>}
                                            {app.status === 'done' && app.data && (() => {
                                                const priority = dossierPriority(app.data.documents || []);
                                                const purpose = dossierPurpose(app.data.documents || []);
                                                return (
                                                    <>
                                                        <span style={{ fontFamily: "'Inter', sans-serif", fontSize: '9px', padding: '2px 5px', borderRadius: '3px', background: priority.bg, color: priority.color, border: `1px solid ${priority.color}40` }}>
                                                            {priority.label}
                                                        </span>
                                                        <span style={{ fontFamily: "'Inter', sans-serif", fontSize: '9px', color: '#64748b', fontStyle: 'italic' }}>
                                                            {purpose}
                                                        </span>
                                                    </>
                                                );
                                            })()}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div style={{ height: '1px', backgroundColor: 'rgba(255,255,255,0.05)', flexShrink: 0 }} />

                        <div className="flex flex-col" style={{ flex: 1, overflow: 'hidden' }}>
                            {activeApplicant ? (
                                <ForensicNavigator
                                    backendData={activeApplicant}
                                    activeModule={activeModule}
                                    setActiveModule={setActiveModule}
                                />
                            ) : (
                                <div className="flex h-full items-center justify-center text-[#9ca3af]" style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '11px' }}>
                                    No Analysis Active
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="flex-1 h-full overflow-hidden bg-white">
                        {applicants.find(a => a.id === activeApplicantId)?.status === 'error' ? (
                            <div className="flex-1 h-full flex flex-col items-center justify-center text-[#ef4444] p-6 gap-2 text-center" style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '12px' }}>
                                <div className="font-bold text-[14px]">ASSEMBLY OR PIPELINE FAILURE</div>
                                <div className="max-w-[400px] text-[#fca5a5] mt-1 font-sans">
                                    {applicants.find(a => a.id === activeApplicantId)?.errorMessage || "Invalid folder structure or unsupported file format."}
                                </div>
                            </div>
                        ) : activeApplicant ? (
                            <ForensicWorkspace
                                backendData={activeApplicant}
                                activeModule={activeModule}
                                setActiveModule={setActiveModule}
                            />
                        ) : (
                            <div className="flex-1 h-full flex items-center justify-center text-slate-500" style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '12px' }}>
                                Processing document data...
                            </div>
                        )}
                    </div>

                    <div style={{ width: '300px', flexShrink: 0 }} className="bg-[#f9fafb] border-l border-[#e5e7eb] h-full flex flex-col overflow-hidden">
                        <div className="overflow-y-auto flex-1">
                            {activeApplicant && <ThreatEngine backendData={activeApplicant} />}
                        </div>
                    </div>
                </div>
            )}

            {showHistorySidebar && activeApplicant && (
                <ApplicantHistorySidebar
                    pan={activeApplicant.pan}
                    applicantName={activeApplicant.applicant_name || activeApplicant.name}
                    currentRiskLevel={activeApplicant.risk_level}
                    onClose={() => setShowHistorySidebar(false)}
                />
            )}

            {showLoadingScreen && (
                <ForensicLoadingScreen
                    dossierName={loadingDossierName}
                    onComplete={handleLoadingComplete}
                />
            )}
        </div>
    );
}

export default App;
