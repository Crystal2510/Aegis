import { motion, AnimatePresence } from 'framer-motion';
import DocumentConsistency from './DocumentConsistency';
import ApplicantHistory from './ApplicantHistory';
import RelationshipGraph from './RelationshipGraph';
import ComplianceAudit from './ComplianceAudit';

const DashboardMainView = ({ backendData, loading, currentView }) => {
  return (
    <div className="w-full h-full relative">
      <AnimatePresence mode="wait">
        
        {currentView === 'consistency' && (
          <motion.div 
            key="consistency"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3 }}
          >
            <DocumentConsistency backendData={backendData} />
          </motion.div>
        )}

        {currentView === 'history' && (
          <motion.div 
            key="history"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3 }}
          >
            <ApplicantHistory backendData={backendData} />
          </motion.div>
        )}

        {currentView === 'network' && (
          <motion.div 
            key="network"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3 }}
          >
            <RelationshipGraph backendData={backendData} />
          </motion.div>
        )}

        {currentView === 'compliance' && (
          <motion.div 
            key="compliance"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3 }}
            className="flex justify-center"
          >
            <div className="w-full max-w-4xl">
              <ComplianceAudit backendData={backendData} />
            </div>
          </motion.div>
        )}

      </AnimatePresence>
    </div>
  );
};

export default DashboardMainView;
