import { AlertTriangle, CheckCircle, ShieldAlert } from 'lucide-react';

const RiskScoreGauge = ({ score, riskBand }) => {
  const getIcon = () => {
    if (riskBand === 'HIGH') return <ShieldAlert size={32} />;
    if (riskBand === 'MEDIUM') return <AlertTriangle size={32} />;
    return <CheckCircle size={32} />;
  };

  const getSubtext = () => {
    if (riskBand === 'HIGH') return "Critical Anomalies Detected";
    if (riskBand === 'MEDIUM') return "Secondary Review Required";
    return "Standard Processing Approved";
  };

  return (
    <div className="panel" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div className="panel-header">Overall Risk Assessment</div>
      <div className="gauge-container" style={{ flex: 1 }}>
        <div style={{ color: `var(--${riskBand === 'HIGH' ? 'alert-red' : riskBand === 'MEDIUM' ? 'warn-amber' : 'success-green'})` }}>
          {getIcon()}
        </div>
        <div className={`score-display score-${riskBand}`}>
          {score}
        </div>
        <div className={`risk-band score-${riskBand}`}>
          {riskBand} RISK
        </div>
        <div style={{ marginTop: '1rem', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          {getSubtext()}
        </div>
      </div>
    </div>
  );
};

export default RiskScoreGauge;
