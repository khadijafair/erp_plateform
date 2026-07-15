"""
Prévision de la demande hebdomadaire, article par article, sur les
articles classe A (les plus vendus, cf mart_abc_article).

Un modèle Prophet distinct est entraîné par article (pas un modèle global) :
chaque article a sa propre saisonnalité et dynamique de vente, un seul
modèle partagé lisserait ces différences.

Usage :
    python -m ml.demand_forecast.forecast
"""
from __future__ import annotations

import os
import warnings
from pathlib import Path

import pandas as pd
import yaml
from prophet import Prophet
from sqlalchemy import create_engine, text

warnings.filterwarnings("ignore")  # Prophet est bruyant sur stdout/warnings, sans impact sur le résultat

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_engine():
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:changeme@localhost:5432/erp_platform")
    return create_engine(database_url)


def get_articles_a_prevoir(engine, config: dict) -> pd.DataFrame:
    query = f"""
        select article_key, numero_article
        from {config['marts_schema']}.mart_abc_article
        where {config['perimetre']}
    """
    return pd.read_sql(text(query), engine)


def get_historique_hebdo(engine, article_key: str, config: dict) -> pd.DataFrame:
    query = f"""
        select
            date_trunc('week', d.date_ecriture)::date as ds,
            sum(abs(f.quantite_stock))                 as y
        from {config['marts_schema']}.fact_transactions f
        join {config['marts_schema']}.dim_date d on f.date_id = d.date_id
        where f.article_key = :article_key
          and f.is_expedition_vente
        group by 1
        order by 1
    """
    df = pd.read_sql(text(query), engine, params={"article_key": article_key})
    df["ds"] = pd.to_datetime(df["ds"])  # aligne le type sur celui produit par Prophet (sinon .isin échoue silencieusement)
    return df


def forecast_article(historique: pd.DataFrame, horizon_semaines: int) -> pd.DataFrame:
    model = Prophet(
        weekly_seasonality=False,   # non pertinent : la donnée est déjà agrégée à la semaine
        yearly_seasonality=True,    # pertinent : effets saisonniers plausibles sur 3 ans d'historique
        daily_seasonality=False,
        interval_width=0.80,
    )
    model.fit(historique)

    futur = model.make_future_dataframe(periods=horizon_semaines, freq="W")
    prevision = model.predict(futur)

    return prevision[["ds", "yhat", "yhat_lower", "yhat_upper"]]


def run():
    config = load_config()
    engine = get_engine()

    articles = get_articles_a_prevoir(engine, config)
    print(f"{len(articles)} article(s) dans le périmètre ({config['perimetre']})")

    resultats = []
    articles_ignores = []

    for _, row in articles.iterrows():
        hist = get_historique_hebdo(engine, row["article_key"], config)

        if len(hist) < config["min_semaines_historique"]:
            articles_ignores.append((row["numero_article"], len(hist)))
            continue

        prevision = forecast_article(hist, config["horizon_semaines"])
        prevision["article_key"] = row["article_key"]
        prevision["numero_article"] = row["numero_article"]
        prevision["is_historique"] = prevision["ds"].isin(hist["ds"])
        resultats.append(prevision)

        print(f"  OK  {row['numero_article']:<25} {len(hist)} semaines d'historique -> prévu")

    if articles_ignores:
        print(f"\n{len(articles_ignores)} article(s) ignoré(s) (historique < {config['min_semaines_historique']} semaines) :")
        for numero, n in articles_ignores:
            print(f"  SKIP {numero:<25} {n} semaines seulement")

    if not resultats:
        print("Aucun article prévisible avec les critères actuels.")
        return

    df_final = pd.concat(resultats, ignore_index=True).rename(columns={
        "ds": "semaine",
        "yhat": "quantite_prevue",
        "yhat_lower": "quantite_prevue_min",
        "yhat_upper": "quantite_prevue_max",
    })
    df_final["quantite_prevue"] = df_final["quantite_prevue"].clip(lower=0)
    df_final["quantite_prevue_min"] = df_final["quantite_prevue_min"].clip(lower=0)

    schema, table = config["table_sortie"].split(".")
    with engine.begin() as conn:
        conn.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    df_final.to_sql(table, engine, schema=schema, if_exists="replace", index=False)
    print(f"\n{len(df_final)} lignes écrites dans {config['table_sortie']}")


if __name__ == "__main__":
    run()