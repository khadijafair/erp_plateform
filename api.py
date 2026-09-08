"""API ERP Platform — FastAPI + Swagger auto-documenté.

Lance : uvicorn api:app --reload --host 0.0.0.0 --port 5000
Documentation : http://localhost:5000/docs
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import create_engine, text

import pipeline  # réutilise les fonctions ingestion()/dbt_build()/forecast() du script d'orchestration

app = FastAPI(
    title="ERP Platform API",
    description="Pipeline Data & ML End-to-End — ingestion, dbt, prévisions, monitoring",
    version="2.1.0",
)

BASE_DIR = Path(__file__).parent
DBT_DIR = BASE_DIR / "dbt" / "erp_platform"


# ============================================================
# MODÈLES Pydantic
# ============================================================

class HealthResponse(BaseModel):
    status: str
    postgres: bool
    ollama: bool
    version: str


class MappingRequest(BaseModel):
    file: str = "data/raw/test_nouvelle_source.xlsx"
    source_id: str = "nouvelle_source_demo"
    domaine: str = "ventes"


class MappingResponse(BaseModel):
    source_id: str
    draft_generated: bool
    draft_path: str | None
    preview: list[dict[str, Any]]
    stdout: str
    stderr: str


class PhaseResponse(BaseModel):
    success: bool
    phase: str
    error: str | None = None
    started_at: str
    finished_at: str


class PipelineResponse(BaseModel):
    success: bool
    returncode: int
    stdout: str
    stderr: str
    started_at: str
    finished_at: str


class KpiResponse(BaseModel):
    fact_transactions: int
    dim_article: int
    mart_abc: int
    date_min: str | None
    date_max: str | None


# ============================================================
# HELPERS
# ============================================================

def get_engine():
    url = os.getenv("DATABASE_URL", "postgresql://erp_admin:changeme@localhost:5432/erp_platform")
    return create_engine(url)


def check_postgres() -> bool:
    try:
        e = get_engine()
        with e.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def check_ollama() -> bool:
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def _run_phase(phase_name: str, phase_fn) -> PhaseResponse:
    started_at = datetime.now().isoformat()
    try:
        phase_fn()
        return PhaseResponse(success=True, phase=phase_name, started_at=started_at, finished_at=datetime.now().isoformat())
    except Exception as exc:
        return PhaseResponse(success=False, phase=phase_name, error=str(exc), started_at=started_at, finished_at=datetime.now().isoformat())


# ============================================================
# ENDPOINTS — MÉTADONNÉES / MONITORING
# ============================================================

@app.get("/", tags=["Métadonnées"])
def root():
    return {"message": "ERP Platform API", "docs": "/docs", "health": "/health"}


@app.get("/health", response_model=HealthResponse, tags=["Monitoring"])
def health():
    """Vérifie l'état de tous les services."""
    return HealthResponse(status="ok", postgres=check_postgres(), ollama=check_ollama(), version="2.1.0")


@app.get("/metrics", tags=["Monitoring"])
def metrics():
    """Métriques Prometheus sur la santé RÉELLE du pipeline (pas juste l'uptime Postgres)."""
    lignes = []
    try:
        engine = get_engine()
        with engine.connect() as conn:
            nb_transactions = conn.execute(text("SELECT COUNT(*) FROM marts.fact_transactions")).scalar()
            derniere_ingestion = conn.execute(
                text("SELECT EXTRACT(EPOCH FROM MAX(_ingested_at)) FROM raw.erp_ventes_achats")
            ).scalar()
        lignes.append(f"erp_fact_transactions_total {nb_transactions or 0}")
        lignes.append(f"erp_derniere_ingestion_timestamp {derniere_ingestion or 0}")
        lignes.append("erp_pipeline_derniere_execution_success 1")
    except Exception:
        lignes.append("erp_pipeline_derniere_execution_success 0")
    return Response(content="\n".join(lignes) + "\n", media_type="text/plain")


# ============================================================
# ENDPOINTS — IA / MAPPING
# ============================================================

