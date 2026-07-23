"""Connecteur d'ingestion pour fichiers Excel."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from ingestion.core.config_loader import SourceConfig

logger = logging.getLogger(__name__)


def read(source_config: SourceConfig, file_path: str | Path) -> pd.DataFrame:
    """Lit un fichier Excel, valide la présence des colonnes et normalise les en-têtes."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Fichier source introuvable : {path}")

    # Paramètres optionnels depuis la config (ex: sheet_name, header, skiprows)
    excel_opts = source_config.business_rules.get("excel_options", {})
    df = pd.read_excel(path, **excel_opts)

    missing = set(source_config.source_columns) - set(df.columns)
    if missing:
        available = ", ".join(df.columns.tolist())
        raise ValueError(
            f"Colonnes attendues absentes dans '{path.name}' : {sorted(missing)}. "
            f"Colonnes trouvées : [{available}]. "
            f"Vérifiez le mapping pour '{source_config.source_id}'."
        )

    df = df.rename(columns=source_config.reverse_mapping)
    df = df[source_config.business_columns].copy()

    # Traçabilité
    df["_source_id"] = source_config.source_id
    df["_source_file"] = path.name
    df["_ingested_at"] = pd.Timestamp.now(tz="UTC")

    logger.info("Excel lu : %d lignes, %d colonnes depuis %s", len(df), df.shape[1], path.name)
    return df