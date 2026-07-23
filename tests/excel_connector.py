from __future__ import annotations

from pathlib import Path
import pandas as pd

from ingestion.core.config_loader import SourceConfig


def read(source_config: SourceConfig, file_path: str | Path) -> pd.DataFrame:
    df = pd.read_excel(file_path)

    missing_cols = [c for c in source_config.source_columns if c not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Colonnes attendues absentes du fichier '{file_path}': {missing_cols}. "
            f"Vérifie le mapping dans la config de source '{source_config.source_id}'."
        )

    df = df.rename(columns=source_config.reverse_mapping())
    df = df[source_config.business_columns]

    df["_source_id"] = source_config.source_id
    df["_source_file"] = Path(file_path).name
    df["_ingested_at"] = pd.Timestamp.utcnow()

    return df