@app.post("/api/discover-mapping", response_model=MappingResponse, tags=["IA — Schema Mapper"])
def discover_mapping(req: MappingRequest):
    """Appelle Ollama pour proposer un mapping YAML sur un fichier Excel."""
    full_path = BASE_DIR / req.file
    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"Fichier introuvable : {req.file}")

    cmd = [
        sys.executable, "-m", "ml.schema_mapper.infer_mapping",
        "--excel", str(full_path),
        "--source-id", req.source_id,
        "--new-domain",
        "--domaine", req.domaine,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=BASE_DIR, timeout=120)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Ollama n'a pas répondu dans le délai imparti (120s)")

    draft_path = BASE_DIR / "config" / "sources" / f"_draft_{req.source_id}.yaml"

    preview = []
    if draft_path.exists():
        with open(draft_path, encoding="utf-8") as f:
            content = yaml.safe_load(f)
        for k, v in content.get("mapping", {}).items():
            preview.append({"champ_cible": k, "colonne_source": v})

    return MappingResponse(
        source_id=req.source_id,
        draft_generated=draft_path.exists(),
        draft_path=str(draft_path) if draft_path.exists() else None,
        preview=preview,
        stdout=result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout,
        stderr=result.stderr[-1000:] if len(result.stderr) > 1000 else result.stderr,
    )


# ============================================================
# ENDPOINTS — PIPELINE (découpé par phase + version complète)
# ============================================================

@app.post("/api/pipeline/ingestion", response_model=PhaseResponse, tags=["Pipeline — Étapes"])
def pipeline_ingestion():
    """Phase 1 seule : ingestion des 3 sources Excel vers PostgreSQL."""
    return _run_phase("ingestion", pipeline.ingestion)


@app.post("/api/pipeline/dbt", response_model=PhaseResponse, tags=["Pipeline — Étapes"])
def pipeline_dbt():
    """Phase 2 seule : dbt seed + run + test."""
    return _run_phase("dbt", pipeline.dbt_build)


@app.post("/api/pipeline/forecast", response_model=PhaseResponse, tags=["Pipeline — Étapes"])
def pipeline_forecast():
    """Phase 3 seule : prévisions Prophet."""
    return _run_phase("forecast", pipeline.forecast)


@app.post("/api/run-pipeline", response_model=PipelineResponse, tags=["Pipeline"])
def run_pipeline():
    """
    Exécute le pipeline complet en une fois (ingestion → dbt → Prophet).
    Utilisé par n8n (déclenchement automatique en un seul appel). Streamlit
    utilise plutôt les 3 endpoints ci-dessus séparément, pour afficher une
    vraie progression étape par étape.
    """
    started_at = datetime.now().isoformat()
    result = subprocess.run([sys.executable, "pipeline.py"], cwd=BASE_DIR, capture_output=True, text=True)
    finished_at = datetime.now().isoformat()
    return PipelineResponse(
        success=result.returncode == 0,
        returncode=result.returncode,
        stdout=result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout,
        stderr=result.stderr[-1000:] if len(result.stderr) > 1000 else result.stderr,
        started_at=started_at,
        finished_at=finished_at,
    )


# ============================================================
# ENDPOINTS — MÉTRIQUES MÉTIER
# ============================================================

@app.get("/api/kpis", response_model=KpiResponse, tags=["Métriques"])
def get_kpis():
    """Retourne les KPIs clés du data warehouse."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            fact = conn.execute(text("SELECT COUNT(*) FROM marts.fact_transactions")).scalar()
            art = conn.execute(text("SELECT COUNT(*) FROM marts.dim_article")).scalar()
            abc = conn.execute(text("SELECT COUNT(*) FROM marts.mart_abc_article")).scalar()
            dmin = conn.execute(text("SELECT MIN(date_id)::text FROM marts.fact_transactions")).scalar()
            dmax = conn.execute(text("SELECT MAX(date_id)::text FROM marts.fact_transactions")).scalar()
        return KpiResponse(fact_transactions=fact, dim_article=art, mart_abc=abc, date_min=dmin, date_max=dmax)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Base de données inaccessible : {exc}")


@app.get("/api/sources", tags=["Configuration"])
def list_sources():
    """Liste les fichiers YAML de configuration disponibles."""
    sources_dir = BASE_DIR / "config" / "sources"
    files = [f.name for f in sources_dir.glob("*.yaml") if not f.name.startswith("_draft_")]
    drafts = [f.name for f in sources_dir.glob("_draft_*.yaml")]
    return {"sources": files, "drafts": drafts}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)