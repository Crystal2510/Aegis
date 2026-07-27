import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Search, Loader } from 'lucide-react';

const DatabaseView = ({ onSelectDossier }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [activeFilter, setActiveFilter] = useState('ALL'); // 'ALL', 'HIGH RISK', 'CRITICAL'
  const [dbData, setDbData] = useState([]);
  const [stats, setStats] = useState({ total: 0, safe_count: 0, risked_count: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [loadingReports, setLoadingReports] = useState({});
  const rowsPerPage = 50;

  useEffect(() => {
    const fetchDatabase = async () => {
      try {
        setLoading(true);
        let res = await axios.get('http://127.0.0.1:8000/dossiers', { params: { limit: 200, offset: 0 } });
        if (res.data?.items) {
          const mapped = (res.data.items || []).map(item => ({
            applicant_id: item.dossier_id,
            name: item.dossier_id,
            pan: '-',
            doc_date: item.analyzed_at ? new Date(item.analyzed_at).toISOString().split('T')[0] : '-',
            risk_score: item.risk_score || 0,
            risk_level: item.risk_score >= 0.70 ? 'CRITICAL' : item.risk_score >= 0.50 ? 'HIGH' : item.risk_score >= 0.30 ? 'MEDIUM' : 'LOW',
            n_documents: item.n_documents,
            n_flagged: item.n_flagged,
            fraud_flags: item.fraudulent ? ['visual_anomaly'] : [],
            fraudulent: item.fraudulent,
          }));
          setDbData(mapped);
          setStats({ total: res.data.total, safe_count: 0, risked_count: 0 });
        } else {
          res = await axios.get('http://127.0.0.1:8000/database/list');
          setDbData(res.data.records || []);
          setStats({
            total: res.data.total,
            safe_count: res.data.safe_count,
            risked_count: res.data.risked_count
          });
        }
        setError(null);
      } catch (err) {
        try {
          const fallback = await axios.get('http://127.0.0.1:8000/database/list');
          setDbData(fallback.data.records || []);
          setStats({
            total: fallback.data.total,
            safe_count: fallback.data.safe_count,
            risked_count: fallback.data.risked_count
          });
        } catch (err2) {
          console.error("Failed to fetch database:", err);
          setError("Could not connect to the database engine. Ensure the backend is running.");
        }
      } finally {
        setLoading(false);
      }
    };
    fetchDatabase();
  }, []);

  const downloadReport = async (applicant_id) => {
    setLoadingReports(prev => ({ ...prev, [applicant_id]: 'LOADING' }));
    try {
        let response = await fetch(`http://127.0.0.1:8000/dossiers/${applicant_id}/export-pdf`);
        if (!response.ok) {
            response = await fetch(`http://127.0.0.1:8000/report/${applicant_id}`);
        }
        if (!response.ok) {
            setLoadingReports(prev => ({ ...prev, [applicant_id]: 'ERROR' }));
            return;
        }
        const contentType = response.headers.get('content-type') || '';
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `AEGIS_Report_${applicant_id}.${contentType.includes('pdf') ? 'pdf' : 'json'}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        setLoadingReports(prev => ({ ...prev, [applicant_id]: 'SUCCESS' }));
        setTimeout(() => {
            setLoadingReports(prev => ({ ...prev, [applicant_id]: null }));
        }, 1500);
    } catch (err) {
        console.error(err);
        setLoadingReports(prev => ({ ...prev, [applicant_id]: 'ERROR' }));
    }
  };

  const filteredDB = dbData.filter(entry => {
      const matchesSearch = entry.applicant_id?.toLowerCase().includes(searchTerm.toLowerCase()) || 
                            entry.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                            entry.pan?.toLowerCase().includes(searchTerm.toLowerCase());
      
      let matchesFilter = true;
      if (activeFilter === 'HIGH RISK') matchesFilter = entry.risk_level === 'HIGH' || entry.risk_level === 'CRITICAL';
      
      return matchesSearch && matchesFilter;
  });

  const totalPages = Math.ceil(filteredDB.length / rowsPerPage);
  const startIdx = (currentPage - 1) * rowsPerPage;
  const currentRows = filteredDB.slice(startIdx, startIdx + rowsPerPage);

  const getBadgeStyle = (level) => {
      switch(level) {
          case 'CRITICAL': return { border: '1px solid #000', color: '#fff', background: '#000' };
          case 'HIGH': return { border: '1px solid #991b1b', color: '#991b1b', background: '#fff' };
          case 'MEDIUM': return { border: '1px solid #92400e', color: '#92400e', background: '#fff' };
          case 'LOW': return { border: '1px solid #1a3db5', color: '#1a3db5', background: '#fff' };
          default: return { border: '1px solid #111', color: '#111', background: '#fff' };
      }
  };

  const getRowStyle = (level) => {
      if (level === 'CRITICAL') return "bg-[#fafafa] border-l-[3px] border-l-[#000]";
      if (level === 'HIGH') return "bg-[#fff] border-l-[3px] border-l-[#991b1b]";
      return "border-l-[3px] border-l-transparent";
  };

  return (
    <div className="w-full h-full p-8 bg-[#ffffff] text-[#111] overflow-hidden flex flex-col font-['Inter']">
      <div className="max-w-7xl mx-auto w-full flex-1 flex flex-col min-h-0">
        
        {/* TOP PILLS AREA */}
        <div className="flex justify-between items-start mb-6 shrink-0">
          <div>
            <h1 style={{ fontFamily: "'Inter', sans-serif", fontWeight: 700, fontSize: '22px', color: '#111' }}>Applicant Database</h1>
            <p style={{ fontFamily: "'Inter', sans-serif", fontWeight: 400, fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>
              Immutable audit log · {stats.total} records · {stats.risked_count} flagged
            </p>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="relative w-64">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-[#6b7280]" />
              <input 
                type="text" 
                placeholder="Search by ID, Name or PAN..." 
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{ fontFamily: "'Inter', sans-serif", fontSize: '13px' }}
                className="w-full bg-[#fff] border border-[#e5e7eb] pl-9 pr-4 py-2 focus:outline-none focus:border-[#111]"
              />
            </div>

            <div className="flex gap-2">
              {['ALL', 'HIGH RISK'].map(filter => (
                <button 
                  key={filter}
                  onClick={() => { setActiveFilter(filter); setCurrentPage(1); }}
                  style={{
                    fontFamily: "'Inter', sans-serif", fontSize: '12px', padding: '4px 12px',
                    background: activeFilter === filter ? '#111' : '#fff',
                    color: activeFilter === filter ? '#fff' : '#6b7280',
                    border: activeFilter === filter ? '1px solid #111' : '1px solid #e5e7eb',
                  }}
                >
                  {filter}
                </button>
              ))}
              
              {/* Export Audit Trail */}
              <button
                onClick={async () => {
                  try {
                    const response = await fetch('http://127.0.0.1:8000/audit-trail/export?format=csv');
                    if (!response.ok) {
                      alert('Failed to export audit trail');
                      return;
                    }
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `AEGIS_AuditTrail_${new Date().toISOString().split('T')[0]}.csv`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                  } catch (err) {
                    console.error(err);
                    alert('Export failed');
                  }
                }}
                style={{
                  fontFamily: "'Inter', sans-serif", fontSize: '12px', padding: '4px 12px',
                  background: '#fff',
                  color: '#111',
                  border: '1px solid #e5e7eb',
                }}
                title="Export all records and forensic data as CSV"
              >
                 Export CSV
              </button>
            </div>
          </div>
        </div>

        {error && (
          <div className="p-4 bg-[#fff] border border-[#991b1b] text-[#991b1b] mb-6 flex items-center gap-2 shrink-0" style={{ fontFamily: "'Inter', sans-serif", fontSize: '13px' }}>
            {error}
          </div>
        )}

        {/* TABLE AREA */}
        <div className="flex-1 min-h-0 border border-[#e5e7eb] bg-[#fff] flex flex-col relative">
          {loading ? (
            <div className="flex flex-col items-center justify-center flex-1 text-[#6b7280]">
               <Loader className="w-6 h-6 animate-spin mb-4 text-[#111]" />
               <p style={{ fontFamily: "'Inter', sans-serif", fontSize: '13px' }}>Scanning dataset and computing risk matrices...</p>
            </div>
          ) : (
            <div className="overflow-y-auto flex-1">
              <table className="w-full text-left whitespace-nowrap border-collapse relative">
                <thead style={{ background: '#fafafa', borderBottom: '2px solid #111', fontFamily: "'Inter', sans-serif", fontWeight: 600, fontSize: '11px', letterSpacing: '0.1em', color: '#111' }} className="sticky top-0 z-10">
                  <tr>
                    <th className="px-4 py-3 font-semibold">APPLICANT ID</th>
                    <th className="px-4 py-3 font-semibold">NAME</th>
                    <th className="px-4 py-3 font-semibold">PAN</th>
                    <th className="px-4 py-3 font-semibold">DATE</th>
                    <th className="px-4 py-3 font-semibold">RISK SCORE</th>
                    <th className="px-4 py-3 font-semibold">RISK LEVEL</th>
                    <th className="px-4 py-3 font-semibold">DOMINANT RISK</th>
                    <th className="px-4 py-3 font-semibold text-right">ACTION</th>
                  </tr>
                </thead>
                <tbody>
                  {currentRows.map((row, idx) => (
                    <tr 
                      key={row.applicant_id || idx} 
                      onClick={() => onSelectDossier && onSelectDossier(row.applicant_id)}
                      className={`hover:bg-[#f3f4f6] cursor-pointer transition-all border-b border-[#f0f0f0] ${getRowStyle(row.risk_level)}`}
                    >
                      <td className="px-4 py-3" style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '12px', color: '#111' }}>{row.applicant_id}</td>
                      <td className="px-4 py-3" style={{ fontFamily: "'Inter', sans-serif", fontSize: '13px', color: '#111' }}>{row.name}</td>
                      <td className="px-4 py-3" style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '12px', color: '#111' }}>{row.pan}</td>
                      <td className="px-4 py-3" style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '12px', color: '#111' }}>{row.doc_date}</td>
                      <td className="px-4 py-3" style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '12px', color: '#111' }}>{(row.risk_score * 100).toFixed(0)}/100</td>
                      <td className="px-4 py-3">
                        <span style={{ 
                            ...getBadgeStyle(row.risk_level),
                            fontFamily: "'Inter', sans-serif", fontWeight: 600, fontSize: '10px', letterSpacing: '0.06em', padding: '2px 8px'
                         }}>
                          {row.risk_level}
                        </span>
                      </td>
                      <td className="px-4 py-3" style={{ fontFamily: "'Inter', sans-serif", fontSize: '12px', color: '#4b5563' }}>
                        {row.risk_level === 'LOW' ? '-' : (
                            Array.isArray(row.fraud_flags) && row.fraud_flags.length > 0 
                            ? row.fraud_flags[0].replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) 
                            : 'Complex Anomalies'
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {(() => {
                            const state = loadingReports[row.applicant_id];
                            let btnStyle = { border: '1px solid #111', color: '#111', background: '#fff', fontFamily: "'Inter', sans-serif", fontWeight: 600, fontSize: '11px', letterSpacing: '0.06em', padding: '4px 12px', cursor: 'pointer', transition: '150ms' };
                            let label = "REPORT ↓";

                            if (state === 'LOADING') {
                                btnStyle = { ...btnStyle, border: '1px solid #9ca3af', color: '#9ca3af', cursor: 'not-allowed' };
                                label = "GENERATING...";
                            } else if (state === 'ERROR') {
                                btnStyle = { ...btnStyle, border: '1px solid #991b1b', color: '#991b1b' };
                                label = "FAILED";
                            } else if (state === 'SUCCESS') {
                                btnStyle = { ...btnStyle, background: '#111', color: '#fff' };
                                label = "DOWNLOADED ";
                            }

                            return (
                                <button 
                                    onClick={() => state !== 'LOADING' && downloadReport(row.applicant_id)}
                                    style={btnStyle}
                                    className={state === null || state === undefined ? "hover:bg-[#111] hover:text-[#fff]" : ""}
                                    disabled={state === 'LOADING'}
                                >
                                    {label}
                                </button>
                            );
                        })()}
                      </td>
                    </tr>
                  ))}
                  {currentRows.length === 0 && (
                      <tr>
                          <td colSpan="7" className="text-center py-8 text-[#6b7280]" style={{ fontFamily: "'Inter', sans-serif", fontSize: '13px' }}>
                              No records match the current filters.
                          </td>
                      </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* PAGINATION */}
        {!loading && (
            <div className="flex justify-between items-center mt-4" style={{ fontFamily: "'Inter', sans-serif", fontSize: '12px', color: '#6b7280' }}>
                <div>
                    Showing {filteredDB.length === 0 ? 0 : startIdx + 1}–{Math.min(startIdx + rowsPerPage, filteredDB.length)} of {filteredDB.length} records
                </div>
                <div className="flex gap-2">
                    <button 
                        onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                        disabled={currentPage === 1}
                        style={{ border: '1px solid #e5e7eb', padding: '4px 10px', background: currentPage === 1 ? '#fafafa' : '#fff', color: currentPage === 1 ? '#d1d5db' : '#111' }}
                    >
                        Prev
                    </button>
                    <button 
                        onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                        disabled={currentPage === totalPages || totalPages === 0}
                        style={{ border: '1px solid #e5e7eb', padding: '4px 10px', background: (currentPage === totalPages || totalPages === 0) ? '#fafafa' : '#fff', color: (currentPage === totalPages || totalPages === 0) ? '#d1d5db' : '#111' }}
                    >
                        Next
                    </button>
                </div>
            </div>
        )}

      </div>
    </div>
  );
};

export default DatabaseView;
