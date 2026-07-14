"""
Chargement générique des données validées vers le stockage brut.

Couche générique : ce module sait écrire un DataFrame quelque part
(PostgreSQL en priorité, Parquet en repli local si pas de base disponible),
peu importe le domaine métier.
"""
from __future__ import annotations

import os
from pathlib import Path
import pandas as pd

from ingestion.core.config_loader import SourceConfig


def load(df: pd.DataFrame, source_config: SourceConfig, processed_dir: str | Path = "data/processed") -> str:
    """
    Charge le DataFrame dans PostgreSQL si DATABASE_URL est défini dans
    l'environnement (cas d'usage réel avec docker-compose), sinon écrit
    un fichier Parquet local dans data/processed/ (utile pour développer
    et tester sans base de données démarrée).
    Retourne une chaîne décrivant la destination effective.
    """
    database_url = os.getenv("DATABASE_URL")
    table_name = source_config.business_rules.get(
        "cible_table_brute", f"raw.{source_config.source_id}"
    )

    if database_url:
        from sqlalchemy import create_engine

        schema, table = table_name.split(".") if "." in table_name else ("raw", table_name)
        engine = create_engine(database_url)
        with engine.begin() as conn:
            conn.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        df.to_sql(table, engine, schema=schema, if_exists="append", index=False)
        return f"postgres:{schema}.{table} ({len(df)} lignes)"

    processed_dir = Path(processed_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)
    out_path = processed_dir / f"{source_config.source_id}.parquet"
    df.to_parquet(out_path, index=False)
    return f"parquet:{out_path} ({len(df)} lignes) — DATABASE_URL non défini, écriture locale de repli"
