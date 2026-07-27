import { motion } from 'framer-motion';

const DocumentViewer = ({ fileUrl, isAnalyzing }) => {
  return (
    <div className="panel-glass h-full flex flex-col relative overflow-hidden">
      <div className="px-6 py-4 border-b border-[#e5e7eb] bg-[#f9fafb]">
        <h3 className="text-xs font-bold tracking-widest text-[#374151] uppercase">
          Live Document Stream
        </h3>
      </div>
      
      <div className="flex-1 bg-white relative overflow-hidden flex items-center justify-center p-2">
        {fileUrl ? (
          <div className="w-full h-full relative">
            <iframe 
              src={`${fileUrl}#toolbar=0`} 
              className="w-full h-full rounded bg-white relative z-0"
              title="Document Preview"
            />
            
            {/* Scanner Animation Overlay */}
            {isAnalyzing && (
              <motion.div 
                className="absolute top-0 left-0 w-full h-[2px] bg-verification-green shadow-[0_0_10px_rgba(16,185,129,0.8)] pointer-events-none"
                animate={{ top: ['0%', '100%', '0%'] }}
                transition={{ duration: 4, ease: 'linear', repeat: Infinity }}
              />
            )}
          </div>
        ) : (
          <div className="text-slate-500 text-sm italic">Awaiting document payload...</div>
        )}
      </div>
    </div>
  );
};

export default DocumentViewer;
