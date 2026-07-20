"""Module de chargement et de stockage des données ingérées."""

from __future__ import annotations

import os
from pathlib import Path
import pandas as pd

from ingestion.core.config_loader import SourceConfig


def load(
    df: pd.DataFrame,
    source_config: SourceConfig,
    processed_dir: str | Path = "data/processed",
) -> str:
    """Exporte le DataFrame validé vers PostgreSQL ou vers un fichier Parquet local."""
    database_url = os.getenv("DATABASE_URL")
    table_name = source_config.business_rules.get(
        "cible_table_brute", f"raw.{source_config.source_id}"
    )

    if database_url:
        from sqlalchemy import create_engine

        if "." in table_name:
            schema, table = table_name.rsplit(".", 1)
        else:
            schema, table = "raw", table_name

        engine = create_engine(database_url)
        with engine.begin() as conn:
            conn.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")

        df.to_sql(
            name=table,
            con=engine,
            schema=schema,
            if_exists="append",
            index=False,
            chunksize=5000,
            method="multi",
        )
        return f"postgres:{schema}.{table} ({len(df)} lignes)"

    target_dir = Path(processed_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = target_dir / f"{source_config.source_id}.parquet"
    df.to_parquet(out_path, index=False)

    return f"parquet:{out_path} ({len(df)} lignes) — [Mode repli local]"