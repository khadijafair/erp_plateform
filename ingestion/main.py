"""
Point d'entrée du pipeline d'ingestion.

Usage :
    python -m ingestion.main --source config/sources/erp_ventes_achats.yaml --file data/raw/mon_extrait.xlsx

Ce script orchestre la couche générique uniquement :
    config -> connecteur -> validation -> chargement
Il ne contient aucune règle métier (pas de calcul de marge, pas de
nettoyage de signe) : ça, c'est le rôle des modules métier (dbt),
exécutés ensuite sur les données déjà chargées.
"""
from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

from ingestion.core.config_loader import load_source_config
from ingestion.core.validator import validate
from ingestion.core.loader import load

CONNECTORS = {
    "excel": "ingestion.connectors.excel_connector",
}


def resolve_connector(connector_name: str):
    import importlib

    if connector_name not in CONNECTORS:
        raise ValueError(
            f"Connecteur inconnu '{connector_name}'. Connecteurs disponibles : {list(CONNECTORS)}"
        )
    return importlib.import_module(CONNECTORS[connector_name])


def resolve_input_file(source_config, explicit_file: str | None) -> str:
    if explicit_file:
        return explicit_file
    candidates = sorted(glob.glob(f"data/raw/{source_config.file_pattern}"))
    if not candidates:
        raise FileNotFoundError(
            f"Aucun fichier trouvé dans data/raw/ correspondant à '{source_config.file_pattern}'. "
            "Précise --file explicitement."
        )
    return candidates[0]


def run(source_config_path: str, file_path: str | None = None) -> int:
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
    parser = argparse.ArgumentParser(description="Pipeline d'ingestion générique piloté par configuration")
    parser.add_argument("--source", required=True, help="Chemin vers le fichier de config de source (YAML)")
    parser.add_argument("--file", required=False, help="Chemin explicite du fichier à ingérer (sinon auto-détecté dans data/raw/)")
    args = parser.parse_args()
    sys.exit(run(args.source, args.file))


if __name__ == "__main__":
    main()
