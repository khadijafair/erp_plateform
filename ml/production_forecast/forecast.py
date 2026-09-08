"""
Module de prévision de production par article avec Prophet.

Même architecture que ml/demand_forecast/forecast.py : lecture via
PostgreSQL (staging dbt, pas de lecture Excel directe), config-driven,
mêmes régresseurs événements marocains, même logique de validation
rétrospective — pour que les deux modules de prévision du projet soient
cohérents entre eux, pas deux façons différentes de faire la même chose.

Différence assumée avec demand_forecast : une seule année de données
disponible (production 2023) au lieu de 2 ans pour les ventes. La
validation rétrospective se fait donc À L'INTÉRIEUR de 2023 (voir
config.yaml), ce qui donne un test plus court et moins robuste — assumé
et affiché dans les logs, pas caché.
"""
from __future__ import annotations

import logging
import os
import re
import warnings
from pathlib import Path

import pandas as pd
import yaml
from prophet import Prophet
from sqlalchemy import create_engine, text

warnings.filterwarnings("ignore")

logger = logging.getLogger("erp_production_forecast")

CONFIG_PATH = Path(__file__).parent / "config.yaml"
EVENTS_PATH = Path(__file__).parent.parent / "demand_forecast" / "evenements_maroc.csv"

REGRESSOR_COLS = [
    "is_ramadan", "is_aid_fitr", "is_aid_adha", "is_mawlid",
    "is_yennayer", "is_fete_trone", "is_marche_verte", "is_outlier",
]


