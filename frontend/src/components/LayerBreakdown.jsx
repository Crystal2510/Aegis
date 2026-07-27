import { CheckCircle, AlertTriangle, MinusCircle, Shield, Eye, Calculator, FileText, User, Activity, AlertOctagon } from 'lucide-react';

const LAYER_INFO = {
  layer1_ingestion: { title: "1. Document Ingestion", icon: Shield },
  layer2_visual_forensics: { title: "2. Visual Forensics", icon: Eye },
  layer3_mathematical_integrity: { title: "3. Mathematical Integrity", icon: Calculator },
  layer4_semantic_integrity: { title: "4. Semantic & Legal", icon: FileText },
  layer5_behavioural_profile: { title: "5. Profile Intelligence", icon: User },
  layer6_anomaly_scoring: { title: "6. Anomaly Scoring", icon: Activity },
  layer7_explainability: { title: "7. Underwriter Co-Pilot", icon: AlertOctagon },
  layer8_audit_compliance: { title: "8. Audit & Compliance", icon: Shield }
};

const LayerBreakdown = ({ layers }) => {
  if (!layers) return null;

  return (
    <div className="panel">
      <div className="panel-header">Pipeline Analysis Layers</div>
      <div className="layer-list">
        {Object.entries(LAYER_INFO).map(([key, info]) => {
          const layerData = layers[key];
          if (!layerData) return null;
          
          const IconComponent = info.icon;
          const isFlagged = layerData.flagged;
          const isSkipped = layerData.status === 'skipped';
          
          let statusClass = "clean";
          if (isFlagged) statusClass = "flagged";
          if (isSkipped) statusClass = "skipped";
          
          return (
            <div key={key} className={`layer-item ${statusClass}`}>
              <div className="layer-info">
                <IconComponent size={20} className="layer-icon" />
                <div className="layer-name">{info.title}</div>
              </div>
              <div className="layer-status" style={{ color: isFlagged ? 'var(--alert-red)' : isSkipped ? 'var(--text-secondary)' : 'var(--success-green)' }}>
                {isSkipped ? 'Skipped' : isFlagged ? 'Flagged' : 'Passed'}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default LayerBreakdown;
