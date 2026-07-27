import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const LAYER_CONFIG = [
  { id: 'Document Ingestion & Classification', desc: 'OCR extraction, multilingual handling, document type identification' },
  { id: 'Visual Forensics', desc: 'Error Level Analysis, metadata audit, font consistency, template matching' },
  { id: 'Mathematical Integrity', desc: "Arithmetic cross-validation, Benford's Law analysis, stamp duty verification" },
  { id: 'Semantic & Legal Integrity', desc: 'Entity consistency, date logic, legal clause validity via LLM' },
  { id: 'Behavioural Profile Intelligence', desc: 'Financial DNA baseline comparison, income spike detection, fraud ring mapping' },
  { id: 'Anomaly Scoring', desc: 'ML-weighted unified risk score combining all layer signals' },
  { id: 'Explainability & Underwriter Co-Pilot', desc: 'Plain-language fraud summary, heatmap, entity graph, decision interface' },
  { id: 'Audit & Compliance', desc: 'Tamper-proof logs, cryptographic fingerprinting, RBI supervisory export' }
];

const TypewriterText = ({ text }) => {
  const [displayedText, setDisplayedText] = useState('');
  
  useEffect(() => {
    let index = 0;
    setDisplayedText('');
    const timer = setInterval(() => {
      if (index < text.length) {
        setDisplayedText((prev) => prev + text.charAt(index));
        index++;
      } else {
        clearInterval(timer);
      }
    }, 15);
    return () => clearInterval(timer);
  }, [text]);

  return <span>{displayedText}</span>;
};

const PipelineDashboard = ({ backendData }) => {
  const [activeStep, setActiveStep] = useState(-1);
  const [expandedLayer, setExpandedLayer] = useState(null);

  useEffect(() => {
    if (backendData) {
      setActiveStep(8);
    } else {
      setActiveStep(-1);
    }
  }, [backendData]);

  const toggleExpand = (idx) => {
    setExpandedLayer(expandedLayer === idx ? null : idx);
  };

  return (
    <div className="panel-glass p-6 w-full relative z-10 rounded-none">
      <h2 className="text-sm font-bold uppercase tracking-widest text-slate-300 mb-6 flex items-center gap-2 border-b border-white/5 pb-4">
        Aegis Sequential Forensic Pipeline
      </h2>

      <div className="flex flex-col gap-3">
        <AnimatePresence>
          {LAYER_CONFIG.map((layer, idx) => {
            let state = 'Pending';
            if (activeStep === idx) state = 'Checking';
            else if (activeStep > idx && backendData) state = 'Result';

            const layerResult = backendData?.layers?.find(l => l.layer_name === layer.id);
            const isFlagged = layerResult?.status === 'Flagged';
            const isSkipped = layerResult?.status === 'Skipped';
            
            let boxClass = "border-[#e5e7eb] bg-[#f9fafb] text-[#6b7280]";
            let statusText = "Pending";
            let textColor = "text-[#6b7280]";

            if (state === 'Checking') {
              boxClass = "border-[#3b82f6]/30 bg-[#3b82f6]/10 text-[#111111]";
              statusText = "Validating...";
              textColor = "text-[#3b82f6]";
            } else if (state === 'Result' && layerResult) {
              if (isFlagged) {
                boxClass = "border-[#dc2626]/50 bg-[#dc2626]/10 text-[#111111]";
                statusText = "Flagged";
                textColor = "text-[#dc2626]";
              } else if (isSkipped) {
                boxClass = "border-[#e5e7eb] bg-[#f9fafb] text-[#6b7280]";
                statusText = "Skipped";
                textColor = "text-[#6b7280]";
              } else {
                boxClass = "border-[#10b981]/30 bg-[#10b981]/5 text-[#111111]";
                statusText = "Passed";
                textColor = "text-[#10b981]";
              }
            }

            const isExpanded = expandedLayer === idx;

            return (
              <motion.div 
                key={layer.id}
                layout
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: idx * 0.05 }}
                className={`relative overflow-hidden rounded-none border transition-all duration-300 ${boxClass} cursor-pointer`}
                onClick={() => toggleExpand(idx)}
              >
                {state === 'Checking' && (
                  <motion.div 
                    className="absolute inset-0 bg-blue-400/10 pointer-events-none"
                    animate={{ opacity: [0, 0.5, 0] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                  />
                )}

                <div className="px-4 py-3 flex items-center justify-between relative z-10">
                  <div className="flex items-center gap-4">
                    <div className="flex flex-col">
                      <span className="font-semibold text-sm tracking-wide">{layer.id}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <div className={`text-[10px] uppercase font-bold tracking-widest ${state === 'Checking' ? 'animate-pulse text-blue-400' : textColor}`}>
                      {statusText}
                    </div>
                    <motion.div
                      animate={{ rotate: isExpanded ? 180 : 0 }}
                      className="text-slate-500 text-xs"
                    >
                      ▼
                    </motion.div>
                  </div>
                </div>

                <AnimatePresence>
                  {isExpanded && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="border-t border-[#e5e7eb] bg-[#f9fafb] text-[#374151]"
                    >
                      <div className="p-4 text-sm relative">
                        <div className="font-semibold mb-2 text-[#111111]">Underwriter Explanation:</div>
                        {layerResult ? (
                          <div className={isFlagged ? 'text-[#dc2626] pr-32' : 'text-[#10b981]'}>
                            <TypewriterText text={layerResult.human_explanation} />
                          </div>
                        ) : (
                          <div className="italic opacity-50">Analysis pending or unavailable.</div>
                        )}
                        
                        {/* Human-in-the-Loop Override Button */}
                        {isFlagged && (
                          <div className="absolute top-4 right-4">
                             <button className="bg-[#111111] hover:bg-[#374151] text-white text-xs font-bold uppercase tracking-widest px-3 py-2 rounded-none border border-[#e5e7eb] transition-colors flex items-center gap-2">
                               OVERRIDE
                             </button>
                          </div>
                        )}

                        <div className="mt-4 pt-3 border-t border-[#e5e7eb] text-xs text-[#6b7280] flex items-start gap-2">
                          <span>{layer.desc}</span>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
};

export default PipelineDashboard;
