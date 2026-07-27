import { FileKey, Clock, Database } from 'lucide-react';
import { motion } from 'framer-motion';

const AuditLogTable = ({ result }) => {
  if (!result) return null;

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="panel-glass p-6 mt-6 overflow-hidden relative"
    >
      <div className="absolute top-0 left-0 w-1 h-full bg-verification-green" />
      
      <div className="flex items-center gap-2 mb-6 text-gray-400">
        <Database size={18} />
        <h3 className="text-sm font-semibold tracking-wider uppercase">Cryptographic Audit Log</h3>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div>
          <div className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-1">SHA-256 Fingerprint</div>
          <div className="font-mono text-sm text-action-orange break-all flex items-center gap-2">
            <FileKey size={14} className="shrink-0" />
            {result.digital_fingerprint}
          </div>
        </div>
        
        <div>
          <div className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-1">Log ID Reference</div>
          <div className="font-mono text-sm text-gray-300 break-all">{result.audit_log_id}</div>
        </div>

        <div>
          <div className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-1">Execution Timestamp</div>
          <div className="text-sm text-gray-300 flex items-center gap-2">
            <Clock size={14} className="shrink-0" />
            {new Date(result.processed_at).toLocaleString()}
          </div>
        </div>

        <div>
          <div className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-1">Processing Time</div>
          <div className="text-sm text-white font-bold">{result.analysis_time_ms} ms</div>
        </div>
      </div>
    </motion.div>
  );
};

export default AuditLogTable;
