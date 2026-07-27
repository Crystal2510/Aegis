"""
api/main.py (v2)

FastAPI application entry point with complete DossierOut response.

Routers and lifespan are same as v1 but all endpoints now return the
full DossierOut with math_findings, plausibility_findings, primary_evidence,
pipeline_telemetry, entity_graph, legal_timeline_checks, and fused risk scores.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from db import init_db
from inference import load_engine
from api.routers import analyze, dossiers, health, index, stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Aegis v2] Initializing database...")
    init_db()
    print("[Aegis v2] Loading model checkpoint...")
    load_engine()
    print("[Aegis v2] Ready.")
    yield


app = FastAPI(
    title="Aegis Forgery Detection API v2",
    description=(
        "Hybrid document forgery detection for home loan dossiers.\n\n"
        "**Two independent detection layers:**\n"
        "- Visual model (EfficientNet-B0 + SRM noise stream): pixel-level tampering.\n"
        "- OCR/rule layer + NLP clause analysis: content-level forgeries.\n\n"
        "v2 improvements: re-enabled name cross-doc comparisons, confidence-tracked OCR, "
        "complete fused risk score computed at analysis time, UNVERIFIED mismatch reporting, "
        "and NLP clause analysis for rent agreements, appointment letters, and ITR schedules."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_masks_dir = Path(__file__).parent.parent / "masks"
_masks_dir.mkdir(exist_ok=True)
app.mount("/masks", StaticFiles(directory=str(_masks_dir)), name="masks")

app.include_router(health.router, tags=["System"])
app.include_router(stats.router, tags=["Stats"])
app.include_router(analyze.router, prefix="/analyze", tags=["Analysis"])
app.include_router(dossiers.router, prefix="/dossiers", tags=["Database"])
app.include_router(index.router, prefix="/index", tags=["Indexing"])

from api.routers.dossiers import (
    database_list, download_report, export_audit_trail, submit_feedback, export_dossier_pdf
)
from fastapi import APIRouter as _APIRouter, Depends as _Depends
from db import get_db as _get_db

_compat = _APIRouter(tags=["Frontend Compat"])
_compat.get("/database/list")(database_list)
_compat.get("/report/{applicant_id}")(download_report)
_compat.get("/audit-trail/export")(export_audit_trail)
_compat.post("/submit-feedback")(submit_feedback)
_compat.get("/export-pdf/{dossier_id}")(export_dossier_pdf)
app.include_router(_compat)
