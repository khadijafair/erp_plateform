"""Module de chargement et de stockage des données ingérées."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from ingestion.core.config_loader import SourceConfig

logger = logging.getLogger(__name__)

_ENGINE_CACHE = {}


def _get_engine(database_url: str):
    if database_url not in _ENGINE_CACHE:
        _ENGINE_CACHE[database_url] = create_engine(database_url)
    return _ENGINE_CACHE[database_url]


def _sanitize_identifier(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if cleaned[0].isdigit():
        cleaned = "_" + cleaned
    return cleaned


def load(
    df: pd.DataFrame,
    source_config: SourceConfig,
    processed_dir: str | Path = "data/processed",
) -> str:
    """Exporte le DataFrame validé vers PostgreSQL ou vers un fichier Parquet local."""
    database_url = os.getenv("DATABASE_URL")
    raw_target = source_config.business_rules.get(
        "cible_table_brute", f"raw.{source_config.source_id}"
    )

    if "." in raw_target:
        schema_part, table_part = raw_target.rsplit(".", 1)
        schema = _sanitize_identifier(schema_part)
        table = _sanitize_identifier(table_part)
    else:
        schema = "raw"
        table = _sanitize_identifier(raw_target)

    if database_url:
        engine = _get_engine(database_url)

        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

        mode = source_config.business_rules.get("mode_chargement", "append")
        if mode not in ("append", "replace", "fail"):
            raise ValueError(f"Mode de chargement invalide : '{mode}'")

        # CORRECTION : DROP TABLE au lieu de TRUNCATE pour recréer proprement
        if mode == "replace":
            with engine.begin() as conn:
                conn.execute(text(f'DROP TABLE IF EXISTS "{schema}"."{table}" CASCADE'))
            mode = "append"  # to_sql recréera la table avec la bonne structure

        df.to_sql(
            name=table,
            con=engine,
            schema=schema,
            if_exists=mode,
            index=False,
            chunksize=5000,
            method="multi",
        )
        logger.info("Chargement PostgreSQL OK : %s.%s (%d lignes, mode=%s)", schema, table, len(df), mode)
        return f"postgres:{schema}.{table} ({len(df)} lignes, mode={mode})"

    # Fallback Parquet
    target_dir = Path(processed_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = target_dir / f"{source_config.source_id}.parquet"
    df.to_parquet(out_path, index=False)
    logger.info("Chargement Parquet OK : %s (%d lignes)", out_path, len(df))

    return f"parquet:{out_path} ({len(df)} lignes) — [Mode repli local]"