import React from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

const ApplicationTimeline = ({ backendData }) => {
  const extractedName = backendData?.applicant_name || "Applicant";
  const docType = backendData?.document_type || "Income Dossier";
  
  const historyData = backendData?.historical_income || [
    { name: "2023", income: 0 },
    { name: "2024", income: 0 },
    { name: "2025", income: 0 },
    { name: "2026", income: 0 }
  ];

  const deltaText = backendData?.all_flags?.includes('semantic_drift') 
    ? "WARNING: Income spike detected. Trajectory deviates significantly from historical baseline."
    : "Income increased by 20% compared to previous submission. Trajectory is within normal limits.";

  return (
    <div className="w-[300px] bg-white border-r border-slate-200 h-full flex flex-col fixed left-0 top-0 pt-6 z-10 overflow-y-auto hidden lg:flex shadow-sm">
      <div className="px-6 mb-6">
        <h2 className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-6">Application Timeline</h2>
        
        {/* Applicant Context */}
        <div className="flex items-start gap-4 mb-8 pb-6 border-b border-slate-100">
          <div className="w-12 h-12 bg-slate-100 rounded-full flex items-center justify-center text-slate-500 font-bold text-lg">
             {extractedName.charAt(0)}
          </div>
          <div>
            <div className="font-bold text-brand-navy tracking-wide text-sm">{extractedName}</div>
            <div className="text-xs text-brand-gray mt-1 uppercase">ID: AP-992-811</div>
            <div className={`text-[10px] font-bold uppercase tracking-widest mt-2 px-2 py-0.5 inline-block rounded ${backendData?.overall_risk_score >= 50 ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-600'}`}>
              Risk: {backendData?.risk_band || 'PENDING'}
            </div>
          </div>
        </div>

        {/* Timeline Events */}
        <div className="space-y-6">
           <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-4">Verification Events</h3>
           
           <div className="relative pl-4 border-l-2 border-slate-200 space-y-6">
             <div className="relative">
               <div className="absolute -left-[21px] top-1 w-3 h-3 rounded-full bg-emerald-500 border-2 border-white"></div>
               <div className="text-xs font-bold text-brand-navy">Aadhaar Authentication</div>
               <div className="text-[10px] text-slate-400 mt-1">Matched with UIDAI DB</div>
             </div>
             
             <div className="relative">
               <div className="absolute -left-[21px] top-1 w-3 h-3 rounded-full bg-emerald-500 border-2 border-white"></div>
               <div className="text-xs font-bold text-brand-navy">PAN Verification</div>
               <div className="text-[10px] text-slate-400 mt-1">Matched with NSDL</div>
             </div>
             
             <div className="relative">
               <div className="absolute -left-[21px] top-1 w-3 h-3 rounded-full bg-blue-500 border-2 border-white"></div>
               <div className="text-xs font-bold text-brand-navy">Current Submission</div>
               <div className="text-[10px] text-slate-400 mt-1">{docType} Processed</div>
             </div>
           </div>
        </div>

        {/* Systematic Graph (Delta View) */}
        <div className="mt-10 pt-6 border-t border-slate-100">
           <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-4">Historical Income Delta</h3>
           <div className="h-32 w-full -ml-4">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={historyData}>
                  <XAxis dataKey="name" tick={{fontSize: 10, fill: '#64748B'}} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{fontSize: '12px', borderRadius: '4px', border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.1)'}} />
                  <Line type="monotone" dataKey="income" stroke="#2563EB" strokeWidth={2} dot={{r: 3, fill: '#2563EB'}} />
                </LineChart>
              </ResponsiveContainer>
           </div>
           
           <div className={`text-xs mt-4 p-3 rounded border-l-2 ${backendData?.all_flags?.includes('semantic_drift') ? 'bg-red-50 border-red-500 text-red-700' : 'bg-slate-50 border-blue-500 text-slate-600'}`}>
             <span className="font-bold">Delta View:</span> {deltaText}
           </div>
        </div>
      </div>
    </div>
  );
};

export default ApplicationTimeline;