def _sanitize_identifier(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if cleaned[0].isdigit():
        cleaned = "_" + cleaned
    return cleaned


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_engine():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL non définie")
    return create_engine(database_url)


def get_articles_a_prevoir(engine, config: dict) -> pd.DataFrame:
    """Les N articles les plus produits en 2023 (pas de mart_abc dédié à la production -> on trie ici)."""
    schema = _sanitize_identifier(config["staging_schema"])
    query = f"""
        select numero_article, sum(quantite_normalisee) as quantite_totale
        from {schema}.stg_erp_production_assemblage
        where is_resultat
        group by numero_article
        order by quantite_totale desc
        limit :top_n
    """
    return pd.read_sql(text(query), engine, params={"top_n": config["perimetre_top_n_articles"]})


def get_historique_hebdo(engine, numero_article: str, config: dict) -> pd.DataFrame:
    schema = _sanitize_identifier(config["staging_schema"])
    query = f"""
        select
            date_trunc('week', date_ecriture)::date as ds,
            sum(quantite_normalisee)                 as y
        from {schema}.stg_erp_production_assemblage
        where numero_article = :numero_article
          and is_resultat
        group by 1
        order by 1
    """
    df = pd.read_sql(text(query), engine, params={"numero_article": numero_article})
    df["ds"] = pd.to_datetime(df["ds"])

    events = pd.read_csv(EVENTS_PATH)
    events["semaine"] = pd.to_datetime(events["semaine"])
    df = df.merge(events, left_on="ds", right_on="semaine", how="left")
    df = df.drop(columns=["semaine"]).fillna(0)

    q1 = df["y"].quantile(0.25)
    q3 = df["y"].quantile(0.75)
    iqr = q3 - q1
    seuil_haut = q3 + 3.0 * iqr
    df["is_outlier"] = (df["y"] > seuil_haut).astype(int)
    if df["is_outlier"].sum() > 0:
        logger.info("  %d outlier(s) détecté(s) (seuil %.0f)", df["is_outlier"].sum(), seuil_haut)

    return df


def _merge_regressors(futur: pd.DataFrame, historique: pd.DataFrame) -> pd.DataFrame:
    historique = historique.copy()
    historique["ds"] = pd.to_datetime(historique["ds"])
    futur["ds"] = pd.to_datetime(futur["ds"])

    for col in REGRESSOR_COLS:
        if col in historique.columns:
            futur = futur.merge(historique[["ds", col]], on="ds", how="left")
            futur[col] = futur[col].fillna(0)

    return futur


def evaluer_precision(historique: pd.DataFrame, validation_cfg: dict) -> dict:
    """Validation rétrospective à l'intérieur de 2023 (une seule année dispo)."""
    train_cutoff = pd.Timestamp(validation_cfg["train_cutoff"])
    test_start = pd.Timestamp(validation_cfg["test_start"])
    test_end = pd.Timestamp(validation_cfg["test_end"])

    train = historique[historique["ds"] < train_cutoff]
    test = historique[(historique["ds"] >= test_start) & (historique["ds"] <= test_end)]

    if len(train) < 10 or len(test) == 0:
        return {"mape": None, "nb_semaines_test": len(test)}

    model = Prophet(weekly_seasonality=False, yearly_seasonality=False, daily_seasonality=False, interval_width=0.80)
    for col in REGRESSOR_COLS:
        if col in train.columns and train[col].nunique() > 1:
            model.add_regressor(col)
    model.fit(train)

    futur = model.make_future_dataframe(periods=len(test), freq="W-MON")
    futur = _merge_regressors(futur, historique)

    prevision = model.predict(futur)
    prevision_test = prevision[prevision["ds"] >= test_start]
    merged = test.merge(prevision_test[["ds", "yhat"]], on="ds", how="inner")

    if len(merged) == 0:
        return {"mape": None, "nb_semaines_test": 0}

    merged["erreur_pct"] = abs(merged["y"] - merged["yhat"]) / merged["y"].replace(0, pd.NA)
    mape = merged["erreur_pct"].mean() * 100

    wmape = (merged["y"] - merged["yhat"]).abs().sum() / merged["y"].sum() * 100

    return {"mape": round(mape, 2), "wmape": round(wmape, 2), "nb_semaines_test": len(merged)}


def forecast_article(historique: pd.DataFrame, horizon_semaines: int) -> pd.DataFrame | None:
    try:
        model = Prophet(weekly_seasonality=False, yearly_seasonality=False, daily_seasonality=False, interval_width=0.80)

        for col in REGRESSOR_COLS:
            if col in historique.columns and historique[col].nunique() > 1:     
                model.add_regressor(col)

        model.fit(historique)

        futur = model.make_future_dataframe(periods=horizon_semaines, freq="W-MON")
        futur = _merge_regressors(futur, historique)

        prevision = model.predict(futur)
        prevision["yhat"] = prevision["yhat"].clip(lower=0)                     
        prevision["yhat_lower"] = prevision["yhat_lower"].clip(lower=0)
        prevision["yhat_upper"] = prevision["yhat_upper"].clip(lower=0)
        return prevision[["ds", "yhat", "yhat_lower", "yhat_upper"]]
    except Exception as exc:
        logger.warning("Prophet a échoué : %s", exc)
        return None


def run():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

    config = load_config()
    engine = get_engine()

    articles = get_articles_a_prevoir(engine, config)
    logger.info("%d articles à prévoir (top production 2023)", len(articles))

    resultats = []
    articles_ignores = []
    articles_echoues = []
    precisions = []

    for _, row in articles.iterrows():
        hist = get_historique_hebdo(engine, row["numero_article"], config)

        if len(hist) < config["min_semaines_historique"]:
            articles_ignores.append((row["numero_article"], len(hist)))
            continue

        perf = evaluer_precision(hist, config["validation"])
        if perf["mape"] is not None:
            precisions.append({
                "numero_article": row["numero_article"],
                "mape_pct": perf["mape"],
                "nb_semaines_test": perf["nb_semaines_test"],
                "wmape_pct": perf["wmape"]
            })

        prevision = forecast_article(hist, config["horizon_semaines"])
        if prevision is None:
            articles_echoues.append(row["numero_article"])
            continue

        prevision["numero_article"] = row["numero_article"]
        prevision["is_historique"] = prevision["ds"].isin(hist["ds"])
        resultats.append(prevision)

    if articles_ignores:
        logger.info("Articles ignorés (historique insuffisant, < %d semaines) : %d",
                     config["min_semaines_historique"], len(articles_ignores))
    if articles_echoues:
        logger.warning("Articles échoués (Prophet) : %d", len(articles_echoues))

    if precisions:
        df_perf = pd.DataFrame(precisions)
        df_perf["prevision_fiable"] = df_perf["wmape_pct"] < 50
        logger.info("=== PRÉCISION RÉTROSPECTIVE (intérieur 2023, test court — voir limite documentée) ===")
        logger.info("WMAPE moyen : %.1f%% (sur %d articles)", df_perf["wmape_pct"].mean(), len(df_perf))
        logger.info("Prévisions fiables (WMAPE < 50%%) : %d/%d articles", df_perf["prevision_fiable"].sum(), len(df_perf))

        schema, table = config["table_sortie"].split(".")
        schema = _sanitize_identifier(schema)
        perf_table = _sanitize_identifier(table + "_performance")
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        df_perf.to_sql(perf_table, engine, schema=schema, if_exists="replace", index=False)

    if not resultats:
        logger.warning("Aucun article prévu.")
        return

    df_final = pd.concat(resultats, ignore_index=True).rename(columns={
        "ds": "semaine", "yhat": "quantite_prevue",
        "yhat_lower": "quantite_prevue_min", "yhat_upper": "quantite_prevue_max",
    })
    df_final["quantite_prevue"] = df_final["quantite_prevue"].clip(lower=0)
    df_final["quantite_prevue_min"] = df_final["quantite_prevue_min"].clip(lower=0)

    schema, table = config["table_sortie"].split(".")
    schema = _sanitize_identifier(schema)
    table = _sanitize_identifier(table)

    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

    df_final.to_sql(table, engine, schema=schema, if_exists="replace", index=False)
    logger.info("Prévisions enregistrées dans %s.%s (%d lignes)", schema, table, len(df_final))


if __name__ == "__main__":
    run()
































    