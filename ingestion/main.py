"""Orchestrateur principal du pipeline d'ingestion générique."""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

from ingestion.core.config_loader import SourceConfig, load_source_config
from ingestion.core.loader import load
from ingestion.core.validator import validate

# Registre des connecteurs disponibles (Pattern Plugin)
CONNECTORS = {
    "excel": "ingestion.connectors.excel_connector",
}


def resolve_connector(connector_name: str):
    """Charge dynamiquement le module du connecteur demandé."""
    if connector_name not in CONNECTORS:
        raise ValueError(
            f"Connecteur inconnu '{connector_name}'. Connecteurs disponibles : {list(CONNECTORS.keys())}"
        )
    return importlib.import_module(CONNECTORS[connector_name])


def resolve_input_file(source_config: SourceConfig, explicit_file: str | None) -> Path:
    """Détermine le fichier source à traiter (explicite ou via recherche dans data/raw/)."""
    if explicit_file:
        path = Path(explicit_file)
        if not path.is_file():
            raise FileNotFoundError(f"Fichier explicite introuvable : {path}")
        return path

    raw_dir = Path("data/raw")
    if not raw_dir.is_dir():
        raise FileNotFoundError(f"Dossier de données brutes introuvable : {raw_dir}")

    candidates = sorted(raw_dir.glob(source_config.file_pattern))
    if not candidates:
        raise FileNotFoundError(
            f"Aucun fichier correspondant à '{source_config.file_pattern}' dans {raw_dir}. "
            "Précisez un fichier avec l'option --file."
        )
    return candidates[0]


def run(source_config_path: str, file_path: str | None = None) -> int:
    """Exécute la chaîne d'ingestion : Config -> Connecteur -> Validation -> Chargement."""
    print(f"[1/4] Chargement de la configuration : {source_config_path}")
    source_config = load_source_config(source_config_path)
    print(f"      Source : {source_config.label} (id={source_config.source_id})")

    input_file = resolve_input_file(source_config, file_path)
    print(f"[2/4] Lecture via connecteur '{source_config.connector}' : {input_file}")
    connector = resolve_connector(source_config.connector)
    df = connector.read(source_config, input_file)
    print(f"      {len(df)} lignes lues, {df.shape[1]} colonnes normalisées")

    print("[3/4] Validation du schéma")
    report = validate(df, source_config)
    print(report.summary())
    if not report.is_valid:
        print("Échec de la validation — chargement annulé.", file=sys.stderr)
        return 1

    print("[4/4] Chargement vers le stockage brut")
    destination = load(df, source_config)
    print(f"      Terminé -> {destination}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline d'ingestion générique piloté par configuration"
    )
    parser.add_argument(
        "--source", required=True, help="Chemin vers le fichier YAML de configuration"
    )
    parser.add_argument(
        "--file",
        required=False,
        help="Chemin explicite du fichier à ingérer (auto-détecté si omis)",
    )
    args = parser.parse_args()
    sys.exit(run(args.source, args.file))


if __name__ == "__main__":
    main()