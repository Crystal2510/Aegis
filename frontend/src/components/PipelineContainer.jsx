import { motion } from 'framer-motion';
import { 
  ShieldCheck, AlertTriangle, Fingerprint, 
  FileSearch, Calculator, Scale, Activity, Lock 
} from 'lucide-react';
import { useEffect, useState } from 'react';

const LAYER_INFO = [
  { id: 'layer1_ingestion', title: 'Validating Format & Signatures', icon: Fingerprint },
  { id: 'layer2_visual_forensics', title: 'Running Visual ELA Forensics', icon: FileSearch },
  { id: 'layer3_mathematical_integrity', title: 'Validating Arithmetic Integrity', icon: Calculator },
  { id: 'layer4_semantic_integrity', title: 'Cross-Checking Legal Semantics', icon: Scale },
  { id: 'layer5_behavioural_profile', title: 'Querying Financial DNA Profile', icon: Activity },
  { id: 'layer6_anomaly_scoring', title: 'Aggregating Risk Vectors', icon: ShieldCheck },
  { id: 'layer7_explainability', title: 'Compiling Underwriter Summary', icon: Lock },
  { id: 'layer8_audit_compliance', title: 'Writing Cryptographic Audit Log', icon: Lock }
];

const PipelineContainer = ({ layers, isAnalyzing }) => {
  const [activeStep, setActiveStep] = useState(-1);

  // Simulate pipeline progressing if analyzing
  useEffect(() => {
    if (isAnalyzing) {
      setActiveStep(0);
      const interval = setInterval(() => {
        setActiveStep(prev => (prev < 7 ? prev + 1 : prev));
      }, 400); // Progress every 400ms to simulate work
      return () => clearInterval(interval);
    } else if (layers) {
      setActiveStep(8); // All done
    } else {
      setActiveStep(-1); // Reset
    }
  }, [isAnalyzing, layers]);

  return (
    <div className="panel-glass p-6">
      <h3 className="text-sm font-semibold tracking-wider text-gray-400 mb-6 uppercase">
        Forensic Pipeline Execution
      </h3>
      
      <div className="flex flex-col gap-3">
        {LAYER_INFO.map((info, idx) => {
          const Icon = info.icon;
          const isComplete = activeStep > idx;
          const isActive = activeStep === idx;
          
          let statusColor = "text-gray-500";
          let bgColor = "bg-navy-900";
          let borderClass = "border-transparent";

          // If we have final results, color them
          if (layers && isComplete) {
            const layerData = layers[info.id];
            if (layerData?.flagged) {
              statusColor = "text-action-orange";
              borderClass = "border-action-orange";
              bgColor = "bg-action-orange/10";
            } else if (layerData?.status === 'skipped') {
              statusColor = "text-gray-500";
            } else {
              statusColor = "text-verification-green";
              borderClass = "border-verification-green";
              bgColor = "bg-verification-green/10";
            }
          } else if (isActive) {
            statusColor = "text-blue-400";
            bgColor = "bg-blue-400/10 border-blue-400/50";
          } else if (isComplete) {
             statusColor = "text-verification-green";
          }

          return (
            <motion.div 
              key={info.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.1 }}
              className={`flex items-center gap-4 p-3 rounded-lg border ${borderClass} ${bgColor} transition-colors duration-500`}
            >
              <motion.div 
                animate={isActive ? { scale: [1, 1.2, 1], rotate: [0, 180, 360] } : {}} 
                transition={{ duration: 2, repeat: isActive ? Infinity : 0 }}
              >
                <Icon className={`${statusColor} w-5 h-5`} />
              </motion.div>
              
              <div className="flex-1">
                <div className={`text-sm font-medium ${isActive ? 'text-white' : 'text-gray-300'}`}>
                  {info.title}
                </div>
              </div>
              
              <div className="text-xs uppercase font-bold tracking-wider">
                {isActive ? (
                  <span className="text-blue-400 animate-pulse">Processing</span>
                ) : isComplete && layers ? (
                  <span className={statusColor}>
                    {layers[info.id]?.flagged ? 'Flagged' : layers[info.id]?.status === 'skipped' ? 'Skipped' : 'Passed'}
                  </span>
                ) : (
                  <span className="text-gray-600">Pending</span>
                )}
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
};

export default PipelineContainer;
