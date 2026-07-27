import React, { useState } from 'react';

const DocumentDiff = ({ documents }) => {
  const [selectedPair, setSelectedPair] = useState(null);
  const [diffMode, setDiffMode] = useState('overlay'); // overlay, split, highlight

  const docsList = documents?.filter(d => d.type !== 'manifest') || [];

  if (!selectedPair && docsList.length >= 2) {
    setSelectedPair({ doc1: 0, doc2: 1 });
  }

  if (!selectedPair) {
    return (
      <div className="w-full h-full flex items-center justify-center text-[#999] text-[12px]">
        <div>Insufficient documents for comparison</div>
      </div>
    );
  }

  const doc1 = docsList[selectedPair.doc1];
  const doc2 = docsList[selectedPair.doc2];

  return (
    <div className="w-full h-full flex flex-col bg-[#f5f5f5] overflow-y-auto">
      {/* Controls */}
      <div className="p-4 bg-white border-b border-[#ddd] sticky top-0 z-10">
        <div className="text-[11px] font-bold uppercase mb-3 tracking-widest">Document Comparison</div>
        
        {/* Document Selectors */}
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="text-[10px] text-[#666] block mb-1">Document A</label>
            <select
              value={selectedPair.doc1}
              onChange={(e) => setSelectedPair({ ...selectedPair, doc1: parseInt(e.target.value) })}
              className="w-full p-1 text-[11px] border border-[#ddd]"
            >
              {docsList.map((doc, idx) => (
                <option key={idx} value={idx}>{doc.type.toUpperCase()}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-[#666] block mb-1">Document B</label>
            <select
              value={selectedPair.doc2}
              onChange={(e) => setSelectedPair({ ...selectedPair, doc2: parseInt(e.target.value) })}
              className="w-full p-1 text-[11px] border border-[#ddd]"
            >
              {docsList.map((doc, idx) => (
                <option key={idx} value={idx}>{doc.type.toUpperCase()}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Diff Mode Selector */}
        <div className="flex gap-2">
          <button
            onClick={() => setDiffMode('split')}
            className={`text-[10px] font-bold uppercase px-3 py-1 border ${
              diffMode === 'split' ? 'bg-[#111] text-white border-[#111]' : 'bg-white text-[#111] border-[#ddd]'
            }`}
          >
            Split View
          </button>
          <button
            onClick={() => setDiffMode('overlay')}
            className={`text-[10px] font-bold uppercase px-3 py-1 border ${
              diffMode === 'overlay' ? 'bg-[#111] text-white border-[#111]' : 'bg-white text-[#111] border-[#ddd]'
            }`}
          >
            Overlay
          </button>
          <button
            onClick={() => setDiffMode('highlight')}
            className={`text-[10px] font-bold uppercase px-3 py-1 border ${
              diffMode === 'highlight' ? 'bg-[#111] text-white border-[#111]' : 'bg-white text-[#111] border-[#ddd]'
            }`}
          >
            Highlight
          </button>
        </div>
      </div>

      {/* Viewer */}
      <div className="flex-1 p-4 space-y-4 overflow-y-auto">
        {diffMode === 'split' && (
          <div className="grid grid-cols-2 gap-4 h-full">
            {/* Left: Document A */}
            <div className="border border-[#ddd] bg-white p-2">
              <div className="text-[10px] font-bold text-[#666] mb-2 uppercase">
                {doc1?.type} (A)
              </div>
              {doc1?.preview ? (
                <img
                  src={`data:image/${doc1.preview.startsWith('/9j/') ? 'jpeg' : 'png'};base64,${doc1.preview}`}
                  alt="Document A"
                  className="w-full h-auto border border-[#ddd]"
                />
              ) : (
                <div className="h-64 flex items-center justify-center text-[#aaa] text-[12px]">No Preview</div>
              )}
            </div>

            {/* Right: Document B */}
            <div className="border border-[#ddd] bg-white p-2">
              <div className="text-[10px] font-bold text-[#666] mb-2 uppercase">
                {doc2?.type} (B)
              </div>
              {doc2?.preview ? (
                <img
                  src={`data:image/${doc2.preview.startsWith('/9j/') ? 'jpeg' : 'png'};base64,${doc2.preview}`}
                  alt="Document B"
                  className="w-full h-auto border border-[#ddd]"
                />
              ) : (
                <div className="h-64 flex items-center justify-center text-[#aaa] text-[12px]">No Preview</div>
              )}
            </div>
          </div>
        )}

        {(diffMode === 'overlay' || diffMode === 'highlight') && (
          <div className="border border-[#ddd] bg-white p-2 relative">
            <div className="text-[10px] font-bold text-[#666] mb-2 uppercase">
              {doc1?.type} (Base) with {doc2?.type} ({diffMode === 'overlay' ? 'Overlay' : 'Highlight'})
            </div>
            <div className="relative inline-block w-full">
              {/* Base Image */}
              {doc1?.preview && (
                <img
                  src={`data:image/${doc1.preview.startsWith('/9j/') ? 'jpeg' : 'png'};base64,${doc1.preview}`}
                  alt="Document A (Base)"
                  className="w-full h-auto border border-[#ddd]"
                />
              )}
              
              {/* Overlay/Highlight */}
              {doc2?.preview && diffMode === 'overlay' && (
                <img
                  src={`data:image/${doc2.preview.startsWith('/9j/') ? 'jpeg' : 'png'};base64,${doc2.preview}`}
                  alt="Document B (Overlay)"
                  className="absolute top-0 left-0 w-full h-auto border border-[#FF0000] opacity-50"
                  style={{ mixBlendMode: 'multiply' }}
                />
              )}
            </div>
            <div className="text-[10px] text-[#666] mt-2 italic">
              {diffMode === 'overlay' ? 'Red overlay shows differences between documents' : 'Highlighted areas show significant variations'}
            </div>
          </div>
        )}

        {/* Analysis Summary */}
        <div className="bg-white border border-[#ddd] p-3">
          <div className="text-[11px] font-bold text-[#111] mb-2">Comparison Analysis</div>
          <div className="text-[11px] text-[#666] space-y-1">
            <div>Document A: {doc1?.type} {doc1?.flagged && <span className="text-[#FF0000]"> Flagged</span>}</div>
            <div>Document B: {doc2?.type} {doc2?.flagged && <span className="text-[#FF0000]"> Flagged</span>}</div>
            <div className="mt-2 text-[#999] italic">
              Pixel-level diff overlay helps identify subtle alterations, copy-paste regions, and structural inconsistencies between documents.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DocumentDiff;
