import { FileKey, Clock } from 'lucide-react';

const AuditBadge = ({ result }) => {
  if (!result) return null;

  return (
    <div className="audit-badge">
      <div className="audit-field">
        <span className="audit-label">Document Fingerprint (SHA-256)</span>
        <span className="audit-value" style={{ color: 'var(--accent-teal)' }}>
          <FileKey size={14} style={{ display: 'inline', marginRight: '4px', marginBottom: '-2px' }}/>
          {result.digital_fingerprint}
        </span>
      </div>
      <div className="audit-field">
        <span className="audit-label">Audit Log ID</span>
        <span className="audit-value">{result.audit_log_id}</span>
      </div>
      <div className="audit-field">
        <span className="audit-label">Processed At</span>
        <span className="audit-value">
          <Clock size={14} style={{ display: 'inline', marginRight: '4px', marginBottom: '-2px' }}/>
          {new Date(result.processed_at).toLocaleString()}
        </span>
      </div>
      <div className="audit-field">
        <span className="audit-label">Analysis Time</span>
        <span className="audit-value">{result.analysis_time_ms} ms</span>
      </div>
    </div>
  );
};

export default AuditBadge;
