"""Orchestrateur principal du pipeline d'ingestion générique."""

from __future__ import annotations

import argparse
import importlib
import logging
import sys
from pathlib import Path

from ingestion.core.config_loader import SourceConfig, load_source_config
from ingestion.core.loader import load
from ingestion.core.validator import validate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("erp_ingestion")

CONNECTORS = {
    "excel": "ingestion.connectors.excel_connector",
}


def resolve_connector(connector_name: str):
    if connector_name not in CONNECTORS:
        raise ValueError(
            f"Connecteur inconnu '{connector_name}'. "
            f"Disponibles : {list(CONNECTORS.keys())}"
        )
    return importlib.import_module(CONNECTORS[connector_name])


def resolve_input_file(source_config: SourceConfig, explicit_file: str | None) -> Path:
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
            "Précisez un fichier avec --file."
        )
    return candidates[0]


def run(source_config_path: str, file_path: str | None = None) -> int:
    try:
        logger.info("[1/4] Chargement config : %s", source_config_path)
        source_config = load_source_config(source_config_path)
        logger.info("      Source : %s (id=%s)", source_config.label, source_config.source_id)

        input_file = resolve_input_file(source_config, file_path)
        logger.info("[2/4] Lecture via '%s' : %s", source_config.connector, input_file)
        connector = resolve_connector(source_config.connector)
        df = connector.read(source_config, input_file)
        logger.info("      %d lignes, %d colonnes", len(df), df.shape[1])

        logger.info("[3/4] Validation")
        report = validate(df, source_config)
        print(report.summary())  # On garde un print ici pour l'affichage utilisateur
        if not report.is_valid:
            logger.error("Validation échouée — chargement annulé")
            return 1

        logger.info("[4/4] Chargement")
        destination = load(df, source_config)
        logger.info("Terminé -> %s", destination)
        return 0

    except FileNotFoundError as e:
        logger.error("Fichier manquant : %s", e)
        return 2
    except ValueError as e:
        logger.error("Configuration invalide : %s", e)
        return 3
    except Exception:
        logger.exception("Erreur inattendue pendant l'ingestion")
        return 99


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline d'ingestion générique piloté par configuration"
    )
    parser.add_argument("--source", required=True, help="Chemin vers le YAML de config")
    parser.add_argument(
        "--file", required=False, help="Fichier explicite (auto-détecté si omis)"
    )
    args = parser.parse_args()
    sys.exit(run(args.source, args.file))


if __name__ == "__main__":
    main()