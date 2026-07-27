import { AlertTriangle, CheckCircle } from 'lucide-react';

const FlagList = ({ flags, summary }) => {
  return (
    <div className="panel" style={{ marginTop: '2rem' }}>
      <div className="panel-header">Underwriter Explanations</div>
      <div style={{ marginBottom: '1.5rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
        {summary}
      </div>
      
      {flags && flags.length > 0 ? (
        <div className="flag-list">
          {flags.map((flag, idx) => (
            <div key={idx} className="flag-item">
              <AlertTriangle size={20} className="flag-icon" />
              <div className="flag-text">{flag}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="no-flags">
          <CheckCircle size={24} />
          No anomalies detected requiring manual review.
        </div>
      )}
    </div>
  );
};

export default FlagList;
