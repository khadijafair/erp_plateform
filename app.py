"""Plateforme collaborative ERP — Interface non-IT.

Toutes les actions qui déclenchent quelque chose (mapping IA, pipeline)
passent par l'API (api.py), jamais par subprocess direct.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
import yaml
from sqlalchemy import create_engine, text

BASE_DIR = Path(__file__).parent
API_URL = os.getenv("API_URL", "http://localhost:5000")
st.set_page_config(page_title="ERP Platform", page_icon="📊", layout="wide")

st.markdown(
    """
    <style>
    .stMetric { background-color: #f8f9fb; padding: 12px; border-radius: 10px; border: 1px solid #e5e7eb; }
    div[data-testid="stSidebar"] { background-color: #1f3864; }
    div[data-testid="stSidebar"] * { color: #f0f2f6 !important; }
    .phase-ok { color: #16a34a; font-weight: 600; }
    .phase-en-cours { color: #d97706; font-weight: 600; }
    .phase-attente { color: #9ca3af; }
    .phase-echec { color: #dc2626; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def check_postgres() -> bool:
    try:
        engine = create_engine(
            os.getenv("DATABASE_URL", "postgresql://erp_admin:changeme@localhost:5432/erp_platform")
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def check_ollama() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def check_api() -> bool:
    try:
        r = requests.get(f"{API_URL}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def get_last_run() -> str:
    try:
        engine = create_engine(
            os.getenv("DATABASE_URL", "postgresql://erp_admin:changeme@localhost:5432/erp_platform")
        )
        with engine.connect() as conn:
            val = conn.execute(text("SELECT MAX(_ingested_at) FROM raw.erp_ventes_achats")).scalar()
        return str(val)[:16] if val else "Jamais"
    except Exception:
        return "Jamais"


def run_ollama_mapping_via_api(file_name: str, source_id: str, domaine: str) -> dict:
    try:
        r = requests.post(
            f"{API_URL}/api/discover-mapping",
            json={"file": f"data/raw/{file_name}", "source_id": source_id, "domaine": domaine},
            timeout=300,
        )
        r.raise_for_status()
        data = r.json()
        return {
            "success": data["draft_generated"],
            "draft_path": data["draft_path"],
            "preview": pd.DataFrame(data["preview"]),
            "stdout": data["stdout"],
            "stderr": data["stderr"],
        }
    except requests.exceptions.Timeout:
        return {"success": False, "preview": pd.DataFrame(), "stdout": "", "stderr": "Délai dépassé — Ollama n'a pas répondu à temps."}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "preview": pd.DataFrame(), "stdout": "", "stderr": f"Erreur API : {exc}"}


def run_phase_via_api(endpoint: str, timeout: int) -> dict:
    """Appelle un endpoint /api/pipeline/<phase> et renvoie {success, error}."""
    try:
        r = requests.post(f"{API_URL}{endpoint}", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        return {"success": False, "error": f"Délai dépassé (>{timeout}s)"}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "error": str(exc)}


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("📊 ERP Platform")
st.sidebar.caption("Plateforme Data Engineering + IA")
page = st.sidebar.radio(
    "Menu",
    ["🏠 Accueil", "📤 Upload & Mapping IA", "✅ Valider & Lancer", "📈 Résultats"],
)
st.sidebar.divider()
st.sidebar.caption(f"API : {'🟢 connectée' if check_api() else '🔴 injoignable'}")


# ============================================================
# PAGE 1 : ACCUEIL
# ============================================================

if page == "🏠 Accueil":
    st.title("Plateforme de Données ERP")
    st.markdown("""
    Bienvenue ! Cette interface vous permet de :
    1. **Uploader** un fichier Excel de l'ERP
    2. Laisser l'**IA (Ollama)** proposer un mapping des colonnes
    3. **Valider** le mapping proposé
    4. **Lancer** le pipeline automatiquement
    5. **Visualiser** les résultats dans Power BI

    > Aucune compétence technique requise.
    """)

    st.subheader("État du système")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("PostgreSQL", "🟢 En ligne" if check_postgres() else "🔴 Hors ligne")
    with col2:
        st.metric("Ollama IA", "🟢 En ligne" if check_ollama() else "🔴 Hors ligne")
    with col3:
        st.metric("API", "🟢 En ligne" if check_api() else "🔴 Hors ligne")
    with col4:
        st.metric("Dernier pipeline", get_last_run())


# ============================================================
# PAGE 2 : UPLOAD & MAPPING IA
# ============================================================

elif page == "📤 Upload & Mapping IA":
    st.title("Étape 1 : Uploader un fichier Excel")

    uploaded_file = st.file_uploader("Choisissez un fichier Excel", type=["xlsx", "xls"])

    if uploaded_file is not None:
        raw_dir = BASE_DIR / "data" / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        file_path = raw_dir / uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getvalue())

        st.success(f"Fichier sauvegardé : {uploaded_file.name}")

        df = pd.read_excel(file_path, nrows=10)
        st.subheader("Aperçu des données (10 premières lignes)")
        st.dataframe(df, use_container_width=True)

        st.subheader("Paramètres de l'analyse IA")
        source_id = st.text_input("Identifiant de la source", value="nouvelle_source")
        domaine = st.selectbox("Domaine métier", ["ventes", "achats", "production", "rh", "autre"])

        if st.button("🤖 Lancer l'analyse IA (Ollama)", type="primary"):
            with st.spinner("L'IA analyse les colonnes... (30-120 secondes)"):
                result = run_ollama_mapping_via_api(uploaded_file.name, source_id, domaine)

            if result["success"]:
                st.success("Mapping généré ! Passez à l'étape de validation.")
                st.session_state["draft_path"] = result["draft_path"]
                st.session_state["preview"] = result["preview"]
            else:
                st.error("L'IA a rencontré une erreur")
                st.code(result["stderr"])

        if "preview" in st.session_state:
            st.subheader("Mapping proposé par l'IA")
            st.dataframe(st.session_state["preview"], use_container_width=True)
            st.info("👉 Allez dans l'onglet '✅ Valider & Lancer' pour confirmer")


# ============================================================
# PAGE 3 : VALIDER & LANCER — avec vraie progression par phase
# ============================================================

elif page == "✅ Valider & Lancer":
    st.title("Étape 2 : Valider le mapping et lancer le pipeline")

    draft_dir = BASE_DIR / "config" / "sources"
    drafts = list(draft_dir.glob("_draft_*.yaml"))

    if not drafts:
        st.warning("Aucun brouillon de mapping trouvé. Allez d'abord dans 'Upload & Mapping IA'.")
        st.stop()

    selected_draft = st.selectbox("Brouillon à valider", [d.name for d in drafts])

    draft_path = draft_dir / selected_draft
    with open(draft_path, encoding="utf-8") as f:
        draft_content = f.read()

    st.subheader("Contenu du mapping (modifiable)")
    edited = st.text_area("YAML", value=draft_content, height=300)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Sauvegarder les modifications"):
            with open(draft_path, "w", encoding="utf-8") as f:
                f.write(edited)
            st.success("Modifications sauvegardées")

    with col2:
        lancer = st.button("🚀 Lancer le pipeline complet", type="primary")

    if lancer:
        final_name = selected_draft.replace("_draft_", "")
        final_path = draft_dir / final_name
        with open(draft_path, encoding="utf-8") as f:
            content = f.read()
        with open(final_path, "w", encoding="utf-8") as f:
            f.write(content)

        phases = [
            ("Ingestion (Excel → PostgreSQL)", "/api/pipeline/ingestion", 120),
            ("Transformation dbt (staging → marts + tests)", "/api/pipeline/dbt", 180),
            ("Prévisions Prophet", "/api/pipeline/forecast", 120),
        ]

        progress_bar = st.progress(0)
        statut_placeholder = st.empty()
        erreur = None

        for i, (label, endpoint, timeout) in enumerate(phases):
            lignes_statut = []
            for j, (l2, _, _) in enumerate(phases):
                if j < i:
                    lignes_statut.append(f'<span class="phase-ok">✅ {l2}</span>')
                elif j == i:
                    lignes_statut.append(f'<span class="phase-en-cours">⏳ {l2} (en cours...)</span>')
                else:
                    lignes_statut.append(f'<span class="phase-attente">⬜ {l2}</span>')
            statut_placeholder.markdown("<br>".join(lignes_statut), unsafe_allow_html=True)

            resultat = run_phase_via_api(endpoint, timeout)

            if not resultat.get("success"):
                erreur = resultat.get("error", "Erreur inconnue")
                lignes_statut[i] = f'<span class="phase-echec">❌ {label} — ÉCHEC</span>'
                statut_placeholder.markdown("<br>".join(lignes_statut), unsafe_allow_html=True)
                break

            progress_bar.progress(int((i + 1) / len(phases) * 100))

        if erreur:
            st.error(f"❌ Le pipeline s'est arrêté : {erreur}")
        else:
            lignes_finales = [f'<span class="phase-ok">✅ {l}</span>' for l, _, _ in phases]
            statut_placeholder.markdown("<br>".join(lignes_finales), unsafe_allow_html=True)
            st.success("✅ Pipeline terminé avec succès !")
            st.balloons()
            st.info("Les données sont prêtes dans Power BI.")


# ============================================================
# PAGE 4 : RÉSULTATS
# ============================================================

elif page == "📈 Résultats":
    st.title("Étape 3 : Vérifier les résultats")

    try:
        engine = create_engine(
            os.getenv("DATABASE_URL", "postgresql://erp_admin:changeme@localhost:5432/erp_platform")
        )

        st.subheader("Volumes de données")
        col1, col2, col3 = st.columns(3)

        with engine.connect() as conn:
            nb_fact = conn.execute(text("SELECT COUNT(*) FROM marts.fact_transactions")).scalar()
            nb_art = conn.execute(text("SELECT COUNT(*) FROM marts.dim_article")).scalar()
            nb_abc = conn.execute(text("SELECT COUNT(*) FROM marts.mart_abc_article")).scalar()

        with col1:
            st.metric("Transactions", f"{nb_fact:,}")
        with col2:
            st.metric("Articles", f"{nb_art:,}")
        with col3:
            st.metric("Articles ABC", f"{nb_abc:,}")

        st.subheader("Classement ABC (Top 20)")
        df_abc = pd.read_sql("SELECT * FROM marts.mart_abc_article ORDER BY rang_ca LIMIT 20", engine)
        st.dataframe(df_abc, use_container_width=True)

        st.subheader("Répartition ABC")
        abc_counts = pd.read_sql(
            "SELECT classe_abc, COUNT(*) as nb FROM marts.mart_abc_article GROUP BY classe_abc", engine
        )
        st.bar_chart(abc_counts.set_index("classe_abc"))

    except Exception as e:
        st.error(f"Impossible de se connecter à la base : {e}")
        st.info("Vérifiez que PostgreSQL est démarré et que le pipeline a été exécuté.")