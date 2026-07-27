import React, { useState, useEffect } from 'react';

const ApplicantHistorySidebar = ({ pan, applicantName, currentRiskLevel, onClose }) => {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!pan) {
      setLoading(false);
      return;
    }

    const fetchHistory = async () => {
      try {
        setLoading(true);
        const response = await fetch(`http://127.0.0.1:8000/applicant-history?pan=${encodeURIComponent(pan)}`);
        
        if (!response.ok) {
          throw new Error('Failed to fetch history');
        }
        
        const data = await response.json();
        // Filter out the current submission and get previous ones
        setHistory(data.history || []);
      } catch (err) {
        console.error('Error fetching history:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, [pan]);

  const getRiskColor = (riskLevel) => {
    if (riskLevel === 'CRITICAL') return '#FF0000';
    if (riskLevel === 'HIGH') return '#FF6B35';
    if (riskLevel === 'MEDIUM') return '#FFB800';
    return '#00FF88';
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Unknown';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-IN', { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      return dateStr;
    }
  };

  return (
    <div className="fixed right-0 top-0 h-screen w-80 bg-white border-l border-[#ddd] shadow-lg flex flex-col z-50">
      {/* Header */}
      <div className="h-12 px-4 py-3 border-b border-[#ddd] flex justify-between items-center bg-[#f5f5f5]">
        <div style={{ fontFamily: "'Inter', sans-serif", fontWeight: 600, fontSize: '12px', color: '#111', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
          PAN History
        </div>
        <button 
          onClick={onClose}
          style={{ fontSize: '18px', color: '#666', cursor: 'pointer', border: 'none', background: 'none' }}
        >
          ×
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {loading && (
          <div className="text-center py-8">
            <div style={{ fontSize: '12px', color: '#999' }}>Loading history...</div>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-300 p-3 rounded text-[12px] text-red-700">
            {error}
          </div>
        )}

        {!loading && !error && history.length === 0 && (
          <div className="text-center py-8">
            <div style={{ fontSize: '12px', color: '#999' }}>No previous submissions found for this PAN</div>
          </div>
        )}

        {!loading && !error && history.length > 0 && (
          <>
            <div className="bg-amber-50 border border-amber-300 p-3 rounded">
              <div style={{ fontSize: '11px', fontWeight: 600, color: '#854d0e', marginBottom: '4px' }}>
                 REPEATED PAN DETECTED
              </div>
              <div style={{ fontSize: '10px', color: '#854d0e' }}>
                This PAN was previously analyzed {history.length} time(s). Review history below.
              </div>
            </div>

            <div>
              <div style={{ fontSize: '11px', fontWeight: 600, color: '#666', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Previous Submissions
              </div>
              <div className="space-y-2">
                {history.map((record, idx) => (
                  <div key={idx} className="border border-[#ddd] p-3 rounded bg-white">
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <div style={{ fontSize: '10px', color: '#999' }}>
                          {formatDate(record.doc_date)}
                        </div>
                        <div style={{ fontSize: '11px', fontWeight: 600, color: '#111', marginTop: '2px' }}>
                          {record.name || 'Unknown Applicant'}
                        </div>
                      </div>
                      <span 
                        style={{
                          fontSize: '10px',
                          fontWeight: 600,
                          color: getRiskColor(record.risk_level),
                          backgroundColor: `${getRiskColor(record.risk_level)}20`,
                          padding: '2px 6px',
                          borderRadius: '3px',
                          textTransform: 'uppercase',
                          letterSpacing: '0.03em'
                        }}
                      >
                        {record.risk_level}
                      </span>
                    </div>
                    <div style={{ fontSize: '10px', color: '#666' }}>
                      Risk Score: <span style={{ fontWeight: 600, color: '#111' }}>{(record.risk_score * 100).toFixed(1)}</span>
                    </div>
                    {record.fraud_flags && record.fraud_flags.length > 0 && (
                      <div style={{ fontSize: '10px', color: '#FF0000', marginTop: '4px' }}>
                        Flags: {record.fraud_flags.join(', ')}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-blue-50 border border-blue-300 p-3 rounded">
              <div style={{ fontSize: '10px', color: '#1e40af', lineHeight: '1.4' }}>
                <strong>Recommendation:</strong> High-risk pattern detected. Consider manual review and escalation to fraud investigation team.
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default ApplicantHistorySidebar;
