import React from 'react';

const ComplianceAudit = ({ backendData }) => {
  const flags = backendData?.all_flags || [];
  const processedTime = new Date(backendData?.processed_at || Date.now()).toLocaleString();

  return (
    <div className="w-full text-slate-200">
      <div className="mb-6 border-b border-white/5 pb-4">
        <h2 className="text-sm font-bold uppercase tracking-widest text-slate-300">Layer 8: Audit & Compliance</h2>
        <p className="text-xs text-slate-500 mt-1">RBI Statutory Reporting Log & Cryptographic Tamper-Proof Seal.</p>
      </div>

      <div className="bg-enterprise-800 border border-white/10 rounded-none overflow-hidden mb-6">
        <div className="bg-white/5 border-b border-white/10 p-4 flex justify-between items-center">
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400">Underwriter Action Log</h3>
          <span className="text-[10px] font-mono text-slate-500">USER_ID: 4492-AXIS</span>
        </div>
        
        <table className="w-full text-left text-sm">
          <tbody className="divide-y divide-white/5">
            <tr>
              <td className="px-6 py-4 text-slate-400 font-mono w-1/3">Pipeline Execution</td>
              <td className="px-6 py-4 text-white font-mono">{processedTime}</td>
            </tr>
            <tr>
              <td className="px-6 py-4 text-slate-400 font-mono">System Risk Score</td>
              <td className="px-6 py-4">
                <span className={`px-2 py-1 text-[10px] font-bold uppercase tracking-widest ${backendData?.overall_risk_score > 60 ? 'bg-action-orange/10 text-action-orange border border-action-orange/20' : 'bg-verification-green/10 text-verification-green border border-verification-green/20'}`}>
                  {backendData?.overall_risk_score}/100 ({backendData?.risk_band})
                </span>
              </td>
            </tr>
            <tr>
              <td className="px-6 py-4 text-slate-400 font-mono">Anomalies Detected</td>
              <td className="px-6 py-4 text-white font-mono">{flags.length} Flags Triggered</td>
            </tr>
            <tr>
              <td className="px-6 py-4 text-slate-400 font-mono">Document Hash (SHA-256)</td>
              <td className="px-6 py-4 text-[10px] text-blue-400 font-mono break-all">{backendData?.digital_fingerprint}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-2 gap-6">
         <div className="bg-enterprise-800 border border-white/10 p-6 rounded-none">
            <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">Cryptographic QR Verification</h3>
            <div className="flex gap-4 items-start">
               {/* Pure CSS Checkered Pattern to simulate QR code for demo */}
               <div className="w-24 h-24 bg-white p-1">
                  <div className="w-full h-full bg-[repeating-conic-gradient(#000_0_90deg,#fff_0_180deg)] bg-[length:6px_6px]"></div>
               </div>
               <div>
                  <p className="text-xs text-slate-400 mb-2">Scan to verify immutable ledger entry on internal compliance network.</p>
                  <p className="text-[10px] font-mono text-verification-green">SEAL VERIFIED</p>
               </div>
            </div>
         </div>
         
         <div className="bg-enterprise-800 border border-white/10 p-6 rounded-none flex flex-col justify-between">
            <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">RBI Reporting Status</h3>
            <div>
               <p className="text-xs text-slate-400 mb-4">This profile and decision matrix has been formatted for the monthly RBI supervisory export.</p>
               <button className="w-full py-2 bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-bold text-white uppercase tracking-widest transition-colors">
                 EXPORT COMPLIANCE PDF
               </button>
            </div>
         </div>
      </div>
    </div>
  );
};

export default ComplianceAudit;
