"""
api/routers/stats.py (v2 -- unchanged from v1)
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_db
from db.models import Dossier

router = APIRouter()

_events = []


def append_event(message: str, level: str = "INFO"):
    _events.insert(0, {"time": datetime.utcnow().isoformat(), "message": message, "level": level})
    if len(_events) > 500:
        _events.pop()


@router.get("/stats", summary="Live statistics")
def stats(db: Session = Depends(get_db)):
    total = db.query(Dossier).count()
    fraudulent = db.query(Dossier).filter(Dossier.fraudulent == True).count()
    safe = total - fraudulent
    recent = db.query(Dossier).filter(
        Dossier.analyzed_at >= datetime.utcnow() - timedelta(hours=24)
    ).count()
    return {
        "total_dossiers": total, "fraudulent": fraudulent, "safe": safe,
        "analyzed_24h": recent, "accuracy": round((safe / total * 100) if total else 0, 1),
    }


@router.get("/adversarial_stats", summary="Model performance stats")
def adversarial_stats():
    from pathlib import Path
    import json
    results_path = Path(__file__).parent.parent.parent / ".." / "checkpoints" / "test_results.json"
    if results_path.exists():
        data = json.loads(results_path.read_text())
        return {
            "auc": data.get("auc", 0.0), "f1": data.get("f1", 0.0),
            "precision": data.get("precision", 0.0), "recall": data.get("recall", 0.0),
            "threshold": data.get("threshold_used", 0.6),
            "mask_iou": data.get("mean_mask_iou", 0.0),
            "per_tier_recall": data.get("per_tier_recall", {}),
        }
    return {"auc": 0.0, "f1": 0.0, "precision": 0.0, "recall": 0.0,
            "threshold": 0.6, "mask_iou": 0.0, "per_tier_recall": {}}


@router.get("/system/feed", summary="Live event feed")
def system_feed():
    return _events[:50]
