#!/usr/bin/env python3
"""Pipeline ERP Platform — Orchestration complète."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("erp_pipeline")

BASE_DIR = Path(__file__).parent
DBT_DIR = BASE_DIR / "dbt" / "erp_platform"
SOURCES = [
    "config/sources/erp_referentiel_articles.yaml",
    "config/sources/erp_ventes_achats.yaml",
    "config/sources/erp_production_assemblage.yaml",
]


def run(cmd: list[str], cwd: Path | None = None) -> None:
    label = " ".join(cmd[:3]) + ("..." if len(cmd) > 3 else "")
    logger.info("▶ %s", label)
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("Échec de : %s", label)
        logger.error("STDOUT :\n%s", result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
        logger.error("STDERR :\n%s", result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr)
        raise RuntimeError(f"Étape échouée : {label}")
    logger.info("✓ %s terminé", label)


def ingestion() -> None:
    logger.info("=" * 50)
    logger.info("PHASE 1 : INGESTION")
    logger.info("=" * 50)
    for source in SOURCES:
        run([sys.executable, "-m", "ingestion.main", "--source", str(BASE_DIR / source)])


def dbt_build() -> None:
    logger.info("=" * 50)
    logger.info("PHASE 2 : DBT (seed + run + test)")
    logger.info("=" * 50)
    run(["dbt", "seed"], cwd=DBT_DIR)
    run(["dbt", "run"], cwd=DBT_DIR)
    run(["dbt", "test"], cwd=DBT_DIR)


def forecast() -> None:
    logger.info("=" * 50)
    logger.info("PHASE 3 : PRÉVISIONS PROPHET")
    logger.info("=" * 50)
    run([sys.executable, "-m", "ml.demand_forecast.forecast"])


def main() -> int:
    try:
        ingestion()
        dbt_build()
        forecast()
        logger.info("=" * 50)
        logger.info("PIPELINE TERMINÉ AVEC SUCCÈS")
        logger.info("=" * 50)
        return 0
    except Exception as exc:
        logger.error("=" * 50)
        logger.error("PIPELINE ARRÊTÉ : %s", exc)
        logger.error("=" * 50)
        return 1


if __name__ == "__main__":
    sys.exit(main())