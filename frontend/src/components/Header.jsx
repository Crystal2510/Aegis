import React, { useState, useEffect } from 'react';

const Header = ({ currentRoute, setCurrentRoute, applicantName, applicantId, onViewHistory }) => {
  const [modelStatus, setModelStatus] = useState(null); // true = MMFFN, false = FALLBACK
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkModelHealth = async () => {
      try {
        const response = await fetch('http://127.0.0.1:8000/health');
        if (response.ok) {
          const data = await response.json();
          setModelStatus(data.model_loaded);
        } else {
          setModelStatus(false);
        }
      } catch (error) {
        console.error('Error checking model health:', error);
        setModelStatus(false);
      } finally {
        setLoading(false);
      }
    };

    checkModelHealth();
    // Recheck every 30 seconds
    const interval = setInterval(checkModelHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <nav className="w-full bg-[#ffffff] border-b border-[#111111] shrink-0" style={{ height: '52px', padding: '0 24px' }}>
      <div className="flex items-center justify-between h-full">
        {/* LEFT SIDE */}
        <div
          className="text-[#111111] cursor-pointer"
          style={{ fontFamily: "'Cormorant Garamond', serif", fontWeight: 700, fontSize: '22px', letterSpacing: '0.12em' }}
          onClick={() => setCurrentRoute('upload')}
        >
          AEGIS
        </div>

        {/* CENTER */}
        <div className="flex items-center" style={{ gap: '32px', height: '100%' }}>
          <button
            onClick={() => setCurrentRoute('upload')}
            style={{
              fontFamily: "'Inter', sans-serif",
              fontWeight: 500, fontSize: '13px',
              color: (currentRoute === 'upload' || currentRoute === 'hub') ? '#111111' : '#9ca3af',
              borderBottom: (currentRoute === 'upload' || currentRoute === 'hub') ? '2px solid #111111' : 'none',
              paddingBottom: (currentRoute === 'upload' || currentRoute === 'hub') ? '2px' : '0'
            }}
            className="h-full flex items-center transition-colors hover:text-[#111111]"
          >
            Forensic
          </button>
          <button
            onClick={() => setCurrentRoute('database')}
            style={{
              fontFamily: "'Inter', sans-serif",
              fontWeight: 500, fontSize: '13px',
              color: currentRoute === 'database' ? '#111111' : '#9ca3af',
              borderBottom: currentRoute === 'database' ? '2px solid #111111' : 'none',
              paddingBottom: currentRoute === 'database' ? '2px' : '0'
            }}
            className="h-full flex items-center transition-colors hover:text-[#111111]"
          >
            Database
          </button>
        </div>

        {/* RIGHT SIDE */}
        <div className="flex gap-6 items-center">
          {/* Applicant Name */}
          {applicantName && (
            <div className="flex items-center gap-2" style={{ fontFamily: "'Inter', sans-serif", fontSize: '12px', color: '#555' }}>
              <span style={{ fontWeight: 400, color: '#9ca3af' }}>Applicant: </span>
              <span style={{ fontWeight: 600, color: '#111' }}>{applicantName}</span>
              {onViewHistory && (
                <button
                  onClick={onViewHistory}
                  className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-white hover:bg-gray-100 border border-[#e5e7eb] rounded transition-colors text-[#111] cursor-pointer"
                >
                  History
                </button>
              )}
            </div>
          )}

          {/* Bank Info */}
          <div className="flex flex-col items-end justify-center">
            <div style={{ fontFamily: "'Inter', sans-serif", fontWeight: 600, fontSize: '11px', color: '#111111', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              CANARA BANK
            </div>
            <div style={{ fontFamily: "'Inter', sans-serif", fontWeight: 400, fontSize: '10px', color: '#9ca3af' }}>
              Fraud Detection Division
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Header;
