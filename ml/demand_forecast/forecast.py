"""Module de prévision de la demande par article avec Prophet."""

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

logger = logging.getLogger("erp_forecast")

CONFIG_PATH = Path(__file__).parent / "config.yaml"


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
    query = f"""
        select article_key, numero_article
        from {_sanitize_identifier(config['marts_schema'])}.mart_abc_article
        where {config['perimetre']}
    """
    return pd.read_sql(text(query), engine)


def get_historique_hebdo(engine, article_key: str, config: dict) -> pd.DataFrame:
    query = f"""
        select
            date_trunc('week', d.date_ecriture)::date as ds,
            sum(abs(f.quantite_stock))                 as y
        from {_sanitize_identifier(config['marts_schema'])}.fact_transactions f
        join {_sanitize_identifier(config['marts_schema'])}.dim_date d on f.date_id = d.date_id
        where f.article_key = :article_key
          and f.is_expedition_vente
        group by 1
        order by 1
    """
    df = pd.read_sql(text(query), engine, params={"article_key": article_key})
    df["ds"] = pd.to_datetime(df["ds"])
    return df


def forecast_article(historique: pd.DataFrame, horizon_semaines: int) -> pd.DataFrame | None:
    """Entraîne un modèle Prophet et génère les prévisions."""
    try:
        model = Prophet(
            weekly_seasonality=False,
            yearly_seasonality=True,
            daily_seasonality=False,
            interval_width=0.80,
        )
        model.fit(historique)

        futur = model.make_future_dataframe(periods=horizon_semaines, freq="W")
        prevision = model.predict(futur)

        return prevision[["ds", "yhat", "yhat_lower", "yhat_upper"]]
    except Exception as exc:
        logger.warning("Prophet a échoué sur cet article : %s", exc)
        return None


def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    config = load_config()
    engine = get_engine()

    articles = get_articles_a_prevoir(engine, config)
    resultats = []
    articles_ignores = []
    articles_echoues = []

    logger.info("%d articles à prévoir", len(articles))

    for _, row in articles.iterrows():
        hist = get_historique_hebdo(engine, row["article_key"], config)

        if len(hist) < config["min_semaines_historique"]:
            articles_ignores.append((row["numero_article"], len(hist)))
            continue

        prevision = forecast_article(hist, config["horizon_semaines"])
        if prevision is None:
            articles_echoues.append(row["numero_article"])
            continue

        prevision["article_key"] = row["article_key"]
        prevision["numero_article"] = row["numero_article"]
        prevision["is_historique"] = prevision["ds"].isin(hist["ds"])
        resultats.append(prevision)

    if articles_ignores:
        logger.info("Articles ignorés (historique insuffisant) : %d", len(articles_ignores))
        for num, n_semaines in articles_ignores:
            logger.info("  - %s : %d semaines", num, n_semaines)

    if articles_echoues:
        logger.warning("Articles échoués (Prophet) : %d", len(articles_echoues))
        for num in articles_echoues:
            logger.warning("  - %s", num)

    if not resultats:
        logger.warning("Aucun article prévu.")
        return

    df_final = pd.concat(resultats, ignore_index=True).rename(
        columns={
            "ds": "semaine",
            "yhat": "quantite_prevue",
            "yhat_lower": "quantite_prevue_min",
            "yhat_upper": "quantite_prevue_max",
        }
    )

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