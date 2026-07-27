import React, { useState } from 'react';
import PipelineDashboard from './PipelineDashboard';

const DocumentConsistency = ({ backendData }) => {
  const [activeCrop, setActiveCrop] = useState(null);

  const diffData = backendData?.diff_data || [
    { field: "Gross Income", docA: "₹ 12,50,000", docB: "₹ 12,50,000", match: true, sourceA: "Salary_Slip_pg1.pdf", sourceB: "ITR_2025.pdf" },
    { field: "Tax Deducted", docA: "₹ 1,80,000", docB: "₹ 1,80,000", match: true, sourceA: "Salary_Slip_pg1.pdf", sourceB: "ITR_2025.pdf" },
    { field: "Net Pay", docA: "₹ 10,70,000", docB: "₹ 14,70,000", match: false, sourceA: "Salary_Slip_pg1.pdf", sourceB: "ITR_2025.pdf" },
    { field: "Employer Name", docA: "Acme Corp", docB: "Acme Corporation", match: true, sourceA: "Salary_Slip_pg1.pdf", sourceB: "ITR_2025.pdf" },
  ];

  return (
    <div className="w-full flex flex-col gap-6">
      <div className="bg-enterprise-800 border border-white/5 p-6 rounded-none">
        <h2 className="text-sm font-bold uppercase tracking-widest text-slate-300 mb-6 border-b border-white/5 pb-4">
          Document Reconciliation (Diff Grid)
        </h2>
        
        <div className="border border-white/10 rounded-none">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-white/5 text-xs uppercase tracking-widest text-slate-400">
              <tr>
                <th className="px-4 py-3">Extracted Field</th>
                <th className="px-4 py-3 border-l border-white/5">Primary Document (Salary Slip)</th>
                <th className="px-4 py-3 border-l border-white/5">Secondary Document (ITR)</th>
                <th className="px-4 py-3 text-right border-l border-white/5">Integrity Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {diffData.map((row, idx) => (
                <tr key={idx} className={!row.match ? 'bg-action-orange/10' : ''}>
                  <td className="px-4 py-3 font-semibold">{row.field}</td>
                  
                  <td className="px-4 py-3 border-l border-white/5 cursor-pointer hover:bg-white/5" onClick={() => setActiveCrop({ val: row.docA, doc: row.sourceA })}>
                    <div className="flex justify-between items-center">
                      <span className="font-mono">{row.docA}</span>
                    </div>
                  </td>
                  
                  <td className="px-4 py-3 border-l border-white/5 cursor-pointer hover:bg-white/5" onClick={() => setActiveCrop({ val: row.docB, doc: row.sourceA })}>
                    <div className="flex justify-between items-center">
                      <span className={`font-mono ${!row.match ? 'text-action-orange font-bold drop-shadow-[0_0_8px_rgba(249,115,22,0.8)]' : ''}`}>
                        {row.docB}
                      </span>
                    </div>
                  </td>
                  
                  <td className="px-4 py-3 text-right border-l border-white/5 font-bold">
                    {!row.match ? (
                      <span className="text-action-orange">MISMATCH</span>
                    ) : (
                      <span className="text-verification-green">VERIFIED</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* OCR Source Viewer Mockup */}
      {activeCrop && (
        <div className="bg-enterprise-900 border border-white/10 p-6 shadow-2xl relative animate-in fade-in slide-in-from-bottom-4 rounded-none">
          <button onClick={() => setActiveCrop(null)} className="absolute top-4 right-4 text-slate-500 hover:text-white transition-colors">X</button>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">OCR Extraction Source</h3>
          <div className="text-sm mb-4 text-slate-300">
            Value: <span className="font-mono text-white bg-white/10 px-2 py-1">{activeCrop.val}</span> extracted from <span className="text-blue-400">{activeCrop.doc}</span>
          </div>
          <div className="w-full h-32 bg-black border border-white/10 flex items-center justify-center relative rounded-none">
            {/* Simulating a document crop with blurred text and highlighted value */}
            <div className="absolute inset-0 opacity-30 bg-[repeating-linear-gradient(0deg,transparent,transparent_2px,#333_2px,#333_4px)]" />
            <div className="z-10 bg-verification-green/20 border border-verification-green px-4 py-2 font-mono text-xl text-white rounded-none">
              {activeCrop.val}
            </div>
          </div>
        </div>
      )}

      {/* Legacy Pipeline Dashboard */}
      <div className="mt-4">
        <PipelineDashboard backendData={backendData} />
      </div>
    </div>
  );
};

export default DocumentConsistency;
