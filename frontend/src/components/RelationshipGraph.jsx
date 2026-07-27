import React from 'react';

const RelationshipGraph = ({ backendData }) => {
  const applicantName = backendData?.llm_insights?.key_entities?.Name || "Applicant Entity";
  const riskStatus = backendData?.overall_risk_score > 60 ? "HIGH RISK" : "CLEARED";
  
  // Simulate connected nodes based on Risk
  const connections = backendData?.connections || (backendData?.overall_risk_score > 60 ? [
    { type: 'Device Hash', value: 'a8f9c2...11b', status: 'FLAGGED (Linked to 3 applications)' },
    { type: 'Employer GSTIN', value: '27AABCU9603R1ZM', status: 'CLEARED' },
    { type: 'Phone Node', value: '+91-98****1234', status: 'FLAGGED (Prepaid Burner)' }
  ] : [
    { type: 'Device Hash', value: 'e2b4d1...99c', status: 'CLEARED (Unique Device)' },
    { type: 'Employer GSTIN', value: '27AABCU9603R1ZM', status: 'CLEARED' },
    { type: 'Phone Node', value: '+91-98****5678', status: 'CLEARED' }
  ]);

  return (
    <div className="w-full text-slate-200">
      <div className="mb-6 border-b border-white/5 pb-4">
        <h2 className="text-sm font-bold uppercase tracking-widest text-slate-300">Layer 7: Fraud Network Graph</h2>
        <p className="text-xs text-slate-500 mt-1">Cross-Applicant Syndicated Fraud Ring Detection (Entity Link Analysis).</p>
      </div>

      <div className="bg-enterprise-800 border border-white/10 p-8 rounded-none relative">
        
        <div className="flex flex-col items-center justify-center py-12 relative">
           
           {/* Central Node */}
           <div className={`relative z-10 w-48 py-4 px-4 text-center border-2 bg-enterprise-900 shadow-2xl ${backendData?.overall_risk_score > 60 ? 'border-action-orange' : 'border-verification-green'}`}>
             <div className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Target Subject</div>
             <div className="font-bold text-white text-sm">{applicantName}</div>
             <div className={`text-[10px] font-bold mt-2 ${backendData?.overall_risk_score > 60 ? 'text-action-orange' : 'text-verification-green'}`}>
               [{riskStatus}]
             </div>
           </div>

           {/* Connection Lines (CSS) */}
           <div className="absolute top-[50%] left-0 right-0 h-px bg-white/10 w-full z-0"></div>
           <div className="absolute top-[20%] bottom-[20%] left-[50%] w-px bg-white/10 z-0"></div>

           {/* Peripheral Nodes Grid */}
           <div className="w-full grid grid-cols-3 gap-12 mt-16 relative z-10">
             {connections.map((conn, idx) => (
                <div key={idx} className="bg-enterprise-900 border border-white/10 p-4 text-center relative">
                   {/* Line connecting up to center */}
                   <div className="absolute -top-16 left-1/2 w-px h-16 bg-white/10"></div>
                   
                   <div className="text-[10px] uppercase tracking-widest text-slate-500 mb-1">{conn.type}</div>
                   <div className="font-mono text-white text-xs mb-3">{conn.value}</div>
                   
                   <div className={`text-[9px] uppercase tracking-widest px-2 py-1 inline-block ${
                     conn.status.includes('FLAGGED') ? 'bg-action-orange/10 text-action-orange border border-action-orange/20' : 'bg-verification-green/10 text-verification-green border border-verification-green/20'
                   }`}>
                     {conn.status}
                   </div>
                </div>
             ))}
           </div>

        </div>

      </div>
    </div>
  );
};

export default RelationshipGraph;
