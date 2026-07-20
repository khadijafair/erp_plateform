"""Connecteur d'ingestion pour fichiers Excel."""

from __future__ import annotations

from pathlib import Path
import pandas as pd

from ingestion.core.config_loader import SourceConfig


def read(source_config: SourceConfig, file_path: str | Path) -> pd.DataFrame:
    """Lit un fichier Excel, valide la présence des colonnes et normalise les en-têtes."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Fichier source introuvable : {path}")

    df = pd.read_excel(path)

    # Vérification des colonnes requises par le mapping
    missing_cols = set(source_config.source_columns) - set(df.columns)
    if missing_cols:
        raise ValueError(
            f"Colonnes attendues absentes dans '{path.name}' : {sorted(missing_cols)}. "
            f"Vérifiez le dictionnaire de mapping pour '{source_config.source_id}'."
        )

    # Renommage vers les noms métier et filtrage/réordonnancement des colonnes
    df = df.rename(columns=source_config.reverse_mapping)
    df = df[source_config.business_columns].copy()

    # Métadonnées de traçabilité (Data Lineage)
    df["_source_id"] = source_config.source_id
    df["_source_file"] = path.name
    df["_ingested_at"] = pd.Timestamp.now(tz="UTC")

    return df