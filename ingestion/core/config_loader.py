"""Chargement et parsing des fichiers de configuration YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import yaml


@dataclass
class SourceConfig:
    source_id: str
    label: str
    connector: str
    file_pattern: str
    mapping: dict[str, str]
    schema: dict[str, dict[str, Any]]
    business_key: list[str] = field(default_factory=list)
    business_rules: dict[str, Any] = field(default_factory=dict)
    raw_path: Path | None = None

    @property
    def business_columns(self) -> list[str]:
        """Noms de colonnes normalisés (clés du mapping)."""
        return list(self.mapping.keys())

    @property
    def source_columns(self) -> list[str]:
        """Noms de colonnes d'origine attendus dans le fichier source."""
        return list(self.mapping.values())

    @property
    def reverse_mapping(self) -> dict[str, str]:
        """Dictionnaire de correspondance : nom_source -> nom_normalise."""
        return {v: k for k, v in self.mapping.items()}


def load_source_config(path: str | Path) -> SourceConfig:
    """Charge un fichier config/sources/*.yaml et instancie un objet SourceConfig."""
    config_path = Path(path)

    if not config_path.is_file():
        raise FileNotFoundError(f"Fichier de configuration introuvable : {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Fichier de configuration vide ou malformé : {config_path}")

    required_keys = {"source_id", "connector", "mapping", "schema"}
    missing = required_keys - raw.keys()
    if missing:
        raise ValueError(f"Configuration {config_path} incomplète. Clés manquantes : {sorted(missing)}")

    return SourceConfig(
        source_id=raw["source_id"],
        label=raw.get("label", raw["source_id"]),
        connector=raw["connector"],
        file_pattern=raw.get("file_pattern", "*"),
        mapping=raw["mapping"],
        schema=raw["schema"],
        business_key=raw.get("business_key", []),
        business_rules=raw.get("business_rules", {}),
    )