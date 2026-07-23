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
    report = ValidationReport(source_id=source_config.source_id, total_rows=len(df))

    for col_name, rules in source_config.schema.items():
        if col_name not in df.columns:
            report.errors.append(f"Colonne obligatoire absente : '{col_name}'")
            continue

        if rules.get("required", False):
            n_missing = df[col_name].isna().sum()
            if n_missing > 0:
                report.errors.append(
                    f"'{col_name}' : {n_missing} valeur(s) manquante(s) alors que la colonne est obligatoire"
                )

        expected_type = rules.get("type")
        if expected_type == "date":
            parsed = pd.to_datetime(df[col_name], errors="coerce")
            n_bad = parsed.isna().sum() - df[col_name].isna().sum()
            if n_bad > 0:
                report.warnings.append(f"'{col_name}' : {n_bad} valeur(s) non convertibles en date")

        allowed = rules.get("allowed_values")
        if allowed:
            invalid_values = set(df[col_name].dropna().unique()) - set(allowed)
            if invalid_values:
                report.warnings.append(
                    f"'{col_name}' : valeurs inattendues détectées {sorted(invalid_values)} "
                    f"(attendu parmi {allowed})"
                )

    if source_config.business_key:
        key_cols = source_config.business_key
        if all(c in df.columns for c in key_cols):
            n_dup = df.duplicated(subset=key_cols, keep=False).sum()
            if n_dup > 0:
                report.warnings.append(
                    f"Clé métier {key_cols} : {n_dup} ligne(s) impliquée(s) dans un doublon"
                )

    return report