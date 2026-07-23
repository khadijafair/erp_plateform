"""Module de validation générique de schéma de données."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from ingestion.core.config_loader import SourceConfig

logger = logging.getLogger(__name__)


@dataclass
class ValidationReport:
    source_id: str
    total_rows: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        lines = [
            f"Validation '{self.source_id}' — {self.total_rows} lignes",
            f"  Statut : {'OK' if self.is_valid else 'ÉCHEC'}",
        ]
        for w in self.warnings:
            lines.append(f"  [WARN] {w}")
        for e in self.errors:
            lines.append(f"  [ERROR] {e}")
        return "\n".join(lines)


def validate(df: pd.DataFrame, source_config: SourceConfig) -> ValidationReport:
    """Valide la conformité d'un DataFrame par rapport à la configuration de la source."""
    report = ValidationReport(source_id=source_config.source_id, total_rows=len(df))

    for col_name, rules in source_config.schema.items():
        if col_name not in df.columns:
            report.errors.append(f"Colonne obligatoire absente : '{col_name}'")
            continue

        # Complétude
        if rules.get("required", False):
            n_missing = df[col_name].isna().sum()
            if n_missing > 0:
                report.errors.append(
                    f"'{col_name}' : {n_missing} valeur(s) manquante(s)"
                )

        # Type date
        if rules.get("type") == "date":
            parsed = pd.to_datetime(df[col_name], errors="coerce")
            n_bad = parsed.isna().sum() - df[col_name].isna().sum()
            if n_bad > 0:
                report.warnings.append(
                    f"'{col_name}' : {n_bad} valeur(s) non convertibles en date"
                )

        # Domaine de valeurs
        allowed = rules.get("allowed_values")
        if allowed is not None:
            invalid = set(df[col_name].dropna().unique()) - set(allowed)
            if invalid:
                report.warnings.append(
                    f"'{col_name}' : valeurs inattendues {sorted(invalid)} "
                    f"(attendues : {allowed})"
                )

        # Type numérique / float
        if rules.get("type") in ("numeric", "float", "int", "integer"):
            coerced = pd.to_numeric(df[col_name], errors="coerce")
            n_bad = coerced.isna().sum() - df[col_name].isna().sum()
            if n_bad > 0:
                report.warnings.append(
                    f"'{col_name}' : {n_bad} valeur(s) non numériques"
                )

    # Clé métier — DOUBLON = ERREUR
    if source_config.business_key:
        missing_keys = [c for c in source_config.business_key if c not in df.columns]
        if missing_keys:
            report.errors.append(
                f"Clé métier incomplète : colonnes manquantes {missing_keys}"
            )
        else:
            n_dup = df.duplicated(subset=source_config.business_key, keep=False).sum()
            if n_dup > 0:
                report.errors.append(
                    f"Clé métier {source_config.business_key} : "
                    f"{n_dup} ligne(s) en doublon — chargement bloqué"
                )

    return report