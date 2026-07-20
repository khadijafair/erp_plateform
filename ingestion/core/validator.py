"""Module de validation générique de schéma de données."""

from __future__ import annotations

from dataclasses import dataclass, field
import pandas as pd

from ingestion.core.config_loader import SourceConfig


@dataclass
class ValidationReport:
    source_id: str
    total_rows: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Retourne True s'il n'y a aucune erreur bloquante."""
        return len(self.errors) == 0

    def summary(self) -> str:
        """Génère un résumé textuel du rapport de validation."""
        lines = [
            f"Validation '{self.source_id}' — {self.total_rows} lignes",
            f"  Statut : {'OK' if self.is_valid else 'ÉCHEC'}",
        ]
        for warning in self.warnings:
            lines.append(f"  [WARN] {warning}")
        for error in self.errors:
            lines.append(f"  [ERROR] {error}")
        return "\n".join(lines)


def validate(df: pd.DataFrame, source_config: SourceConfig) -> ValidationReport:
    """Valide la conformité d'un DataFrame par rapport à la configuration de la source."""
    report = ValidationReport(source_id=source_config.source_id, total_rows=len(df))

    for col_name, rules in source_config.schema.items():
        if col_name not in df.columns:
            report.errors.append(f"Colonne obligatoire absente : '{col_name}'")
            continue

        # 1. Vérification des valeurs manquantes (Complétude)
        if rules.get("required", False):
            n_missing = df[col_name].isna().sum()
            if n_missing > 0:
                report.errors.append(
                    f"'{col_name}' : {n_missing} valeur(s) manquante(s) (colonne requise)"
                )

        # 2. Vérification du format de date
        if rules.get("type") == "date":
            parsed = pd.to_datetime(df[col_name], errors="coerce")
            n_bad = parsed.isna().sum() - df[col_name].isna().sum()
            if n_bad > 0:
                report.warnings.append(
                    f"'{col_name}' : {n_bad} valeur(s) non convertibles en date"
                )

        # 3. Vérification des valeurs autorisées (Domain Check)
        allowed = rules.get("allowed_values")
        if allowed:
            invalid_values = set(df[col_name].dropna().unique()) - set(allowed)
            if invalid_values:
                report.warnings.append(
                    f"'{col_name}' : valeurs inattendues {sorted(invalid_values)} "
                    f"(attendues : {allowed})"
                )

    # 4. Vérification d'unicité de la clé métier
    if source_config.business_key and all(c in df.columns for c in source_config.business_key):
        n_dup = df.duplicated(subset=source_config.business_key, keep=False).sum()
        if n_dup > 0:
            report.warnings.append(
                f"Clé métier {source_config.business_key} : {n_dup} ligne(s) impliquée(s) dans un doublon"
            )

    return report