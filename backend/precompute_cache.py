"""Pre-compute analysis cache for demo dossiers."""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from pathlib import Path
from pipeline import analyze_dossier

def precompute(dossier_path: str):
    dp = Path(dossier_path)
    print(f"Analyzing {dp.name}...")
    result = analyze_dossier(str(dp))
    
    from db.crud import upsert_dossier
    from api.routers.dossiers import _to_out
    from db import SessionLocal
    
    db = SessionLocal()
    try:
        db_record = upsert_dossier(db, result)
        out = _to_out(db_record)
        out_dict = out.model_dump()
        
        cache_file = dp / "analysis_cache.json"
        cache_file.write_text(json.dumps(out_dict, indent=2, default=str), encoding="utf-8")
        print(f"  -> Cached to {cache_file} ({cache_file.stat().st_size} bytes)")
        print(f"  -> Risk: {out_dict['risk_score']}, Docs: {out_dict['n_documents']}")
    finally:
        db.close()

if __name__ == "__main__":
    paths = sys.argv[1:] or [
        r"D:\Programs\aegis-dataset\outputs\demo_showcase\demo_dossier_A",
        r"D:\Programs\aegis-dataset\outputs\demo_showcase\demo_dossier_B",
    ]
    for p in paths:
        precompute(p)
    print("Done.")
