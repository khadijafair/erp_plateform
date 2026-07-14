"""
Chargement et validation légère des fichiers de configuration de source.

Ce module fait partie de la COUCHE GÉNÉRIQUE du pipeline : il ne connaît
rien du sens métier des colonnes, il sait juste lire et structurer un
fichier YAML de configuration de source.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import yaml


@dataclass
class SourceConfig:
    source_id: str
    label: str
    connector: str
    file_pattern: str
    mapping: dict[str, str]
    schema: dict[str, dict]
    business_key: list[str]
    business_rules: dict = field(default_factory=dict)
    raw_path: Path | None = None  # renseigné à l'exécution

    @property
    def business_columns(self) -> list[str]:
        """Noms de colonnes 'métier génériques' (clés du mapping)."""
        return list(self.mapping.keys())

    @property
    def source_columns(self) -> list[str]:
        """Noms de colonnes réels attendus dans le fichier source."""
        return list(self.mapping.values())

    def reverse_mapping(self) -> dict[str, str]:
        """nom réel de colonne -> nom métier générique."""
        return {v: k for k, v in self.mapping.items()}


def load_source_config(path: str | Path) -> SourceConfig:
    """Charge un fichier config/sources/*.yaml et le structure en objet SourceConfig."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    required_keys = ["source_id", "connector", "mapping", "schema"]
    missing = [k for k in required_keys if k not in raw]
    if missing:
        raise ValueError(
            f"Configuration invalide ({path}) : clés manquantes {missing}. "
            "Une configuration de source doit définir au minimum "
            "source_id, connector, mapping et schema."
        )

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
