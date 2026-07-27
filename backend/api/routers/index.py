"""
api/routers/index.py (v2 -- unchanged from v1)
"""

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db import get_db
from db.crud import upsert_dossier
from pipeline import analyze_dossier
from api.schemas import IndexRequest, IndexStatus

router = APIRouter()

_tasks = {}


@router.post("/dataset", response_model=IndexStatus, summary="Index all dossiers in a dataset path")
def index_dataset(body: IndexRequest, db: Session = Depends(get_db)):
    root = Path(body.dataset_path)
    if not root.exists():
        raise HTTPException(status_code=404, detail=f"Dataset path not found: {body.dataset_path}")

    dossier_dirs = sorted([d for d in root.iterdir() if d.is_dir() and d.name.startswith("dossier_")])
    if not dossier_dirs:
        raise HTTPException(status_code=422, detail=f"No dossier_XXXXXX folders found under {root}")

    task_id = str(uuid.uuid4())
    task = {"task_id": task_id, "total": len(dossier_dirs), "done": 0, "errors": 0, "running": True, "message": "Starting..."}
    _tasks[task_id] = task

    for ddir in dossier_dirs:
        try:
            result = analyze_dossier(str(ddir))
            upsert_dossier(db, result)
            task["done"] += 1
        except Exception as e:
            task["errors"] += 1
            print(f"[Index] Error indexing {ddir.name}: {e}")
        task["message"] = f"Processed {task['done']}/{task['total']} dossiers ({task['errors']} errors)"

    task["running"] = False
    task["message"] = f"Complete. {task['done']}/{task['total']} dossiers indexed ({task['errors']} errors)"

    return IndexStatus(**task)


@router.get("/status/{task_id}", response_model=IndexStatus, summary="Check indexing progress")
def index_status(task_id: str):
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return IndexStatus(**task)
