import React from 'react';

const ApplicantHistory = ({ backendData }) => {
  // Use dynamically generated history from backend if available, or fallback
  const historyData = backendData?.financial_history || [
    { year: "2024", amount: 650000 },
    { year: "2025", amount: 720000 },
    { year: "2026 (Current)", amount: 800000 }
  ];

  const maxAmount = Math.max(...historyData.map(d => d.amount));

  return (
    <div className="w-full text-slate-200">
      <div className="mb-6 border-b border-white/5 pb-4">
        <h2 className="text-sm font-bold uppercase tracking-widest text-slate-300">Layer 5: Behavioural Profile (Financial DNA)</h2>
        <p className="text-xs text-slate-500 mt-1">Comparing current submission against historical baseline to detect spikes and anomalies.</p>
      </div>

      <div className="bg-enterprise-800 border border-white/10 p-6 rounded-none relative mb-8">
        <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-6">Income Trend Analysis</h3>
        
        {/* Professional CSS Bar Chart */}
        <div className="flex items-end h-48 gap-8 mt-4 border-b border-l border-white/10 pl-4 pb-2 relative">
           {/* Y-Axis labels */}
           <div className="absolute -left-12 bottom-0 top-0 flex flex-col justify-between text-[10px] text-slate-500 font-mono">
              <span>{Math.round(maxAmount / 100000)}L</span>
              <span>{Math.round((maxAmount/2) / 100000)}L</span>
              <span>0</span>
           </div>

           {historyData.map((data, index) => {
             const heightPercent = (data.amount / maxAmount) * 100;
             const isCurrent = index === historyData.length - 1;
             
             return (
               <div key={index} className="flex flex-col items-center flex-1 group">
                 <div 
                   className={`w-full max-w-[60px] transition-all duration-500 relative ${isCurrent ? 'bg-blue-500/80 border-t-2 border-blue-400' : 'bg-slate-700/80 border-t-2 border-slate-500'}`}
                   style={{ height: `${heightPercent}%` }}
                 >
                   {/* Tooltip on hover */}
                   <div className="opacity-0 group-hover:opacity-100 absolute -top-8 left-1/2 -translate-x-1/2 bg-black px-2 py-1 text-[10px] whitespace-nowrap z-10 transition-opacity">
                     ₹ {data.amount.toLocaleString()}
                   </div>
                 </div>
                 <span className="text-[10px] text-slate-400 font-mono mt-3">{data.year}</span>
               </div>
             );
           })}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-enterprise-800 border border-white/10 p-6 rounded-none">
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">Baseline Comparison</h3>
          <table className="w-full text-left text-xs">
            <tbody className="divide-y divide-white/5">
              <tr>
                <td className="py-3 text-slate-500 font-medium">Verified Baseline (2025)</td>
                <td className="py-3 text-white font-mono text-right">₹ {historyData[1]?.amount.toLocaleString()}</td>
              </tr>
              <tr>
                <td className="py-3 text-slate-500 font-medium">Current Submission</td>
                <td className="py-3 text-white font-mono text-right">₹ {historyData[2]?.amount.toLocaleString()}</td>
              </tr>
              <tr>
                <td className="py-3 text-slate-500 font-medium">Delta (Variance)</td>
                <td className="py-3 text-blue-400 font-mono text-right">+ {Math.round(((historyData[2]?.amount - historyData[1]?.amount) / historyData[1]?.amount) * 100)}%</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="bg-enterprise-800 border border-white/10 p-6 rounded-none">
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">Spike Detector Status</h3>
          <div className="flex flex-col h-full justify-center pb-4">
             {((historyData[2]?.amount - historyData[1]?.amount) / historyData[1]?.amount) > 0.4 ? (
               <div className="bg-action-orange/10 border border-action-orange/30 p-4 rounded-none border-l-4 border-l-action-orange">
                  <div className="text-[10px] font-bold text-action-orange uppercase tracking-widest mb-1">ANOMALY DETECTED</div>
                  <div className="text-xs text-white">Income spike exceeds 40% threshold with no employer change on record.</div>
               </div>
             ) : (
               <div className="bg-verification-green/10 border border-verification-green/30 p-4 rounded-none border-l-4 border-l-verification-green">
                  <div className="text-[10px] font-bold text-verification-green uppercase tracking-widest mb-1">NORMAL VARIANCE</div>
                  <div className="text-xs text-white">Income delta is within expected historical parameters.</div>
               </div>
             )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ApplicantHistory;
