"""
api/routers/health.py (v2 -- unchanged from v1)
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_db
from db.models import Dossier
from inference import load_engine
from api.schemas import HealthOut, ModelInfoOut

router = APIRouter()


@router.get("/health", response_model=HealthOut, summary="Liveness check")
def health(db: Session = Depends(get_db)):
    n_dossiers = db.query(Dossier).count()
    model_loaded = True
    try:
        _ = load_engine()
    except Exception:
        model_loaded = False
    return HealthOut(status="ok", model_loaded=model_loaded, db_dossiers=n_dossiers)


@router.get("/model-info", response_model=ModelInfoOut, summary="Model metrics")
def model_info():
    from pathlib import Path
    import json
    results_path = Path(__file__).parent.parent.parent / ".." / "checkpoints" / "test_results.json"
    if results_path.exists():
        data = json.loads(results_path.read_text())
        return ModelInfoOut(
            checkpoint="best_model.pt",
            auc=data.get("auc", 0.0),
            precision=data.get("precision", 0.0),
            recall=data.get("recall", 0.0),
            f1=data.get("f1", 0.0),
            threshold_used=data.get("threshold_used", 0.6),
            mean_mask_iou=data.get("mean_mask_iou", 0.0),
            per_tier_recall=data.get("per_tier_recall", {}),
            n_test_samples=data.get("n_samples", 0),
            architecture="AegisForgeryNet (EfficientNet-B0 + SRM dual-stream)",
        )
    return ModelInfoOut(
        checkpoint="best_model.pt",
        auc=0.0, precision=0.0, recall=0.0, f1=0.0,
        threshold_used=0.6, mean_mask_iou=0.0,
        per_tier_recall={}, n_test_samples=0,
        architecture="AegisForgeryNet (EfficientNet-B0 + SRM dual-stream)",
    )
