"""
Connecteur Excel — un "connecteur" au sens tap/target (Airbyte, Meltano...).

Rôle unique : lire un fichier Excel et renvoyer un DataFrame dont les colonnes
ont été renommées vers les noms métier génériques définis dans le mapping
de la configuration de source. Ce connecteur ne fait AUCUNE règle métier
(pas de nettoyage de signe, pas de séparation Vente/Achat) : ça, c'est le
rôle de la couche "modules métier" (dbt / analyse), pas du connecteur.

Pour brancher une nouvelle source demain (CSV, API, autre ERP), on ajoute
un nouveau fichier ici (ex: csv_connector.py, api_connector.py) qui respecte
la même interface : read(source_config, file_path) -> DataFrame normalisé.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd

from ingestion.core.config_loader import SourceConfig


def read(source_config: SourceConfig, file_path: str | Path) -> pd.DataFrame:
    """Lit un fichier Excel et renomme les colonnes vers les noms métier génériques."""
    df = pd.read_excel(file_path)

    missing_cols = [c for c in source_config.source_columns if c not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Colonnes attendues absentes du fichier '{file_path}': {missing_cols}. "
            f"Vérifie le mapping dans la config de source '{source_config.source_id}'."
        )

    df = df.rename(columns=source_config.reverse_mapping())
    df = df[source_config.business_columns]  # ordre stable, colonnes non mappées ignorées

    # métadonnées de traçabilité (couche générique : d'où vient la ligne, quand a-t-elle été ingérée)
    df["_source_id"] = source_config.source_id
    df["_source_file"] = Path(file_path).name
    df["_ingested_at"] = pd.Timestamp.utcnow()

    return df
