"""Module de génération automatique de brouillons de mapping YAML via Ollama."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml

from ml.schema_mapper.ollama_client import DEFAULT_MODEL, ask_json

PANDAS_TO_GENERIC_TYPE = {
    "int64": "float",
    "float64": "float",
    "object": "string",
    "datetime64[ns]": "date",
    "bool": "string",
}


def load_target_schema(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def profil_colonnes_excel(excel_path: str) -> list[dict]:
    """Extrait uniquement les en-têtes et types de colonnes (sans données métier)."""
    df = pd.read_excel(excel_path, nrows=50)
    colonnes = []
    for col in df.columns:
        dtype = str(df[col].dtype)
        colonnes.append({
            "nom_colonne": col,
            "type_detecte": PANDAS_TO_GENERIC_TYPE.get(dtype, "string"),
        })
    return colonnes


def build_prompt(target_schema: dict, colonnes_source: list[dict]) -> str:
    champs_cible = [
        {"nom": c["nom"], "description": c["description"], "type": c["type"]}
        for c in target_schema["champs"]
    ]

    return f"""Tu es un assistant d'ingénierie de données.
Schéma cible :
{json.dumps(champs_cible, ensure_ascii=False, indent=2)}

Colonnes réelles du fichier :
{json.dumps(colonnes_source, ensure_ascii=False, indent=2)}

Propose un mapping en JSON sous cette forme exacte :
{{
  "mapping": [
    {{"champ_cible": "nom_champ", "colonne_source": "Nom Colonne ou null", "confiance": 0.0, "justification": "..."}}
  ]
}}
"""


def build_prompt_bootstrap(colonnes_source: list[dict], domaine: str) -> str:
    return f"""Tu es un assistant d'ingénierie de données.
Domaine métier : "{domaine}"

Colonnes réelles du fichier :
{json.dumps(colonnes_source, ensure_ascii=False, indent=2)}

Propose les champs génériques et le mapping en JSON :
{{
  "champs_proposes": [
    {{"nom_generique": "...", "colonne_source": "Nom Colonne", "description": "...", "type": "date|string|float", "obligatoire": true, "confiance": 0.0}}
  ]
}}
"""


def afficher_revue(mapping_propose: list[dict]) -> None:
    print("\n=== Mapping proposé par Ollama (à valider) ===\n")
    for m in mapping_propose:
        confiance = m.get("confiance", 0)
        marqueur = "⚠️ À VÉRIFIER" if confiance < 0.6 or m.get("colonne_source") is None else "OK"
        print(f" [{marqueur}] {m['champ_cible']:<20} <- {m.get('colonne_source')!r:<30} (confiance {confiance:.2f}) — {m.get('justification', '')}")
    print()


def ecrire_draft_config(mapping_propose: list[dict], target_schema: dict, source_id: str, output_path: Path) -> None:
    mapping = {m["champ_cible"]: m["colonne_source"] for m in mapping_propose if m.get("colonne_source") is not None}
    schema = {c["nom"]: {"type": c["type"], "required": c["obligatoire"]} for c in target_schema["champs"] if c["nom"] in mapping}

    draft = {
        "source_id": source_id,
        "label": f"Source {source_id} (brouillon proposé par IA)",
        "connector": "excel",
        "file_pattern": "*.xlsx",
        "mapping": mapping,
        "schema": schema,
        "business_key": [],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# ⚠️ BROUILLON généré par IA — valider puis retirer le préfixe _draft_.\n\n")
        yaml.safe_dump(draft, f, allow_unicode=True, sort_keys=False)

    print(f"Brouillon généré : {output_path}")


def afficher_revue_bootstrap(champs_proposes: list[dict]) -> None:
    print("\n=== Champs et mapping proposés par Ollama (à valider) ===\n")
    for c in champs_proposes:
        confiance = c.get("confiance", 0)
        marqueur = "⚠️ À VÉRIFIER" if confiance < 0.6 else "OK"
        print(f" [{marqueur}] {c['nom_generique']:<25} <- {c['colonne_source']!r:<30} ({c.get('type', '?'):<6}, confiance {confiance:.2f})")
    print()


def ecrire_draft_config_bootstrap(champs_proposes: list[dict], source_id: str, domaine: str, output_path: Path) -> None:
    mapping = {c["nom_generique"]: c["colonne_source"] for c in champs_proposes}
    schema = {c["nom_generique"]: {"type": c["type"], "required": c.get("obligatoire", False)} for c in champs_proposes}

    draft = {
        "source_id": source_id,
        "label": f"Source {source_id} — domaine {domaine} (brouillon généré par IA)",
        "connector": "excel",
        "file_pattern": "*.xlsx",
        "mapping": mapping,
        "schema": schema,
        "business_key": [],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# ⚠️ BROUILLON (Mode bootstrap) — valider puis retirer le préfixe _draft_.\n\n")
        yaml.safe_dump(draft, f, allow_unicode=True, sort_keys=False)

    print(f"Brouillon généré : {output_path}")


def run(excel_path: str, target_schema_path: str | None, source_id: str, model: str, bootstrap: bool = False, domaine: str = "non précisé") -> None:
    colonnes_source = profil_colonnes_excel(excel_path)
    print(f"{len(colonnes_source)} colonnes détectées dans {excel_path}")

    if bootstrap:
        prompt = build_prompt_bootstrap(colonnes_source, domaine)
        reponse = ask_json(prompt, model=model)
        champs_proposes = reponse["champs_proposes"]
        afficher_revue_bootstrap(champs_proposes)
        output_path = Path("config/sources") / f"_draft_{source_id}.yaml"
        ecrire_draft_config_bootstrap(champs_proposes, source_id, domaine, output_path)
    else:
        target_schema = load_target_schema(target_schema_path)
        prompt = build_prompt(target_schema, colonnes_source)
        reponse = ask_json(prompt, model=model)
        mapping_propose = reponse["mapping"]
        afficher_revue(mapping_propose)
        output_path = Path("config/sources") / f"_draft_{source_id}.yaml"
        ecrire_draft_config(mapping_propose, target_schema, source_id, output_path)


def main():
    parser = argparse.ArgumentParser(description="Propose un mapping YAML via Ollama")
    parser.add_argument("--excel", required=True)
    parser.add_argument("--target-schema", default=None)
    parser.add_argument("--new-domain", action="store_true")
    parser.add_argument("--domaine", default="non précisé")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    if not args.new_domain and not args.target_schema:
        parser.error("Précise --target-schema OU --new-domain.")

    run(args.excel, args.target_schema, args.source_id, args.model, bootstrap=args.new_domain, domaine=args.domaine)


if __name__ == "__main__":
    main()