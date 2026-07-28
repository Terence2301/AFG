#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  AFG ASSURANCES BÉNIN VIE — DASHBOARD ACTUARIEL EXPERT v3.0
  Bug-fixes v3 : chargement direct (no pickle) · filtre date corrigé
                 navigation cachée · jointures inter-bases fiables
================================================================================
  LANCEMENT : streamlit run app_afg.py
  LOGIN     : PDG AFG/1001 · ADMIN AFG/1003 · ACTUAIRE AFG/1005 · DEMO/0000
================================================================================
"""
import streamlit as st
st.set_page_config(
    page_title="AFG Bénin Vie — Dashboard Expert",
    page_icon="🛡️", layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "AFG Assurances Bénin Vie v3.0"}
)

# ── Masquer le bouton collapse/expand de la sidebar (flèches ◀ ▶) ────────────────────────────────────────
# Injecté immédiatement après set_page_config pour être actif dès le premier frame.
st.markdown("""
<style>
/* Masquer le bouton collapse/expand (flèches gauche/droite) */
[data-testid="collapsedControl"] { display: none !important; }
button[kind="header"]            { display: none !important; }

/* La sidebar reste toujours visible, jamais rétractable */
section[data-testid="stSidebar"] {
    min-width: 285px !important;
    max-width: 320px !important;
    transform: translateX(0) !important;
    visibility: visible !important;
    display: block !important;
}
section[data-testid="stSidebar"][aria-expanded="false"] {
    margin-left: 0 !important;
    min-width: 285px !important;
}
</style>
""", unsafe_allow_html=True)

import pandas as pd, numpy as np, io, os, tempfile, warnings, hashlib, sqlite3
from datetime import datetime, date
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
warnings.filterwarnings("ignore")

# ── Tentative d'import psycopg2 (PostgreSQL centralisé) ──────────────────────
try:
    import psycopg2
    import psycopg2.extras
    _PSYCOPG2_OK = True
except ImportError:
    _PSYCOPG2_OK = False

# ─────────────────────────────────────────────
#  PALETTE — vert dominant, zéro jaune
# ─────────────────────────────────────────────
NAVY   = "#0D1F3C"
GREEN  = "#1A7F6E"
GREEN2 = "#0F5C4E"
GREEN3 = "#27AE60"
TEAL   = "#148F77"
MINT   = "#A9DFBF"
LGREEN = "#D5F5E3"
RED    = "#C0392B"
AMBER  = "#CA6F1E"
BLUE   = "#1A56A7"
LGRAY  = "#F3F6FA"
MGRAY  = "#DDE3EE"
PAL    = [GREEN,BLUE,RED,TEAL,AMBER,"#6C3483","#117A65","#1A5276","#784212","#1B4F72","#4A235A","#0E6251"]

MOIS_FR   = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"]
MOIS_LONG = ["Janvier","Février","Mars","Avril","Mai","Juin",
             "Juillet","Août","Septembre","Octobre","Novembre","Décembre"]

CODEPERI_MAP = {"U":"Unique","M":"Mensuel","A":"Annuel","T":"Trimestriel","S":"Semestriel","L":"Libre"}

PRODUITS = [
    {"code":"220","nom":"ASSURTOUS Vigninou","grp":"Groupe 1","cat":"Décès"},
    {"code":"221","nom":"ASSURTOUS AVIGBO","grp":"Groupe 1","cat":"Décès"},
    {"code":"EP0","nom":"Épargne","grp":"Groupe 2","cat":"Épargne"},
]

# ── Barèmes AVIGBO (capital garanti selon prime) ──────────────────────────────
# Structure : {prime_mensuelle: (capital, prime_unique)}
AVIGBO_BAREME = {
    100:  (100_000,  1_000),
    200:  (200_000,  2_000),
    300:  (300_000,  3_000),
}

# ── Barèmes VIGNINOU (capital garanti selon prime) ────────────────────────────
# Durée max : 12 mois
# Structure : {prime_mensuelle: (capital, prime_unique)}
VIGNINOU_BAREME = {
    400:  (500_000,   48_000),
    800:  (1_000_000, 96_000),
    1200: (1_500_000, 144_000),
}

# ── Paramètres épargne ────────────────────────────────────────────────────────
ALPHA_EPARGNE = 0.01   # 1 % chargement acquisition
BETA_EPARGNE  = 0.005  # 0.5 % chargement gestion
I_EPARGNE     = 0.035  # 3.5 % taux technique CIMA

PERIO_M = {
    "Journalière": 365,
    "Hebdomadaire": 52,
    "Mensuelle": 12,
    "Trimestrielle": 4,
    "Semestrielle": 2,
    "Annuelle": 1,
    "Unique": 0,  # paiement unique traité séparément
}

def calcul_capital_epargne(P_brut: float, periodicite: str, duree_ans: int,
                            i: float = I_EPARGNE,
                            alpha: float = ALPHA_EPARGNE,
                            beta: float = BETA_EPARGNE) -> dict:
    """
    Capital au terme — FORMULE CORRIGÉE (annuité-due directe par sous-période).

    P_brut  = cotisation brute PAR PÉRIODE (ex. 10 000 FCFA/mois si Mensuelle)
    m       = nb de versements/an  (365 jour / 52 sem / 12 mois / 4 trim / 2 sem / 1 an)
    N       = m × n                (nb total de versements)
    i_pér   = (1+i)^(1/m) − 1     (taux équivalent par sous-période)
    P_net   = P_brut × (1−α−β)    (cotisation nette par période)
    C       = P_net × [(1+i_pér)^N − 1] / i_pér × (1+i_pér)   ← annuité-due

    Vérif : 10 000 F/mois, 5 ans, i=3,5 % → C ≈ 645 797 FCFA ✓
    """
    Pnet  = P_brut * (1 - alpha - beta)
    m     = PERIO_M.get(periodicite, 12)
    n     = duree_ans

    # Cas paiement unique
    if periodicite == "Unique" or m == 0:
        capital   = Pnet * ((1 + i) ** n)
        rend      = (capital / max(Pnet, 1) - 1) * 100
        return {"Pnet": Pnet, "m": 1, "N": n, "i_per": i, "sdot": None,
                "capital_brut": capital, "total_verse": P_brut,
                "total_net": Pnet, "rendement": rend,
                "formule": (f"C = {Pnet:,.0f} × (1+{i*100:.2f}%)^{n}"
                            f" = {capital:,.2f} FCFA  [versement unique]")}

    if n == 0:
        return {"capital_brut": 0, "total_verse": 0, "total_net": 0,
                "rendement": 0, "Pnet": Pnet, "m": m, "N": 0,
                "i_per": 0, "sdot": None, "formule": "Durée = 0"}

    N     = m * n
    i_per = (1 + i) ** (1.0 / m) - 1         # taux équivalent par sous-période
    # Valeur acquise annuité-due N versements de 1 FCFA :
    sdot  = ((1 + i_per) ** N - 1) / i_per * (1 + i_per)
    capital     = Pnet * sdot
    total_verse = P_brut * N
    total_net   = Pnet   * N
    rendement   = (capital / max(total_net, 1) - 1) * 100
    lbl = _fmt_periode_label(periodicite)
    return {
        "Pnet": Pnet, "m": m, "N": N, "i_per": i_per, "sdot": sdot,
        "capital_brut": capital, "total_verse": total_verse,
        "total_net": total_net, "rendement": rendement,
        "formule": (
            f"P_net/{lbl} = {Pnet:,.0f} FCFA  |  "
            f"N = {m}×{n} = {N} vers.  |  "
            f"i_pér = {i_per*100:.5f}%  |  "
            f"s̈ = {sdot:.4f}  |  "
            f"C = {Pnet:,.0f} × {sdot:.4f} = {capital:,.2f} FCFA"
        ),
    }


def _fmt_periode_label(periodicite: str) -> str:
    return {"Journalière":"jour","Hebdomadaire":"sem.","Mensuelle":"mois",
            "Trimestrielle":"trim.","Semestrielle":"sem.","Annuelle":"an",
            "Unique":"unique"}.get(periodicite, periodicite)


def _fmt_periode(periodicite: str) -> str:
    return {"Journalière":"jour","Hebdomadaire":"sem.","Mensuelle":"mois",
            "Trimestrielle":"trim.","Semestrielle":"sem.","Annuelle":"an","Unique":"unique"}.get(periodicite, periodicite)
AGENCES = ["","Siège Social — Cotonou","Agence Cotonou Centre","Agence Cotonou Littoral",
    "Agence Cotonou Cadjèhoun","Agence Porto-Novo","Agence Abomey-Calavi",
    "Agence Parakou","Agence Bohicon","Agence Natitingou","Agence Ouidah",
    "Agence Lokossa","Agence Kandi","Agence Abomey","Agence Djougou","Agence Allada"]

USERS = {
    "PDG AFG":       hashlib.sha256(b"1001").hexdigest(),
    "DG AFG":        hashlib.sha256(b"1002").hexdigest(),
    "ADMIN AFG":     hashlib.sha256(b"1003").hexdigest(),
    "MANAGER AFG":   hashlib.sha256(b"1004").hexdigest(),
    "ACTUAIRE AFG":  hashlib.sha256(b"1005").hexdigest(),
    "DEMO VISITEUR": hashlib.sha256(b"0000").hexdigest(),
}

# ─────────────────────────────────────────────
#  CSS EXPERT
# ─────────────────────────────────────────────
st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap');
html,body,[class*="css"]{{font-family:'DM Sans',sans-serif!important;background:{LGRAY};}}
#MainMenu,footer,header,.stDeployButton,[data-testid="stToolbar"],.stDecoration{{display:none!important}}
.block-container,.stMainBlockContainer{{padding-top:0!important;max-width:100%!important;padding-left:.8rem!important;padding-right:.8rem!important}}
section[data-testid="stSidebar"]{{background:linear-gradient(175deg,{NAVY} 0%,{GREEN2} 100%)!important;border-right:3px solid {GREEN}!important}}
section[data-testid="stSidebar"] *{{color:rgba(255,255,255,.88)!important}}
section[data-testid="stSidebar"] .stRadio label{{background:rgba(255,255,255,.05);border:1px solid rgba(26,127,110,.25);border-radius:8px;padding:7px 10px!important;margin:2px 0;font-size:12px!important;cursor:pointer;transition:.15s all}}
section[data-testid="stSidebar"] .stRadio label:hover{{background:rgba(26,127,110,.22)!important;border-color:{GREEN}!important}}
section[data-testid="stSidebar"] hr{{border-color:rgba(26,127,110,.2)!important}}
section[data-testid="stSidebar"] .stButton>button{{background:rgba(26,127,110,.2)!important;border:1px solid {GREEN}!important;color:{MINT}!important;border-radius:8px!important;font-weight:700!important;width:100%;font-size:11px!important}}
.afg-bar{{background:linear-gradient(135deg,{NAVY},{GREEN2});padding:.75rem 1.3rem;border-bottom:3px solid {GREEN};display:flex;align-items:center;justify-content:space-between;box-shadow:0 4px 20px rgba(0,0,0,.2);margin-bottom:12px}}
.afg-logo{{width:44px;height:44px;background:linear-gradient(135deg,{GREEN},{GREEN3});border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:900;color:white;line-height:1.2;text-align:center;box-shadow:0 4px 14px rgba(26,127,110,.5);flex-shrink:0}}
.kc{{background:white;border-radius:12px;padding:.9rem 1rem .8rem;border-left:4px solid {GREEN};box-shadow:0 2px 8px rgba(13,31,60,.07);transition:transform .15s,box-shadow .15s}}
.kc:hover{{transform:translateY(-2px);box-shadow:0 6px 22px rgba(13,31,60,.12)}}
.kc.red{{border-left-color:{RED}}}.kc.blue{{border-left-color:{BLUE}}}.kc.teal{{border-left-color:{TEAL}}}.kc.amber{{border-left-color:{AMBER}}}
.kl{{font-size:9px;font-weight:700;color:#6B7A99;text-transform:uppercase;letter-spacing:.09em;margin-bottom:2px}}
.kv{{font-size:1.35rem;font-weight:800;color:{NAVY};line-height:1;margin-bottom:2px;font-family:'DM Mono',monospace}}
.ks{{font-size:10px;color:#8899AA}}
.stt{{font-size:13px;font-weight:700;color:{NAVY};border-bottom:2px solid {GREEN};padding-bottom:4px;margin:12px 0 7px;display:flex;align-items:center;gap:8px}}
.stg{{background:{GREEN};color:white;font-size:8px;font-weight:800;padding:2px 6px;border-radius:3px}}
.al{{border-radius:8px;padding:8px 12px;font-size:11.5px;border-left:4px solid;margin-bottom:6px}}
.al.good{{background:{LGREEN};border-color:{GREEN};color:{GREEN2}}}
.al.warn{{background:#FDF0E0;border-color:{AMBER};color:#7B3C00}}
.al.danger{{background:#FDECEA;border-color:{RED};color:#7B1414}}
.al.info{{background:#E8F4FF;border-color:{BLUE};color:#003366}}
.stTabs [data-baseweb="tab-list"]{{background:white!important;border-bottom:2px solid {MGRAY}!important}}
.stTabs [data-baseweb="tab"]{{font-weight:600!important;font-size:12px!important;color:#6B7A99!important;padding:8px 13px!important}}
.stTabs [aria-selected="true"]{{color:{NAVY}!important;border-bottom:3px solid {GREEN}!important;background:{LGREEN}!important}}
[data-testid="stDataFrame"]{{border-radius:8px!important;border:1px solid {MGRAY}!important;overflow:hidden!important}}
.stDownloadButton>button{{background:{GREEN}!important;color:white!important;border:none!important;border-radius:7px!important;font-weight:700!important;font-size:11px!important}}
.stButton>button{{background:{NAVY}!important;color:white!important;border:none!important;border-radius:8px!important;font-weight:700!important;font-size:11px!important}}
.nav-btn-active{{background:{GREEN}!important;border-left:4px solid {MINT}!important}}
</style>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  UTILITAIRES
# ─────────────────────────────────────────────
def fmt(v, u="FCFA"):
    if v is None: return "—"
    try: v = float(v)
    except: return "—"
    if np.isnan(v): return "—"
    if abs(v) >= 1e9: return f"{v/1e9:.3f} Mrd {u}"
    if abs(v) >= 1e6: return f"{v/1e6:.3f} M {u}"
    if abs(v) >= 1e3: return f"{v/1e3:.0f} K {u}"
    return f"{v:,.0f} {u}"

def pct(v, d=1):
    try: return f"{float(v or 0):.{d}f}%"
    except: return "—%"

def ds(d):
    try: return pd.Timestamp(d).strftime("%d/%m/%Y")
    except: return str(d) if d else ""

def clean_num(s):
    if hasattr(s,"dtype") and s.dtype.kind in ("f","i","u"): return s.astype("float64")
    return pd.to_numeric(
        s.astype(str).str.strip()
         .str.replace("\xa0","",regex=False).str.replace("\u202f","",regex=False)
         .str.replace(" ","",regex=False).str.replace(",",".",regex=False),
        errors="coerce")

def dl_csv(df):
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

def dl_xlsx(df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w: df.to_excel(w, index=False)
    return buf.getvalue()

def kpi(col, label, value, sub="", color="", icon=""):
    col.markdown(f"""<div class="kc {color}">
      <div class="kl">{icon} {label}</div>
      <div class="kv">{value}</div>
      <div class="ks">{sub}</div>
    </div>""", unsafe_allow_html=True)

def section(title, tag=""):
    tg = f'<span class="stg">{tag}</span>' if tag else ""
    st.markdown(f'<div class="stt">{title} {tg}</div>', unsafe_allow_html=True)

def alert(msg, typ="info"):
    cls = {"info":"info","good":"good","warn":"warn","danger":"danger"}[typ]
    ic  = {"info":"ℹ️","good":"✅","warn":"⚠️","danger":"🚨"}[typ]
    st.markdown(f'<div class="al {cls}">{ic} {msg}</div>', unsafe_allow_html=True)

def fig_style(fig, h=420, title=""):
    fig.update_layout(
        height=h, plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="DM Sans,sans-serif", size=11, color="#2C3E50"),
        margin=dict(l=50,r=25,t=44 if title else 16,b=50),
        title=dict(text=title, font=dict(size=12.5,color=NAVY), x=.01) if title else {},
        legend=dict(orientation="h",y=1.02,x=0,bgcolor="rgba(255,255,255,.9)",
                    bordercolor=MGRAY,borderwidth=1),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="white",bordercolor=NAVY,font_size=12))
    fig.update_xaxes(showgrid=True,gridwidth=1,gridcolor="#EEF2F7",showline=True,linecolor=MGRAY)
    fig.update_yaxes(showgrid=True,gridwidth=1,gridcolor="#EEF2F7")
    return fig

# ══════════════════════════════════════════════════════════════════════════════
#  BASE BIA — CENTRALISÉE (PostgreSQL) avec fallback SQLite local
#
#  ARCHITECTURE :
#    • PostgreSQL (Supabase / Neon / serveur AFG) → base partagée entre tous
#      les utilisateurs, persistante entre les rechargements.
#    • SQLite local → fallback automatique si PostgreSQL non configuré
#      (utile pour les tests en local avant déploiement).
#
#  CONFIGURATION PostgreSQL :
#    Définir la variable d'environnement DATABASE_URL dans :
#      - Streamlit Cloud : Settings → Secrets → [database] url = "..."
#      - Ou fichier .streamlit/secrets.toml :
#          [database]
#          url = "postgresql://user:password@host:5432/dbname"
#
#  FORMAT URL : postgresql://USER:PASSWORD@HOST:PORT/DBNAME
#  Exemple Supabase : postgresql://postgres:xxx@db.xxx.supabase.co:5432/postgres
#  Exemple Neon     : postgresql://user:pwd@ep-xxx.neon.tech/neondb?sslmode=require
# ══════════════════════════════════════════════════════════════════════════════

# ── Lecture de la config base de données ─────────────────────────────────────
def _get_db_url() -> str | None:
    """
    Cherche l'URL PostgreSQL dans :
    1. st.secrets["database"]["url"]   (Streamlit Cloud / secrets.toml)
    2. Variable d'environnement DATABASE_URL
    Retourne None si aucune URL n'est trouvée → fallback SQLite.
    """
    try:
        url = st.secrets["database"]["url"]
        if url and url.startswith("postgresql"):
            return url
    except Exception:
        pass
    env_url = os.environ.get("DATABASE_URL", "")
    if env_url.startswith("postgresql") or env_url.startswith("postgres"):
        # Neon/Heroku écrivent parfois "postgres://" → normaliser
        return env_url.replace("postgres://", "postgresql://", 1)
    return None

_DB_URL  = _get_db_url()
_USE_PG  = _PSYCOPG2_OK and _DB_URL is not None
_DB_FILE = "afg_bia.db"   # fallback SQLite local

# ── DDL commun (syntaxe compatible PG et SQLite) ─────────────────────────────
_DDL = """
CREATE TABLE IF NOT EXISTS bulletins_bia (
    id              SERIAL PRIMARY KEY,
    numero_bia      TEXT UNIQUE,
    date_saisie     TEXT, saisi_par TEXT, agence TEXT,
    code_apporteur  TEXT, nom_apporteur TEXT, realisateur TEXT,
    deja_assure     TEXT, num_ct_exist TEXT,
    c_titre TEXT, c_nom TEXT, c_prenom TEXT, c_ddn TEXT,
    c_lieu TEXT, c_nat TEXT, c_mat TEXT, c_prof TEXT,
    c_adr TEXT, c_bp TEXT, c_email TEXT, c_wapp TEXT,
    c_tel TEXT, c_fixe TEXT, c_npi TEXT,
    ass_meme        INTEGER DEFAULT 1,
    a_titre TEXT, a_nom TEXT, a_prenom TEXT, a_ddn TEXT, a_npi TEXT,
    benef_conj      INTEGER DEFAULT 1, benef_autres TEXT,
    code_produit TEXT, produit TEXT, groupe_produit TEXT,
    cotisation      REAL DEFAULT 0, cotisation_lettres TEXT, periodicite TEXT,
    date_effet TEXT, duree INTEGER, option_gar TEXT,
    mode_reglement TEXT, mode_ref TEXT, capital_terme REAL DEFAULT 0,
    q1 TEXT,q1d TEXT,q2 TEXT,q2d TEXT,q3 TEXT,q3d TEXT,
    q4 TEXT,q4d TEXT,q5 TEXT,q5d TEXT,
    q6 TEXT,q6d TEXT,q7 TEXT,q7d TEXT,
    decl_cond INTEGER DEFAULT 0, decl_data INTEGER DEFAULT 0,
    statut TEXT DEFAULT 'Brouillon', obs TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""
# SQLite n'accepte pas SERIAL → on remplace
_DDL_SQLITE = _DDL.replace(
    "id              SERIAL PRIMARY KEY",
    "id              INTEGER PRIMARY KEY AUTOINCREMENT"
)

# ── Connexion ─────────────────────────────────────────────────────────────────
def get_conn():
    """
    Retourne une connexion active.
    • PostgreSQL si DATABASE_URL configurée et psycopg2 disponible.
    • SQLite local sinon.
    La connexion est NON mise en cache (chaque appel ouvre/ferme proprement).
    """
    if _USE_PG:
        conn = psycopg2.connect(_DB_URL, connect_timeout=10)
        conn.autocommit = False
        return conn
    return sqlite3.connect(_DB_FILE, check_same_thread=False)

def _is_pg(conn) -> bool:
    return _USE_PG and hasattr(conn, "cursor") and not isinstance(conn, sqlite3.Connection)

# ── Init tables (BIA + persistance bases partagées) ──────────────────────────
# Stockage Parquet compressé en blob/bytea pour les 3 bases Excel
_DDL_BASES_META = """
CREATE TABLE IF NOT EXISTS bases_metadata (
    id          SERIAL PRIMARY KEY,
    base_type   TEXT NOT NULL,
    fichier     TEXT,
    taille_mb   REAL DEFAULT 0,
    nb_lignes   INTEGER DEFAULT 0,
    nb_fichiers INTEGER DEFAULT 1,
    charge_par  TEXT,
    charge_le   TEXT
)
"""
_DDL_BASES_META_SQ = _DDL_BASES_META.replace(
    "SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")

_DDL_DATA = """
CREATE TABLE IF NOT EXISTS bases_data (
    base_type    TEXT PRIMARY KEY,
    data_parquet BYTEA,
    updated_at   TEXT
)
"""
_DDL_DATA_SQ = _DDL_DATA.replace("BYTEA", "BLOB")

def init_db():
    """Crée toutes les tables (idempotent)."""
    try:
        conn = get_conn()
        cur  = conn.cursor()
        pg   = _is_pg(conn)
        cur.execute(_DDL    if pg else _DDL_SQLITE)
        cur.execute(_DDL_BASES_META if pg else _DDL_BASES_META_SQ)
        cur.execute(_DDL_DATA       if pg else _DDL_DATA_SQ)
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        st.warning(f"⚠️ Init DB : {e}")
# ── Numéro BIA unique ─────────────────────────────────────────────────────────
def gen_bia() -> str:
    """Génère un numéro BIA séquentiel unique, robuste multi-utilisateurs."""
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM bulletins_bia")
        n = cur.fetchone()[0] + 1
        cur.close(); conn.close()
    except Exception:
        import time; n = int(time.time()) % 100000
    return f"BIA-{datetime.now().year}-{str(n).zfill(5)}"

# ── Lire tous les BIA ────────────────────────────────────────────────────────
def bia_all() -> pd.DataFrame:
    """Retourne tous les bulletins BIA triés du plus récent au plus ancien."""
    try:
        conn = get_conn()
        if _is_pg(conn):
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM bulletins_bia ORDER BY created_at DESC")
            rows = cur.fetchall()
            cur.close(); conn.close()
            return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
        else:
            df = pd.read_sql(
                "SELECT * FROM bulletins_bia ORDER BY created_at DESC", conn)
            conn.close()
            return df
    except Exception as e:
        st.error(f"Erreur lecture BIA : {e}")
        return pd.DataFrame()

# ── Insérer un BIA ───────────────────────────────────────────────────────────
def insert_bia(data: dict) -> bool:
    """
    Insère un bulletin BIA.
    Compatible PostgreSQL (%s) et SQLite (?).
    Retourne True si succès, False sinon.
    """
    try:
        conn  = get_conn()
        pg    = _is_pg(conn)
        ph    = "%s" if pg else "?"   # placeholder selon le driver
        cols  = ", ".join(data.keys())
        phs   = ", ".join([ph] * len(data))
        sql   = f"INSERT INTO bulletins_bia ({cols}) VALUES ({phs})"
        cur   = conn.cursor()
        cur.execute(sql, list(data.values()))
        conn.commit()
        cur.close(); conn.close()
        return True
    except Exception as e:
        st.error(f"❌ Erreur enregistrement BIA : {e}")
        return False

# ── Mise à jour statut ───────────────────────────────────────────────────────
def update_bia_statut(bia_id: int, statut: str):
    """Met à jour le statut d'un BIA (ex. Brouillon → Validé)."""
    try:
        conn = get_conn()
        ph   = "%s" if _is_pg(conn) else "?"
        cur  = conn.cursor()
        cur.execute(f"UPDATE bulletins_bia SET statut={ph} WHERE id={ph}",
                    [statut, bia_id])
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        st.error(f"Erreur mise à jour BIA : {e}")

# ── Suppression BIA ───────────────────────────────────────────────────────────
def delete_bia(bia_id: int):
    """Supprime un BIA par son id."""
    try:
        conn = get_conn()
        ph   = "%s" if _is_pg(conn) else "?"
        cur  = conn.cursor()
        cur.execute(f"DELETE FROM bulletins_bia WHERE id={ph}", [bia_id])
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        st.error(f"Erreur suppression BIA : {e}")

# ── Indicateur de mode (affiché dans la sidebar) ─────────────────────────────
_BIA_MODE = "🌐 PostgreSQL centralisé" if _USE_PG else "💾 SQLite local (non partagé)"

init_db()


# ══════════════════════════════════════════════════════════════════════════════
#  PERSISTANCE DES 3 BASES EXCEL — stockage Parquet en base centralisée
#  Les DataFrames sont sérialisés en Parquet (compact, typé) puis stockés
#  en bytea/BLOB dans PostgreSQL. Toutes les sessions lisent la même version.
# ══════════════════════════════════════════════════════════════════════════════

def _df_to_parquet_bytes(df: pd.DataFrame) -> bytes:
    """Sérialise un DataFrame en Parquet compressé (snappy)."""
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, compression="snappy")
    return buf.getvalue()

def _parquet_bytes_to_df(b) -> pd.DataFrame:
    """Désérialise des bytes Parquet → DataFrame."""
    if isinstance(b, memoryview):
        b = bytes(b)
    return pd.read_parquet(io.BytesIO(b))

def save_base(base_type: str, df: pd.DataFrame,
              fichier: str, charge_par: str) -> bool:
    """
    Persiste un DataFrame dans la table bases_data.
    base_type : "pf" | "ca" | "sin"
    Écrase la version précédente (UPSERT).
    """
    try:
        data_bytes = _df_to_parquet_bytes(df)
        now        = datetime.now().isoformat()
        conn = get_conn()
        pg   = _is_pg(conn)
        ph   = "%s" if pg else "?"
        cur  = conn.cursor()
        if pg:
            cur.execute(
                f"INSERT INTO bases_data (base_type, data_parquet, updated_at) "
                f"VALUES ({ph},{ph},{ph}) "
                f"ON CONFLICT (base_type) DO UPDATE "
                f"SET data_parquet=EXCLUDED.data_parquet, "
                f"    updated_at=EXCLUDED.updated_at",
                [base_type, psycopg2.Binary(data_bytes), now])
        else:
            cur.execute(
                f"INSERT OR REPLACE INTO bases_data "
                f"(base_type, data_parquet, updated_at) VALUES ({ph},{ph},{ph})",
                [base_type, data_bytes, now])
        # Upsert métadonnées
        if pg:
            cur.execute(
                f"INSERT INTO bases_metadata "
                f"(base_type,fichier,taille_mb,nb_lignes,charge_par,charge_le) "
                f"VALUES ({ph},{ph},{ph},{ph},{ph},{ph}) "
                f"ON CONFLICT DO NOTHING",
                [base_type, fichier, round(len(data_bytes)/1e6,2),
                 len(df), charge_par, now])
        else:
            cur.execute(
                f"INSERT OR REPLACE INTO bases_metadata "
                f"(base_type,fichier,taille_mb,nb_lignes,charge_par,charge_le) "
                f"VALUES ({ph},{ph},{ph},{ph},{ph},{ph})",
                [base_type, fichier, round(len(data_bytes)/1e6,2),
                 len(df), charge_par, now])
        conn.commit(); cur.close(); conn.close()
        return True
    except Exception as e:
        st.error(f"❌ Erreur sauvegarde base {base_type} : {e}")
        return False

def load_base(base_type: str):
    """
    Charge un DataFrame depuis la base centralisée.
    Retourne (DataFrame, metadata_dict) ou (None, None) si absent.
    """
    try:
        conn = get_conn()
        pg   = _is_pg(conn)
        ph   = "%s" if pg else "?"
        cur  = conn.cursor()
        cur.execute(f"SELECT data_parquet, updated_at FROM bases_data WHERE base_type={ph}",
                    [base_type])
        row = cur.fetchone()
        cur.close(); conn.close()
        if not row:
            return None, None
        df = _parquet_bytes_to_df(row[0])
        meta = {"updated_at": row[1]}
        return df, meta
    except Exception as e:
        return None, None

def delete_base(base_type: str) -> bool:
    """Supprime une base de la table centralisée."""
    try:
        conn = get_conn()
        ph   = "%s" if pg else "?" if not _is_pg(conn) else "%s"
        pg   = _is_pg(conn)
        ph   = "%s" if pg else "?"
        cur  = conn.cursor()
        cur.execute(f"DELETE FROM bases_data WHERE base_type={ph}", [base_type])
        cur.execute(f"DELETE FROM bases_metadata WHERE base_type={ph}", [base_type])
        conn.commit(); cur.close(); conn.close()
        return True
    except Exception as e:
        st.error(f"❌ Erreur suppression base {base_type} : {e}")
        return False

def get_bases_meta() -> dict:
    """Retourne les métadonnées des bases chargées {base_type: dict}."""
    try:
        conn = get_conn()
        pg   = _is_pg(conn)
        cur  = conn.cursor()
        cur.execute("SELECT base_type,fichier,taille_mb,nb_lignes,charge_par,charge_le "
                    "FROM bases_metadata ORDER BY charge_le DESC")
        rows = cur.fetchall()
        cur.close(); conn.close()
        meta = {}
        for r in rows:
            meta[r[0]] = {
                "fichier": r[1], "taille_mb": r[2],
                "nb_lignes": r[3], "charge_par": r[4], "charge_le": r[5]
            }
        return meta
    except Exception:
        return {}

# ── Rôles admin (seuls ces rôles peuvent charger/supprimer les bases) ─────────
ADMIN_ROLES = {"PDG", "DG", "ADMIN"}

def is_admin(user_dict: dict) -> bool:
    return user_dict.get("role","").upper() in ADMIN_ROLES

# ══════════════════════════════════════════════════════════════════════════════
#  CHARGEMENT OPTIMISÉ — lecture directe, colonnes filtrées, typage minimal
#  Fixes : removeChild DOM bug, lenteur 300K lignes, crash mémoire
# ══════════════════════════════════════════════════════════════════════════════

# Colonnes utiles uniquement — élimine les ~80 colonnes mortes du PF (306K×100 → 306K×21)
PF_COLS = {
    "CODEINTE_P","NUMEPOLI_P","LIBECATE","ETAT_POLICE","NOM_ASSU","NOM_APP",
    "LIBEVILL","DATESOUS","DATEEFFE","DATEECHE","DATENAIS",
    "COTI_PERIODIQUE","MONTENCA","SEXERISQ","CODEPERI","NBRE_PRIME",
    "COMMGEST","CODEAPPO","CODERISQ",
}
CA_COLS = {
    "CODEINTE","NUMEPOLI","DATECOMP","NOMPRODUIT","LIBECATE",
    "NOM_INTERMEDIAIRE","CODEAPPO","CHIFAFFA","PRIMNETT","COMMAPPO",
    "COMMGEST","TYPEMOUV","SORTQUIT",
}
SIN_COLS = {
    "Int police","No Police","Date Survenance","Date Déclaration","Date validation",
    "Date Emission","Date Comptabilisation","Libéllé Catégorie","Nature Sinistre",
    "Sort Sinistre","Souscripteur","Désignation risque","Nom Bénéficiaire",
    "Exercice Sinistre","Réglement Total","Réglement Principal",
    "SAP au 31/12/2025","Réglement Honoraires",
}

def _excel_sheet(path: str, preferred: str) -> str:
    """Retourne le nom de feuille existant (préféré en premier, sinon sheet[0])."""
    xl = pd.ExcelFile(path, engine="openpyxl")
    if preferred in xl.sheet_names:
        return preferred
    # Cherche une feuille dont le nom contient 'liste' (insensible casse)
    for s in xl.sheet_names:
        if "liste" in s.lower():
            return s
    return xl.sheet_names[0]

def _keep_cols(df: pd.DataFrame, wanted: set) -> pd.DataFrame:
    """Conserve uniquement les colonnes présentes ET utiles."""
    keep = [c for c in df.columns if c in wanted]
    return df[keep] if keep else df

def load_pf(f) -> pd.DataFrame:
    """
    Charge le Portefeuille de façon optimisée.

    OPTIMISATIONS :
    • usecols = seulement les 19 colonnes utiles (PF_COLS) → 306K×19 au lieu de 306K×100
    • Lecture en une seule passe (pas de double-lecture des headers)
    • Toutes les colonnes lues en str → typage minimal uniquement sur celles utilisées
    • Nettoyage mémoire immédiat après typage

    RÉSULTAT : ~3× plus rapide, ~80% moins de RAM vs lecture complète
    """
    data = f.read()
    name = getattr(f, "name", "f.xlsx").lower()

    if name.endswith(".csv"):
        raw = data.decode("utf-8", errors="replace")
        sep = ";" if ";" in raw.split("\n")[0] else ","
        df  = pd.read_csv(io.StringIO(raw), sep=sep, dtype=str, low_memory=False)
        df.columns = [str(c).strip() for c in df.columns]
        df = _keep_cols(df, PF_COLS)
    else:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp.write(data)
            path = tmp.name
        try:
            # Lecture des en-têtes uniquement pour construire usecols
            xl  = pd.ExcelFile(path, engine="openpyxl")
            hdr = pd.read_excel(xl, nrows=0)
            hdr.columns = [str(c).strip() for c in hdr.columns]
            use = [c for c in hdr.columns if c in PF_COLS] or None
            del hdr  # libérer mémoire immédiatement

            # Lecture principale : uniquement les colonnes utiles
            df = pd.read_excel(xl, dtype=str, usecols=use,
                               engine="openpyxl")
            df.columns = [str(c).strip() for c in df.columns]
            xl.close()
        finally:
            try: os.unlink(path)
            except: pass

    # Nettoyage : supprimer lignes totalement vides
    df = df.dropna(how="all").reset_index(drop=True)

    # Typage uniquement sur les colonnes présentes et nécessaires
    for c in ["DATESOUS", "DATEEFFE", "DATEECHE", "DATENAIS"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    for c in ["MONTENCA", "COTI_PERIODIQUE", "NBRE_PRIME", "COMMGEST"]:
        if c in df.columns:
            df[c] = clean_num(df[c])

    # Clé de jointure inter-bases
    if "CODEINTE_P" in df.columns and "NUMEPOLI_P" in df.columns:
        df["POLICE_KEY"] = (df["CODEINTE_P"].astype(str).str.strip()
                            + "-" + df["NUMEPOLI_P"].astype(str).str.strip())

    # Normalisation ETAT_POLICE (supprime espaces parasites fréquents)
    if "ETAT_POLICE" in df.columns:
        df["ETAT_POLICE"] = df["ETAT_POLICE"].astype(str).str.strip()

    return df


def load_ca(f) -> pd.DataFrame:
    """
    Charge une Base CA — colonnes utiles uniquement.
    CA_COLS = 13 colonnes sur ~79 dans le fichier original.
    """
    data = f.read()
    name = getattr(f, "name", "f.xlsx").lower()

    if name.endswith(".csv"):
        raw = data.decode("utf-8", errors="replace")
        sep = ";" if ";" in raw.split("\n")[0] else ","
        df  = pd.read_csv(io.StringIO(raw), sep=sep, dtype=str, low_memory=False)
        df.columns = [str(c).strip() for c in df.columns]
        df = _keep_cols(df, CA_COLS)
    else:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp.write(data); path = tmp.name
        try:
            xl  = pd.ExcelFile(path, engine="openpyxl")
            hdr = pd.read_excel(xl, nrows=0)
            hdr.columns = [str(c).strip() for c in hdr.columns]
            use = [c for c in hdr.columns if c in CA_COLS] or None
            del hdr
            df  = pd.read_excel(xl, dtype=str, usecols=use)
            df.columns = [str(c).strip() for c in df.columns]
            xl.close()
        finally:
            try: os.unlink(path)
            except: pass

    df = df.dropna(how="all").reset_index(drop=True)

    if "DATECOMP" in df.columns:
        df["DATECOMP"] = pd.to_datetime(df["DATECOMP"], errors="coerce")
        df["ANNEE"]    = df["DATECOMP"].dt.year.astype("Int64")
        df["MOIS"]     = df["DATECOMP"].dt.month.astype("Int64")
    for c in ["CHIFAFFA","PRIMNETT","COMMAPPO","COMMGEST"]:
        if c in df.columns:
            df[c] = clean_num(df[c])
    if "CODEINTE" in df.columns and "NUMEPOLI" in df.columns:
        df["POLICE_KEY"] = (df["CODEINTE"].astype(str).str.strip()
                            + "-" + df["NUMEPOLI"].astype(str).str.strip())
    if "CODEAPPO" in df.columns:
        def _norm(x):
            if pd.isna(x): return ""
            s = str(x).strip().replace(".0","")
            return s if s.isdigit() else str(x).strip()
        df["CODEAPPO_STR"] = df["CODEAPPO"].apply(_norm)
    # Supprimer colonnes vides
    df = df.loc[:, df.notna().any(axis=0)]
    return df


def load_sin(f) -> pd.DataFrame:
    """
    Charge les Prestations — SIN_COLS uniquement (18 colonnes sur ~77).
    Détecte automatiquement la feuille "Liste" ou équivalent.
    """
    data = f.read()
    name = getattr(f, "name", "f.xlsx").lower()

    if name.endswith(".csv"):
        raw = data.decode("utf-8", errors="replace")
        sep = ";" if ";" in raw.split("\n")[0] else ","
        df  = pd.read_csv(io.StringIO(raw), sep=sep, dtype=str, low_memory=False)
        df.columns = [str(c).strip() for c in df.columns]
        df = _keep_cols(df, SIN_COLS)
    else:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp.write(data); path = tmp.name
        try:
            sh  = _excel_sheet(path, "Liste")
            xl  = pd.ExcelFile(path, engine="openpyxl")
            hdr = pd.read_excel(xl, sheet_name=sh, nrows=0)
            hdr.columns = [str(c).strip() for c in hdr.columns]
            use = [c for c in hdr.columns if c in SIN_COLS] or None
            del hdr
            df  = pd.read_excel(xl, sheet_name=sh, dtype=str, usecols=use)
            df.columns = [str(c).strip() for c in df.columns]
            xl.close()
        finally:
            try: os.unlink(path)
            except: pass

    df = df.dropna(how="all").reset_index(drop=True)

    for c in ["Date Survenance","Date Déclaration","Date validation",
              "Date Emission","Date Comptabilisation"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    for c in ["Réglement Total","Réglement Principal",
              "SAP au 31/12/2025","Réglement Honoraires"]:
        if c in df.columns:
            df[c] = clean_num(df[c])
    if "Int police" in df.columns and "No Police" in df.columns:
        df["POLICE_KEY"] = (df["Int police"].astype(str).str.strip()
                            + "-" + df["No Police"].astype(str).str.strip())
    if "Exercice Sinistre" in df.columns:
        df["ANNEE_SIN"] = pd.to_numeric(
            df["Exercice Sinistre"], errors="coerce").astype("Int64")
    # Supprimer colonnes vides
    df = df.loc[:, df.notna().any(axis=0)]
    return df

# ─────────────────────────────────────────────
#  FILTRE PÉRIODE — CORRIGÉ
#  Clé : comparer dt.date == sel (date Python)
#  Pour Prestations, filtre sur Exercice Sinistre (annuel) ou Date Survenance
# ─────────────────────────────────────────────
def filter_df(df, dcol, sel: date, mode: str) -> pd.DataFrame:
    """
    Filtre df sur la colonne dcol selon mode :
      jour → dcol.dt.date == sel
      mois → même année et mois
      trim → même année et trimestre
      sem  → même année et semestre
      annee→ même année
    """
    if df is None or df.empty: return pd.DataFrame()
    if dcol not in df.columns: return df  # pas de filtre si col absente
    col = df[dcol]
    if not pd.api.types.is_datetime64_any_dtype(col):
        col = pd.to_datetime(col, errors="coerce")
    if mode == "jour":
        mask = col.dt.date == sel
    elif mode == "mois":
        mask = (col.dt.year == sel.year) & (col.dt.month == sel.month)
    elif mode == "trim":
        q = (sel.month - 1) // 3
        mask = (col.dt.year == sel.year) & (((col.dt.month - 1) // 3) == q)
    elif mode == "sem":
        h = 0 if sel.month <= 6 else 1
        mask = (col.dt.year == sel.year) & (((col.dt.month - 1) // 6) == h)
    else:  # annee
        mask = col.dt.year == sel.year
    return df[mask.fillna(False)].copy()

def filter_sin_exo(df, sel: date, mode: str) -> pd.DataFrame:
    """
    Pour les prestations, filtre par exercice sinistre (annee/sem/trim)
    ou par Date Survenance (jour/mois).
    Exercice sinistre = colonne ANNEE_SIN (int).
    """
    if df is None or df.empty: return pd.DataFrame()
    if mode in ("jour","mois"):
        return filter_df(df, "Date Survenance", sel, mode)
    # Pour trimestre/semestre/annee → filtre sur ANNEE_SIN
    if "ANNEE_SIN" not in df.columns: return df
    yr = sel.year
    if mode == "annee":
        mask = df["ANNEE_SIN"] == yr
    elif mode == "trim":
        mask = df["ANNEE_SIN"] == yr   # exercice pas découpé en trim → filtre annuel
    elif mode == "sem":
        mask = df["ANNEE_SIN"] == yr
    else:
        mask = df["ANNEE_SIN"] == yr
    return df[mask.fillna(False)].copy()

# ─────────────────────────────────────────────
#  SESSION STATE
# ─────────────────────────────────────────────
DEFAULTS = {
    "auth": False, "user": {},
    "pf": None, "ca": None, "sin": None,
    "ca_list_raw": [],
    "pf_ok": False, "ca_ok": False, "sin_ok": False,
    "bases_loaded_from_db": False,   # True quand les bases ont été chargées depuis PG
    "current_page": "📝  Saisie BIA",
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────
#  LOGIN
# ─────────────────────────────────────────────
if not st.session_state.auth:
    _, col, _ = st.columns([1, 1.3, 1])
    with col:
        st.markdown(f"""
        <div style="text-align:center;padding:2.5rem 0 1.5rem">
          <div style="width:66px;height:66px;background:linear-gradient(135deg,{GREEN},{GREEN3});
               border-radius:14px;display:inline-flex;align-items:center;justify-content:center;
               font-size:10.5px;font-weight:900;color:white;line-height:1.2;
               box-shadow:0 10px 30px rgba(26,127,110,.45);">AFG<br>VIE</div>
          <h2 style="color:{NAVY};font-weight:800;margin:14px 0 3px">AFG Assurances Bénin Vie</h2>
          <p style="color:#8899AA;font-size:12px">Tableau de bord actuariel expert · Conforme CIMA</p>
        </div>""", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(f"""<div style="background:linear-gradient(135deg,{NAVY},{GREEN2});
                border-radius:8px;padding:10px 14px;margin-bottom:12px;">
              <b style="color:{MINT};font-size:12px">🔑 Codes de démonstration</b><br>
              <span style="color:rgba(255,255,255,.65);font-size:11px">
              PDG AFG → 1001 &nbsp;·&nbsp; ADMIN → 1003 &nbsp;·&nbsp; ACTUAIRE → 1005 &nbsp;·&nbsp; DEMO → 0000
              </span></div>""", unsafe_allow_html=True)
            ident = st.text_input("👤 Identifiant", placeholder="Ex : PDG AFG")
            code  = st.text_input("🔑 Code PIN (4 chiffres)", type="password", max_chars=4)
            if st.button("🔐 Accéder au système", use_container_width=True, type="primary"):
                up = ident.strip().upper()
                if up in USERS and USERS[up] == hashlib.sha256(code.encode()).hexdigest():
                    st.session_state.auth = True
                    st.session_state.user = {"nom": ident.strip(), "role": up.split()[0]}
                    st.rerun()
                else:
                    st.error("❌ Identifiant ou code PIN incorrect.")
    st.stop()

user  = st.session_state.user
today = date.today()

# ══════════════════════════════════════════════════════════════════════════════
#  CHARGEMENT AUTOMATIQUE DES BASES DEPUIS LA BASE CENTRALISÉE
#  Au premier rendu après login, on vérifie si des bases sont déjà stockées.
#  Si oui → chargement transparent, aucun upload nécessaire.
#  Les bases restent disponibles pour TOUS les visiteurs même après refresh.
# ══════════════════════════════════════════════════════════════════════════════
# Chargement initial des bases depuis la base centralisée.
# Pas de st.rerun() ici — le rendu sera correct au prochain cycle naturel.
if not st.session_state.bases_loaded_from_db:
    _meta = get_bases_meta()
    for _bt, _attr in [("pf","pf"), ("ca","ca"), ("sin","sin")]:
        if _bt in _meta and not getattr(st.session_state, f"{_attr}_ok"):
            _df, _ = load_base(_bt)
            if _df is not None and not _df.empty:
                setattr(st.session_state, _attr, _df)
                setattr(st.session_state, f"{_attr}_ok", True)
    st.session_state.bases_loaded_from_db = True
    # Pas de st.rerun() — Streamlit re-rendra naturellement au prochain cycle

# ─────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────
# ── Définition de toutes les pages disponibles ────────────────────────────────
ALL_PAGES = [
    "🏠  Accueil & KPIs",
    "📊  Analyse CA",
    "📋  Portefeuille",
    "🛒  Produits",
    "👥  Commerciaux & Partenaires",
    "👤  Clients & Géographie",
    "⚠️  Sinistres & Provisions",
    "📐  Actuariat Avancé",
    "🔮  Prévisions & Tendances",
    "📝  Saisie BIA",
    "🗂️  Base BIA",
    "📤  Exports",
]
# Seule page visible sans aucune base chargée
VISIBLE_DEFAULT = ["📝  Saisie BIA"]

# ── Calcul des pages disponibles selon les bases chargées ─────────────────────
# RÈGLE : Saisie BIA toujours visible.
#         Dès qu'AU MOINS une base est chargée → toutes les pages se débloquent.
#         Ce calcul est fait à chaque rendu (pas besoin de bouton).
_any_data = (st.session_state.pf_ok or st.session_state.ca_ok or st.session_state.sin_ok)
pages_visible = ALL_PAGES if _any_data else VISIBLE_DEFAULT

# Sécurité : si la page courante a disparu (ex. données effacées), revenir à BIA
if st.session_state.current_page not in pages_visible:
    st.session_state.current_page = "📝  Saisie BIA"

with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center;padding:.8rem 0 .4rem">
      <div style="width:50px;height:50px;background:linear-gradient(135deg,{GREEN},{GREEN3});
           border-radius:11px;display:inline-flex;align-items:center;justify-content:center;
           font-size:9.5px;font-weight:900;color:white;line-height:1.2;
           box-shadow:0 4px 16px rgba(26,127,110,.4)">AFG<br>VIE</div>
    </div><hr>
    <div style="background:rgba(26,127,110,.12);border-radius:8px;padding:8px 10px;margin:0 4px 8px">
      <div style="font-size:9px;opacity:.5;text-transform:uppercase;letter-spacing:.05em">Connecté</div>
      <div style="font-weight:700;font-size:12px;margin-top:1px">{user['nom']}</div>
    </div>""", unsafe_allow_html=True)

    # ── Message d'état navigation ─────────────────────────────────────────────
    if not _any_data:
        st.markdown(f"""
        <div style="background:rgba(202,111,30,.15);border:1px solid {AMBER};border-radius:8px;
             padding:8px 10px;margin:6px 4px 4px;font-size:10px;color:rgba(255,255,255,.7);line-height:1.5">
          🔒 <b style="color:{MINT}">Accès limité</b><br>
          Chargez au moins une base pour accéder aux tableaux de bord analytiques.
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="background:rgba(26,127,110,.15);border:1px solid {GREEN};border-radius:8px;
             padding:8px 10px;margin:6px 4px 4px;font-size:10px;color:rgba(255,255,255,.7);line-height:1.5">
          ✅ <b style="color:{MINT}">{sum([st.session_state.pf_ok, st.session_state.ca_ok, st.session_state.sin_ok])}/3 base(s)</b> chargée(s) — tous les onglets sont disponibles.
        </div>""", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    nav_choice = st.radio("", pages_visible,
                          index=pages_visible.index(st.session_state.current_page),
                          label_visibility="collapsed")
    st.session_state.current_page = nav_choice

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Filtre période ──────────────────────────────────────────────────────
    st.markdown(f"<div style='font-size:9.5px;font-weight:700;opacity:.55;text-transform:uppercase;letter-spacing:.07em;margin-bottom:5px'>📅 Période d'analyse</div>", unsafe_allow_html=True)
    mode_lbl = st.selectbox("", ["Jour","Mois","Trimestre","Semestre","Année"],
                            label_visibility="collapsed", key="mode_sel")
    MODE = {"Jour":"jour","Mois":"mois","Trimestre":"trim","Semestre":"sem","Année":"annee"}[mode_lbl]

    # Date par défaut : 2024-01-15 pour que le filtre "jour" renvoie des données CA
    default_date = date(2024, 1, 15)
    sel_date = st.date_input("", value=default_date, label_visibility="collapsed", key="sel_date")

    if MODE=="jour":   period_lbl = ds(sel_date)
    elif MODE=="mois": period_lbl = f"{MOIS_LONG[sel_date.month-1]} {sel_date.year}"
    elif MODE=="trim": period_lbl = f"T{(sel_date.month-1)//3+1} {sel_date.year}"
    elif MODE=="sem":  period_lbl = f"S{'1' if sel_date.month<=6 else '2'} {sel_date.year}"
    else:              period_lbl = str(sel_date.year)

    st.markdown(f"<div style='background:{GREEN};color:white;text-align:center;border-radius:7px;padding:5px;margin:5px 4px;font-weight:700;font-size:11px'>{period_lbl}</div>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Statut des bases (lecture seule, visible par tous) ───────────────────
    _meta_disp = get_bases_meta()
    st.markdown(
        f"<div style='font-size:9.5px;font-weight:700;opacity:.55;text-transform:uppercase;"
        f"letter-spacing:.07em;margin-bottom:4px'>📂 Bases de données</div>",
        unsafe_allow_html=True)
    for _btype, _icon, _lbl in [("pf","📋","Portefeuille"),
                                  ("ca","💰","Base CA"),
                                  ("sin","🏥","Prestations")]:
        _ok  = getattr(st.session_state, f"{_btype}_ok")
        _df  = getattr(st.session_state, _btype)
        _nb  = len(_df) if _ok and _df is not None else 0
        _m   = _meta_disp.get(_btype, {})
        _col = GREEN if _ok else AMBER
        _txt = f"{_nb:,} lignes" if _ok else "Non chargée"
        _upd = _m.get("charge_le","")[:16].replace("T"," ") if _m else ""
        st.markdown(f"""
        <div style="background:{_col}14;border-left:3px solid {_col};border-radius:0 7px 7px 0;
             padding:5px 9px;margin-bottom:4px">
          <div style="font-size:10px;font-weight:700;color:rgba(255,255,255,.85)">{_icon} {_lbl}</div>
          <div style="font-size:9px;color:rgba(255,255,255,.5)">{_txt}{" · " + _upd if _upd else ""}</div>
        </div>""", unsafe_allow_html=True)

    # ── Interface admin — UNIQUEMENT les widgets d'upload et boutons ──────────
    # RÈGLE CRITIQUE anti-removeChild :
    #   • Les file_uploader enregistrent le fichier dans session_state["_pending_XX"]
    #   • Aucun traitement lourd ni rerun ici
    #   • Le traitement réel (load_pf, save_base) se fait APRÈS la sidebar,
    #     dans une zone dédiée, une fois React terminé
    if is_admin(user):
        st.markdown(f"<div style='font-size:9px;color:{MINT};font-weight:700;margin:8px 0 3px'>"
                    f"⚙️ Gestion des bases (ADMIN)</div>", unsafe_allow_html=True)

        with st.expander(f"📋 Portefeuille {'✅' if st.session_state.pf_ok else '▶ Charger'}",
                         expanded=not st.session_state.pf_ok):
            if st.session_state.pf_ok:
                st.caption(f"{len(st.session_state.pf):,} polices · {len(st.session_state.pf.columns)} col.")
            f_pf = st.file_uploader(
                "💡 CSV recommandé pour vitesse maximale | xlsx accepté",
                type=["csv","xlsx","xls"], key="up_pf",
                label_visibility="visible")
            if f_pf is not None and not st.session_state.get("_pf_bytes_stored"):
                # Lire les bytes IMMÉDIATEMENT — ultra-rapide, évite timeout websocket
                _raw = f_pf.read()
                st.session_state["_pending_pf_bytes"] = _raw
                st.session_state["_pending_pf_name"]  = f_pf.name
                st.session_state["_pf_bytes_stored"]  = True
            if st.session_state.pf_ok:
                c1,c2 = st.columns(2)
                if c1.button("🔄 Remplacer", key="rep_pf", use_container_width=True):
                    st.session_state["_action_pf"] = "delete"
                    st.session_state["_pf_bytes_stored"] = False
                if c2.button("🗑️ Supprimer", key="del_pf", use_container_width=True):
                    st.session_state["_action_pf"] = "delete"
                    st.session_state["_pf_bytes_stored"] = False

        with st.expander(f"💰 Base CA {'✅' if st.session_state.ca_ok else '▶ Charger'}",
                         expanded=not st.session_state.ca_ok):
            if st.session_state.ca_ok:
                _yrs = (sorted(st.session_state.ca["ANNEE"].dropna().unique().astype(int).tolist())
                        if "ANNEE" in st.session_state.ca.columns else [])
                st.caption(f"{len(st.session_state.ca):,} quittances · {', '.join(map(str,_yrs))}")
            st.caption("💡 CSV recommandé · Plusieurs exercices : charger un par un")
            f_ca = st.file_uploader("CA .csv/.xlsx", type=["csv","xlsx","xls"],
                                    key="up_ca", label_visibility="collapsed")
            if f_ca is not None:
                _ca_id = f"{f_ca.name}_{f_ca.size}"
                if _ca_id not in st.session_state.get("_ca_seen_ids", set()):
                    _raw_ca = f_ca.read()
                    _pending_list = st.session_state.get("_pending_ca_list", [])
                    _pending_list.append({"bytes": _raw_ca, "name": f_ca.name, "id": _ca_id})
                    st.session_state["_pending_ca_list"] = _pending_list
            if st.session_state.ca_ok:
                if st.button("🗑️ Vider tout le CA", key="del_ca", use_container_width=True):
                    st.session_state["_action_ca"] = "delete"

        with st.expander(f"🏥 Prestations {'✅' if st.session_state.sin_ok else '▶ Charger'}",
                         expanded=not st.session_state.sin_ok):
            if st.session_state.sin_ok:
                st.caption(f"{len(st.session_state.sin):,} dossiers · {len(st.session_state.sin.columns)} col.")
            f_sin = st.file_uploader(
                "💡 CSV recommandé | xlsx accepté",
                type=["csv","xlsx","xls"], key="up_sin",
                label_visibility="visible")
            if f_sin is not None and not st.session_state.get("_sin_bytes_stored"):
                _raw_sin = f_sin.read()
                st.session_state["_pending_sin_bytes"] = _raw_sin
                st.session_state["_pending_sin_name"]  = f_sin.name
                st.session_state["_sin_bytes_stored"]  = True
            if st.session_state.sin_ok:
                c1,c2 = st.columns(2)
                if c1.button("🔄 Remplacer", key="rep_sin", use_container_width=True):
                    st.session_state["_action_sin"] = "delete"
                    st.session_state["_sin_bytes_stored"] = False
                if c2.button("🗑️ Supprimer", key="del_sin", use_container_width=True):
                    st.session_state["_action_sin"] = "delete"
                    st.session_state["_sin_bytes_stored"] = False
    else:
        if not _any_data:
            st.markdown(f"""
            <div style="background:rgba(202,111,30,.15);border:1px solid {AMBER};border-radius:8px;
                 padding:8px 10px;margin:4px;font-size:10px;color:rgba(255,255,255,.7)">
              ⏳ Les bases sont en cours de chargement par l'administrateur.
            </div>""", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    _logout = st.button("🚪 Déconnexion")
    st.markdown(
        f"<div style='text-align:center;font-size:8px;opacity:.22;padding:4px 0'>"
        f"© 2025 AFG Assurances Bénin Vie<br>Dashboard Expert v3.0 · CIMA</div>",
        unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  TRAITEMENT DES ACTIONS — CYCLE 2 (hors sidebar, hors widget)
#
#  PRINCIPE ANTI-removeChild :
#  On ne fait JAMAIS st.rerun() pendant ou juste après un widget Streamlit.
#  À la place :
#   • Cycle 1 : widget stocke fichier dans _pending_XX → rendu normal → fin
#   • Cycle 2 : on détecte _pending_XX → on traite (load + save) →
#               on met _ok=True → st.rerun() EN TOUTE FIN de script
#               (après tous les widgets, après tout le rendu)
#   • Cycle 3 : _ok=True → onglets disponibles → affichage normal
#
#  Le st.rerun() est appelé UNE SEULE FOIS, à la toute fin, quand le DOM
#  est stable et React a terminé tous ses effets.
# ══════════════════════════════════════════════════════════════════════════════

# ── Déconnexion ───────────────────────────────────────────────────────────────
if "_logout" in dir() and _logout:
    for k in DEFAULTS:
        st.session_state[k] = DEFAULTS[k]
    st.rerun()

# ── Suppressions / remplacements ──────────────────────────────────────────────
_did_action = False
for _bt in ["pf", "ca", "sin"]:
    if st.session_state.pop(f"_action_{_bt}", None):
        delete_base(_bt)
        setattr(st.session_state, _bt, None)
        setattr(st.session_state, f"{_bt}_ok", False)
        if _bt == "ca":
            st.session_state.ca_list_raw = []
            st.session_state["_ca_seen_ids"] = set()
        _did_action = True
if _did_action:
    st.rerun()

# ── Traitement fichiers en attente ────────────────────────────────────────────
# Zone de progression visible pendant le traitement (avant le rendu principal)
_processed = False

# ── Helpers pour lire depuis bytes stockés ───────────────────────────────────
def _bytes_to_df_pf(raw: bytes, fname: str) -> pd.DataFrame:
    """Parse bytes (CSV ou XLSX) en DataFrame PF filtré."""
    if fname.lower().endswith(".csv"):
        txt = raw.decode("utf-8", errors="replace")
        sep = ";" if ";" in txt.split("\n")[0] else ","
        df  = pd.read_csv(io.StringIO(txt), sep=sep, dtype=str, low_memory=False)
        df.columns = [str(c).strip() for c in df.columns]
        df = _keep_cols(df, PF_COLS)
    else:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp.write(raw); path = tmp.name
        try:
            xl  = pd.ExcelFile(path, engine="openpyxl")
            hdr = pd.read_excel(xl, nrows=0)
            hdr.columns = [str(c).strip() for c in hdr.columns]
            use = [c for c in hdr.columns if c in PF_COLS] or None
            del hdr
            df  = pd.read_excel(xl, dtype=str, usecols=use)
            df.columns = [str(c).strip() for c in df.columns]
            xl.close()
        finally:
            try: os.unlink(path)
            except: pass
    df = df.dropna(how="all").reset_index(drop=True)
    for c in ["DATESOUS","DATEEFFE","DATEECHE","DATENAIS"]:
        if c in df.columns: df[c] = pd.to_datetime(df[c], errors="coerce")
    for c in ["MONTENCA","COTI_PERIODIQUE","NBRE_PRIME","COMMGEST"]:
        if c in df.columns: df[c] = clean_num(df[c])
    if "CODEINTE_P" in df.columns and "NUMEPOLI_P" in df.columns:
        df["POLICE_KEY"] = (df["CODEINTE_P"].astype(str).str.strip()
                            + "-" + df["NUMEPOLI_P"].astype(str).str.strip())
    if "ETAT_POLICE" in df.columns:
        df["ETAT_POLICE"] = df["ETAT_POLICE"].astype(str).str.strip()
    return df.loc[:, df.notna().any(axis=0)]

def _bytes_to_df_ca(raw: bytes, fname: str) -> pd.DataFrame:
    """Parse bytes (CSV ou XLSX) en DataFrame CA filtré."""
    if fname.lower().endswith(".csv"):
        txt = raw.decode("utf-8", errors="replace")
        sep = ";" if ";" in txt.split("\n")[0] else ","
        df  = pd.read_csv(io.StringIO(txt), sep=sep, dtype=str, low_memory=False)
        df.columns = [str(c).strip() for c in df.columns]
        df = _keep_cols(df, CA_COLS)
    else:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp.write(raw); path = tmp.name
        try:
            xl  = pd.ExcelFile(path, engine="openpyxl")
            hdr = pd.read_excel(xl, nrows=0)
            hdr.columns = [str(c).strip() for c in hdr.columns]
            use = [c for c in hdr.columns if c in CA_COLS] or None
            del hdr
            df  = pd.read_excel(xl, dtype=str, usecols=use)
            df.columns = [str(c).strip() for c in df.columns]
            xl.close()
        finally:
            try: os.unlink(path)
            except: pass
    df = df.dropna(how="all").reset_index(drop=True)
    if "DATECOMP" in df.columns:
        df["DATECOMP"] = pd.to_datetime(df["DATECOMP"], errors="coerce")
        df["ANNEE"]    = df["DATECOMP"].dt.year.astype("Int64")
        df["MOIS"]     = df["DATECOMP"].dt.month.astype("Int64")
    for c in ["CHIFAFFA","PRIMNETT","COMMAPPO","COMMGEST"]:
        if c in df.columns: df[c] = clean_num(df[c])
    if "CODEINTE" in df.columns and "NUMEPOLI" in df.columns:
        df["POLICE_KEY"] = (df["CODEINTE"].astype(str).str.strip()
                            + "-" + df["NUMEPOLI"].astype(str).str.strip())
    if "CODEAPPO" in df.columns:
        def _n(x):
            if pd.isna(x): return ""
            s = str(x).strip().replace(".0","")
            return s if s.isdigit() else str(x).strip()
        df["CODEAPPO_STR"] = df["CODEAPPO"].apply(_n)
    return df.loc[:, df.notna().any(axis=0)]

def _bytes_to_df_sin(raw: bytes, fname: str) -> pd.DataFrame:
    """Parse bytes (CSV ou XLSX) en DataFrame Prestations filtré."""
    if fname.lower().endswith(".csv"):
        txt = raw.decode("utf-8", errors="replace")
        sep = ";" if ";" in txt.split("\n")[0] else ","
        df  = pd.read_csv(io.StringIO(txt), sep=sep, dtype=str, low_memory=False)
        df.columns = [str(c).strip() for c in df.columns]
        df = _keep_cols(df, SIN_COLS)
    else:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp.write(raw); path = tmp.name
        try:
            sh  = _excel_sheet(path, "Liste")
            xl  = pd.ExcelFile(path, engine="openpyxl")
            hdr = pd.read_excel(xl, sheet_name=sh, nrows=0)
            hdr.columns = [str(c).strip() for c in hdr.columns]
            use = [c for c in hdr.columns if c in SIN_COLS] or None
            del hdr
            df  = pd.read_excel(xl, sheet_name=sh, dtype=str, usecols=use)
            df.columns = [str(c).strip() for c in df.columns]
            xl.close()
        finally:
            try: os.unlink(path)
            except: pass
    df = df.dropna(how="all").reset_index(drop=True)
    for c in ["Date Survenance","Date Déclaration","Date validation",
              "Date Emission","Date Comptabilisation"]:
        if c in df.columns: df[c] = pd.to_datetime(df[c], errors="coerce")
    for c in ["Réglement Total","Réglement Principal",
              "SAP au 31/12/2025","Réglement Honoraires"]:
        if c in df.columns: df[c] = clean_num(df[c])
    if "Int police" in df.columns and "No Police" in df.columns:
        df["POLICE_KEY"] = (df["Int police"].astype(str).str.strip()
                            + "-" + df["No Police"].astype(str).str.strip())
    if "Exercice Sinistre" in df.columns:
        df["ANNEE_SIN"] = pd.to_numeric(
            df["Exercice Sinistre"], errors="coerce").astype("Int64")
    return df.loc[:, df.notna().any(axis=0)]

# ── Traitement des bytes stockés — parsing et sauvegarde ─────────────────────
# Les bytes sont déjà en mémoire (lus instantanément dans la sidebar).
# On parse ici, sans aucun widget actif → DOM stable → st.rerun() sûr.

if st.session_state.get("_pending_pf_bytes") is not None:
    _raw  = st.session_state.pop("_pending_pf_bytes")
    _name = st.session_state.pop("_pending_pf_name", "portefeuille.xlsx")
    with st.status(f"⏳ Traitement du Portefeuille ({len(_raw)//1024} KB)…",
                   expanded=True) as _st:
        try:
            st.write("📊 Filtrage des colonnes utiles (19 sur ~100)…")
            _df = _bytes_to_df_pf(_raw, _name)
            del _raw
            st.write(f"✅ {len(_df):,} polices · {len(_df.columns)} colonnes conservées")
            st.write("💾 Sauvegarde en base centralisée…")
            _ok = save_base("pf", _df, _name, user["nom"])
            if _ok:
                st.session_state.pf    = _df
                st.session_state.pf_ok = True
                _processed = True
                _st.update(label=f"✅ Portefeuille — {len(_df):,} polices chargées",
                           state="complete")
            else:
                _st.update(label="❌ Erreur lors de la sauvegarde", state="error")
        except Exception as _e:
            _st.update(label=f"❌ {_e}", state="error")
            st.session_state["_pf_bytes_stored"] = False

if st.session_state.get("_pending_ca_list"):
    _pending_list = st.session_state.pop("_pending_ca_list")
    for _item in _pending_list:
        _raw  = _item["bytes"]
        _name = _item["name"]
        _cid  = _item["id"]
        with st.status(f"⏳ Traitement CA — {_name} ({len(_raw)//1024} KB)…",
                       expanded=True) as _st:
            try:
                st.write("📊 Filtrage des colonnes utiles (13 sur ~79)…")
                _df_new = _bytes_to_df_ca(_raw, _name)
                del _raw
                st.write(f"✅ {len(_df_new):,} quittances lues")
                _seen = st.session_state.get("_ca_seen_ids", set())
                _seen.add(_cid)
                st.session_state["_ca_seen_ids"] = _seen
                st.session_state.ca_list_raw.append(_df_new)
                _merged = (
                    _df_new if len(st.session_state.ca_list_raw) == 1
                    else pd.concat(st.session_state.ca_list_raw, ignore_index=True))
                st.write("💾 Sauvegarde en base centralisée…")
                _ok = save_base("ca", _merged, _name, user["nom"])
                if _ok:
                    st.session_state.ca    = _merged
                    st.session_state.ca_ok = True
                    _processed = True
                    _yrs = (sorted(_merged["ANNEE"].dropna().unique().astype(int).tolist())
                            if "ANNEE" in _merged.columns else [])
                    _st.update(
                        label=f"✅ CA — {len(_merged):,} quittances · {', '.join(map(str,_yrs))}",
                        state="complete")
                else:
                    _st.update(label="❌ Erreur lors de la sauvegarde", state="error")
            except Exception as _e:
                _st.update(label=f"❌ {_e}", state="error")

if st.session_state.get("_pending_sin_bytes") is not None:
    _raw  = st.session_state.pop("_pending_sin_bytes")
    _name = st.session_state.pop("_pending_sin_name", "prestations.xlsx")
    with st.status(f"⏳ Traitement des Prestations ({len(_raw)//1024} KB)…",
                   expanded=True) as _st:
        try:
            st.write("📊 Filtrage des colonnes utiles (18 sur ~77)…")
            _df = _bytes_to_df_sin(_raw, _name)
            del _raw
            st.write(f"✅ {len(_df):,} dossiers · {len(_df.columns)} colonnes conservées")
            st.write("💾 Sauvegarde en base centralisée…")
            _ok = save_base("sin", _df, _name, user["nom"])
            if _ok:
                st.session_state.sin    = _df
                st.session_state.sin_ok = True
                _processed = True
                _st.update(label=f"✅ Prestations — {len(_df):,} dossiers chargés",
                           state="complete")
            else:
                _st.update(label="❌ Erreur lors de la sauvegarde", state="error")
        except Exception as _e:
            _st.update(label=f"❌ {_e}", state="error")
            st.session_state["_sin_bytes_stored"] = False

# ── Rerun final — uniquement si un traitement a eu lieu ──────────────────────
# À ce point, TOUT le DOM est stable : sidebar rendue, widgets stabilisés,
# traitements terminés. st.rerun() est sûr.
if _processed:
    st.rerun()

# ─────────────────────────────────────────────
#  RACCOURCIS
# ─────────────────────────────────────────────
pf  = st.session_state.pf
ca  = st.session_state.ca
sin = st.session_state.sin
page = st.session_state.current_page

# Fonctions filtre période
def pf_f():  return filter_df(pf,  "DATESOUS",        sel_date, MODE)
def ca_f():  return filter_df(ca,  "DATECOMP",        sel_date, MODE)
def sin_f(): return filter_sin_exo(sin, sel_date, MODE)

# ─────────────────────────────────────────────
#  TOPBAR
# ─────────────────────────────────────────────
pf_ct  = f"{len(pf):,}"  if pf  is not None else "—"
ca_ct  = f"{len(ca):,}"  if ca  is not None else "—"
sin_ct = f"{len(sin):,}" if sin is not None else "—"
st.markdown(f"""
<div class="afg-bar">
  <div style="display:flex;align-items:center;gap:12px">
    <div class="afg-logo">AFG<br>VIE</div>
    <div>
      <div style="color:white;font-size:1.05rem;font-weight:800">AFG Assurances Bénin Vie</div>
      <div style="color:rgba(255,255,255,.45);font-size:9px;letter-spacing:.1em">DASHBOARD ACTUARIEL EXPERT · CIMA · GROUPE AFG HOLDING</div>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:9px">
    <div style="font-size:10px;color:rgba(255,255,255,.4)">
      PF: <b style="color:{MINT}">{pf_ct}</b> &nbsp;·&nbsp;
      CA: <b style="color:{MINT}">{ca_ct}</b> &nbsp;·&nbsp;
      SIN: <b style="color:{MINT}">{sin_ct}</b>
    </div>
    <div style="background:rgba(26,127,110,.22);border:1px solid {GREEN};border-radius:7px;padding:4px 12px;color:{MINT};font-size:11px;font-weight:700">{period_lbl}</div>
    <div style="background:rgba(255,255,255,.08);border-radius:7px;padding:4px 11px;color:white;font-size:11px">{user['nom']}</div>
  </div>
</div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — ACCUEIL & KPIs
# ═══════════════════════════════════════════════════════════════════════════════
if "Accueil" in page:
    if pf is None and ca is None and sin is None:
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,{NAVY},{GREEN2});border-radius:16px;
             padding:3rem;text-align:center;margin:2rem 0">
          <div style="font-size:46px;margin-bottom:1rem">🛡️</div>
          <h2 style="color:white;font-weight:800;margin-bottom:.5rem">Bienvenue — Dashboard AFG Expert v3.0</h2>
          <p style="color:rgba(255,255,255,.65);font-size:13px;max-width:480px;margin:0 auto">
            Chargez vos bases dans la barre latérale.<br>
            Portefeuille (306K polices) · CA multi-exercices · Prestations (26K dossiers)
          </p>
        </div>""", unsafe_allow_html=True)
        st.stop()

    df_pf  = pf_f()
    df_ca  = ca_f()
    df_sin = sin_f()

    # Compteurs filtrés pour contexte
    section(f"📊 Indicateurs clés — {period_lbl}", "CIMA · PORTEFEUILLE")
    nb  = len(df_pf)
    eok = "ETAT_POLICE" in df_pf.columns if nb else False
    actifs = int((df_pf["ETAT_POLICE"].str.strip().isin(["ACTIF"])).sum()) if eok and nb else 0
    resil  = int((df_pf["ETAT_POLICE"].str.strip()=="RESILIE").sum()) if eok and nb else 0
    echu   = int((df_pf["ETAT_POLICE"].str.strip().isin(["ECHU","ASSURE ECHU"])).sum()) if eok and nb else 0
    inact  = int((df_pf["ETAT_POLICE"].str.strip()=="INACTIF").sum()) if eok and nb else 0
    tx_act = actifs/max(nb,1)*100
    tx_res = resil/max(nb-inact,1)*100
    monten = float(df_pf["MONTENCA"].fillna(0).sum()) if nb and "MONTENCA" in df_pf.columns else 0

    c1,c2,c3,c4,c5,c6 = st.columns(6)
    kpi(c1,"Polices",f"{nb:,}",period_lbl,"",icon="📋")
    kpi(c2,"Actives",f"{actifs:,}",pct(tx_act),"",icon="✅")
    kpi(c3,"Résiliées",f"{resil:,}",f"Tx CIMA {pct(tx_res)}","red" if tx_res>25 else "",icon="📉")
    kpi(c4,"Échues",f"{echu:,}",pct(echu/max(nb,1)*100),"amber",icon="⌛")
    kpi(c5,"Encaissements",fmt(monten),"MONTENCA","teal",icon="💰")
    kpi(c6,"NOM_APP uniques",str(df_pf["NOM_APP"].nunique()) if nb and "NOM_APP" in df_pf.columns else "—","Apporteurs","blue",icon="👥")

    if ca is not None and not df_ca.empty:
        st.markdown("")
        section("💰 CA — Chiffre d'Affaires","CA · "+period_lbl)
        chifaffa = float(df_ca["CHIFAFFA"].fillna(0).sum()) if "CHIFAFFA" in df_ca.columns else 0
        commappo = float(df_ca["COMMAPPO"].fillna(0).sum()) if "COMMAPPO" in df_ca.columns else 0
        primnett = float(df_ca["PRIMNETT"].fillna(0).sum()) if "PRIMNETT" in df_ca.columns else 0
        tx_comm  = commappo/max(chifaffa,1)*100
        nb_q     = len(df_ca)
        annul    = float(df_ca.loc[df_ca.get("TYPEMOUV","")=="ANNULATIONS","CHIFAFFA"].fillna(0).sum()) if "TYPEMOUV" in df_ca.columns else 0
        ca_net   = chifaffa - abs(annul)
        d1,d2,d3,d4,d5 = st.columns(5)
        kpi(d1,"CA brut",fmt(chifaffa),"CHIFAFFA","",icon="💵")
        kpi(d2,"CA net",fmt(ca_net),"Hors annulations","teal",icon="✅")
        kpi(d3,"Prime nette",fmt(primnett),"PRIMNETT","",icon="📄")
        kpi(d4,"Commissions",fmt(commappo),f"Taux {pct(tx_comm)}","amber",icon="💼")
        kpi(d5,"Nb quittances",f"{nb_q:,}","Émissions","",icon="🧾")
    elif ca is not None:
        alert(f"Aucune quittance CA pour {period_lbl}. Essayez mode Mois ou Année.","info")

    if sin is not None:
        st.markdown("")
        section("🏥 Sinistres & Provisions","TOUTES PÉRIODES")
        tot_sin = float(sin["Réglement Total"].fillna(0).sum()) if "Réglement Total" in sin.columns else 0
        tot_sap = float(sin["SAP au 31/12/2025"].fillna(0).sum()) if "SAP au 31/12/2025" in sin.columns else 0
        nb_sin  = len(sin); nb_ouv = int((sin["Sort Sinistre"]=="Ouvert").sum()) if "Sort Sinistre" in sin.columns else 0
        nb_clos = int((sin["Sort Sinistre"]=="Cloturé").sum()) if "Sort Sinistre" in sin.columns else 0
        ca_all  = float(ca["CHIFAFFA"].fillna(0).sum()) if ca is not None and "CHIFAFFA" in ca.columns else 0
        sp = tot_sin/max(ca_all,1)*100
        actifs_tot = int((pf["ETAT_POLICE"].str.strip().isin(["ACTIF"])).sum()) if pf is not None and "ETAT_POLICE" in pf.columns else 1
        burning = (tot_sin+tot_sap)/max(actifs_tot,1)*1000
        e1,e2,e3,e4,e5 = st.columns(5)
        kpi(e1,"Total réglé",fmt(tot_sin),"Toutes périodes","red",icon="💊")
        kpi(e2,"SAP (provisions)",fmt(tot_sap),"Au 31/12/2025","amber",icon="📌")
        kpi(e3,"Charge ultime",fmt(tot_sin+tot_sap),"Réglé+SAP","red",icon="⚖️")
        kpi(e4,"Ratio S/P",pct(sp),"vs CA","red" if sp>80 else "amber",icon="📐")
        kpi(e5,"Burning Cost",fmt(burning),"Charge/1 000 actifs","red",icon="🔥")

    # Jointure inter-bases — résumé
    st.markdown("")
    section("🔗 Jointures inter-bases","POLICE_KEY · MATCHING")
    j1,j2,j3 = st.columns(3)
    if pf is not None and ca is not None and "POLICE_KEY" in pf.columns and "POLICE_KEY" in ca.columns:
        mc = ca["POLICE_KEY"].isin(pf["POLICE_KEY"]).sum()
        kpi(j1,"CA ↔ PF",f"{mc:,}",f"{mc/max(len(ca),1)*100:.1f}% des quittances","teal",icon="🔗")
    if pf is not None and sin is not None and "POLICE_KEY" in pf.columns and "POLICE_KEY" in sin.columns:
        ms = sin["POLICE_KEY"].isin(pf["POLICE_KEY"]).sum()
        kpi(j2,"SIN ↔ PF",f"{ms:,}",f"{ms/max(len(sin),1)*100:.1f}% des sinistres","teal",icon="🔗")
    if ca is not None and sin is not None and "POLICE_KEY" in ca.columns and "POLICE_KEY" in sin.columns:
        mcs = sin["POLICE_KEY"].isin(ca["POLICE_KEY"]).sum()
        kpi(j3,"SIN ↔ CA",f"{mcs:,}",f"{mcs/max(len(sin),1)*100:.1f}% des sinistres","blue",icon="🔗")

    # Scorecard CIMA
    if pf is not None:
        st.markdown("")
        section("🏛️ Scorecard CIMA","CONFORMITÉ RÉGLEMENTAIRE")
        sp2 = sp if sin is not None else 0
        indics=[
            (tx_act,"Taux d'activité net",50,">=",GREEN),
            (tx_res,"Taux résiliation CIMA",25,"<=",RED),
            (sp2,"Ratio S/P",80,"<=",AMBER),
            (inact/max(nb,1)*100,"Part inactifs",5,"<=",AMBER),
        ]
        score = sum(1 for v,_,s,op,_ in indics if (v>=s if op==">=" else v<=s))
        sc_c  = GREEN if score>=3 else AMBER if score==2 else RED
        ci1,ci2 = st.columns([1.4,1])
        with ci1:
            for v,lbl,seuil,op,col in indics:
                ok = v>=seuil if op==">=" else v<=seuil
                c_ = GREEN if ok else RED
                st.markdown(f"""<div style="display:flex;align-items:center;justify-content:space-between;
                     padding:9px 13px;border-left:4px solid {c_};background:{c_}0D;
                     border-radius:0 9px 9px 0;margin-bottom:7px">
                  <div><div style="font-size:12px;font-weight:600;color:{NAVY}">{lbl}</div>
                  <div style="font-size:9.5px;color:#8899AA">Seuil CIMA : {op}{seuil}%</div></div>
                  <div style="font-size:15px;font-weight:900;color:{c_}">{pct(v)} {'✅' if ok else '⚠️'}</div>
                </div>""", unsafe_allow_html=True)
        with ci2:
            st.markdown(f"""<div style="background:{sc_c}12;border:2.5px solid {sc_c};border-radius:14px;
                 padding:1.5rem;text-align:center">
              <div style="font-size:52px;font-weight:900;color:{sc_c}">{score}/{len(indics)}</div>
              <div style="font-size:12px;color:#555">indicateurs conformes</div>
              <div style="height:6px;background:{MGRAY};border-radius:3px;margin:10px 0;overflow:hidden">
                <div style="height:100%;width:{score/len(indics)*100:.0f}%;background:{sc_c};border-radius:3px"></div>
              </div>
              <div style="font-size:13px;font-weight:700;color:{sc_c}">
                {'✅ Conforme CIMA' if score==4 else '⚠️ Surveillance' if score>=2 else '🔴 Intervention requise'}
              </div></div>""", unsafe_allow_html=True)
        if tx_res>25: alert(f"Taux résiliation {pct(tx_res)} > 25% (seuil CIMA). Action corrective recommandée.","warn")
        if sp2>80: alert(f"Ratio S/P {pct(sp2)} > 80%. Révision tarifaire urgente.","danger")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — ANALYSE CA
# ═══════════════════════════════════════════════════════════════════════════════
elif "Analyse CA" in page:
    if ca is None: alert("Chargez la Base CA dans la barre latérale.","warn"); st.stop()
    df = ca_f()
    all_ca = ca  # total toutes périodes pour comparaison

    section(f"📊 Analyse CA — {period_lbl}","CHIFAFFA · COMMISSIONS · PARETO")
    chifaffa = float(df["CHIFAFFA"].fillna(0).sum()) if "CHIFAFFA" in df.columns and not df.empty else 0
    commappo = float(df["COMMAPPO"].fillna(0).sum()) if "COMMAPPO" in df.columns and not df.empty else 0
    primnett = float(df["PRIMNETT"].fillna(0).sum()) if "PRIMNETT" in df.columns and not df.empty else 0
    tx_comm  = commappo/max(chifaffa,1)*100
    nb_q     = len(df)
    ca_total = float(all_ca["CHIFAFFA"].fillna(0).sum()) if "CHIFAFFA" in all_ca.columns else 0
    part     = chifaffa/max(ca_total,1)*100

    if df.empty:
        alert(f"Aucune donnée CA pour {period_lbl}. Le filtre 'Jour' cherche des quittances à la date exacte. Essayez 'Mois' ou 'Année'.", "warn")
        # Afficher résumé global
        section("📊 CA global (toutes périodes)","APERÇU")
        c1,c2,c3 = st.columns(3)
        kpi(c1,"CA total",fmt(ca_total),"Toutes quittances","",icon="💵")
        kpi(c2,"Nb quittances",f"{len(all_ca):,}","Total","",icon="🧾")
        kpi(c3,"Ticket moyen",fmt(ca_total/max(len(all_ca),1)),"CA/quittance","teal",icon="🎫")
    else:
        c1,c2,c3,c4,c5,c6 = st.columns(6)
        kpi(c1,"CA brut",fmt(chifaffa),"CHIFAFFA","",icon="💵")
        kpi(c2,"Prime nette",fmt(primnett),"PRIMNETT","",icon="📄")
        kpi(c3,"Commissions",fmt(commappo),f"Taux {pct(tx_comm)}","amber",icon="💼")
        kpi(c4,"Nb quittances",f"{nb_q:,}","Émissions","",icon="🧾")
        kpi(c5,"Ticket moyen",fmt(chifaffa/max(nb_q,1)),"CA/quittance","teal",icon="🎫")
        kpi(c6,"Part du CA total",pct(part),"vs toutes périodes","blue",icon="📊")

        st.markdown("")
        t_evo, t_prod, t_int, t_raw = st.tabs(["📈 Évolution","🛒 Par produit","🤝 Par intermédiaire","🔍 Données brutes"])

        with t_evo:
            if "DATECOMP" in df.columns:
                c1,c2 = st.columns(2)
                with c1:
                    evo = all_ca.groupby(all_ca["DATECOMP"].dt.to_period("M").astype(str))["CHIFAFFA"].sum().reset_index()
                    evo.columns = ["Période","CA"]; evo["Cumul"] = evo["CA"].cumsum()
                    fig = make_subplots(specs=[[{"secondary_y":True}]])
                    fig.add_bar(x=evo["Période"],y=evo["CA"],name="CA mensuel",marker_color=GREEN,opacity=.88)
                    fig.add_scatter(x=evo["Période"],y=evo["Cumul"],name="Cumul",line=dict(color=BLUE,width=2.5),secondary_y=True)
                    fig_style(fig,380,"📅 CA mensuel + cumul — tous exercices")
                    st.plotly_chart(fig,use_container_width=True)
                    a,_ = st.columns(2)
                    a.download_button("📥 CSV",dl_csv(evo),"ca_mensuel.csv","text/csv",use_container_width=True,key="dl_evo_m")
                with c2:
                    # Saisonnalité
                    saison = all_ca.groupby("MOIS")["CHIFAFFA"].mean().reset_index() if "MOIS" in all_ca.columns else pd.DataFrame()
                    if not saison.empty:
                        saison.columns=["Mois","CA moyen"]
                        saison["Label"]=saison["Mois"].apply(lambda m:MOIS_FR[int(m)-1] if pd.notna(m) else "")
                        moy_g = saison["CA moyen"].mean()
                        fig2=go.Figure(go.Bar(x=saison["Label"],y=saison["CA moyen"],
                            marker_color=[GREEN if v>=moy_g else f"{GREEN}55" for v in saison["CA moyen"]],
                            text=[fmt(v) for v in saison["CA moyen"]],textposition="outside",textfont_size=9))
                        fig2.add_hline(y=moy_g,line_dash="dash",line_color=RED,
                            annotation_text=f"Moy. {fmt(moy_g)}",annotation_font_size=9)
                        fig_style(fig2,380,"📅 Saisonnalité — CA moyen par mois")
                        st.plotly_chart(fig2,use_container_width=True)
                # Multi-exercices
                if "ANNEE" in all_ca.columns:
                    evo_a=all_ca.groupby("ANNEE")["CHIFAFFA"].sum().reset_index()
                    evo_a=evo_a[evo_a["ANNEE"].between(2000,2030)].sort_values("ANNEE")
                    if len(evo_a)>1:
                        section("📈 Évolution annuelle","MULTI-EXERCICES")
                        fig3=go.Figure(go.Bar(x=evo_a["ANNEE"].astype(str),y=evo_a["CHIFAFFA"],
                            marker=dict(color=evo_a["CHIFAFFA"],colorscale=[[0,MINT],[1,GREEN2]],showscale=False),
                            text=[fmt(v) for v in evo_a["CHIFAFFA"]],textposition="outside"))
                        fig_style(fig3,340,"📈 CA annuel")
                        st.plotly_chart(fig3,use_container_width=True)
                        a,_=st.columns(2)
                        a.download_button("📥 CSV",dl_csv(evo_a),"ca_annuel.csv","text/csv",use_container_width=True,key="dl_ann")

        with t_prod:
            if "LIBECATE" in df.columns:
                cp=df.groupby("LIBECATE").agg(CA=("CHIFAFFA","sum"),NbQ=("CHIFAFFA","count"),
                    Comm=("COMMAPPO","sum"),Prime=("PRIMNETT","sum")).reset_index().sort_values("CA",ascending=False)
                cp["Tx comm"]=cp["Comm"]/cp["CA"].replace(0,np.nan)*100
                cp["Part CA"]=cp["CA"]/cp["CA"].sum()*100
                c1,c2=st.columns(2)
                with c1:
                    fig=go.Figure(go.Bar(x=cp["CA"],y=cp["LIBECATE"].str[:26],orientation="h",
                        marker=dict(color=cp["Tx comm"],colorscale=[[0,MINT],[.5,GREEN],[1,GREEN2]],showscale=True,
                            colorbar=dict(title="Tx comm%",len=.6,thickness=12)),
                        text=[fmt(v) for v in cp["CA"]],textposition="outside",textfont_size=10))
                    fig.update_layout(yaxis=dict(autorange="reversed"))
                    fig_style(fig,400,f"💰 CA + taux commission · {period_lbl}")
                    st.plotly_chart(fig,use_container_width=True)
                with c2:
                    fig2=px.sunburst(cp,path=["LIBECATE"],values="CA",color="Part CA",
                        color_continuous_scale=[[0,MINT],[.5,GREEN],[1,GREEN2]])
                    fig2.update_layout(height=400,margin=dict(l=5,r=5,t=20,b=5))
                    st.plotly_chart(fig2,use_container_width=True)
                cp_d=cp.copy()
                for c_ in ["CA","Comm","Prime"]: cp_d[c_]=cp_d[c_].apply(fmt)
                cp_d["Tx comm"]=cp_d["Tx comm"].apply(lambda x:f"{x:.2f}%")
                cp_d["Part CA"]=cp_d["Part CA"].apply(lambda x:f"{x:.2f}%")
                cp_d.columns=["Produit","CA","Nb quittances","Commissions","Prime nette","Tx comm","Part CA"]
                st.dataframe(cp_d,use_container_width=True,hide_index=True)
                a,b=st.columns(2)
                a.download_button("📥 CSV",dl_csv(cp),"ca_produits.csv","text/csv",use_container_width=True,key="dl_cprod")
                b.download_button("📥 Excel",dl_xlsx(cp),"ca_produits.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_cprod_xl")

        with t_int:
            ag_k="NOM_INTERMEDIAIRE" if "NOM_INTERMEDIAIRE" in df.columns else "NOM_APP"
            if ag_k in df.columns:
                ci=df.groupby(ag_k).agg(CA=("CHIFAFFA","sum"),NbQ=("CHIFAFFA","count"),
                    Comm=("COMMAPPO","sum")).reset_index().sort_values("CA",ascending=False)
                tot_ci=ci["CA"].sum()
                ci["Part %"]=(ci["CA"]/tot_ci*100).round(2)
                ci["Part cum %"]=ci["Part %"].cumsum().round(1)
                # Pareto
                top20=ci.head(20)
                fig=make_subplots(specs=[[{"secondary_y":True}]])
                fig.add_bar(x=top20[ag_k].str[:22],y=top20["CA"],name="CA",marker_color=GREEN,opacity=.85)
                fig.add_scatter(x=top20[ag_k].str[:22],y=top20["Part cum %"],name="Cumul %",
                    line=dict(color=RED,width=2.5),secondary_y=True)
                fig.update_xaxes(tickangle=-35)
                fig_style(fig,420,f"📊 Pareto CA — Top 20 · {period_lbl}")
                st.plotly_chart(fig,use_container_width=True)
                # Partenaires financiers
                if "CODEAPPO_STR" in df.columns:
                    def is_pf(x):
                        s=str(x).strip()
                        return s.isdigit() and len(s)==3 and s!="100"
                    pm=df["CODEAPPO_STR"].apply(is_pf)
                    if pm.sum()>0:
                        ca_pf=float(df.loc[pm,"CHIFAFFA"].sum()); ca_ri=float(df.loc[~pm,"CHIFAFFA"].sum())
                        section("🏦 Partenaires financiers vs Réseau interne","CODEAPPO")
                        pp1,pp2,pp3=st.columns(3)
                        kpi(pp1,"CA Réseau interne",fmt(ca_ri),pct(ca_ri/max(chifaffa,1)*100),"teal",icon="🏢")
                        kpi(pp2,"CA Partenaires",fmt(ca_pf),pct(ca_pf/max(chifaffa,1)*100),"blue",icon="🏦")
                        kpi(pp3,"Nb partenaires",str(df.loc[pm,"CODEAPPO_STR"].nunique()),"Codes 3 chiffres ≠100","",icon="🤝")
                ci_d=ci.head(50).copy()
                for c_ in ["CA","Comm"]: ci_d[c_]=ci_d[c_].apply(fmt)
                ci_d["Part %"]=ci_d["Part %"].apply(lambda x:f"{x:.2f}%")
                ci_d["Part cum %"]=ci_d["Part cum %"].apply(lambda x:f"{x:.1f}%")
                st.dataframe(ci_d,use_container_width=True,hide_index=True,height=360)
                a,b=st.columns(2)
                a.download_button("📥 CSV",dl_csv(ci),"intermediaires.csv","text/csv",use_container_width=True,key="dl_int")
                b.download_button("📥 Excel",dl_xlsx(ci.head(50000)),"intermediaires.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_int_xl")

        with t_raw:
            show_c=[c for c in ["DATECOMP","LIBECATE","NOM_INTERMEDIAIRE","NUMEPOLI","CODEAPPO_STR","CHIFAFFA","PRIMNETT","COMMAPPO","TYPEMOUV","POLICE_KEY"] if c in df.columns]
            srch=st.text_input("🔍 Rechercher",placeholder="Produit, intermédiaire, N° police…",label_visibility="collapsed",key="srch_ca")
            di=df[show_c].copy()
            if "DATECOMP" in di.columns: di["DATECOMP"]=di["DATECOMP"].apply(ds)
            for nc in ["CHIFAFFA","PRIMNETT","COMMAPPO"]:
                if nc in di.columns: di[nc]=di[nc].apply(lambda x:fmt(x,""))
            if srch: di=di[di.apply(lambda r:srch.lower() in str(r).lower(),axis=1)]
            st.dataframe(di.head(500),use_container_width=True,hide_index=True,height=400)
            st.caption(f"Affichage 500 / {len(di):,} lignes")
            a,b=st.columns(2)
            a.download_button("📥 CSV complet",dl_csv(df),f"ca_{period_lbl}.csv","text/csv",use_container_width=True,key="dl_ca_raw")
            b.download_button("📥 Excel",dl_xlsx(df[show_c].head(50000)),f"ca_{period_lbl}.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_ca_raw_xl")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — PORTEFEUILLE
# ═══════════════════════════════════════════════════════════════════════════════
elif "Portefeuille" in page:
    if pf is None: alert("Chargez le Portefeuille dans la barre latérale.","warn"); st.stop()
    df_all = pf  # portefeuille complet pour l'évolution historique
    df = pf_f()  # filtré par période

    section(f"📋 Portefeuille — {period_lbl}","ANALYSE · FILTRES · EXPORT")

    if df.empty and MODE != "annee":
        alert(f"Aucune souscription pour {period_lbl}. Le filtre s'applique sur DATESOUS. Essayez 'Année' ou 'Mois'.","info")
        df = df_all  # afficher tout si filtre trop restrictif pour la période

    # Filtres
    f1,f2,f3,f4 = st.columns(4)
    etat_opts=["Tous"]+sorted(df_all["ETAT_POLICE"].str.strip().dropna().unique().tolist()) if "ETAT_POLICE" in df_all.columns else ["Tous"]
    prod_opts=["Tous"]+sorted(df_all["LIBECATE"].dropna().unique().tolist()) if "LIBECATE" in df_all.columns else ["Tous"]
    etat_sel=f1.selectbox("État",etat_opts,label_visibility="collapsed")
    prod_sel=f2.selectbox("Produit",prod_opts,label_visibility="collapsed")
    srch_pf=f3.text_input("🔍 Rechercher",label_visibility="collapsed",placeholder="Nom assuré, ville, apporteur…")
    villes_opts=["Toutes"]+sorted(df_all["LIBEVILL"].dropna().unique().tolist()[:60]) if "LIBEVILL" in df_all.columns else ["Toutes"]
    ville_sel=f4.selectbox("Ville",villes_opts,label_visibility="collapsed")

    fi=df.copy()
    if etat_sel!="Tous" and "ETAT_POLICE" in fi.columns: fi=fi[fi["ETAT_POLICE"].str.strip()==etat_sel]
    if prod_sel!="Tous" and "LIBECATE" in fi.columns: fi=fi[fi["LIBECATE"]==prod_sel]
    if ville_sel!="Toutes" and "LIBEVILL" in fi.columns: fi=fi[fi["LIBEVILL"]==ville_sel]
    if srch_pf:
        cols_s=[c for c in ["NOM_ASSU","LIBEVILL","NOM_APP","LIBECATE"] if c in fi.columns]
        mask=pd.Series(False,index=fi.index)
        for c_ in cols_s: mask|=fi[c_].astype(str).str.lower().str.contains(srch_pf.lower(),na=False)
        fi=fi[mask]

    nb=len(fi)
    actifs=int((fi["ETAT_POLICE"].str.strip()=="ACTIF").sum()) if "ETAT_POLICE" in fi.columns and nb else 0
    resil =int((fi["ETAT_POLICE"].str.strip()=="RESILIE").sum()) if "ETAT_POLICE" in fi.columns and nb else 0
    monten=float(fi["MONTENCA"].fillna(0).sum()) if "MONTENCA" in fi.columns and nb else 0
    coti_p=float(fi["COTI_PERIODIQUE"].fillna(0).sum()) if "COTI_PERIODIQUE" in fi.columns and nb else 0

    c1,c2,c3,c4,c5 = st.columns(5)
    kpi(c1,"Polices filtrées",f"{nb:,}",f"sur {len(df_all):,} total","",icon="📋")
    kpi(c2,"Actives",f"{actifs:,}",pct(actifs/max(nb,1)*100),"",icon="✅")
    kpi(c3,"Résiliées",f"{resil:,}",pct(resil/max(nb,1)*100),"red",icon="📉")
    kpi(c4,"Encaissements",fmt(monten),"MONTENCA","teal",icon="💰")
    kpi(c5,"Cotisation périodique",fmt(coti_p),"COTI_PERIODIQUE","blue",icon="💳")

    st.markdown("")
    t1,t2,t3,t4 = st.tabs(["📋 Tableau","📊 Statistiques","📈 Évolution souscriptions","🔗 Jointure CA"])

    with t1:
        COLS_SHOW=[c for c in ["POLICE_KEY","NUMEPOLI_P","LIBECATE","ETAT_POLICE","NOM_ASSU","LIBEVILL","NOM_APP","DATESOUS","DATEEFFE","DATEECHE","COTI_PERIODIQUE","MONTENCA","SEXERISQ","CODEPERI","NBRE_PRIME"] if c in fi.columns]
        di=fi[COLS_SHOW].copy()
        for dc in ["DATESOUS","DATEEFFE","DATEECHE"]:
            if dc in di.columns: di[dc]=di[dc].apply(ds)
        for nc in ["COTI_PERIODIQUE","MONTENCA"]:
            if nc in di.columns: di[nc]=di[nc].apply(lambda x:fmt(x,""))
        st.dataframe(di.head(500),use_container_width=True,hide_index=True,height=400)
        st.caption(f"Affichage 500 / {nb:,} polices")
        a,b=st.columns(2)
        a.download_button("📥 CSV",dl_csv(fi),f"pf_{period_lbl}.csv","text/csv",use_container_width=True,key="dl_pf_csv")
        b.download_button("📥 Excel",dl_xlsx(fi[COLS_SHOW].head(50000)),f"pf_{period_lbl}.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_pf_xl")

    with t2:
        sc1,sc2=st.columns(2)
        with sc1:
            if "LIBECATE" in fi.columns:
                pc_=fi.groupby("LIBECATE").agg(Nb=("LIBECATE","count"),CA=("MONTENCA","sum")).reset_index().sort_values("Nb",ascending=False)
                fig=go.Figure(go.Bar(x=pc_["Nb"],y=pc_["LIBECATE"].str[:24],orientation="h",
                    marker=dict(color=pc_["Nb"],colorscale=[[0,MINT],[1,GREEN2]],showscale=False),
                    text=pc_["Nb"].astype(str),textposition="outside",textfont_size=10))
                fig.update_layout(yaxis=dict(autorange="reversed"))
                fig_style(fig,380,"📦 Polices par produit")
                st.plotly_chart(fig,use_container_width=True)
        with sc2:
            if "ETAT_POLICE" in fi.columns:
                etat_c_={"ACTIF":GREEN,"RESILIE":RED,"INACTIF":AMBER,"ECHU":"#5A6478","ASSURE ECHU":"#2C3E50","SUSPENDU":BLUE}
                ec=fi["ETAT_POLICE"].str.strip().value_counts().reset_index(); ec.columns=["État","Nb"]
                fig2=go.Figure(go.Pie(labels=ec["État"],values=ec["Nb"],hole=.44,
                    marker_colors=[etat_c_.get(e,"#888") for e in ec["État"]],
                    textinfo="percent+label",textfont_size=11))
                fig_style(fig2,380,"🔵 États du portefeuille filtré")
                st.plotly_chart(fig2,use_container_width=True)
        sc3,sc4=st.columns(2)
        with sc3:
            if "CODEPERI" in fi.columns:
                per=fi["CODEPERI"].map(CODEPERI_MAP).fillna("Autre").value_counts().reset_index(); per.columns=["Périodicité","Nb"]
                fig3=go.Figure(go.Pie(labels=per["Périodicité"],values=per["Nb"],hole=.44,marker_colors=PAL,textinfo="percent+label",textfont_size=11))
                fig_style(fig3,320,"📅 Périodicité cotisations")
                st.plotly_chart(fig3,use_container_width=True)
        with sc4:
            if "LIBEVILL" in fi.columns:
                vl=fi["LIBEVILL"].value_counts().head(10).reset_index(); vl.columns=["Ville","Nb"]
                fig4=go.Figure(go.Bar(x=vl["Nb"],y=vl["Ville"].str[:18],orientation="h",
                    marker_color=PALETTE if (PALETTE:=PAL[:len(vl)]) else PAL,
                    text=vl["Nb"].astype(str),textposition="outside",textfont_size=10))
                fig4.update_layout(yaxis=dict(autorange="reversed"))
                fig_style(fig4,320,"📍 Top 10 villes")
                st.plotly_chart(fig4,use_container_width=True)
        a,b=st.columns(2)
        a.download_button("📥 CSV stats",dl_csv(pc_ if "LIBECATE" in fi.columns else fi),"stats_pf.csv","text/csv",use_container_width=True,key="dl_stats_pf")

    with t3:
        if "DATESOUS" in df_all.columns:
            es=df_all.groupby(df_all["DATESOUS"].dt.year).agg(Souscriptions=("DATESOUS","count"),CA=("MONTENCA","sum")).reset_index()
            es.columns=["Année","Souscriptions","CA"]; es=es[es["Année"].between(1995,2026)].sort_values("Année")
            fig=make_subplots(specs=[[{"secondary_y":True}]])
            fig.add_bar(x=es["Année"].astype(str),y=es["Souscriptions"],name="Souscriptions",
                marker=dict(color=es["Souscriptions"],colorscale=[[0,MINT],[.4,GREEN],[1,GREEN2]],showscale=False))
            fig.add_scatter(x=es["Année"].astype(str),y=es["CA"],name="CA MONTENCA",
                line=dict(color=RED,width=2.5),mode="lines+markers",secondary_y=True)
            fig.update_yaxes(title_text="Nb souscriptions",secondary_y=False)
            fig.update_yaxes(title_text="CA MONTENCA",secondary_y=True,showgrid=False)
            fig_style(fig,420,"📈 Évolution souscriptions & CA 1995–2025")
            st.plotly_chart(fig,use_container_width=True)
            a,b=st.columns(2)
            a.download_button("📥 CSV",dl_csv(es),"evo_sous.csv","text/csv",use_container_width=True,key="dl_evo_pf")
            b.download_button("📥 Excel",dl_xlsx(es),"evo_sous.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_evo_pf_xl")

    with t4:
        if ca is not None and "POLICE_KEY" in fi.columns and "POLICE_KEY" in ca.columns:
            section("🔗 Polices actives avec CA 2024","JOINTURE PF × CA")
            ca_pf=ca.merge(fi[["POLICE_KEY","LIBECATE","ETAT_POLICE","NOM_ASSU","LIBEVILL","NOM_APP"]].drop_duplicates("POLICE_KEY"),on="POLICE_KEY",how="inner",suffixes=("_CA","_PF"))
            tp=ca_pf.groupby(["POLICE_KEY","LIBECATE","ETAT_POLICE","NOM_ASSU","NOM_APP"]).agg(CA=("CHIFAFFA","sum"),NbQ=("CHIFAFFA","count")).reset_index().sort_values("CA",ascending=False).head(25)
            tp_d=tp.copy(); tp_d["CA"]=tp_d["CA"].apply(fmt)
            st.dataframe(tp_d,use_container_width=True,hide_index=True)
            a,b=st.columns(2)
            a.download_button("📥 CSV jointure",dl_csv(tp),"jointure_pf_ca.csv","text/csv",use_container_width=True,key="dl_join_pf")
        else: alert("Chargez la Base CA pour voir la jointure PF × CA.","info")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — PRODUITS
# ═══════════════════════════════════════════════════════════════════════════════
elif "Produits" in page:
    section(f"🛒 Analyse Produits — {period_lbl}","CA · ÉTATS · STRUCTURE")
    t_cap,t_pfp=st.tabs(["💰 CA par produit","📋 Portefeuille par produit"])
    with t_cap:
        if ca is None: alert("Chargez la Base CA.","warn")
        else:
            df=ca_f()
            if df.empty: alert(f"Aucune donnée CA pour {period_lbl}. Essayez 'Année'.","warn")
            else:
                cp=df.groupby("LIBECATE").agg(CA=("CHIFAFFA","sum"),NbQ=("CHIFAFFA","count"),Comm=("COMMAPPO","sum"),Prime=("PRIMNETT","sum")).reset_index().sort_values("CA",ascending=False)
                cp["Tx comm"]=cp["Comm"]/cp["CA"].replace(0,np.nan)*100; cp["Part CA"]=cp["CA"]/cp["CA"].sum()*100
                c1,c2=st.columns(2)
                with c1:
                    fig=go.Figure(go.Bar(x=cp["CA"],y=cp["LIBECATE"].str[:26],orientation="h",
                        marker=dict(color=cp["Tx comm"],colorscale=[[0,MINT],[.5,GREEN],[1,GREEN2]],showscale=True),
                        text=[fmt(v) for v in cp["CA"]],textposition="outside",textfont_size=10))
                    fig.update_layout(yaxis=dict(autorange="reversed"))
                    fig_style(fig,400,"💰 CA + taux commission")
                    st.plotly_chart(fig,use_container_width=True)
                with c2:
                    fig2=px.sunburst(cp,path=["LIBECATE"],values="CA",color="Part CA",color_continuous_scale=[[0,MINT],[.5,GREEN],[1,GREEN2]])
                    fig2.update_layout(height=400,margin=dict(l=5,r=5,t=20,b=5))
                    st.plotly_chart(fig2,use_container_width=True)
                cp_d=cp.copy()
                for c_ in ["CA","Comm","Prime"]: cp_d[c_]=cp_d[c_].apply(fmt)
                cp_d["Tx comm"]=cp_d["Tx comm"].apply(lambda x:f"{x:.2f}%"); cp_d["Part CA"]=cp_d["Part CA"].apply(lambda x:f"{x:.2f}%")
                cp_d.columns=["Produit","CA","Nb quittances","Commissions","Prime nette","Tx comm","Part CA"]
                st.dataframe(cp_d,use_container_width=True,hide_index=True)
                a,b=st.columns(2)
                a.download_button("📥 CSV",dl_csv(cp),"prod_ca.csv","text/csv",use_container_width=True,key="dl_prod_ca")
                b.download_button("📥 Excel",dl_xlsx(cp),"prod_ca.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_prod_ca_xl")
    with t_pfp:
        if pf is None: alert("Chargez le Portefeuille.","warn")
        else:
            df_p=pf_f() if not pf_f().empty else pf
            pp=df_p.groupby("LIBECATE").agg(Nb=("LIBECATE","count"),
                Actifs=("ETAT_POLICE",lambda x:(x.str.strip()=="ACTIF").sum()),
                Resil=("ETAT_POLICE",lambda x:(x.str.strip()=="RESILIE").sum()),
                Echus=("ETAT_POLICE",lambda x:(x.str.strip().isin(["ECHU","ASSURE ECHU"])).sum()),
                CA=("MONTENCA","sum")).reset_index()
            pp["Tx actif"]=(pp["Actifs"]/pp["Nb"].replace(0,np.nan)*100).round(1)
            pp["Tx resil"]=(pp["Resil"]/pp["Nb"].replace(0,np.nan)*100).round(1); pp=pp.sort_values("Nb",ascending=False)
            fig=go.Figure()
            fig.add_bar(name="✅ Actifs",y=pp["LIBECATE"].str[:22],x=pp["Actifs"],orientation="h",marker_color=GREEN)
            fig.add_bar(name="📉 Résiliés",y=pp["LIBECATE"].str[:22],x=pp["Resil"],orientation="h",marker_color=RED)
            fig.add_bar(name="⌛ Échus",y=pp["LIBECATE"].str[:22],x=pp["Echus"],orientation="h",marker_color=AMBER)
            fig.update_layout(barmode="stack",yaxis=dict(autorange="reversed"))
            fig_style(fig,440,"📊 États polices par produit")
            st.plotly_chart(fig,use_container_width=True)
            pp_d=pp.copy(); pp_d["CA"]=pp_d["CA"].apply(fmt)
            pp_d["Tx actif"]=pp_d["Tx actif"].apply(lambda x:f"{x:.1f}%"); pp_d["Tx resil"]=pp_d["Tx resil"].apply(lambda x:f"{x:.1f}%")
            st.dataframe(pp_d,use_container_width=True,hide_index=True)
            a,b=st.columns(2)
            a.download_button("📥 CSV",dl_csv(pp),"pf_produits.csv","text/csv",use_container_width=True,key="dl_prod_pf")
            b.download_button("📥 Excel",dl_xlsx(pp),"pf_produits.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_prod_pf_xl")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — COMMERCIAUX & PARTENAIRES
# ═══════════════════════════════════════════════════════════════════════════════
elif "Commerciaux" in page:
    section(f"👥 Commerciaux & Partenaires — {period_lbl}","CLASSEMENT · PARETO")
    src=ca_f() if ca is not None else pf_f()
    if src is None or src.empty: alert("Chargez la Base CA ou le Portefeuille.","warn"); st.stop()
    ag_k="NOM_INTERMEDIAIRE" if "NOM_INTERMEDIAIRE" in src.columns else "NOM_APP"
    ca_k="CHIFAFFA" if "CHIFAFFA" in src.columns else "MONTENCA"
    comm_k="COMMAPPO" if "COMMAPPO" in src.columns else None
    grp=src.groupby(ag_k).agg(CA=(ca_k,"sum"),Nb=(ca_k,"count"),
        **({} if not comm_k else {"Comm":(comm_k,"sum")})).reset_index().sort_values("CA",ascending=False).reset_index(drop=True)
    grp.index+=1; tot=grp["CA"].sum()
    grp["Part %"]=(grp["CA"]/max(tot,1)*100).round(2); grp["Part cum %"]=grp["Part %"].cumsum().round(1)
    medals=["🥇","🥈","🥉"]; mc_colors=[GREEN,TEAL,BLUE]
    c1,c2,c3=st.columns(3)
    for col,(med,mc_c),(idx,row) in zip([c1,c2,c3],zip(medals,mc_colors),grp.head(3).iterrows()):
        with col:
            col.markdown(f"""<div style="background:linear-gradient(135deg,{mc_c}18,white);border:2px solid {mc_c};
                 border-radius:14px;padding:1rem;text-align:center">
              <div style="font-size:28px">{med}</div>
              <div style="font-size:12px;font-weight:700;margin:5px 0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{row[ag_k]}">{str(row[ag_k])[:24]}</div>
              <div style="font-size:11px;color:#666">{row['Nb']:,} contrats</div>
              <div style="font-size:17px;font-weight:800;color:{mc_c};margin-top:5px">{fmt(row['CA'])}</div>
              <div style="font-size:10px;color:#888">{pct(row['Part %'])} du CA total</div>
            </div>""", unsafe_allow_html=True)
    st.markdown("")
    t_r,t_p=st.tabs(["🏆 Classement","📊 Pareto"])
    with t_r:
        dr=grp.head(50).copy(); dr["CA"]=dr["CA"].apply(fmt)
        if "Comm" in dr.columns: dr["Comm"]=dr["Comm"].apply(fmt)
        dr["Part %"]=dr["Part %"].apply(lambda x:f"{x:.2f}%"); dr["Part cum %"]=dr["Part cum %"].apply(lambda x:f"{x:.1f}%")
        st.dataframe(dr,use_container_width=True,height=440)
        a,b=st.columns(2)
        a.download_button("📥 CSV",dl_csv(grp),"classement.csv","text/csv",use_container_width=True,key="dl_rank")
        b.download_button("📥 Excel",dl_xlsx(grp.head(50000)),"classement.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_rank_xl")
    with t_p:
        t30=grp.head(30)
        fig=go.Figure(go.Bar(x=t30["CA"],y=t30[ag_k].str[:22],name="CA",marker_color=GREEN,orientation="h",
            text=[fmt(v) for v in t30["CA"]],textposition="outside",textfont_size=10))
        fig.update_layout(yaxis=dict(autorange="reversed"))
        fig_style(fig,500,"📊 Pareto CA — Top 30")
        st.plotly_chart(fig,use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — CLIENTS & GÉOGRAPHIE
# ═══════════════════════════════════════════════════════════════════════════════
elif "Clients" in page:
    if pf is None: alert("Chargez le Portefeuille.","warn"); st.stop()
    df=pf; section("👤 Clients & Géographie","ASSURÉS · VILLES · DÉMOGRAPHIE · ÂGES")
    nb_cli=df["NOM_ASSU"].nunique() if "NOM_ASSU" in df.columns else 0
    nb_vl=df["LIBEVILL"].nunique() if "LIBEVILL" in df.columns else 0
    ca_moy=float(df["MONTENCA"].fillna(0).sum())/max(nb_cli,1) if "MONTENCA" in df.columns else 0
    c1,c2,c3=st.columns(3)
    kpi(c1,"Clients distincts",f"{nb_cli:,}","NOM_ASSU uniques","teal",icon="👤")
    kpi(c2,"Villes couvertes",f"{nb_vl:,}","LIBEVILL","",icon="📍")
    kpi(c3,"MONTENCA moy/client",fmt(ca_moy),"Encaissement moyen","blue",icon="💰")
    t_g,t_d,t_a=st.tabs(["🗺️ Géographie","📊 Démographie","🎂 Pyramide des âges"])
    with t_g:
        if "LIBEVILL" in df.columns:
            c1,c2=st.columns(2)
            with c1:
                vl=df.groupby("LIBEVILL").agg(Nb=("LIBEVILL","count"),CA=("MONTENCA","sum")).reset_index().sort_values("Nb",ascending=False).head(15)
                fig=go.Figure(go.Bar(x=vl["Nb"],y=vl["LIBEVILL"].str[:18],orientation="h",
                    marker=dict(color=vl["Nb"],colorscale=[[0,MINT],[1,GREEN2]],showscale=False),
                    text=vl["Nb"].astype(str),textposition="outside",textfont_size=10))
                fig.update_layout(yaxis=dict(autorange="reversed"))
                fig_style(fig,400,"📍 Top 15 villes — Polices")
                st.plotly_chart(fig,use_container_width=True)
            with c2:
                vl_ca=df.groupby("LIBEVILL")["MONTENCA"].sum().reset_index().sort_values("MONTENCA",ascending=False).head(12)
                fig2=go.Figure(go.Bar(x=vl_ca["MONTENCA"],y=vl_ca["LIBEVILL"].str[:18],orientation="h",
                    marker=dict(color=vl_ca["MONTENCA"],colorscale=[[0,MINT],[1,GREEN2]],showscale=False),
                    text=[fmt(v) for v in vl_ca["MONTENCA"]],textposition="outside",textfont_size=10))
                fig2.update_layout(yaxis=dict(autorange="reversed"))
                fig_style(fig2,400,"💰 Top 12 villes — CA (MONTENCA)")
                st.plotly_chart(fig2,use_container_width=True)
            vl_e=df.groupby("LIBEVILL").agg(Nb=("LIBEVILL","count"),CA=("MONTENCA","sum")).reset_index().sort_values("Nb",ascending=False)
            vl_e["CA"]=vl_e["CA"].apply(fmt)
            st.dataframe(vl_e.head(30),use_container_width=True,hide_index=True)
            a,b=st.columns(2)
            a.download_button("📥 CSV villes",dl_csv(vl_e),"geo.csv","text/csv",use_container_width=True,key="dl_geo")
            b.download_button("📥 Excel",dl_xlsx(vl_e),"geo.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_geo_xl")
    with t_d:
        c1,c2,c3=st.columns(3)
        with c1:
            if "SEXERISQ" in df.columns:
                sx=df["SEXERISQ"].map({"M":"Hommes","F":"Femmes"}).value_counts().reset_index(); sx.columns=["Sexe","Nb"]
                fig=go.Figure(go.Pie(labels=sx["Sexe"],values=sx["Nb"],hole=.44,marker_colors=[BLUE,GREEN],textinfo="percent+label+value",textfont_size=12))
                fig_style(fig,320,"👥 Répartition H/F"); st.plotly_chart(fig,use_container_width=True)
        with c2:
            if "CODEPERI" in df.columns:
                per=df["CODEPERI"].map(CODEPERI_MAP).fillna("Autre").value_counts().reset_index(); per.columns=["Périodicité","Nb"]
                fig2=go.Figure(go.Pie(labels=per["Périodicité"],values=per["Nb"],hole=.44,marker_colors=PAL,textinfo="percent+label",textfont_size=11))
                fig_style(fig2,320,"📅 Périodicité cotisations"); st.plotly_chart(fig2,use_container_width=True)
        with c3:
            if "NOM_APP" in df.columns:
                ap=df[df["ETAT_POLICE"].str.strip()=="ACTIF"]["NOM_APP"].value_counts().head(10).reset_index() if "ETAT_POLICE" in df.columns else df["NOM_APP"].value_counts().head(10).reset_index()
                ap.columns=["Apporteur","Nb actifs"]
                fig3=go.Figure(go.Bar(y=ap["Apporteur"].str[:18],x=ap["Nb actifs"],orientation="h",marker_color=GREEN,text=ap["Nb actifs"].astype(str),textposition="outside",textfont_size=10))
                fig3.update_layout(yaxis=dict(autorange="reversed"))
                fig_style(fig3,320,"🏆 Top apporteurs (polices actives)"); st.plotly_chart(fig3,use_container_width=True)
    with t_a:
        if "DATENAIS" in df.columns and "SEXERISQ" in df.columns:
            da=df[["DATENAIS","SEXERISQ","MONTENCA"]].copy()
            da["DATENAIS"]=pd.to_datetime(da["DATENAIS"],errors="coerce")
            da=da.dropna(subset=["DATENAIS"])
            da["age"]=(pd.Timestamp.now()-da["DATENAIS"]).dt.days/365.25
            da=da[(da["age"]>=0)&(da["age"]<=95)]
            bins=list(range(0,100,5)); da["tranch"]=pd.cut(da["age"],bins=bins,right=False).astype(str)
            pyr=da.groupby(["tranch","SEXERISQ"]).size().unstack(fill_value=0).reset_index()
            if "M" in pyr.columns and "F" in pyr.columns:
                fig=go.Figure()
                fig.add_bar(y=pyr["tranch"],x=-pyr["M"],name="Hommes",orientation="h",marker_color=BLUE,text=pyr["M"].astype(str),textposition="outside",textfont_size=9)
                fig.add_bar(y=pyr["tranch"],x=pyr["F"],name="Femmes",orientation="h",marker_color=GREEN,text=pyr["F"].astype(str),textposition="outside",textfont_size=9)
                fig.update_layout(barmode="overlay",xaxis=dict(tickvals=list(range(-4000,4001,500)),ticktext=[str(abs(x)) for x in range(-4000,4001,500)]))
                fig_style(fig,520,"🎂 Pyramide des âges (tranches quinquennales)")
                st.plotly_chart(fig,use_container_width=True)
                a,_=st.columns(2)
                a.download_button("📥 CSV pyramide",dl_csv(da[["age","SEXERISQ"]]),"pyramide.csv","text/csv",use_container_width=True,key="dl_pyr")
        else: alert("Colonnes DATENAIS et SEXERISQ requises dans le portefeuille.","info")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — SINISTRES & PROVISIONS
# ═══════════════════════════════════════════════════════════════════════════════
elif "Sinistres" in page:
    if sin is None: alert("Chargez le fichier Prestations.","warn"); st.stop()
    df_s=sin  # tout le fichier pour les provisions historiques
    df_sf=sin_f()  # filtré par période

    section(f"⚠️ Sinistres & Provisions — {period_lbl}","ANALYSE ACTUARIELLE · SAP · S/P")
    tot_sin=float(sin["Réglement Total"].fillna(0).sum()) if "Réglement Total" in sin.columns else 0
    tot_sap=float(sin["SAP au 31/12/2025"].fillna(0).sum()) if "SAP au 31/12/2025" in sin.columns else 0
    tot_hon=float(sin["Réglement Honoraires"].fillna(0).sum()) if "Réglement Honoraires" in sin.columns else 0
    charge_u=tot_sin+tot_sap+tot_hon
    nb_sin=len(sin); nb_clos=int((sin["Sort Sinistre"]=="Cloturé").sum()) if "Sort Sinistre" in sin.columns else 0
    nb_ouv=int((sin["Sort Sinistre"]=="Ouvert").sum()) if "Sort Sinistre" in sin.columns else 0
    ca_all=float(ca["CHIFAFFA"].fillna(0).sum()) if ca is not None and "CHIFAFFA" in ca.columns else 0
    sp=tot_sin/max(ca_all,1)*100; cout_m=tot_sin/max(nb_clos,1)
    actifs_n=int((pf["ETAT_POLICE"].str.strip()=="ACTIF").sum()) if pf is not None and "ETAT_POLICE" in pf.columns else 1
    burning=charge_u/max(actifs_n,1)*1000

    c1,c2,c3,c4,c5,c6=st.columns(6)
    kpi(c1,"Total réglé",fmt(tot_sin),"Toutes périodes","red",icon="💊")
    kpi(c2,"SAP (provisions)",fmt(tot_sap),"Au 31/12/2025","amber",icon="📌")
    kpi(c3,"Charge ultime",fmt(charge_u),"Réglé+SAP+Hon.","red",icon="⚖️")
    kpi(c4,"Ratio S/P",pct(sp),"vs CA","red" if sp>80 else "amber",icon="📐")
    kpi(c5,"Coût moy/clos",fmt(cout_m),"Dossiers clos","teal",icon="💰")
    kpi(c6,"Burning Cost",fmt(burning),"Charge/1 000 actifs","red",icon="🔥")

    if not df_sf.empty and len(df_sf)<len(sin):
        alert(f"Période filtrée : {len(df_sf):,} dossiers (sur {len(sin):,}) pour {period_lbl}. Les KPIs ci-dessus couvrent toutes les périodes.","info")

    t_n,t_e,t_p,t_tri,t_r=st.tabs(["🏷️ Par nature","📈 Évolution","🛒 Par produit","📐 Triangle dev.","🔍 Données brutes"])

    with t_n:
        if "Nature Sinistre" in sin.columns:
            nat=sin.groupby("Nature Sinistre").agg(
                Nb=("Nature Sinistre","count"),Regle=("Réglement Total","sum"),SAP=("SAP au 31/12/2025","sum")).reset_index().sort_values("Regle",ascending=False)
            nat["Charge"]=nat["Regle"]+nat["SAP"]; nat["Coût moy"]=nat["Regle"]/nat["Nb"].replace(0,np.nan)
            c1,c2=st.columns(2)
            with c1:
                fig=go.Figure()
                fig.add_bar(y=nat["Nature Sinistre"].str[:22],x=nat["Regle"],name="Réglé",marker_color=RED,orientation="h")
                fig.add_bar(y=nat["Nature Sinistre"].str[:22],x=nat["SAP"],name="SAP",marker_color=AMBER,orientation="h")
                fig.update_layout(barmode="stack",yaxis=dict(autorange="reversed"))
                fig_style(fig,360,"💊 Réglé + SAP par nature"); st.plotly_chart(fig,use_container_width=True)
            with c2:
                fig2=px.treemap(nat,path=["Nature Sinistre"],values="Charge",color="Nb",
                    color_continuous_scale=[[0,MINT],[.5,AMBER],[1,RED]])
                fig2.update_layout(height=360,margin=dict(l=5,r=5,t=20,b=5)); st.plotly_chart(fig2,use_container_width=True)
            nat_d=nat.copy()
            for c_ in ["Regle","SAP","Charge","Coût moy"]: nat_d[c_]=nat_d[c_].apply(fmt)
            st.dataframe(nat_d,use_container_width=True,hide_index=True)
            a,b=st.columns(2)
            a.download_button("📥 CSV",dl_csv(nat),"sin_nature.csv","text/csv",use_container_width=True,key="dl_sin_nat")
            b.download_button("📥 Excel",dl_xlsx(nat),"sin_nature.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_sin_nat_xl")

    with t_e:
        if "ANNEE_SIN" in sin.columns:
            evo=sin.groupby("ANNEE_SIN").agg(Nb=("ANNEE_SIN","count"),Regle=("Réglement Total","sum"),SAP=("SAP au 31/12/2025","sum")).reset_index()
            evo=evo[evo["ANNEE_SIN"].between(1997,2025)].sort_values("ANNEE_SIN")
            fig=make_subplots(specs=[[{"secondary_y":True}]])
            fig.add_bar(x=evo["ANNEE_SIN"].astype(str),y=evo["Regle"],name="Réglé",marker_color=RED,opacity=.82)
            fig.add_bar(x=evo["ANNEE_SIN"].astype(str),y=evo["SAP"],name="SAP",marker_color=AMBER,opacity=.82)
            fig.add_scatter(x=evo["ANNEE_SIN"].astype(str),y=evo["Nb"],name="Nb dossiers",
                line=dict(color=GREEN,width=2.5),mode="lines+markers",secondary_y=True)
            fig.update_layout(barmode="stack")
            fig.update_yaxes(title_text="Montant (FCFA)",secondary_y=False)
            fig.update_yaxes(title_text="Nb dossiers",secondary_y=True,showgrid=False)
            fig_style(fig,420,"📈 Sinistres par exercice 1997–2025"); st.plotly_chart(fig,use_container_width=True)
            a,b=st.columns(2)
            a.download_button("📥 CSV",dl_csv(evo),"evo_sin.csv","text/csv",use_container_width=True,key="dl_evo_sin")
            b.download_button("📥 Excel",dl_xlsx(evo),"evo_sin.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_evo_sin_xl")

    with t_p:
        cat_c="Libéllé Catégorie" if "Libéllé Catégorie" in sin.columns else "Libellé Catégorie"
        if cat_c in sin.columns:
            sp2=sin.groupby(cat_c).agg(Nb=(cat_c,"count"),Regle=("Réglement Total","sum"),SAP=("SAP au 31/12/2025","sum")).reset_index().sort_values("Regle",ascending=False)
            sp2["Charge"]=sp2["Regle"]+sp2["SAP"]
            fig=go.Figure()
            fig.add_bar(x=sp2["Regle"],y=sp2[cat_c].str[:24],name="Réglé",marker_color=RED,orientation="h")
            fig.add_bar(x=sp2["SAP"],y=sp2[cat_c].str[:24],name="SAP",marker_color=AMBER,orientation="h")
            fig.update_layout(barmode="stack",yaxis=dict(autorange="reversed"))
            fig_style(fig,360,"🛒 Sinistres par produit"); st.plotly_chart(fig,use_container_width=True)
            sp2_d=sp2.copy()
            for c_ in ["Regle","SAP","Charge"]: sp2_d[c_]=sp2_d[c_].apply(fmt)
            st.dataframe(sp2_d,use_container_width=True,hide_index=True)
            a,_=st.columns(2)
            a.download_button("📥 CSV",dl_csv(sp2),"sin_prod.csv","text/csv",use_container_width=True,key="dl_sin_p")

    with t_tri:
        section("📐 Triangle de développement des sinistres","EXERCICE × SURVENANCE")
        if "ANNEE_SIN" in sin.columns and "Date Survenance" in sin.columns:
            sin2=sin.copy()
            sin2["DEV_YEAR"]=pd.to_datetime(sin2["Date Survenance"],errors="coerce").dt.year.astype("Int64")
            tri=sin2.pivot_table(index="ANNEE_SIN",columns="DEV_YEAR",values="Réglement Total",aggfunc="sum",fill_value=0)
            tri_d=tri.copy().astype(float)
            for col_ in tri_d.columns: tri_d[col_]=tri_d[col_].apply(fmt)
            alert("Triangle des montants réglés par exercice sinistre (lignes) et année de survenance (colonnes).","info")
            st.dataframe(tri_d,use_container_width=True,height=380)
            a,_=st.columns(2)
            a.download_button("📥 CSV triangle",dl_csv(tri.reset_index()),"triangle.csv","text/csv",use_container_width=True,key="dl_tri")
        else: alert("Colonnes ANNEE_SIN et Date Survenance requises.","info")

    with t_r:
        cs=[c for c in ["Date Survenance","Libéllé Catégorie","Nature Sinistre","Sort Sinistre","Souscripteur","Désignation risque","Réglement Total","SAP au 31/12/2025","Date Déclaration","Date validation","Nom Bénéficiaire","Exercice Sinistre","POLICE_KEY"] if c in sin.columns]
        srch_s=st.text_input("🔍 Rechercher",label_visibility="collapsed",placeholder="Nature, souscripteur, produit…",key="srch_sin")
        di_s=sin[cs].copy()
        for dc in ["Date Survenance","Date Déclaration","Date validation"]:
            if dc in di_s.columns: di_s[dc]=di_s[dc].apply(ds)
        for nc in ["Réglement Total","SAP au 31/12/2025"]:
            if nc in di_s.columns: di_s[nc]=di_s[nc].apply(lambda x:fmt(x,""))
        if srch_s: di_s=di_s[di_s.apply(lambda r:srch_s.lower() in str(r).lower(),axis=1)]
        st.dataframe(di_s.head(500),use_container_width=True,hide_index=True,height=420)
        st.caption(f"Affichage 500 / {len(di_s):,} lignes")
        a,b=st.columns(2)
        a.download_button("📥 CSV complet",dl_csv(sin),"prestations.csv","text/csv",use_container_width=True,key="dl_sin_raw")
        b.download_button("📥 Excel",dl_xlsx(sin[cs].head(50000)),"prestations.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_sin_raw_xl")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — ACTUARIAT AVANCÉ
# ═══════════════════════════════════════════════════════════════════════════════
elif "Actuariat" in page:
    section("📐 Actuariat Avancé","CIMA · SAP · BURNING COST · JOINTURES")
    t_c,t_p,t_l=st.tabs(["🏛️ CIMA & Solvabilité","📌 Provisions SAP","🔗 Liaison inter-bases"])
    with t_c:
        if pf is None: alert("Chargez le Portefeuille.","warn")
        else:
            nb=len(pf); ek="ETAT_POLICE"
            actifs=int((pf[ek].str.strip().isin(["ACTIF"])).sum()) if ek in pf.columns else 0
            resil=int((pf[ek].str.strip()=="RESILIE").sum()) if ek in pf.columns else 0
            inact=int((pf[ek].str.strip()=="INACTIF").sum()) if ek in pf.columns else 0
            echu=int((pf[ek].str.strip().isin(["ECHU","ASSURE ECHU"])).sum()) if ek in pf.columns else 0
            tx_act=actifs/max(nb,1)*100; tx_res=resil/max(nb-inact,1)*100
            ca_t=float(ca["CHIFAFFA"].fillna(0).sum()) if ca is not None and "CHIFAFFA" in ca.columns else 0
            sin_t=float(sin["Réglement Total"].fillna(0).sum()) if sin is not None and "Réglement Total" in sin.columns else 0
            sap_t=float(sin["SAP au 31/12/2025"].fillna(0).sum()) if sin is not None and "SAP au 31/12/2025" in sin.columns else 0
            sp=sin_t/max(ca_t,1)*100; charge_u=sin_t+sap_t; burning=charge_u/max(actifs,1)*1000
            monten=float(pf["MONTENCA"].fillna(0).apply(lambda x: float(str(x).replace(" ","").replace(",",".")) if str(x).replace(" ","").replace(",",".").replace(".","",1).replace("-","",1).isdigit() else 0).sum()) if "MONTENCA" in pf.columns else 0
            indics=[
                (tx_act,"Taux d'activité net",50,">=",GREEN),
                (tx_res,"Taux résiliation CIMA",25,"<=",RED),
                (sp,"Ratio S/P",80,"<=",AMBER),
                (inact/max(nb,1)*100,"Part inactifs",5,"<=",AMBER),
            ]
            for v,lbl,seuil,op,col in indics:
                ok=v>=seuil if op==">=" else v<=seuil; c_=GREEN if ok else RED
                st.markdown(f"""<div style="display:flex;align-items:center;justify-content:space-between;
                     padding:10px 14px;border-left:4px solid {c_};background:{c_}0D;
                     border-radius:0 10px 10px 0;margin-bottom:8px">
                  <div><div style="font-size:13px;font-weight:700;color:{NAVY}">{lbl}</div>
                  <div style="font-size:10px;color:#8899AA">Norme CIMA : {op}{seuil}%</div></div>
                  <div style="font-size:20px;font-weight:900;color:{c_}">{pct(v)} {'✅' if ok else '⚠️'}</div>
                </div>""", unsafe_allow_html=True)
            st.markdown("")
            ac1,ac2,ac3,ac4=st.columns(4)
            kpi(ac1,"Burning Cost",fmt(burning),"Charge ultime / 1 000 actifs","red",icon="🔥")
            kpi(ac2,"Charge ultime",fmt(charge_u),"Réglé + SAP","red",icon="⚖️")
            kpi(ac3,"CA 2024",fmt(ca_t),"Base calcul S/P","teal",icon="💰")
            kpi(ac4,"Encaissements PF",fmt(monten),"MONTENCA total","blue",icon="📊")
    with t_p:
        if sin is None: alert("Chargez les Prestations.","warn")
        else:
            prov=sin.groupby("Nature Sinistre").agg(
                Nb=("Nature Sinistre","count"),Regle=("Réglement Total","sum"),
                SAP=("SAP au 31/12/2025","sum"),Ouvert=("Sort Sinistre",lambda x:(x=="Ouvert").sum())
            ).reset_index()
            prov["Charge"]=prov["Regle"]+prov["SAP"]
            prov["Ratio SAP/Charge"]=prov["SAP"]/prov["Charge"].replace(0,np.nan)*100
            prov["Coût moy clos"]=prov["Regle"]/(prov["Nb"]-prov["Ouvert"]).replace(0,np.nan)
            fig=go.Figure()
            fig.add_bar(y=prov["Nature Sinistre"].str[:22],x=prov["Regle"],name="Réglé cumulé",marker_color=GREEN,orientation="h")
            fig.add_bar(y=prov["Nature Sinistre"].str[:22],x=prov["SAP"],name="SAP résiduel",marker_color=AMBER,orientation="h")
            fig.update_layout(barmode="stack",yaxis=dict(autorange="reversed"))
            fig_style(fig,360,"📌 Structure Réglé / SAP par nature"); st.plotly_chart(fig,use_container_width=True)
            pv=prov.copy()
            for c_ in ["Regle","SAP","Charge","Coût moy clos"]: pv[c_]=pv[c_].apply(fmt)
            pv["Ratio SAP/Charge"]=pv["Ratio SAP/Charge"].apply(lambda x:f"{x:.1f}%" if pd.notna(x) else "—")
            pv.columns=["Nature","Nb","Réglé","SAP","Dossiers ouverts","Charge","Ratio SAP/Charge","Coût moy clos"]
            st.dataframe(pv,use_container_width=True,hide_index=True)
            a,b=st.columns(2)
            a.download_button("📥 CSV provisions",dl_csv(prov),"provisions.csv","text/csv",use_container_width=True,key="dl_prov")
            b.download_button("📥 Excel",dl_xlsx(prov),"provisions.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_prov_xl")
    with t_l:
        section("🔗 Liaison inter-bases","POLICE_KEY · MATCHING · CA × PF × SIN")
        if pf is not None and ca is not None and "POLICE_KEY" in pf.columns and "POLICE_KEY" in ca.columns:
            mc=ca["POLICE_KEY"].isin(pf["POLICE_KEY"]).sum()
            ms=sin["POLICE_KEY"].isin(pf["POLICE_KEY"]).sum() if sin is not None and "POLICE_KEY" in sin.columns else 0
            mcs=sin["POLICE_KEY"].isin(ca["POLICE_KEY"]).sum() if sin is not None and "POLICE_KEY" in sin.columns and "POLICE_KEY" in ca.columns else 0
            l1,l2,l3=st.columns(3)
            kpi(l1,"CA ↔ PF",f"{mc:,}",f"{mc/max(len(ca),1)*100:.1f}% des quittances","teal",icon="🔗")
            kpi(l2,"SIN ↔ PF",f"{ms:,}",f"{ms/max(len(sin) if sin is not None else 1,1)*100:.1f}%","teal",icon="🔗")
            kpi(l3,"SIN ↔ CA",f"{mcs:,}",f"{mcs/max(len(sin) if sin is not None else 1,1)*100:.1f}%","blue",icon="🔗")
            section("📊 Top polices — Jointure CA × PF × SIN","CA DÉCROISSANT")
            pf_lk=pf[["POLICE_KEY","LIBECATE","ETAT_POLICE","NOM_ASSU","LIBEVILL","NOM_APP"]].drop_duplicates("POLICE_KEY")
            ca_pf=ca.merge(pf_lk,on="POLICE_KEY",how="inner",suffixes=("","_PF"))
            if sin is not None and "POLICE_KEY" in sin.columns:
                sin_agg=sin.groupby("POLICE_KEY").agg(Regle=("Réglement Total","sum"),SAP=("SAP au 31/12/2025","sum"),NbSin=("POLICE_KEY","count")).reset_index()
                ca_pf=ca_pf.merge(sin_agg,on="POLICE_KEY",how="left")
            else:
                ca_pf["Regle"]=np.nan; ca_pf["SAP"]=np.nan; ca_pf["NbSin"]=np.nan
            tp=ca_pf.groupby(["POLICE_KEY","LIBECATE","ETAT_POLICE","NOM_ASSU","NOM_APP"]).agg(
                CA=("CHIFAFFA","sum"),NbQ=("CHIFAFFA","count"),
                Regle=("Regle","first"),SAP=("SAP","first"),NbSin=("NbSin","first")
            ).reset_index().sort_values("CA",ascending=False).head(30)
            tp_d=tp.copy()
            for c_ in ["CA","Regle","SAP"]: tp_d[c_]=tp_d[c_].apply(lambda x:fmt(x) if pd.notna(x) else "—")
            tp_d["NbSin"]=tp_d["NbSin"].apply(lambda x:str(int(x)) if pd.notna(x) else "0")
            st.dataframe(tp_d,use_container_width=True,hide_index=True)
            a,_=st.columns(2)
            a.download_button("📥 CSV jointure 3 bases",dl_csv(tp),"jointure_3bases.csv","text/csv",use_container_width=True,key="dl_join3")
        else: alert("Chargez le Portefeuille et la Base CA.","info")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — PRÉVISIONS & TENDANCES
# ═══════════════════════════════════════════════════════════════════════════════
elif "Prévisions" in page:
    section("🔮 Prévisions & Tendances","MODÈLE POLYNOMIAL · SAISONNALITÉ · PROJECTION")
    if ca is None and pf is None: alert("Chargez la Base CA ou le Portefeuille.","warn"); st.stop()
    src=ca if ca is not None else pf
    ca_k="CHIFAFFA" if "CHIFAFFA" in src.columns else "MONTENCA"
    d_k="DATECOMP" if "DATECOMP" in src.columns else "DATESOUS"
    if d_k not in src.columns: alert("Colonne date introuvable.","warn"); st.stop()
    src2=src[[d_k,ca_k]].copy()
    src2[d_k]=pd.to_datetime(src2[d_k],errors="coerce"); src2=src2.dropna(subset=[d_k])
    mo=src2.groupby(src2[d_k].dt.to_period("M").astype(str))[ca_k].sum().reset_index()
    mo.columns=["Période","CA"]; mo=mo.sort_values("Période")
    n=len(mo)
    if n<6: alert("Données insuffisantes pour les prévisions (< 6 mois).","warn"); st.stop()
    c1,c2=st.columns(2)
    deg_sel=c1.slider("Degré du polynôme",1,4,2,key="deg_s")
    n_hor=c2.slider("Mois à prévoir",1,24,12,key="n_hor_s")
    xs=np.arange(n); ys=mo["CA"].values.astype(float)
    coeffs=np.polyfit(xs,ys,deg_sel)
    trend_h=np.polyval(coeffs,xs)
    x_f=np.arange(n,n+n_hor); trend_f=np.maximum(np.polyval(coeffs,x_f),0)
    r2=1-np.sum((ys-trend_h)**2)/max(np.sum((ys-ys.mean())**2),1)
    last_p=pd.Period(mo["Période"].iloc[-1],"M")
    fut_l=[str(last_p+i+1) for i in range(n_hor)]
    kc1,kc2,kc3=st.columns(3)
    kpi(kc1,"CA historique total",fmt(ys.sum()),"Série complète","",icon="💰")
    kpi(kc2,f"R² modèle (deg {deg_sel})",f"{r2:.4f}","Qualité ajustement","teal" if r2>.8 else "amber",icon="📐")
    kpi(kc3,f"Prévision H+{n_hor}",fmt(trend_f[-1]),"Projection","blue",icon="🔮")
    st.markdown("")
    fig=go.Figure()
    fig.add_scatter(x=mo["Période"],y=ys,name="CA historique",line=dict(color=GREEN,width=2),mode="lines+markers",marker=dict(size=4))
    fig.add_scatter(x=mo["Période"],y=trend_h,name="Tendance ajustée",line=dict(color=TEAL,width=2,dash="dot"),mode="lines")
    fig.add_scatter(x=fut_l,y=trend_f,name="Prévision",line=dict(color=RED,width=2.5,dash="dash"),mode="lines+markers",marker=dict(symbol="star",size=9,color=RED))
    fig.add_vrect(x0=fut_l[0],x1=fut_l[-1],fillcolor="rgba(192,57,43,0.04)",line_width=0,annotation_text="Zone prévision")
    fig_style(fig,480,f"🔮 Modèle polynomial (deg {deg_sel}) — R²={r2:.3f}")
    st.plotly_chart(fig,use_container_width=True)
    df_fut=pd.DataFrame({"Période":fut_l,"CA prévu":[fmt(v) for v in trend_f],"Valeur (FCFA)":trend_f.round(0)})
    st.dataframe(df_fut[["Période","CA prévu"]],use_container_width=True,hide_index=True)
    a,b=st.columns(2)
    a.download_button("📥 CSV prévisions",dl_csv(df_fut),"previsions.csv","text/csv",use_container_width=True,key="dl_prev")
    b.download_button("📥 Excel",dl_xlsx(df_fut),"previsions.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_prev_xl")
    if n>=12:
        section("📅 Saisonnalité mensuelle","CA MOYEN PAR MOIS")
        src2["MOIS"]=src2[d_k].dt.month
        saison=src2.groupby("MOIS")[ca_k].mean().reset_index(); saison.columns=["Mois","CA moyen"]
        saison["Label"]=saison["Mois"].apply(lambda m:MOIS_FR[int(m)-1] if pd.notna(m) else "")
        moy_g=saison["CA moyen"].mean()
        fig2=go.Figure(go.Bar(x=saison["Label"],y=saison["CA moyen"],
            marker_color=[GREEN if v>=moy_g else f"{GREEN}55" for v in saison["CA moyen"]],
            text=[fmt(v) for v in saison["CA moyen"]],textposition="outside",textfont_size=10))
        fig2.add_hline(y=moy_g,line_dash="dash",line_color=RED,annotation_text=f"Moy. {fmt(moy_g)}",annotation_font_size=10)
        fig_style(fig2,360,"📅 Saisonnalité — CA moyen par mois")
        st.plotly_chart(fig2,use_container_width=True)
        a2,_=st.columns(2)
        a2.download_button("📥 CSV saisonnalité",dl_csv(saison),"saisonnalite.csv","text/csv",use_container_width=True,key="dl_sai")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — SAISIE BIA (7 étapes)
# ═══════════════════════════════════════════════════════════════════════════════
elif "Saisie BIA" in page:
    # Compteurs BIA (compatibles PG et SQLite via bia_all())
    _df_bia_hdr = bia_all()
    nb_bia  = len(_df_bia_hdr)
    cot_tot = float(_df_bia_hdr["cotisation"].fillna(0).astype(float).sum()) if not _df_bia_hdr.empty else 0
    nb_val  = int((_df_bia_hdr["statut"]=="Validé").sum()) if not _df_bia_hdr.empty else 0
    c1,c2,c3=st.columns(3)
    kpi(c1,"BIA enregistrés",str(nb_bia),"Total base BIA","teal",icon="📋")
    kpi(c2,"Validés",str(nb_val),f"{nb_val/max(nb_bia,1)*100:.0f}%","",icon="✅")
    kpi(c3,"Cotisations BIA",fmt(cot_tot),"Total","blue",icon="💰")

    # ── Étape 1 : Sélection du produit ────────────────────────────────────────
    section("Étape 1 — Sélection du produit","AFG ASSURANCES BÉNIN VIE")
    GC={"Groupe 1":RED,"Groupe 2":GREEN}

    # Groupe 1 — Décès
    with st.expander("🛡️ Groupe 1 — Décès & Vie", expanded=True):
        col_a, col_b = st.columns(2)
        # AVIGBO
        with col_a:
            st.markdown(f"""<div style="border:2px solid {RED}44;border-radius:10px;padding:12px 14px;margin-bottom:6px">
              <span style="background:{RED};color:white;font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px">221</span>
              <div style="font-size:13px;font-weight:700;margin-top:6px;color:{NAVY}">ASSURTOUS AVIGBO</div>
              <div style="font-size:11px;color:#666;margin-top:3px">Décès · Barème fixe</div>
              <div style="font-size:10px;color:#888;margin-top:5px;line-height:1.6">
                100 F/mois → Capital 100 000 F  (unique : 1 000 F)<br>
                200 F/mois → Capital 200 000 F  (unique : 2 000 F)<br>
                300 F/mois → Capital 300 000 F  (unique : 3 000 F)
              </div>
            </div>""", unsafe_allow_html=True)
            if st.button("Choisir AVIGBO (221)", key="bp_221", use_container_width=True):
                st.session_state["bia_prod"]="221"; st.session_state["bia_step"]=2; st.rerun()
        # VIGNINOU
        with col_b:
            st.markdown(f"""<div style="border:2px solid {RED}44;border-radius:10px;padding:12px 14px;margin-bottom:6px">
              <span style="background:{RED};color:white;font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px">220</span>
              <div style="font-size:13px;font-weight:700;margin-top:6px;color:{NAVY}">ASSURTOUS VIGNINOU</div>
              <div style="font-size:11px;color:#666;margin-top:3px">Décès · Durée max 12 mois · Barème fixe</div>
              <div style="font-size:10px;color:#888;margin-top:5px;line-height:1.6">
                400 F/mois → Capital 500 000 F  (unique : 48 000 F)<br>
                800 F/mois → Capital 1 000 000 F (unique : 96 000 F)<br>
                1 200 F/mois → Capital 1 500 000 F (unique : 144 000 F)
              </div>
            </div>""", unsafe_allow_html=True)
            if st.button("Choisir VIGNINOU (220)", key="bp_220", use_container_width=True):
                st.session_state["bia_prod"]="220"; st.session_state["bia_step"]=2; st.rerun()

    # Groupe 2 — Épargne
    with st.expander("💰 Groupe 2 — Épargne & Capitalisation", expanded=True):
        st.markdown(f"""<div style="border:2px solid {GREEN}44;border-radius:10px;padding:12px 14px;margin-bottom:6px">
          <span style="background:{GREEN};color:white;font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px">EP0</span>
          <div style="font-size:13px;font-weight:700;margin-top:6px;color:{NAVY}">Épargne</div>
          <div style="font-size:11px;color:#666;margin-top:3px">Épargne vie · Périodicité libre · Capital calculé à la souscription</div>
          <div style="font-size:10px;color:#888;margin-top:5px">
            Périodicités disponibles : Journalière · Hebdomadaire · Mensuelle · Trimestrielle · Semestrielle · Annuelle · Unique<br>
            Chargements : 1% acquisition + 0.5% gestion · Taux technique : 3.5%
          </div>
        </div>""", unsafe_allow_html=True)
        if st.button("Choisir Épargne", key="bp_EP0", use_container_width=True):
            st.session_state["bia_prod"]="EP0"; st.session_state["bia_step"]=2; st.rerun()

    if "bia_prod" not in st.session_state:
        alert("Sélectionnez un produit pour afficher le formulaire BIA.","info"); st.stop()
    prod=next((p for p in PRODUITS if p["code"]==st.session_state.get("bia_prod")),None)
    if not prod: st.session_state.pop("bia_prod",None); st.rerun()
    gc=GC.get(prod["grp"],BLUE); step=st.session_state.get("bia_step",2)
    is_avigbo   = prod["code"]=="221"
    is_vigninou = prod["code"]=="220"
    is_deces    = prod["code"] in ("220","221")
    is_epargne  = prod["code"]=="EP0"

    st.markdown(f"""<div style="background:{NAVY};border-radius:10px;padding:10px 16px;margin:10px 0;display:flex;align-items:center;justify-content:space-between">
      <div><div style="color:rgba(255,255,255,.45);font-size:9px;letter-spacing:.1em">BIA — BULLETIN INDIVIDUEL D'ADHÉSION</div>
      <div style="color:white;font-size:14px;font-weight:700">{prod['nom']}</div></div>
      <span style="background:{gc};color:white;font-size:12px;font-weight:700;padding:5px 12px;border-radius:6px">{prod['code']}</span>
    </div>""",unsafe_allow_html=True)
    if st.button("↩️ Changer de produit",key="chg_p"): st.session_state.pop("bia_prod",None); st.session_state.pop("bia_step",None); st.rerun()
    SLBL={2:"Identification",3:"Souscripteur",4:"Assuré",5:"Contrat",6:"Médical",7:"Validation"}
    st.progress((step-2)/5,text=f"Étape {step-1}/6 — {SLBL.get(step,'')}")
    st.markdown("")

    def ti(k,lbl,ph="",t="text"):
        st.session_state[k]=st.text_input(lbl,value=st.session_state.get(k,""),placeholder=ph,key=f"i_{k}")
    def si(k,lbl,opts):
        cur=st.session_state.get(k,opts[0]); idx=opts.index(cur) if cur in opts else 0
        st.session_state[k]=st.selectbox(lbl,opts,index=idx,key=f"s_{k}")

    if step==2:
        section("Étape 2 — Identification & Agence")
        c1,c2,c3=st.columns(3)
        with c1: si("f_agence","Agence",AGENCES)
        with c2: ti("f_code_appo","Code apporteur","Ex : AFG001")
        with c3: ti("f_nom_appo","Nom apporteur")
        c4,c5=st.columns(2)
        with c4: ti("f_realis","Réalisateur",user["nom"])
        with c5: si("f_deja","Déjà assuré AFGVie ?",["Non","Oui"])
        if st.session_state.get("f_deja")=="Oui": ti("f_num_ct","N° contrat existant")
        if st.button("Suivant ▶",type="primary"): st.session_state["bia_step"]=3; st.rerun()

    elif step==3:
        section("Étape 3 — Souscripteur / Contractant")
        c1,c2,c3=st.columns([1,2,2])
        with c1: si("f_c_tit","Civilité *",["","M.","Mme","Mlle"])
        with c2: ti("f_c_nom","Nom *","NOM (majuscules)")
        with c3: ti("f_c_prn","Prénoms *")
        c4,c5,c6=st.columns(3)
        with c4:
            cur_d=st.session_state.get("f_c_ddn",date(1985,1,1))
            if isinstance(cur_d,str):
                try: cur_d=date.fromisoformat(cur_d)
                except: cur_d=date(1985,1,1)
            st.session_state["f_c_ddn"]=st.date_input("Date naissance *",value=cur_d,min_value=date(1930,1,1),max_value=today,key="ddn_c")
        with c5: ti("f_c_lieu","Lieu naissance *","Cotonou")
        with c6: ti("f_c_nat","Nationalité","Béninoise")
        if not st.session_state.get("f_c_nat"): st.session_state["f_c_nat"]="Béninoise"
        c7,c8,c9=st.columns(3)
        with c7: si("f_c_mat","Sit. matrimoniale",["","Célibataire","Marié(e)","Divorcé(e)","Veuf(ve)"])
        with c8: ti("f_c_prof","Profession *")
        with c9: ti("f_c_adr","Adresse *","Quartier, rue")
        c10,c11,c12=st.columns(3)
        with c10: ti("f_c_tel","Tél. cel. *","+229 97…")
        with c11: ti("f_c_wapp","WhatsApp *","+229 97…")
        with c12: ti("f_c_npi","N°NPI / Passeport *","BJ123456")
        c13,c14=st.columns(2)
        with c13: ti("f_c_eml","Email","exemple@mail.com")
        with c14: ti("f_c_bp","Boîte postale","01 BP…")
        st.session_state["f_ass_meme"]=st.checkbox("✓ L'assuré(e) est identique au souscripteur",value=st.session_state.get("f_ass_meme",True))
        b1,b2=st.columns(2)
        if b1.button("← Retour"): st.session_state["bia_step"]=2; st.rerun()
        if b2.button("Suivant ▶",type="primary"):
            if not st.session_state.get("f_c_nom","").strip(): st.error("Nom obligatoire")
            elif not st.session_state.get("f_c_prn","").strip(): st.error("Prénom obligatoire")
            else: st.session_state["bia_step"]=4; st.rerun()

    elif step==4:
        section("Étape 4 — Assuré(e) & Bénéficiaires")
        if st.session_state.get("f_ass_meme",True):
            st.success(f"✅ Assuré(e) = {st.session_state.get('f_c_tit','')} {st.session_state.get('f_c_nom','').upper()} {st.session_state.get('f_c_prn','')} — reprises du souscripteur.")
        else:
            c1,c2,c3=st.columns([1,2,2])
            with c1: si("f_a_tit","Civilité",["","M.","Mme","Mlle"])
            with c2:
                st.session_state["f_a_nom"]=st.text_input("Nom *",value=st.session_state.get("f_a_nom",""),key="an")
            with c3:
                st.session_state["f_a_prn"]=st.text_input("Prénoms *",value=st.session_state.get("f_a_prn",""),key="ap")
            c4,c5=st.columns(2)
            with c4:
                cur_a=st.session_state.get("f_a_ddn",date(1990,1,1))
                if isinstance(cur_a,str):
                    try: cur_a=date.fromisoformat(cur_a)
                    except: cur_a=date(1990,1,1)
                st.session_state["f_a_ddn"]=st.date_input("Date naissance",value=cur_a,key="ddn_a")
            with c5:
                st.session_state["f_a_npi"]=st.text_input("NPI",value=st.session_state.get("f_a_npi",""),key="ani")
        section("Bénéficiaires")
        st.session_state["f_bc"]=st.checkbox("Mon conjoint, mes enfants nés et à naître, à défaut mes ayants droits",value=st.session_state.get("f_bc",True))
        st.session_state["f_ba"]=st.text_input("Autres bénéficiaires",value=st.session_state.get("f_ba",""),key="ba_t")
        b1,b2=st.columns(2)
        if b1.button("← Retour"): st.session_state["bia_step"]=3; st.rerun()
        if b2.button("Suivant ▶",type="primary"): st.session_state["bia_step"]=5; st.rerun()

    elif step==5:
        section("Étape 5 — Caractéristiques du Contrat")

        # ── Date d'effet (commun) ─────────────────────────────────────────────
        cur_e=st.session_state.get("f_deff",today)
        if isinstance(cur_e,str):
            try: cur_e=date.fromisoformat(cur_e)
            except: cur_e=today

        # ══════════════════════════════════════════════════════════════════════
        # AVIGBO — barème fixe, 3 options, durée libre
        # ══════════════════════════════════════════════════════════════════════
        if is_avigbo:
            alert("Contrat AVIGBO : le capital et la cotisation unique sont déterminés automatiquement selon la prime mensuelle choisie.","info")
            # Sélection du barème
            opt_map = {
                "100 F/mois → Capital 100 000 F (unique : 1 000 F)":   (100,  100_000,  1_000),
                "200 F/mois → Capital 200 000 F (unique : 2 000 F)":   (200,  200_000,  2_000),
                "300 F/mois → Capital 300 000 F (unique : 3 000 F)":   (300,  300_000,  3_000),
            }
            opts_list = list(opt_map.keys())
            cur_opt = st.session_state.get("f_avigbo_opt", opts_list[0])
            if cur_opt not in opts_list: cur_opt = opts_list[0]
            selected_opt = st.radio("Barème de cotisation *", opts_list,
                                    index=opts_list.index(cur_opt), key="avigbo_opt_r")
            st.session_state["f_avigbo_opt"] = selected_opt
            prime_m, capital_g, prime_u = opt_map[selected_opt]

            c1,c2=st.columns(2)
            with c1:
                peri_av_opts=["Mensuelle","Unique"]
                cur_pav=st.session_state.get("f_peri","Mensuelle")
                if cur_pav not in peri_av_opts: cur_pav="Mensuelle"
                st.session_state["f_peri"]=st.radio("Périodicité *",peri_av_opts,
                    horizontal=True,index=peri_av_opts.index(cur_pav),key="peri_av_r")
            with c2:
                st.session_state["f_deff"]=st.date_input("Date d'effet *",value=cur_e,key="eff_d")

            # Cotisation et capital automatiques
            if st.session_state["f_peri"]=="Mensuelle":
                coti_auto=prime_m
            else:
                coti_auto=prime_u
            st.session_state["f_coti"]=coti_auto
            st.session_state["f_cap"] =capital_g

            st.markdown(f"""
            <div style="background:{GREEN}12;border:1.5px solid {GREEN};border-radius:10px;padding:12px 16px;margin:10px 0">
              <div style="font-size:10px;color:{GREEN};font-weight:700;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">Paramètres automatiques AVIGBO</div>
              <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;font-size:13px">
                <div><span style="color:#888;font-size:10px">Cotisation</span><br><b>{coti_auto:,} FCFA / {st.session_state['f_peri'].lower()}</b></div>
                <div><span style="color:#888;font-size:10px">Capital garanti décès</span><br><b style="color:{RED}">{capital_g:,} FCFA</b></div>
                <div><span style="color:#888;font-size:10px">Option garantie</span><br><b>Avec garantie décès</b></div>
              </div>
            </div>""", unsafe_allow_html=True)
            st.session_state["f_gar"]="Avec garantie décès"
            st.session_state["f_duree"]=st.number_input("Durée du contrat (ans) *",min_value=1,max_value=40,
                value=int(st.session_state.get("f_duree",5)),key="dur_av")

        # ══════════════════════════════════════════════════════════════════════
        # VIGNINOU — barème fixe, durée MAX 12 mois
        # ══════════════════════════════════════════════════════════════════════
        elif is_vigninou:
            alert("Contrat VIGNINOU : durée maximale 12 mois. Capital et cotisation unique fixés par le barème.","warn")
            opt_map_v = {
                "400 F/mois → Capital 500 000 F (unique : 48 000 F)":    (400,  500_000,  48_000),
                "800 F/mois → Capital 1 000 000 F (unique : 96 000 F)":  (800,  1_000_000,96_000),
                "1 200 F/mois → Capital 1 500 000 F (unique : 144 000 F)": (1200, 1_500_000,144_000),
            }
            opts_list_v = list(opt_map_v.keys())
            cur_opt_v = st.session_state.get("f_vigninou_opt", opts_list_v[0])
            if cur_opt_v not in opts_list_v: cur_opt_v = opts_list_v[0]
            selected_opt_v = st.radio("Barème de cotisation *", opts_list_v,
                                       index=opts_list_v.index(cur_opt_v), key="vign_opt_r")
            st.session_state["f_vigninou_opt"] = selected_opt_v
            prime_m_v, capital_g_v, prime_u_v = opt_map_v[selected_opt_v]

            c1,c2,c3=st.columns(3)
            with c1:
                peri_v_opts=["Mensuelle","Unique"]
                cur_pv=st.session_state.get("f_peri","Mensuelle")
                if cur_pv not in peri_v_opts: cur_pv="Mensuelle"
                st.session_state["f_peri"]=st.radio("Périodicité *",peri_v_opts,
                    horizontal=True,index=peri_v_opts.index(cur_pv),key="peri_v_r")
            with c2:
                # Durée en MOIS pour VIGNINOU (max 12 mois)
                dur_v_mois=st.number_input("Durée (mois, max 12) *",min_value=1,max_value=12,
                    value=int(st.session_state.get("f_duree_mois_v",12)),key="dur_v_m")
                st.session_state["f_duree_mois_v"]=dur_v_mois
                # On stocke en fraction d'année pour cohérence BIA
                st.session_state["f_duree"]=1  # 1 an max
            with c3:
                st.session_state["f_deff"]=st.date_input("Date d'effet *",value=cur_e,key="eff_d")

            if st.session_state["f_peri"]=="Mensuelle":
                coti_auto_v=prime_m_v
            else:
                coti_auto_v=prime_u_v
            st.session_state["f_coti"]=coti_auto_v
            st.session_state["f_cap"] =capital_g_v

            st.markdown(f"""
            <div style="background:{RED}08;border:1.5px solid {RED};border-radius:10px;padding:12px 16px;margin:10px 0">
              <div style="font-size:10px;color:{RED};font-weight:700;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">Paramètres automatiques VIGNINOU · Durée max 12 mois</div>
              <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px;font-size:13px">
                <div><span style="color:#888;font-size:10px">Cotisation</span><br><b>{coti_auto_v:,} FCFA / {st.session_state['f_peri'].lower()}</b></div>
                <div><span style="color:#888;font-size:10px">Capital garanti décès</span><br><b style="color:{RED}">{capital_g_v:,} FCFA</b></div>
                <div><span style="color:#888;font-size:10px">Durée choisie</span><br><b>{dur_v_mois} mois</b></div>
                <div><span style="color:#888;font-size:10px">Option garantie</span><br><b>Avec garantie décès</b></div>
              </div>
            </div>""", unsafe_allow_html=True)
            st.session_state["f_gar"]="Avec garantie décès"

        # ══════════════════════════════════════════════════════════════════════
        # ÉPARGNE — libre, calcul du capital à terme
        # ══════════════════════════════════════════════════════════════════════
        else:
            c1,c2=st.columns(2)
            with c1:
                st.session_state["f_deff"]=st.date_input("Date d'effet *",value=cur_e,key="eff_d")
            with c2:
                st.session_state["f_duree"]=st.number_input("Durée (ans) *",min_value=1,max_value=40,
                    value=int(st.session_state.get("f_duree",10)),key="dur_n")

            c3,c4=st.columns(2)
            with c3:
                st.session_state["f_coti"]=st.number_input("Cotisation FCFA *",min_value=100,
                    value=int(st.session_state.get("f_coti",5000)),key="cot_n")
            with c4:
                peri_ep_opts=["Journalière","Hebdomadaire","Mensuelle","Trimestrielle","Semestrielle","Annuelle","Unique"]
                cur_pep=st.session_state.get("f_peri","Mensuelle")
                if cur_pep not in peri_ep_opts: cur_pep="Mensuelle"
                st.session_state["f_peri"]=st.selectbox("Périodicité *",peri_ep_opts,
                    index=peri_ep_opts.index(cur_pep),key="peri_ep_s")

            # ── Calcul dynamique du capital au terme ─────────────────────────
            P_ep   = float(st.session_state.get("f_coti",5000))
            n_ep   = int(st.session_state.get("f_duree",10))
            peri_ep= st.session_state.get("f_peri","Mensuelle")
            res_ep = calcul_capital_epargne(P_ep, peri_ep, n_ep)
            cap_ep = res_ep["capital_brut"]
            st.session_state["f_cap"] = int(cap_ep)

            st.markdown(f"""
            <div style="background:{GREEN}10;border:1.5px solid {GREEN};border-radius:10px;padding:14px 16px;margin:12px 0">
              <div style="font-size:10px;color:{GREEN};font-weight:700;text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px">
                Simulation actuarielle — Capital au terme
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-bottom:10px">
                <div style="background:white;border-radius:8px;padding:10px 12px;border:0.5px solid {MGRAY}">
                  <div style="font-size:9px;color:#888;text-transform:uppercase;letter-spacing:.06em">Cotisation nette P_net</div>
                  <div style="font-size:18px;font-weight:700;color:{NAVY}">{res_ep['Pnet']:,.0f} <span style="font-size:11px;font-weight:400">FCFA</span></div>
                  <div style="font-size:10px;color:#888">α=1% acq. + β=0.5% gest.</div>
                </div>
                <div style="background:white;border-radius:8px;padding:10px 12px;border:0.5px solid {MGRAY}">
                  <div style="font-size:9px;color:#888;text-transform:uppercase;letter-spacing:.06em">Total cotisations versées</div>
                  <div style="font-size:18px;font-weight:700;color:{NAVY}">{res_ep['total_verse']:,.0f} <span style="font-size:11px;font-weight:400">FCFA</span></div>
                  <div style="font-size:10px;color:#888">Sur {n_ep} an(s) · {peri_ep}</div>
                </div>
                <div style="background:linear-gradient(135deg,{GREEN},{GREEN2});border-radius:8px;padding:10px 12px">
                  <div style="font-size:9px;color:rgba(255,255,255,.7);text-transform:uppercase;letter-spacing:.06em">Capital au terme C_n</div>
                  <div style="font-size:20px;font-weight:800;color:white">{cap_ep:,.0f} <span style="font-size:12px;font-weight:400">FCFA</span></div>
                  <div style="font-size:10px;color:rgba(255,255,255,.7)">Rendement : +{res_ep['rendement']:.1f}%</div>
                </div>
              </div>
              <div style="font-size:10px;color:#666;font-family:monospace;background:#f8f9fa;border-radius:6px;padding:8px 10px;line-height:1.7">
                {res_ep['formule']}
              </div>
            </div>""", unsafe_allow_html=True)

        # ── Mode de règlement (commun tous produits) ─────────────────────────
        section("Mode de règlement")
        m_o=["","Mobile Monnaie","Par chèque","Par virement bancaire","Par prélèvement sur salaire"]
        cur_m=st.session_state.get("f_mode","")
        st.session_state["f_mode"]=st.radio("Mode *",m_o,horizontal=True,
            index=m_o.index(cur_m) if cur_m in m_o else 0,key="mode_r",
            format_func=lambda x:"— Choisir —" if x=="" else x)
        if st.session_state["f_mode"]:
            ref_l={"Mobile Monnaie":"📱 N° Mobile Money","Par chèque":"📄 N° Chèque",
                   "Par virement bancaire":"🏦 N° Compte/RIB",
                   "Par prélèvement sur salaire":"💼 N° Matricule"}.get(st.session_state["f_mode"],"Référence")
            ti("f_mref",ref_l)

        b1,b2=st.columns(2)
        if b1.button("← Retour"): st.session_state["bia_step"]=4; st.rerun()
        if b2.button("Suivant ▶",type="primary"): st.session_state["bia_step"]=6; st.rerun()

    elif step==6:
        section("Étape 6 — Questionnaire Médical CIMA")
        alert("Art. 18 CIMA : Toute fausse déclaration est sanctionnée par la nullité du contrat.","warn")
        c1,c2,c3=st.columns(3)
        st.session_state["f_taille"]=c1.text_input("Taille (m)",value=st.session_state.get("f_taille",""),placeholder="1.72",key="taille_t")
        st.session_state["f_poids"]=c2.text_input("Poids (kg)",value=st.session_state.get("f_poids",""),placeholder="75",key="poids_t")
        per_m=["Non","Oui"]
        cur_pp=st.session_state.get("f_perte","Non")
        st.session_state["f_perte"]=c3.radio("Grossi/maigri >5 kg (6 mois) ?",per_m,horizontal=True,index=per_m.index(cur_pp) if cur_pp in per_m else 0,key="perte_r")
        MED=[
            ("q1","Maladie ou séquelles — surveillance médicale requise (10 ans) ?",False),
            ("q2","Arrêts de travail >21 jours (5 dernières années) ?",False),
            ("q3","Traitement médical >21 jours (5 ans, hors contraception) ?",False),
            ("q4","Actuellement en arrêt de travail sur prescription médicale ?",False),
            ("q5","Traitement médical en cours (hors contraception) ?",False),
            ("q6","Hospitalisation ou analyses dans les 12 prochains mois ?",True),
            ("q7","Méningite, hépatite B, VIH/Sida, cancer ou maladie grave ?",False),
        ]
        for qk,qtxt,special in MED:
            with st.container(border=True):
                qa,qb=st.columns([3.5,1])
                qa.markdown(f"<div style='font-size:11px;line-height:1.4'><b>{qk[1:]}.</b> {qtxt}</div>",unsafe_allow_html=True)
                r_o=["Non","Oui"]
                cur_r=st.session_state.get(f"f_{qk}","Non")
                st.session_state[f"f_{qk}"]=qb.radio("",r_o,horizontal=True,index=r_o.index(cur_r) if cur_r in r_o else 0,key=f"r_{qk}")
                if st.session_state[f"f_{qk}"]=="Oui":
                    st.session_state[f"f_{qk}d"]=st.text_input("Précisions :",value=st.session_state.get(f"f_{qk}d",""),placeholder="Soyez précis(e)",key=f"d_{qk}")
        b1,b2=st.columns(2)
        if b1.button("← Retour"): st.session_state["bia_step"]=5; st.rerun()
        if b2.button("Suivant ▶",type="primary"): st.session_state["bia_step"]=7; st.rerun()

    elif step==7:
        section("Étape 7 — Déclaration & Validation")
        st.markdown("""<div style="background:#f8f9fa;border:1px solid #ddd;border-radius:8px;padding:12px;
            font-size:11px;line-height:1.8;max-height:120px;overflow-y:auto;margin-bottom:12px">
            Je reconnais avoir reçu la notice d'information du produit et les conditions générales.
            Je certifie exactes et sincères toutes les informations renseignées.
            Conformément à l'article 18 du code CIMA, toute fausse déclaration
            entraîne la nullité du contrat.</div>""",unsafe_allow_html=True)
        st.session_state["f_dc"]=st.checkbox("☑ J'accepte les conditions de souscription *",value=st.session_state.get("f_dc",False))
        st.session_state["f_dd"]=st.checkbox("☑ J'accepte la politique de protection des données *",value=st.session_state.get("f_dd",False))
        c1,c2=st.columns(2)
        stat_o=["Brouillon","En cours","Validé"]
        cur_st=st.session_state.get("f_stat","Brouillon")
        st.session_state["f_stat"]=c1.selectbox("Statut",stat_o,index=stat_o.index(cur_st) if cur_st in stat_o else 0,key="stat_s")
        st.session_state["f_obs"]=c2.text_input("Observations",value=st.session_state.get("f_obs",""),key="obs_t")
        with st.expander("📋 Récapitulatif complet", expanded=True):
            cap_recap = int(st.session_state.get("f_cap",0))
            dur_recap = st.session_state.get("f_duree",1)
            # Pour VIGNINOU, afficher la durée en mois
            dur_label = f"{st.session_state.get('f_duree_mois_v',12)} mois" if is_vigninou else f"{dur_recap} an(s)"
            st.markdown(f"""| Champ | Valeur |
|---|---|
|**Souscripteur**|{st.session_state.get('f_c_tit','')} {st.session_state.get('f_c_nom','').upper()} {st.session_state.get('f_c_prn','')}|
|**Produit**|{prod['nom']} — code {prod['code']}|
|**Cotisation**|{st.session_state.get('f_coti',0):,} FCFA / {st.session_state.get('f_peri','—')}|
|**Capital garanti / au terme**|**{cap_recap:,} FCFA**|
|**Date d'effet**|{ds(st.session_state.get('f_deff',today))}|
|**Durée**|{dur_label}|
|**Mode règlement**|{st.session_state.get('f_mode','—')}|
|**Option garantie**|{st.session_state.get('f_gar','—')}|""")

        def save_bia(statut_ov=None):
            ass = st.session_state.get("f_ass_meme", True)
            data = {
                "numero_bia":       gen_bia(),
                "date_saisie":      today.isoformat(),
                "saisi_par":        user["nom"],
                "agence":           st.session_state.get("f_agence",""),
                "code_apporteur":   st.session_state.get("f_code_appo",""),
                "nom_apporteur":    st.session_state.get("f_nom_appo",""),
                "realisateur":      st.session_state.get("f_realis",""),
                "deja_assure":      st.session_state.get("f_deja","Non"),
                "num_ct_exist":     st.session_state.get("f_num_ct",""),
                "c_titre":          st.session_state.get("f_c_tit",""),
                "c_nom":            st.session_state.get("f_c_nom","").upper().strip(),
                "c_prenom":         st.session_state.get("f_c_prn","").strip(),
                "c_ddn":            str(st.session_state.get("f_c_ddn", date(1985,1,1))),
                "c_lieu":           st.session_state.get("f_c_lieu",""),
                "c_nat":            st.session_state.get("f_c_nat","Béninoise"),
                "c_mat":            st.session_state.get("f_c_mat",""),
                "c_prof":           st.session_state.get("f_c_prof",""),
                "c_adr":            st.session_state.get("f_c_adr",""),
                "c_bp":             st.session_state.get("f_c_bp",""),
                "c_email":          st.session_state.get("f_c_eml",""),
                "c_wapp":           st.session_state.get("f_c_wapp",""),
                "c_tel":            st.session_state.get("f_c_tel",""),
                "c_fixe":           st.session_state.get("f_c_fixe",""),
                "c_npi":            st.session_state.get("f_c_npi",""),
                "ass_meme":         1 if ass else 0,
                "a_titre":          "" if ass else st.session_state.get("f_a_tit",""),
                "a_nom":            "" if ass else st.session_state.get("f_a_nom","").upper(),
                "a_prenom":         "" if ass else st.session_state.get("f_a_prn",""),
                "a_ddn":            "" if ass else str(st.session_state.get("f_a_ddn","")),
                "a_npi":            "" if ass else st.session_state.get("f_a_npi",""),
                "benef_conj":       1 if st.session_state.get("f_bc", True) else 0,
                "benef_autres":     st.session_state.get("f_ba",""),
                "code_produit":     prod["code"],
                "produit":          prod["nom"],
                "groupe_produit":   prod["grp"],
                "cotisation":       float(st.session_state.get("f_coti", 0)),
                "cotisation_lettres": st.session_state.get("f_cotil",""),
                "periodicite":      st.session_state.get("f_peri","Mensuelle"),
                "date_effet":       str(st.session_state.get("f_deff", today)),
                "duree":            (st.session_state.get("f_duree_mois_v", 12)
                                     if is_vigninou
                                     else int(st.session_state.get("f_duree", 10))),
                "option_gar":       st.session_state.get("f_gar","Sans garantie décès"),
                "mode_reglement":   st.session_state.get("f_mode",""),
                "mode_ref":         st.session_state.get("f_mref",""),
                "capital_terme":    float(st.session_state.get("f_cap", 0) or 0),
                **{f"q{qi}":  st.session_state.get(f"f_q{qi}","Non") for qi in range(1,8)},
                **{f"q{qi}d": st.session_state.get(f"f_q{qi}d","")  for qi in range(1,8)},
                "decl_cond":        1 if st.session_state.get("f_dc") else 0,
                "decl_data":        1 if st.session_state.get("f_dd") else 0,
                "statut":           statut_ov or st.session_state.get("f_stat","Brouillon"),
                "obs":              st.session_state.get("f_obs",""),
            }
            # insert_bia() gère PG (%s) et SQLite (?) automatiquement
            ok = insert_bia(data)
            if ok:
                for k in [k for k in list(st.session_state.keys()) if k.startswith("f_")]:
                    del st.session_state[k]
                st.session_state.pop("bia_prod", None)
                st.session_state.pop("bia_step", None)
                return data["numero_bia"]
            return None
        b1,b2,b3=st.columns([1,1,1.4])
        if b1.button("← Retour"): st.session_state["bia_step"]=6; st.rerun()
        if b2.button("💾 Brouillon"):
            num=save_bia("Brouillon")
            if num: st.info(f"💾 Brouillon **{num}** enregistré. Retrouvez-le dans la Base BIA.")
        if b3.button("✅ VALIDER LE BIA",type="primary"):
            errs=[]
            if not st.session_state.get("f_c_nom","").strip(): errs.append("Nom souscripteur obligatoire")
            if not st.session_state.get("f_dc"): errs.append("Conditions de souscription requises")
            if not st.session_state.get("f_dd"): errs.append("Politique données requise")
            if errs:
                for e in errs: st.error(f"❌ {e}")
            else:
                num=save_bia("Validé")
                if num: st.balloons(); st.success(f"🎉 BIA **{num}** validé ! {st.session_state.get('f_c_tit','')} {st.session_state.get('f_c_nom','').upper()}")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — BASE BIA
# ═══════════════════════════════════════════════════════════════════════════════
elif "Base BIA" in page:
    df_bia=bia_all()
    section("🗂️ Base BIA — Registre des bulletins","CONSULTATION · GESTION · EXPORT")
    if df_bia.empty:
        alert("Aucun BIA enregistré. Utilisez l'onglet <b>Saisie BIA</b>.","info"); st.stop()
    nb_all=len(df_bia); nb_val=int((df_bia["statut"]=="Validé").sum())
    nb_bro=int((df_bia["statut"]=="Brouillon").sum()); cot_t=float(df_bia["cotisation"].fillna(0).astype(float).sum())
    c1,c2,c3,c4=st.columns(4)
    kpi(c1,"Total BIA",str(nb_all),"Base complète","teal",icon="📋")
    kpi(c2,"Cotisations",fmt(cot_t),"Total FCFA","",icon="💰")
    kpi(c3,"Validés",str(nb_val),f"{nb_val/max(nb_all,1)*100:.0f}%","",icon="✅")
    kpi(c4,"Brouillons",str(nb_bro),"À compléter","amber",icon="💾")
    # Graphiques
    g1,g2=st.columns(2)
    with g1:
        by_st=df_bia["statut"].value_counts().reset_index(); by_st.columns=["Statut","Nb"]
        fig=go.Figure(go.Pie(labels=by_st["Statut"],values=by_st["Nb"],hole=.44,
            marker_colors=[GREEN,AMBER,RED,BLUE],textinfo="percent+label+value",textfont_size=12))
        fig_style(fig,260,"📊 Répartition par statut"); st.plotly_chart(fig,use_container_width=True)
    with g2:
        if "produit" in df_bia.columns:
            by_p=df_bia.groupby("produit").agg(Nb=("produit","count"),Cot=("cotisation","sum")).reset_index().sort_values("Cot",ascending=False).head(8)
            fig2=go.Figure(go.Bar(x=by_p["Cot"],y=by_p["produit"].str[:22],orientation="h",
                marker_color=GREEN,text=[fmt(v) for v in by_p["Cot"]],textposition="outside",textfont_size=10))
            fig2.update_layout(yaxis=dict(autorange="reversed"))
            fig_style(fig2,260,"💰 Cotisations BIA par produit"); st.plotly_chart(fig2,use_container_width=True)
    # Valider brouillons
    brous=df_bia[df_bia["statut"]=="Brouillon"]
    if not brous.empty:
        alert(f"<b>{len(brous)} brouillon(s)</b> en attente de validation.","warn")
        with st.expander(f"📋 Valider un brouillon ({len(brous)} en attente)"):
            for _,br in brous.iterrows():
                cc1,cc2,cc3=st.columns([4,1,1])
                cc1.markdown(f"**{br['numero_bia']}** · {br.get('c_titre','')} {br.get('c_nom','')} {br.get('c_prenom','')} · {br.get('produit','')} · {fmt(br.get('cotisation',0))}")
                if cc2.button("✅", key=f"val_{br['id']}"):
                    update_bia_statut(int(br["id"]), "Validé")
                    st.balloons(); st.rerun()
                if cc3.button("🗑️", key=f"del_{br['id']}"):
                    delete_bia(int(br["id"])); st.rerun()
    # Filtres
    f1,f2,f3,f4 = st.columns(4)
    etat_opts=["Tous"]+sorted(df_all["ETAT_POLICE"].str.strip().dropna().unique().tolist()) if "ETAT_POLICE" in df_all.columns else ["Tous"]
    prod_opts=["Tous"]+sorted(df_all["LIBECATE"].dropna().unique().tolist()) if "LIBECATE" in df_all.columns else ["Tous"]
    etat_sel=f1.selectbox("État",etat_opts,label_visibility="collapsed")
    prod_sel=f2.selectbox("Produit",prod_opts,label_visibility="collapsed")
    srch_pf=f3.text_input("🔍 Rechercher",label_visibility="collapsed",placeholder="Nom assuré, ville, apporteur…")
    villes_opts=["Toutes"]+sorted(df_all["LIBEVILL"].dropna().unique().tolist()[:60]) if "LIBEVILL" in df_all.columns else ["Toutes"]
    ville_sel=f4.selectbox("Ville",villes_opts,label_visibility="collapsed")

    fi=df.copy()
    if etat_sel!="Tous" and "ETAT_POLICE" in fi.columns: fi=fi[fi["ETAT_POLICE"].str.strip()==etat_sel]
    if prod_sel!="Tous" and "LIBECATE" in fi.columns: fi=fi[fi["LIBECATE"]==prod_sel]
    if ville_sel!="Toutes" and "LIBEVILL" in fi.columns: fi=fi[fi["LIBEVILL"]==ville_sel]
    if srch_pf:
        cols_s=[c for c in ["NOM_ASSU","LIBEVILL","NOM_APP","LIBECATE"] if c in fi.columns]
        mask=pd.Series(False,index=fi.index)
        for c_ in cols_s: mask|=fi[c_].astype(str).str.lower().str.contains(srch_pf.lower(),na=False)
        fi=fi[mask]

    nb=len(fi)
    actifs=int((fi["ETAT_POLICE"].str.strip()=="ACTIF").sum()) if "ETAT_POLICE" in fi.columns and nb else 0
    resil =int((fi["ETAT_POLICE"].str.strip()=="RESILIE").sum()) if "ETAT_POLICE" in fi.columns and nb else 0
    monten=float(fi["MONTENCA"].fillna(0).sum()) if "MONTENCA" in fi.columns and nb else 0
    coti_p=float(fi["COTI_PERIODIQUE"].fillna(0).sum()) if "COTI_PERIODIQUE" in fi.columns and nb else 0

    c1,c2,c3,c4,c5 = st.columns(5)
    kpi(c1,"Polices filtrées",f"{nb:,}",f"sur {len(df_all):,} total","",icon="📋")
    kpi(c2,"Actives",f"{actifs:,}",pct(actifs/max(nb,1)*100),"",icon="✅")
    kpi(c3,"Résiliées",f"{resil:,}",pct(resil/max(nb,1)*100),"red",icon="📉")
    kpi(c4,"Encaissements",fmt(monten),"MONTENCA","teal",icon="💰")
    kpi(c5,"Cotisation périodique",fmt(coti_p),"COTI_PERIODIQUE","blue",icon="💳")

    st.markdown("")
    t1,t2,t3,t4 = st.tabs(["📋 Tableau","📊 Statistiques","📈 Évolution souscriptions","🔗 Jointure CA"])

    with t1:
        COLS_SHOW=[c for c in ["POLICE_KEY","NUMEPOLI_P","LIBECATE","ETAT_POLICE","NOM_ASSU","LIBEVILL","NOM_APP","DATESOUS","DATEEFFE","DATEECHE","COTI_PERIODIQUE","MONTENCA","SEXERISQ","CODEPERI","NBRE_PRIME"] if c in fi.columns]
        di=fi[COLS_SHOW].copy()
        for dc in ["DATESOUS","DATEEFFE","DATEECHE"]:
            if dc in di.columns: di[dc]=di[dc].apply(ds)
        for nc in ["COTI_PERIODIQUE","MONTENCA"]:
            if nc in di.columns: di[nc]=di[nc].apply(lambda x:fmt(x,""))
        st.dataframe(di.head(500),use_container_width=True,hide_index=True,height=400)
        st.caption(f"Affichage 500 / {nb:,} polices")
        a,b=st.columns(2)
        a.download_button("📥 CSV",dl_csv(fi),f"pf_{period_lbl}.csv","text/csv",use_container_width=True,key="dl_pf_csv")
        b.download_button("📥 Excel",dl_xlsx(fi[COLS_SHOW].head(50000)),f"pf_{period_lbl}.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_pf_xl")

    with t2:
        sc1,sc2=st.columns(2)
        with sc1:
            if "LIBECATE" in fi.columns:
                pc_=fi.groupby("LIBECATE").agg(Nb=("LIBECATE","count"),CA=("MONTENCA","sum")).reset_index().sort_values("Nb",ascending=False)
                fig=go.Figure(go.Bar(x=pc_["Nb"],y=pc_["LIBECATE"].str[:24],orientation="h",
                    marker=dict(color=pc_["Nb"],colorscale=[[0,MINT],[1,GREEN2]],showscale=False),
                    text=pc_["Nb"].astype(str),textposition="outside",textfont_size=10))
                fig.update_layout(yaxis=dict(autorange="reversed"))
                fig_style(fig,380,"📦 Polices par produit")
                st.plotly_chart(fig,use_container_width=True)
        with sc2:
            if "ETAT_POLICE" in fi.columns:
                etat_c_={"ACTIF":GREEN,"RESILIE":RED,"INACTIF":AMBER,"ECHU":"#5A6478","ASSURE ECHU":"#2C3E50","SUSPENDU":BLUE}
                ec=fi["ETAT_POLICE"].str.strip().value_counts().reset_index(); ec.columns=["État","Nb"]
                fig2=go.Figure(go.Pie(labels=ec["État"],values=ec["Nb"],hole=.44,
                    marker_colors=[etat_c_.get(e,"#888") for e in ec["État"]],
                    textinfo="percent+label",textfont_size=11))
                fig_style(fig2,380,"🔵 États du portefeuille filtré")
                st.plotly_chart(fig2,use_container_width=True)
        sc3,sc4=st.columns(2)
        with sc3:
            if "CODEPERI" in fi.columns:
                per=fi["CODEPERI"].map(CODEPERI_MAP).fillna("Autre").value_counts().reset_index(); per.columns=["Périodicité","Nb"]
                fig3=go.Figure(go.Pie(labels=per["Périodicité"],values=per["Nb"],hole=.44,marker_colors=PAL,textinfo="percent+label",textfont_size=11))
                fig_style(fig3,320,"📅 Périodicité cotisations")
                st.plotly_chart(fig3,use_container_width=True)
        with sc4:
            if "LIBEVILL" in fi.columns:
                vl=fi["LIBEVILL"].value_counts().head(10).reset_index(); vl.columns=["Ville","Nb"]
                fig4=go.Figure(go.Bar(x=vl["Nb"],y=vl["Ville"].str[:18],orientation="h",
                    marker_color=PALETTE if (PALETTE:=PAL[:len(vl)]) else PAL,
                    text=vl["Nb"].astype(str),textposition="outside",textfont_size=10))
                fig4.update_layout(yaxis=dict(autorange="reversed"))
                fig_style(fig4,320,"📍 Top 10 villes")
                st.plotly_chart(fig4,use_container_width=True)
        a,b=st.columns(2)
        a.download_button("📥 CSV stats",dl_csv(pc_ if "LIBECATE" in fi.columns else fi),"stats_pf.csv","text/csv",use_container_width=True,key="dl_stats_pf")

    with t3:
        if "DATESOUS" in df_all.columns:
            es=df_all.groupby(df_all["DATESOUS"].dt.year).agg(Souscriptions=("DATESOUS","count"),CA=("MONTENCA","sum")).reset_index()
            es.columns=["Année","Souscriptions","CA"]; es=es[es["Année"].between(1995,2026)].sort_values("Année")
            fig=make_subplots(specs=[[{"secondary_y":True}]])
            fig.add_bar(x=es["Année"].astype(str),y=es["Souscriptions"],name="Souscriptions",
                marker=dict(color=es["Souscriptions"],colorscale=[[0,MINT],[.4,GREEN],[1,GREEN2]],showscale=False))
            fig.add_scatter(x=es["Année"].astype(str),y=es["CA"],name="CA MONTENCA",
                line=dict(color=RED,width=2.5),mode="lines+markers",secondary_y=True)
            fig.update_yaxes(title_text="Nb souscriptions",secondary_y=False)
            fig.update_yaxes(title_text="CA MONTENCA",secondary_y=True,showgrid=False)
            fig_style(fig,420,"📈 Évolution souscriptions & CA 1995–2025")
            st.plotly_chart(fig,use_container_width=True)
            a,b=st.columns(2)
            a.download_button("📥 CSV",dl_csv(es),"evo_sous.csv","text/csv",use_container_width=True,key="dl_evo_pf")
            b.download_button("📥 Excel",dl_xlsx(es),"evo_sous.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_evo_pf_xl")

    with t4:
        if ca is not None and "POLICE_KEY" in fi.columns and "POLICE_KEY" in ca.columns:
            section("🔗 Polices actives avec CA 2024","JOINTURE PF × CA")
            ca_pf=ca.merge(fi[["POLICE_KEY","LIBECATE","ETAT_POLICE","NOM_ASSU","LIBEVILL","NOM_APP"]].drop_duplicates("POLICE_KEY"),on="POLICE_KEY",how="inner",suffixes=("_CA","_PF"))
            tp=ca_pf.groupby(["POLICE_KEY","LIBECATE","ETAT_POLICE","NOM_ASSU","NOM_APP"]).agg(CA=("CHIFAFFA","sum"),NbQ=("CHIFAFFA","count")).reset_index().sort_values("CA",ascending=False).head(25)
            tp_d=tp.copy(); tp_d["CA"]=tp_d["CA"].apply(fmt)
            st.dataframe(tp_d,use_container_width=True,hide_index=True)
            a,b=st.columns(2)
            a.download_button("📥 CSV jointure",dl_csv(tp),"jointure_pf_ca.csv","text/csv",use_container_width=True,key="dl_join_pf")
        else: alert("Chargez la Base CA pour voir la jointure PF × CA.","info")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — PRODUITS
# ═══════════════════════════════════════════════════════════════════════════════
elif "Produits" in page:
    section(f"🛒 Analyse Produits — {period_lbl}","CA · ÉTATS · STRUCTURE")
    t_cap,t_pfp=st.tabs(["💰 CA par produit","📋 Portefeuille par produit"])
    with t_cap:
        if ca is None: alert("Chargez la Base CA.","warn")
        else:
            df=ca_f()
            if df.empty: alert(f"Aucune donnée CA pour {period_lbl}. Essayez 'Année'.","warn")
            else:
                cp=df.groupby("LIBECATE").agg(CA=("CHIFAFFA","sum"),NbQ=("CHIFAFFA","count"),Comm=("COMMAPPO","sum"),Prime=("PRIMNETT","sum")).reset_index().sort_values("CA",ascending=False)
                cp["Tx comm"]=cp["Comm"]/cp["CA"].replace(0,np.nan)*100; cp["Part CA"]=cp["CA"]/cp["CA"].sum()*100
                c1,c2=st.columns(2)
                with c1:
                    fig=go.Figure(go.Bar(x=cp["CA"],y=cp["LIBECATE"].str[:26],orientation="h",
                        marker=dict(color=cp["Tx comm"],colorscale=[[0,MINT],[.5,GREEN],[1,GREEN2]],showscale=True),
                        text=[fmt(v) for v in cp["CA"]],textposition="outside",textfont_size=10))
                    fig.update_layout(yaxis=dict(autorange="reversed"))
                    fig_style(fig,400,"💰 CA + taux commission")
                    st.plotly_chart(fig,use_container_width=True)
                with c2:
                    fig2=px.sunburst(cp,path=["LIBECATE"],values="CA",color="Part CA",color_continuous_scale=[[0,MINT],[.5,GREEN],[1,GREEN2]])
                    fig2.update_layout(height=400,margin=dict(l=5,r=5,t=20,b=5))
                    st.plotly_chart(fig2,use_container_width=True)
                cp_d=cp.copy()
                for c_ in ["CA","Comm","Prime"]: cp_d[c_]=cp_d[c_].apply(fmt)
                cp_d["Tx comm"]=cp_d["Tx comm"].apply(lambda x:f"{x:.2f}%"); cp_d["Part CA"]=cp_d["Part CA"].apply(lambda x:f"{x:.2f}%")
                cp_d.columns=["Produit","CA","Nb quittances","Commissions","Prime nette","Tx comm","Part CA"]
                st.dataframe(cp_d,use_container_width=True,hide_index=True)
                a,b=st.columns(2)
                a.download_button("📥 CSV",dl_csv(cp),"prod_ca.csv","text/csv",use_container_width=True,key="dl_prod_ca")
                b.download_button("📥 Excel",dl_xlsx(cp),"prod_ca.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_prod_ca_xl")
    with t_pfp:
        if pf is None: alert("Chargez le Portefeuille.","warn")
        else:
            df_p=pf_f() if not pf_f().empty else pf
            pp=df_p.groupby("LIBECATE").agg(Nb=("LIBECATE","count"),
                Actifs=("ETAT_POLICE",lambda x:(x.str.strip()=="ACTIF").sum()),
                Resil=("ETAT_POLICE",lambda x:(x.str.strip()=="RESILIE").sum()),
                Echus=("ETAT_POLICE",lambda x:(x.str.strip().isin(["ECHU","ASSURE ECHU"])).sum()),
                CA=("MONTENCA","sum")).reset_index()
            pp["Tx actif"]=(pp["Actifs"]/pp["Nb"].replace(0,np.nan)*100).round(1)
            pp["Tx resil"]=(pp["Resil"]/pp["Nb"].replace(0,np.nan)*100).round(1); pp=pp.sort_values("Nb",ascending=False)
            fig=go.Figure()
            fig.add_bar(name="✅ Actifs",y=pp["LIBECATE"].str[:22],x=pp["Actifs"],orientation="h",marker_color=GREEN)
            fig.add_bar(name="📉 Résiliés",y=pp["LIBECATE"].str[:22],x=pp["Resil"],orientation="h",marker_color=RED)
            fig.add_bar(name="⌛ Échus",y=pp["LIBECATE"].str[:22],x=pp["Echus"],orientation="h",marker_color=AMBER)
            fig.update_layout(barmode="stack",yaxis=dict(autorange="reversed"))
            fig_style(fig,440,"📊 États polices par produit")
            st.plotly_chart(fig,use_container_width=True)
            pp_d=pp.copy(); pp_d["CA"]=pp_d["CA"].apply(fmt)
            pp_d["Tx actif"]=pp_d["Tx actif"].apply(lambda x:f"{x:.1f}%"); pp_d["Tx resil"]=pp_d["Tx resil"].apply(lambda x:f"{x:.1f}%")
            st.dataframe(pp_d,use_container_width=True,hide_index=True)
            a,b=st.columns(2)
            a.download_button("📥 CSV",dl_csv(pp),"pf_produits.csv","text/csv",use_container_width=True,key="dl_prod_pf")
            b.download_button("📥 Excel",dl_xlsx(pp),"pf_produits.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_prod_pf_xl")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — COMMERCIAUX & PARTENAIRES
# ═══════════════════════════════════════════════════════════════════════════════
elif "Commerciaux" in page:
    section(f"👥 Commerciaux & Partenaires — {period_lbl}","CLASSEMENT · PARETO")
    src=ca_f() if ca is not None else pf_f()
    if src is None or src.empty: alert("Chargez la Base CA ou le Portefeuille.","warn"); st.stop()
    ag_k="NOM_INTERMEDIAIRE" if "NOM_INTERMEDIAIRE" in src.columns else "NOM_APP"
    ca_k="CHIFAFFA" if "CHIFAFFA" in src.columns else "MONTENCA"
    comm_k="COMMAPPO" if "COMMAPPO" in src.columns else None
    grp=src.groupby(ag_k).agg(CA=(ca_k,"sum"),Nb=(ca_k,"count"),
        **({} if not comm_k else {"Comm":(comm_k,"sum")})).reset_index().sort_values("CA",ascending=False).reset_index(drop=True)
    grp.index+=1; tot=grp["CA"].sum()
    grp["Part %"]=(grp["CA"]/max(tot,1)*100).round(2); grp["Part cum %"]=grp["Part %"].cumsum().round(1)
    medals=["🥇","🥈","🥉"]; mc_colors=[GREEN,TEAL,BLUE]
    c1,c2,c3=st.columns(3)
    for col,(med,mc_c),(idx,row) in zip([c1,c2,c3],zip(medals,mc_colors),grp.head(3).iterrows()):
        with col:
            col.markdown(f"""<div style="background:linear-gradient(135deg,{mc_c}18,white);border:2px solid {mc_c};
                 border-radius:14px;padding:1rem;text-align:center">
              <div style="font-size:28px">{med}</div>
              <div style="font-size:12px;font-weight:700;margin:5px 0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{row[ag_k]}">{str(row[ag_k])[:24]}</div>
              <div style="font-size:11px;color:#666">{row['Nb']:,} contrats</div>
              <div style="font-size:17px;font-weight:800;color:{mc_c};margin-top:5px">{fmt(row['CA'])}</div>
              <div style="font-size:10px;color:#888">{pct(row['Part %'])} du CA total</div>
            </div>""", unsafe_allow_html=True)
    st.markdown("")
    t_r,t_p=st.tabs(["🏆 Classement","📊 Pareto"])
    with t_r:
        dr=grp.head(50).copy(); dr["CA"]=dr["CA"].apply(fmt)
        if "Comm" in dr.columns: dr["Comm"]=dr["Comm"].apply(fmt)
        dr["Part %"]=dr["Part %"].apply(lambda x:f"{x:.2f}%"); dr["Part cum %"]=dr["Part cum %"].apply(lambda x:f"{x:.1f}%")
        st.dataframe(dr,use_container_width=True,height=440)
        a,b=st.columns(2)
        a.download_button("📥 CSV",dl_csv(grp),"classement.csv","text/csv",use_container_width=True,key="dl_rank")
        b.download_button("📥 Excel",dl_xlsx(grp.head(50000)),"classement.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_rank_xl")
    with t_p:
        t30=grp.head(30)
        fig=go.Figure(go.Bar(x=t30["CA"],y=t30[ag_k].str[:22],name="CA",marker_color=GREEN,orientation="h",
            text=[fmt(v) for v in t30["CA"]],textposition="outside",textfont_size=10))
        fig.update_layout(yaxis=dict(autorange="reversed"))
        fig_style(fig,500,"📊 Pareto CA — Top 30")
        st.plotly_chart(fig,use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — CLIENTS & GÉOGRAPHIE
# ═══════════════════════════════════════════════════════════════════════════════
elif "Clients" in page:
    if pf is None: alert("Chargez le Portefeuille.","warn"); st.stop()
    df=pf; section("👤 Clients & Géographie","ASSURÉS · VILLES · DÉMOGRAPHIE · ÂGES")
    nb_cli=df["NOM_ASSU"].nunique() if "NOM_ASSU" in df.columns else 0
    nb_vl=df["LIBEVILL"].nunique() if "LIBEVILL" in df.columns else 0
    ca_moy=float(df["MONTENCA"].fillna(0).sum())/max(nb_cli,1) if "MONTENCA" in df.columns else 0
    c1,c2,c3=st.columns(3)
    kpi(c1,"Clients distincts",f"{nb_cli:,}","NOM_ASSU uniques","teal",icon="👤")
    kpi(c2,"Villes couvertes",f"{nb_vl:,}","LIBEVILL","",icon="📍")
    kpi(c3,"MONTENCA moy/client",fmt(ca_moy),"Encaissement moyen","blue",icon="💰")
    t_g,t_d,t_a=st.tabs(["🗺️ Géographie","📊 Démographie","🎂 Pyramide des âges"])
    with t_g:
        if "LIBEVILL" in df.columns:
            c1,c2=st.columns(2)
            with c1:
                vl=df.groupby("LIBEVILL").agg(Nb=("LIBEVILL","count"),CA=("MONTENCA","sum")).reset_index().sort_values("Nb",ascending=False).head(15)
                fig=go.Figure(go.Bar(x=vl["Nb"],y=vl["LIBEVILL"].str[:18],orientation="h",
                    marker=dict(color=vl["Nb"],colorscale=[[0,MINT],[1,GREEN2]],showscale=False),
                    text=vl["Nb"].astype(str),textposition="outside",textfont_size=10))
                fig.update_layout(yaxis=dict(autorange="reversed"))
                fig_style(fig,400,"📍 Top 15 villes — Polices")
                st.plotly_chart(fig,use_container_width=True)
            with c2:
                vl_ca=df.groupby("LIBEVILL")["MONTENCA"].sum().reset_index().sort_values("MONTENCA",ascending=False).head(12)
                fig2=go.Figure(go.Bar(x=vl_ca["MONTENCA"],y=vl_ca["LIBEVILL"].str[:18],orientation="h",
                    marker=dict(color=vl_ca["MONTENCA"],colorscale=[[0,MINT],[1,GREEN2]],showscale=False),
                    text=[fmt(v) for v in vl_ca["MONTENCA"]],textposition="outside",textfont_size=10))
                fig2.update_layout(yaxis=dict(autorange="reversed"))
                fig_style(fig2,400,"💰 Top 12 villes — CA (MONTENCA)")
                st.plotly_chart(fig2,use_container_width=True)
            vl_e=df.groupby("LIBEVILL").agg(Nb=("LIBEVILL","count"),CA=("MONTENCA","sum")).reset_index().sort_values("Nb",ascending=False)
            vl_e["CA"]=vl_e["CA"].apply(fmt)
            st.dataframe(vl_e.head(30),use_container_width=True,hide_index=True)
            a,b=st.columns(2)
            a.download_button("📥 CSV villes",dl_csv(vl_e),"geo.csv","text/csv",use_container_width=True,key="dl_geo")
            b.download_button("📥 Excel",dl_xlsx(vl_e),"geo.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_geo_xl")
    with t_d:
        c1,c2,c3=st.columns(3)
        with c1:
            if "SEXERISQ" in df.columns:
                sx=df["SEXERISQ"].map({"M":"Hommes","F":"Femmes"}).value_counts().reset_index(); sx.columns=["Sexe","Nb"]
                fig=go.Figure(go.Pie(labels=sx["Sexe"],values=sx["Nb"],hole=.44,marker_colors=[BLUE,GREEN],textinfo="percent+label+value",textfont_size=12))
                fig_style(fig,320,"👥 Répartition H/F"); st.plotly_chart(fig,use_container_width=True)
        with c2:
            if "CODEPERI" in df.columns:
                per=df["CODEPERI"].map(CODEPERI_MAP).fillna("Autre").value_counts().reset_index(); per.columns=["Périodicité","Nb"]
                fig2=go.Figure(go.Pie(labels=per["Périodicité"],values=per["Nb"],hole=.44,marker_colors=PAL,textinfo="percent+label",textfont_size=11))
                fig_style(fig2,320,"📅 Périodicité cotisations"); st.plotly_chart(fig2,use_container_width=True)
        with c3:
            if "NOM_APP" in df.columns:
                ap=df[df["ETAT_POLICE"].str.strip()=="ACTIF"]["NOM_APP"].value_counts().head(10).reset_index() if "ETAT_POLICE" in df.columns else df["NOM_APP"].value_counts().head(10).reset_index()
                ap.columns=["Apporteur","Nb actifs"]
                fig3=go.Figure(go.Bar(y=ap["Apporteur"].str[:18],x=ap["Nb actifs"],orientation="h",marker_color=GREEN,text=ap["Nb actifs"].astype(str),textposition="outside",textfont_size=10))
                fig3.update_layout(yaxis=dict(autorange="reversed"))
                fig_style(fig3,320,"🏆 Top apporteurs (polices actives)"); st.plotly_chart(fig3,use_container_width=True)
    with t_a:
        if "DATENAIS" in df.columns and "SEXERISQ" in df.columns:
            da=df[["DATENAIS","SEXERISQ","MONTENCA"]].copy()
            da["DATENAIS"]=pd.to_datetime(da["DATENAIS"],errors="coerce")
            da=da.dropna(subset=["DATENAIS"])
            da["age"]=(pd.Timestamp.now()-da["DATENAIS"]).dt.days/365.25
            da=da[(da["age"]>=0)&(da["age"]<=95)]
            bins=list(range(0,100,5)); da["tranch"]=pd.cut(da["age"],bins=bins,right=False).astype(str)
            pyr=da.groupby(["tranch","SEXERISQ"]).size().unstack(fill_value=0).reset_index()
            if "M" in pyr.columns and "F" in pyr.columns:
                fig=go.Figure()
                fig.add_bar(y=pyr["tranch"],x=-pyr["M"],name="Hommes",orientation="h",marker_color=BLUE,text=pyr["M"].astype(str),textposition="outside",textfont_size=9)
                fig.add_bar(y=pyr["tranch"],x=pyr["F"],name="Femmes",orientation="h",marker_color=GREEN,text=pyr["F"].astype(str),textposition="outside",textfont_size=9)
                fig.update_layout(barmode="overlay",xaxis=dict(tickvals=list(range(-4000,4001,500)),ticktext=[str(abs(x)) for x in range(-4000,4001,500)]))
                fig_style(fig,520,"🎂 Pyramide des âges (tranches quinquennales)")
                st.plotly_chart(fig,use_container_width=True)
                a,_=st.columns(2)
                a.download_button("📥 CSV pyramide",dl_csv(da[["age","SEXERISQ"]]),"pyramide.csv","text/csv",use_container_width=True,key="dl_pyr")
        else: alert("Colonnes DATENAIS et SEXERISQ requises dans le portefeuille.","info")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — SINISTRES & PROVISIONS
# ═══════════════════════════════════════════════════════════════════════════════
elif "Sinistres" in page:
    if sin is None: alert("Chargez le fichier Prestations.","warn"); st.stop()
    df_s=sin  # tout le fichier pour les provisions historiques
    df_sf=sin_f()  # filtré par période

    section(f"⚠️ Sinistres & Provisions — {period_lbl}","ANALYSE ACTUARIELLE · SAP · S/P")
    tot_sin=float(sin["Réglement Total"].fillna(0).sum()) if "Réglement Total" in sin.columns else 0
    tot_sap=float(sin["SAP au 31/12/2025"].fillna(0).sum()) if "SAP au 31/12/2025" in sin.columns else 0
    tot_hon=float(sin["Réglement Honoraires"].fillna(0).sum()) if "Réglement Honoraires" in sin.columns else 0
    charge_u=tot_sin+tot_sap+tot_hon
    nb_sin=len(sin); nb_clos=int((sin["Sort Sinistre"]=="Cloturé").sum()) if "Sort Sinistre" in sin.columns else 0
    nb_ouv=int((sin["Sort Sinistre"]=="Ouvert").sum()) if "Sort Sinistre" in sin.columns else 0
    ca_all=float(ca["CHIFAFFA"].fillna(0).sum()) if ca is not None and "CHIFAFFA" in ca.columns else 0
    sp=tot_sin/max(ca_all,1)*100; cout_m=tot_sin/max(nb_clos,1)
    actifs_n=int((pf["ETAT_POLICE"].str.strip()=="ACTIF").sum()) if pf is not None and "ETAT_POLICE" in pf.columns else 1
    burning=charge_u/max(actifs_n,1)*1000

    c1,c2,c3,c4,c5,c6=st.columns(6)
    kpi(c1,"Total réglé",fmt(tot_sin),"Toutes périodes","red",icon="💊")
    kpi(c2,"SAP (provisions)",fmt(tot_sap),"Au 31/12/2025","amber",icon="📌")
    kpi(c3,"Charge ultime",fmt(charge_u),"Réglé+SAP+Hon.","red",icon="⚖️")
    kpi(c4,"Ratio S/P",pct(sp),"vs CA","red" if sp>80 else "amber",icon="📐")
    kpi(c5,"Coût moy/clos",fmt(cout_m),"Dossiers clos","teal",icon="💰")
    kpi(c6,"Burning Cost",fmt(burning),"Charge/1 000 actifs","red",icon="🔥")

    if not df_sf.empty and len(df_sf)<len(sin):
        alert(f"Période filtrée : {len(df_sf):,} dossiers (sur {len(sin):,}) pour {period_lbl}. Les KPIs ci-dessus couvrent toutes les périodes.","info")

    t_n,t_e,t_p,t_tri,t_r=st.tabs(["🏷️ Par nature","📈 Évolution","🛒 Par produit","📐 Triangle dev.","🔍 Données brutes"])

    with t_n:
        if "Nature Sinistre" in sin.columns:
            nat=sin.groupby("Nature Sinistre").agg(
                Nb=("Nature Sinistre","count"),Regle=("Réglement Total","sum"),SAP=("SAP au 31/12/2025","sum")).reset_index().sort_values("Regle",ascending=False)
            nat["Charge"]=nat["Regle"]+nat["SAP"]; nat["Coût moy"]=nat["Regle"]/nat["Nb"].replace(0,np.nan)
            c1,c2=st.columns(2)
            with c1:
                fig=go.Figure()
                fig.add_bar(y=nat["Nature Sinistre"].str[:22],x=nat["Regle"],name="Réglé",marker_color=RED,orientation="h")
                fig.add_bar(y=nat["Nature Sinistre"].str[:22],x=nat["SAP"],name="SAP",marker_color=AMBER,orientation="h")
                fig.update_layout(barmode="stack",yaxis=dict(autorange="reversed"))
                fig_style(fig,360,"💊 Réglé + SAP par nature"); st.plotly_chart(fig,use_container_width=True)
            with c2:
                fig2=px.treemap(nat,path=["Nature Sinistre"],values="Charge",color="Nb",
                    color_continuous_scale=[[0,MINT],[.5,AMBER],[1,RED]])
                fig2.update_layout(height=360,margin=dict(l=5,r=5,t=20,b=5)); st.plotly_chart(fig2,use_container_width=True)
            nat_d=nat.copy()
            for c_ in ["Regle","SAP","Charge","Coût moy"]: nat_d[c_]=nat_d[c_].apply(fmt)
            st.dataframe(nat_d,use_container_width=True,hide_index=True)
            a,b=st.columns(2)
            a.download_button("📥 CSV",dl_csv(nat),"sin_nature.csv","text/csv",use_container_width=True,key="dl_sin_nat")
            b.download_button("📥 Excel",dl_xlsx(nat),"sin_nature.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_sin_nat_xl")

    with t_e:
        if "ANNEE_SIN" in sin.columns:
            evo=sin.groupby("ANNEE_SIN").agg(Nb=("ANNEE_SIN","count"),Regle=("Réglement Total","sum"),SAP=("SAP au 31/12/2025","sum")).reset_index()
            evo=evo[evo["ANNEE_SIN"].between(1997,2025)].sort_values("ANNEE_SIN")
            fig=make_subplots(specs=[[{"secondary_y":True}]])
            fig.add_bar(x=evo["ANNEE_SIN"].astype(str),y=evo["Regle"],name="Réglé",marker_color=RED,opacity=.82)
            fig.add_bar(x=evo["ANNEE_SIN"].astype(str),y=evo["SAP"],name="SAP",marker_color=AMBER,opacity=.82)
            fig.add_scatter(x=evo["ANNEE_SIN"].astype(str),y=evo["Nb"],name="Nb dossiers",
                line=dict(color=GREEN,width=2.5),mode="lines+markers",secondary_y=True)
            fig.update_layout(barmode="stack")
            fig.update_yaxes(title_text="Montant (FCFA)",secondary_y=False)
            fig.update_yaxes(title_text="Nb dossiers",secondary_y=True,showgrid=False)
            fig_style(fig,420,"📈 Sinistres par exercice 1997–2025"); st.plotly_chart(fig,use_container_width=True)
            a,b=st.columns(2)
            a.download_button("📥 CSV",dl_csv(evo),"evo_sin.csv","text/csv",use_container_width=True,key="dl_evo_sin")
            b.download_button("📥 Excel",dl_xlsx(evo),"evo_sin.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_evo_sin_xl")

    with t_p:
        cat_c="Libéllé Catégorie" if "Libéllé Catégorie" in sin.columns else "Libellé Catégorie"
        if cat_c in sin.columns:
            sp2=sin.groupby(cat_c).agg(Nb=(cat_c,"count"),Regle=("Réglement Total","sum"),SAP=("SAP au 31/12/2025","sum")).reset_index().sort_values("Regle",ascending=False)
            sp2["Charge"]=sp2["Regle"]+sp2["SAP"]
            fig=go.Figure()
            fig.add_bar(x=sp2["Regle"],y=sp2[cat_c].str[:24],name="Réglé",marker_color=RED,orientation="h")
            fig.add_bar(x=sp2["SAP"],y=sp2[cat_c].str[:24],name="SAP",marker_color=AMBER,orientation="h")
            fig.update_layout(barmode="stack",yaxis=dict(autorange="reversed"))
            fig_style(fig,360,"🛒 Sinistres par produit"); st.plotly_chart(fig,use_container_width=True)
            sp2_d=sp2.copy()
            for c_ in ["Regle","SAP","Charge"]: sp2_d[c_]=sp2_d[c_].apply(fmt)
            st.dataframe(sp2_d,use_container_width=True,hide_index=True)
            a,_=st.columns(2)
            a.download_button("📥 CSV",dl_csv(sp2),"sin_prod.csv","text/csv",use_container_width=True,key="dl_sin_p")

    with t_tri:
        section("📐 Triangle de développement des sinistres","EXERCICE × SURVENANCE")
        if "ANNEE_SIN" in sin.columns and "Date Survenance" in sin.columns:
            sin2=sin.copy()
            sin2["DEV_YEAR"]=pd.to_datetime(sin2["Date Survenance"],errors="coerce").dt.year.astype("Int64")
            tri=sin2.pivot_table(index="ANNEE_SIN",columns="DEV_YEAR",values="Réglement Total",aggfunc="sum",fill_value=0)
            tri_d=tri.copy().astype(float)
            for col_ in tri_d.columns: tri_d[col_]=tri_d[col_].apply(fmt)
            alert("Triangle des montants réglés par exercice sinistre (lignes) et année de survenance (colonnes).","info")
            st.dataframe(tri_d,use_container_width=True,height=380)
            a,_=st.columns(2)
            a.download_button("📥 CSV triangle",dl_csv(tri.reset_index()),"triangle.csv","text/csv",use_container_width=True,key="dl_tri")
        else: alert("Colonnes ANNEE_SIN et Date Survenance requises.","info")

    with t_r:
        cs=[c for c in ["Date Survenance","Libéllé Catégorie","Nature Sinistre","Sort Sinistre","Souscripteur","Désignation risque","Réglement Total","SAP au 31/12/2025","Date Déclaration","Date validation","Nom Bénéficiaire","Exercice Sinistre","POLICE_KEY"] if c in sin.columns]
        srch_s=st.text_input("🔍 Rechercher",label_visibility="collapsed",placeholder="Nature, souscripteur, produit…",key="srch_sin")
        di_s=sin[cs].copy()
        for dc in ["Date Survenance","Date Déclaration","Date validation"]:
            if dc in di_s.columns: di_s[dc]=di_s[dc].apply(ds)
        for nc in ["Réglement Total","SAP au 31/12/2025"]:
            if nc in di_s.columns: di_s[nc]=di_s[nc].apply(lambda x:fmt(x,""))
        if srch_s: di_s=di_s[di_s.apply(lambda r:srch_s.lower() in str(r).lower(),axis=1)]
        st.dataframe(di_s.head(500),use_container_width=True,hide_index=True,height=420)
        st.caption(f"Affichage 500 / {len(di_s):,} lignes")
        a,b=st.columns(2)
        a.download_button("📥 CSV complet",dl_csv(sin),"prestations.csv","text/csv",use_container_width=True,key="dl_sin_raw")
        b.download_button("📥 Excel",dl_xlsx(sin[cs].head(50000)),"prestations.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_sin_raw_xl")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — ACTUARIAT AVANCÉ
# ═══════════════════════════════════════════════════════════════════════════════
elif "Actuariat" in page:
    section("📐 Actuariat Avancé","CIMA · SAP · BURNING COST · JOINTURES")
    t_c,t_p,t_l=st.tabs(["🏛️ CIMA & Solvabilité","📌 Provisions SAP","🔗 Liaison inter-bases"])
    with t_c:
        if pf is None: alert("Chargez le Portefeuille.","warn")
        else:
            nb=len(pf); ek="ETAT_POLICE"
            actifs=int((pf[ek].str.strip().isin(["ACTIF"])).sum()) if ek in pf.columns else 0
            resil=int((pf[ek].str.strip()=="RESILIE").sum()) if ek in pf.columns else 0
            inact=int((pf[ek].str.strip()=="INACTIF").sum()) if ek in pf.columns else 0
            echu=int((pf[ek].str.strip().isin(["ECHU","ASSURE ECHU"])).sum()) if ek in pf.columns else 0
            tx_act=actifs/max(nb,1)*100; tx_res=resil/max(nb-inact,1)*100
            ca_t=float(ca["CHIFAFFA"].fillna(0).sum()) if ca is not None and "CHIFAFFA" in ca.columns else 0
            sin_t=float(sin["Réglement Total"].fillna(0).sum()) if sin is not None and "Réglement Total" in sin.columns else 0
            sap_t=float(sin["SAP au 31/12/2025"].fillna(0).sum()) if sin is not None and "SAP au 31/12/2025" in sin.columns else 0
            sp=sin_t/max(ca_t,1)*100; charge_u=sin_t+sap_t; burning=charge_u/max(actifs,1)*1000
            monten=float(pf["MONTENCA"].fillna(0).apply(lambda x: float(str(x).replace(" ","").replace(",",".")) if str(x).replace(" ","").replace(",",".").replace(".","",1).replace("-","",1).isdigit() else 0).sum()) if "MONTENCA" in pf.columns else 0
            indics=[
                (tx_act,"Taux d'activité net",50,">=",GREEN),
                (tx_res,"Taux résiliation CIMA",25,"<=",RED),
                (sp,"Ratio S/P",80,"<=",AMBER),
                (inact/max(nb,1)*100,"Part inactifs",5,"<=",AMBER),
            ]
            for v,lbl,seuil,op,col in indics:
                ok=v>=seuil if op==">=" else v<=seuil; c_=GREEN if ok else RED
                st.markdown(f"""<div style="display:flex;align-items:center;justify-content:space-between;
                     padding:10px 14px;border-left:4px solid {c_};background:{c_}0D;
                     border-radius:0 10px 10px 0;margin-bottom:8px">
                  <div><div style="font-size:13px;font-weight:700;color:{NAVY}">{lbl}</div>
                  <div style="font-size:10px;color:#8899AA">Norme CIMA : {op}{seuil}%</div></div>
                  <div style="font-size:20px;font-weight:900;color:{c_}">{pct(v)} {'✅' if ok else '⚠️'}</div>
                </div>""", unsafe_allow_html=True)
            st.markdown("")
            ac1,ac2,ac3,ac4=st.columns(4)
            kpi(ac1,"Burning Cost",fmt(burning),"Charge ultime / 1 000 actifs","red",icon="🔥")
            kpi(ac2,"Charge ultime",fmt(charge_u),"Réglé + SAP","red",icon="⚖️")
            kpi(ac3,"CA 2024",fmt(ca_t),"Base calcul S/P","teal",icon="💰")
            kpi(ac4,"Encaissements PF",fmt(monten),"MONTENCA total","blue",icon="📊")
    with t_p:
        if sin is None: alert("Chargez les Prestations.","warn")
        else:
            prov=sin.groupby("Nature Sinistre").agg(
                Nb=("Nature Sinistre","count"),Regle=("Réglement Total","sum"),
                SAP=("SAP au 31/12/2025","sum"),Ouvert=("Sort Sinistre",lambda x:(x=="Ouvert").sum())
            ).reset_index()
            prov["Charge"]=prov["Regle"]+prov["SAP"]
            prov["Ratio SAP/Charge"]=prov["SAP"]/prov["Charge"].replace(0,np.nan)*100
            prov["Coût moy clos"]=prov["Regle"]/(prov["Nb"]-prov["Ouvert"]).replace(0,np.nan)
            fig=go.Figure()
            fig.add_bar(y=prov["Nature Sinistre"].str[:22],x=prov["Regle"],name="Réglé cumulé",marker_color=GREEN,orientation="h")
            fig.add_bar(y=prov["Nature Sinistre"].str[:22],x=prov["SAP"],name="SAP résiduel",marker_color=AMBER,orientation="h")
            fig.update_layout(barmode="stack",yaxis=dict(autorange="reversed"))
            fig_style(fig,360,"📌 Structure Réglé / SAP par nature"); st.plotly_chart(fig,use_container_width=True)
            pv=prov.copy()
            for c_ in ["Regle","SAP","Charge","Coût moy clos"]: pv[c_]=pv[c_].apply(fmt)
            pv["Ratio SAP/Charge"]=pv["Ratio SAP/Charge"].apply(lambda x:f"{x:.1f}%" if pd.notna(x) else "—")
            pv.columns=["Nature","Nb","Réglé","SAP","Dossiers ouverts","Charge","Ratio SAP/Charge","Coût moy clos"]
            st.dataframe(pv,use_container_width=True,hide_index=True)
            a,b=st.columns(2)
            a.download_button("📥 CSV provisions",dl_csv(prov),"provisions.csv","text/csv",use_container_width=True,key="dl_prov")
            b.download_button("📥 Excel",dl_xlsx(prov),"provisions.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_prov_xl")
    with t_l:
        section("🔗 Liaison inter-bases","POLICE_KEY · MATCHING · CA × PF × SIN")
        if pf is not None and ca is not None and "POLICE_KEY" in pf.columns and "POLICE_KEY" in ca.columns:
            mc=ca["POLICE_KEY"].isin(pf["POLICE_KEY"]).sum()
            ms=sin["POLICE_KEY"].isin(pf["POLICE_KEY"]).sum() if sin is not None and "POLICE_KEY" in sin.columns else 0
            mcs=sin["POLICE_KEY"].isin(ca["POLICE_KEY"]).sum() if sin is not None and "POLICE_KEY" in sin.columns and "POLICE_KEY" in ca.columns else 0
            l1,l2,l3=st.columns(3)
            kpi(l1,"CA ↔ PF",f"{mc:,}",f"{mc/max(len(ca),1)*100:.1f}% des quittances","teal",icon="🔗")
            kpi(l2,"SIN ↔ PF",f"{ms:,}",f"{ms/max(len(sin) if sin is not None else 1,1)*100:.1f}%","teal",icon="🔗")
            kpi(l3,"SIN ↔ CA",f"{mcs:,}",f"{mcs/max(len(sin) if sin is not None else 1,1)*100:.1f}%","blue",icon="🔗")
            section("📊 Top polices — Jointure CA × PF × SIN","CA DÉCROISSANT")
            pf_lk=pf[["POLICE_KEY","LIBECATE","ETAT_POLICE","NOM_ASSU","LIBEVILL","NOM_APP"]].drop_duplicates("POLICE_KEY")
            ca_pf=ca.merge(pf_lk,on="POLICE_KEY",how="inner",suffixes=("","_PF"))
            if sin is not None and "POLICE_KEY" in sin.columns:
                sin_agg=sin.groupby("POLICE_KEY").agg(Regle=("Réglement Total","sum"),SAP=("SAP au 31/12/2025","sum"),NbSin=("POLICE_KEY","count")).reset_index()
                ca_pf=ca_pf.merge(sin_agg,on="POLICE_KEY",how="left")
            else:
                ca_pf["Regle"]=np.nan; ca_pf["SAP"]=np.nan; ca_pf["NbSin"]=np.nan
            tp=ca_pf.groupby(["POLICE_KEY","LIBECATE","ETAT_POLICE","NOM_ASSU","NOM_APP"]).agg(
                CA=("CHIFAFFA","sum"),NbQ=("CHIFAFFA","count"),
                Regle=("Regle","first"),SAP=("SAP","first"),NbSin=("NbSin","first")
            ).reset_index().sort_values("CA",ascending=False).head(30)
            tp_d=tp.copy()
            for c_ in ["CA","Regle","SAP"]: tp_d[c_]=tp_d[c_].apply(lambda x:fmt(x) if pd.notna(x) else "—")
            tp_d["NbSin"]=tp_d["NbSin"].apply(lambda x:str(int(x)) if pd.notna(x) else "0")
            st.dataframe(tp_d,use_container_width=True,hide_index=True)
            a,_=st.columns(2)
            a.download_button("📥 CSV jointure 3 bases",dl_csv(tp),"jointure_3bases.csv","text/csv",use_container_width=True,key="dl_join3")
        else: alert("Chargez le Portefeuille et la Base CA.","info")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — PRÉVISIONS & TENDANCES
# ═══════════════════════════════════════════════════════════════════════════════
elif "Prévisions" in page:
    section("🔮 Prévisions & Tendances","MODÈLE POLYNOMIAL · SAISONNALITÉ · PROJECTION")
    if ca is None and pf is None: alert("Chargez la Base CA ou le Portefeuille.","warn"); st.stop()
    src=ca if ca is not None else pf
    ca_k="CHIFAFFA" if "CHIFAFFA" in src.columns else "MONTENCA"
    d_k="DATECOMP" if "DATECOMP" in src.columns else "DATESOUS"
    if d_k not in src.columns: alert("Colonne date introuvable.","warn"); st.stop()
    src2=src[[d_k,ca_k]].copy()
    src2[d_k]=pd.to_datetime(src2[d_k],errors="coerce"); src2=src2.dropna(subset=[d_k])
    mo=src2.groupby(src2[d_k].dt.to_period("M").astype(str))[ca_k].sum().reset_index()
    mo.columns=["Période","CA"]; mo=mo.sort_values("Période")
    n=len(mo)
    if n<6: alert("Données insuffisantes pour les prévisions (< 6 mois).","warn"); st.stop()
    c1,c2=st.columns(2)
    deg_sel=c1.slider("Degré du polynôme",1,4,2,key="deg_s")
    n_hor=c2.slider("Mois à prévoir",1,24,12,key="n_hor_s")
    xs=np.arange(n); ys=mo["CA"].values.astype(float)
    coeffs=np.polyfit(xs,ys,deg_sel)
    trend_h=np.polyval(coeffs,xs)
    x_f=np.arange(n,n+n_hor); trend_f=np.maximum(np.polyval(coeffs,x_f),0)
    r2=1-np.sum((ys-trend_h)**2)/max(np.sum((ys-ys.mean())**2),1)
    last_p=pd.Period(mo["Période"].iloc[-1],"M")
    fut_l=[str(last_p+i+1) for i in range(n_hor)]
    kc1,kc2,kc3=st.columns(3)
    kpi(kc1,"CA historique total",fmt(ys.sum()),"Série complète","",icon="💰")
    kpi(kc2,f"R² modèle (deg {deg_sel})",f"{r2:.4f}","Qualité ajustement","teal" if r2>.8 else "amber",icon="📐")
    kpi(kc3,f"Prévision H+{n_hor}",fmt(trend_f[-1]),"Projection","blue",icon="🔮")
    st.markdown("")
    fig=go.Figure()
    fig.add_scatter(x=mo["Période"],y=ys,name="CA historique",line=dict(color=GREEN,width=2),mode="lines+markers",marker=dict(size=4))
    fig.add_scatter(x=mo["Période"],y=trend_h,name="Tendance ajustée",line=dict(color=TEAL,width=2,dash="dot"),mode="lines")
    fig.add_scatter(x=fut_l,y=trend_f,name="Prévision",line=dict(color=RED,width=2.5,dash="dash"),mode="lines+markers",marker=dict(symbol="star",size=9,color=RED))
    fig.add_vrect(x0=fut_l[0],x1=fut_l[-1],fillcolor="rgba(192,57,43,0.04)",line_width=0,annotation_text="Zone prévision")
    fig_style(fig,480,f"🔮 Modèle polynomial (deg {deg_sel}) — R²={r2:.3f}")
    st.plotly_chart(fig,use_container_width=True)
    df_fut=pd.DataFrame({"Période":fut_l,"CA prévu":[fmt(v) for v in trend_f],"Valeur (FCFA)":trend_f.round(0)})
    st.dataframe(df_fut[["Période","CA prévu"]],use_container_width=True,hide_index=True)
    a,b=st.columns(2)
    a.download_button("📥 CSV prévisions",dl_csv(df_fut),"previsions.csv","text/csv",use_container_width=True,key="dl_prev")
    b.download_button("📥 Excel",dl_xlsx(df_fut),"previsions.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_prev_xl")
    if n>=12:
        section("📅 Saisonnalité mensuelle","CA MOYEN PAR MOIS")
        src2["MOIS"]=src2[d_k].dt.month
        saison=src2.groupby("MOIS")[ca_k].mean().reset_index(); saison.columns=["Mois","CA moyen"]
        saison["Label"]=saison["Mois"].apply(lambda m:MOIS_FR[int(m)-1] if pd.notna(m) else "")
        moy_g=saison["CA moyen"].mean()
        fig2=go.Figure(go.Bar(x=saison["Label"],y=saison["CA moyen"],
            marker_color=[GREEN if v>=moy_g else f"{GREEN}55" for v in saison["CA moyen"]],
            text=[fmt(v) for v in saison["CA moyen"]],textposition="outside",textfont_size=10))
        fig2.add_hline(y=moy_g,line_dash="dash",line_color=RED,annotation_text=f"Moy. {fmt(moy_g)}",annotation_font_size=10)
        fig_style(fig2,360,"📅 Saisonnalité — CA moyen par mois")
        st.plotly_chart(fig2,use_container_width=True)
        a2,_=st.columns(2)
        a2.download_button("📥 CSV saisonnalité",dl_csv(saison),"saisonnalite.csv","text/csv",use_container_width=True,key="dl_sai")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — SAISIE BIA (7 étapes)
# ═══════════════════════════════════════════════════════════════════════════════
elif "Saisie BIA" in page:
    # Compteurs BIA (compatibles PG et SQLite via bia_all())
    _df_bia_hdr = bia_all()
    nb_bia  = len(_df_bia_hdr)
    cot_tot = float(_df_bia_hdr["cotisation"].fillna(0).astype(float).sum()) if not _df_bia_hdr.empty else 0
    nb_val  = int((_df_bia_hdr["statut"]=="Validé").sum()) if not _df_bia_hdr.empty else 0
    c1,c2,c3=st.columns(3)
    kpi(c1,"BIA enregistrés",str(nb_bia),"Total base BIA","teal",icon="📋")
    kpi(c2,"Validés",str(nb_val),f"{nb_val/max(nb_bia,1)*100:.0f}%","",icon="✅")
    kpi(c3,"Cotisations BIA",fmt(cot_tot),"Total","blue",icon="💰")

    # ── Étape 1 : Sélection du produit ────────────────────────────────────────
    section("Étape 1 — Sélection du produit","AFG ASSURANCES BÉNIN VIE")
    GC={"Groupe 1":RED,"Groupe 2":GREEN}

    # Groupe 1 — Décès
    with st.expander("🛡️ Groupe 1 — Décès & Vie", expanded=True):
        col_a, col_b = st.columns(2)
        # AVIGBO
        with col_a:
            st.markdown(f"""<div style="border:2px solid {RED}44;border-radius:10px;padding:12px 14px;margin-bottom:6px">
              <span style="background:{RED};color:white;font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px">221</span>
              <div style="font-size:13px;font-weight:700;margin-top:6px;color:{NAVY}">ASSURTOUS AVIGBO</div>
              <div style="font-size:11px;color:#666;margin-top:3px">Décès · Barème fixe</div>
              <div style="font-size:10px;color:#888;margin-top:5px;line-height:1.6">
                100 F/mois → Capital 100 000 F  (unique : 1 000 F)<br>
                200 F/mois → Capital 200 000 F  (unique : 2 000 F)<br>
                300 F/mois → Capital 300 000 F  (unique : 3 000 F)
              </div>
            </div>""", unsafe_allow_html=True)
            if st.button("Choisir AVIGBO (221)", key="bp_221", use_container_width=True):
                st.session_state["bia_prod"]="221"; st.session_state["bia_step"]=2; st.rerun()
        # VIGNINOU
        with col_b:
            st.markdown(f"""<div style="border:2px solid {RED}44;border-radius:10px;padding:12px 14px;margin-bottom:6px">
              <span style="background:{RED};color:white;font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px">220</span>
              <div style="font-size:13px;font-weight:700;margin-top:6px;color:{NAVY}">ASSURTOUS VIGNINOU</div>
              <div style="font-size:11px;color:#666;margin-top:3px">Décès · Durée max 12 mois · Barème fixe</div>
              <div style="font-size:10px;color:#888;margin-top:5px;line-height:1.6">
                400 F/mois → Capital 500 000 F  (unique : 48 000 F)<br>
                800 F/mois → Capital 1 000 000 F (unique : 96 000 F)<br>
                1 200 F/mois → Capital 1 500 000 F (unique : 144 000 F)
              </div>
            </div>""", unsafe_allow_html=True)
            if st.button("Choisir VIGNINOU (220)", key="bp_220", use_container_width=True):
                st.session_state["bia_prod"]="220"; st.session_state["bia_step"]=2; st.rerun()

    # Groupe 2 — Épargne
    with st.expander("💰 Groupe 2 — Épargne & Capitalisation", expanded=True):
        st.markdown(f"""<div style="border:2px solid {GREEN}44;border-radius:10px;padding:12px 14px;margin-bottom:6px">
          <span style="background:{GREEN};color:white;font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px">EP0</span>
          <div style="font-size:13px;font-weight:700;margin-top:6px;color:{NAVY}">Épargne</div>
          <div style="font-size:11px;color:#666;margin-top:3px">Épargne vie · Périodicité libre · Capital calculé à la souscription</div>
          <div style="font-size:10px;color:#888;margin-top:5px">
            Périodicités disponibles : Journalière · Hebdomadaire · Mensuelle · Trimestrielle · Semestrielle · Annuelle · Unique<br>
            Chargements : 1% acquisition + 0.5% gestion · Taux technique : 3.5%
          </div>
        </div>""", unsafe_allow_html=True)
        if st.button("Choisir Épargne", key="bp_EP0", use_container_width=True):
            st.session_state["bia_prod"]="EP0"; st.session_state["bia_step"]=2; st.rerun()

    if "bia_prod" not in st.session_state:
        alert("Sélectionnez un produit pour afficher le formulaire BIA.","info"); st.stop()
    prod=next((p for p in PRODUITS if p["code"]==st.session_state.get("bia_prod")),None)
    if not prod: st.session_state.pop("bia_prod",None); st.rerun()
    gc=GC.get(prod["grp"],BLUE); step=st.session_state.get("bia_step",2)
    is_avigbo   = prod["code"]=="221"
    is_vigninou = prod["code"]=="220"
    is_deces    = prod["code"] in ("220","221")
    is_epargne  = prod["code"]=="EP0"

    st.markdown(f"""<div style="background:{NAVY};border-radius:10px;padding:10px 16px;margin:10px 0;display:flex;align-items:center;justify-content:space-between">
      <div><div style="color:rgba(255,255,255,.45);font-size:9px;letter-spacing:.1em">BIA — BULLETIN INDIVIDUEL D'ADHÉSION</div>
      <div style="color:white;font-size:14px;font-weight:700">{prod['nom']}</div></div>
      <span style="background:{gc};color:white;font-size:12px;font-weight:700;padding:5px 12px;border-radius:6px">{prod['code']}</span>
    </div>""",unsafe_allow_html=True)
    if st.button("↩️ Changer de produit",key="chg_p"): st.session_state.pop("bia_prod",None); st.session_state.pop("bia_step",None); st.rerun()
    SLBL={2:"Identification",3:"Souscripteur",4:"Assuré",5:"Contrat",6:"Médical",7:"Validation"}
    st.progress((step-2)/5,text=f"Étape {step-1}/6 — {SLBL.get(step,'')}")
    st.markdown("")

    def ti(k,lbl,ph="",t="text"):
        st.session_state[k]=st.text_input(lbl,value=st.session_state.get(k,""),placeholder=ph,key=f"i_{k}")
    def si(k,lbl,opts):
        cur=st.session_state.get(k,opts[0]); idx=opts.index(cur) if cur in opts else 0
        st.session_state[k]=st.selectbox(lbl,opts,index=idx,key=f"s_{k}")

    if step==2:
        section("Étape 2 — Identification & Agence")
        c1,c2,c3=st.columns(3)
        with c1: si("f_agence","Agence",AGENCES)
        with c2: ti("f_code_appo","Code apporteur","Ex : AFG001")
        with c3: ti("f_nom_appo","Nom apporteur")
        c4,c5=st.columns(2)
        with c4: ti("f_realis","Réalisateur",user["nom"])
        with c5: si("f_deja","Déjà assuré AFGVie ?",["Non","Oui"])
        if st.session_state.get("f_deja")=="Oui": ti("f_num_ct","N° contrat existant")
        if st.button("Suivant ▶",type="primary"): st.session_state["bia_step"]=3; st.rerun()

    elif step==3:
        section("Étape 3 — Souscripteur / Contractant")
        c1,c2,c3=st.columns([1,2,2])
        with c1: si("f_c_tit","Civilité *",["","M.","Mme","Mlle"])
        with c2: ti("f_c_nom","Nom *","NOM (majuscules)")
        with c3: ti("f_c_prn","Prénoms *")
        c4,c5,c6=st.columns(3)
        with c4:
            cur_d=st.session_state.get("f_c_ddn",date(1985,1,1))
            if isinstance(cur_d,str):
                try: cur_d=date.fromisoformat(cur_d)
                except: cur_d=date(1985,1,1)
            st.session_state["f_c_ddn"]=st.date_input("Date naissance *",value=cur_d,min_value=date(1930,1,1),max_value=today,key="ddn_c")
        with c5: ti("f_c_lieu","Lieu naissance *","Cotonou")
        with c6: ti("f_c_nat","Nationalité","Béninoise")
        if not st.session_state.get("f_c_nat"): st.session_state["f_c_nat"]="Béninoise"
        c7,c8,c9=st.columns(3)
        with c7: si("f_c_mat","Sit. matrimoniale",["","Célibataire","Marié(e)","Divorcé(e)","Veuf(ve)"])
        with c8: ti("f_c_prof","Profession *")
        with c9: ti("f_c_adr","Adresse *","Quartier, rue")
        c10,c11,c12=st.columns(3)
        with c10: ti("f_c_tel","Tél. cel. *","+229 97…")
        with c11: ti("f_c_wapp","WhatsApp *","+229 97…")
        with c12: ti("f_c_npi","N°NPI / Passeport *","BJ123456")
        c13,c14=st.columns(2)
        with c13: ti("f_c_eml","Email","exemple@mail.com")
        with c14: ti("f_c_bp","Boîte postale","01 BP…")
        st.session_state["f_ass_meme"]=st.checkbox("✓ L'assuré(e) est identique au souscripteur",value=st.session_state.get("f_ass_meme",True))
        b1,b2=st.columns(2)
        if b1.button("← Retour"): st.session_state["bia_step"]=2; st.rerun()
        if b2.button("Suivant ▶",type="primary"):
            if not st.session_state.get("f_c_nom","").strip(): st.error("Nom obligatoire")
            elif not st.session_state.get("f_c_prn","").strip(): st.error("Prénom obligatoire")
            else: st.session_state["bia_step"]=4; st.rerun()

    elif step==4:
        section("Étape 4 — Assuré(e) & Bénéficiaires")
        if st.session_state.get("f_ass_meme",True):
            st.success(f"✅ Assuré(e) = {st.session_state.get('f_c_tit','')} {st.session_state.get('f_c_nom','').upper()} {st.session_state.get('f_c_prn','')} — reprises du souscripteur.")
        else:
            c1,c2,c3=st.columns([1,2,2])
            with c1: si("f_a_tit","Civilité",["","M.","Mme","Mlle"])
            with c2:
                st.session_state["f_a_nom"]=st.text_input("Nom *",value=st.session_state.get("f_a_nom",""),key="an")
            with c3:
                st.session_state["f_a_prn"]=st.text_input("Prénoms *",value=st.session_state.get("f_a_prn",""),key="ap")
            c4,c5=st.columns(2)
            with c4:
                cur_a=st.session_state.get("f_a_ddn",date(1990,1,1))
                if isinstance(cur_a,str):
                    try: cur_a=date.fromisoformat(cur_a)
                    except: cur_a=date(1990,1,1)
                st.session_state["f_a_ddn"]=st.date_input("Date naissance",value=cur_a,key="ddn_a")
            with c5:
                st.session_state["f_a_npi"]=st.text_input("NPI",value=st.session_state.get("f_a_npi",""),key="ani")
        section("Bénéficiaires")
        st.session_state["f_bc"]=st.checkbox("Mon conjoint, mes enfants nés et à naître, à défaut mes ayants droits",value=st.session_state.get("f_bc",True))
        st.session_state["f_ba"]=st.text_input("Autres bénéficiaires",value=st.session_state.get("f_ba",""),key="ba_t")
        b1,b2=st.columns(2)
        if b1.button("← Retour"): st.session_state["bia_step"]=3; st.rerun()
        if b2.button("Suivant ▶",type="primary"): st.session_state["bia_step"]=5; st.rerun()

    elif step==5:
        section("Étape 5 — Caractéristiques du Contrat")

        # ── Date d'effet (commun) ─────────────────────────────────────────────
        cur_e=st.session_state.get("f_deff",today)
        if isinstance(cur_e,str):
            try: cur_e=date.fromisoformat(cur_e)
            except: cur_e=today

        # ══════════════════════════════════════════════════════════════════════
        # AVIGBO — barème fixe, 3 options, durée libre
        # ══════════════════════════════════════════════════════════════════════
        if is_avigbo:
            alert("Contrat AVIGBO : le capital et la cotisation unique sont déterminés automatiquement selon la prime mensuelle choisie.","info")
            # Sélection du barème
            opt_map = {
                "100 F/mois → Capital 100 000 F (unique : 1 000 F)":   (100,  100_000,  1_000),
                "200 F/mois → Capital 200 000 F (unique : 2 000 F)":   (200,  200_000,  2_000),
                "300 F/mois → Capital 300 000 F (unique : 3 000 F)":   (300,  300_000,  3_000),
            }
            opts_list = list(opt_map.keys())
            cur_opt = st.session_state.get("f_avigbo_opt", opts_list[0])
            if cur_opt not in opts_list: cur_opt = opts_list[0]
            selected_opt = st.radio("Barème de cotisation *", opts_list,
                                    index=opts_list.index(cur_opt), key="avigbo_opt_r")
            st.session_state["f_avigbo_opt"] = selected_opt
            prime_m, capital_g, prime_u = opt_map[selected_opt]

            c1,c2=st.columns(2)
            with c1:
                peri_av_opts=["Mensuelle","Unique"]
                cur_pav=st.session_state.get("f_peri","Mensuelle")
                if cur_pav not in peri_av_opts: cur_pav="Mensuelle"
                st.session_state["f_peri"]=st.radio("Périodicité *",peri_av_opts,
                    horizontal=True,index=peri_av_opts.index(cur_pav),key="peri_av_r")
            with c2:
                st.session_state["f_deff"]=st.date_input("Date d'effet *",value=cur_e,key="eff_d")

            # Cotisation et capital automatiques
            if st.session_state["f_peri"]=="Mensuelle":
                coti_auto=prime_m
            else:
                coti_auto=prime_u
            st.session_state["f_coti"]=coti_auto
            st.session_state["f_cap"] =capital_g

            st.markdown(f"""
            <div style="background:{GREEN}12;border:1.5px solid {GREEN};border-radius:10px;padding:12px 16px;margin:10px 0">
              <div style="font-size:10px;color:{GREEN};font-weight:700;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">Paramètres automatiques AVIGBO</div>
              <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;font-size:13px">
                <div><span style="color:#888;font-size:10px">Cotisation</span><br><b>{coti_auto:,} FCFA / {st.session_state['f_peri'].lower()}</b></div>
                <div><span style="color:#888;font-size:10px">Capital garanti décès</span><br><b style="color:{RED}">{capital_g:,} FCFA</b></div>
                <div><span style="color:#888;font-size:10px">Option garantie</span><br><b>Avec garantie décès</b></div>
              </div>
            </div>""", unsafe_allow_html=True)
            st.session_state["f_gar"]="Avec garantie décès"
            st.session_state["f_duree"]=st.number_input("Durée du contrat (ans) *",min_value=1,max_value=40,
                value=int(st.session_state.get("f_duree",5)),key="dur_av")

        # ══════════════════════════════════════════════════════════════════════
        # VIGNINOU — barème fixe, durée MAX 12 mois
        # ══════════════════════════════════════════════════════════════════════
        elif is_vigninou:
            alert("Contrat VIGNINOU : durée maximale 12 mois. Capital et cotisation unique fixés par le barème.","warn")
            opt_map_v = {
                "400 F/mois → Capital 500 000 F (unique : 48 000 F)":    (400,  500_000,  48_000),
                "800 F/mois → Capital 1 000 000 F (unique : 96 000 F)":  (800,  1_000_000,96_000),
                "1 200 F/mois → Capital 1 500 000 F (unique : 144 000 F)": (1200, 1_500_000,144_000),
            }
            opts_list_v = list(opt_map_v.keys())
            cur_opt_v = st.session_state.get("f_vigninou_opt", opts_list_v[0])
            if cur_opt_v not in opts_list_v: cur_opt_v = opts_list_v[0]
            selected_opt_v = st.radio("Barème de cotisation *", opts_list_v,
                                       index=opts_list_v.index(cur_opt_v), key="vign_opt_r")
            st.session_state["f_vigninou_opt"] = selected_opt_v
            prime_m_v, capital_g_v, prime_u_v = opt_map_v[selected_opt_v]

            c1,c2,c3=st.columns(3)
            with c1:
                peri_v_opts=["Mensuelle","Unique"]
                cur_pv=st.session_state.get("f_peri","Mensuelle")
                if cur_pv not in peri_v_opts: cur_pv="Mensuelle"
                st.session_state["f_peri"]=st.radio("Périodicité *",peri_v_opts,
                    horizontal=True,index=peri_v_opts.index(cur_pv),key="peri_v_r")
            with c2:
                # Durée en MOIS pour VIGNINOU (max 12 mois)
                dur_v_mois=st.number_input("Durée (mois, max 12) *",min_value=1,max_value=12,
                    value=int(st.session_state.get("f_duree_mois_v",12)),key="dur_v_m")
                st.session_state["f_duree_mois_v"]=dur_v_mois
                # On stocke en fraction d'année pour cohérence BIA
                st.session_state["f_duree"]=1  # 1 an max
            with c3:
                st.session_state["f_deff"]=st.date_input("Date d'effet *",value=cur_e,key="eff_d")

            if st.session_state["f_peri"]=="Mensuelle":
                coti_auto_v=prime_m_v
            else:
                coti_auto_v=prime_u_v
            st.session_state["f_coti"]=coti_auto_v
            st.session_state["f_cap"] =capital_g_v

            st.markdown(f"""
            <div style="background:{RED}08;border:1.5px solid {RED};border-radius:10px;padding:12px 16px;margin:10px 0">
              <div style="font-size:10px;color:{RED};font-weight:700;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">Paramètres automatiques VIGNINOU · Durée max 12 mois</div>
              <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px;font-size:13px">
                <div><span style="color:#888;font-size:10px">Cotisation</span><br><b>{coti_auto_v:,} FCFA / {st.session_state['f_peri'].lower()}</b></div>
                <div><span style="color:#888;font-size:10px">Capital garanti décès</span><br><b style="color:{RED}">{capital_g_v:,} FCFA</b></div>
                <div><span style="color:#888;font-size:10px">Durée choisie</span><br><b>{dur_v_mois} mois</b></div>
                <div><span style="color:#888;font-size:10px">Option garantie</span><br><b>Avec garantie décès</b></div>
              </div>
            </div>""", unsafe_allow_html=True)
            st.session_state["f_gar"]="Avec garantie décès"

        # ══════════════════════════════════════════════════════════════════════
        # ÉPARGNE — libre, calcul du capital à terme
        # ══════════════════════════════════════════════════════════════════════
        else:
            c1,c2=st.columns(2)
            with c1:
                st.session_state["f_deff"]=st.date_input("Date d'effet *",value=cur_e,key="eff_d")
            with c2:
                st.session_state["f_duree"]=st.number_input("Durée (ans) *",min_value=1,max_value=40,
                    value=int(st.session_state.get("f_duree",10)),key="dur_n")

            c3,c4=st.columns(2)
            with c3:
                st.session_state["f_coti"]=st.number_input("Cotisation FCFA *",min_value=100,
                    value=int(st.session_state.get("f_coti",5000)),key="cot_n")
            with c4:
                peri_ep_opts=["Journalière","Hebdomadaire","Mensuelle","Trimestrielle","Semestrielle","Annuelle","Unique"]
                cur_pep=st.session_state.get("f_peri","Mensuelle")
                if cur_pep not in peri_ep_opts: cur_pep="Mensuelle"
                st.session_state["f_peri"]=st.selectbox("Périodicité *",peri_ep_opts,
                    index=peri_ep_opts.index(cur_pep),key="peri_ep_s")

            # ── Calcul dynamique du capital au terme ─────────────────────────
            P_ep   = float(st.session_state.get("f_coti",5000))
            n_ep   = int(st.session_state.get("f_duree",10))
            peri_ep= st.session_state.get("f_peri","Mensuelle")
            res_ep = calcul_capital_epargne(P_ep, peri_ep, n_ep)
            cap_ep = res_ep["capital_brut"]
            st.session_state["f_cap"] = int(cap_ep)

            st.markdown(f"""
            <div style="background:{GREEN}10;border:1.5px solid {GREEN};border-radius:10px;padding:14px 16px;margin:12px 0">
              <div style="font-size:10px;color:{GREEN};font-weight:700;text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px">
                Simulation actuarielle — Capital au terme
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-bottom:10px">
                <div style="background:white;border-radius:8px;padding:10px 12px;border:0.5px solid {MGRAY}">
                  <div style="font-size:9px;color:#888;text-transform:uppercase;letter-spacing:.06em">Cotisation nette P_net</div>
                  <div style="font-size:18px;font-weight:700;color:{NAVY}">{res_ep['Pnet']:,.0f} <span style="font-size:11px;font-weight:400">FCFA</span></div>
                  <div style="font-size:10px;color:#888">α=1% acq. + β=0.5% gest.</div>
                </div>
                <div style="background:white;border-radius:8px;padding:10px 12px;border:0.5px solid {MGRAY}">
                  <div style="font-size:9px;color:#888;text-transform:uppercase;letter-spacing:.06em">Total cotisations versées</div>
                  <div style="font-size:18px;font-weight:700;color:{NAVY}">{res_ep['total_verse']:,.0f} <span style="font-size:11px;font-weight:400">FCFA</span></div>
                  <div style="font-size:10px;color:#888">Sur {n_ep} an(s) · {peri_ep}</div>
                </div>
                <div style="background:linear-gradient(135deg,{GREEN},{GREEN2});border-radius:8px;padding:10px 12px">
                  <div style="font-size:9px;color:rgba(255,255,255,.7);text-transform:uppercase;letter-spacing:.06em">Capital au terme C_n</div>
                  <div style="font-size:20px;font-weight:800;color:white">{cap_ep:,.0f} <span style="font-size:12px;font-weight:400">FCFA</span></div>
                  <div style="font-size:10px;color:rgba(255,255,255,.7)">Rendement : +{res_ep['rendement']:.1f}%</div>
                </div>
              </div>
              <div style="font-size:10px;color:#666;font-family:monospace;background:#f8f9fa;border-radius:6px;padding:8px 10px;line-height:1.7">
                {res_ep['formule']}
              </div>
            </div>""", unsafe_allow_html=True)

        # ── Mode de règlement (commun tous produits) ─────────────────────────
        section("Mode de règlement")
        m_o=["","Mobile Monnaie","Par chèque","Par virement bancaire","Par prélèvement sur salaire"]
        cur_m=st.session_state.get("f_mode","")
        st.session_state["f_mode"]=st.radio("Mode *",m_o,horizontal=True,
            index=m_o.index(cur_m) if cur_m in m_o else 0,key="mode_r",
            format_func=lambda x:"— Choisir —" if x=="" else x)
        if st.session_state["f_mode"]:
            ref_l={"Mobile Monnaie":"📱 N° Mobile Money","Par chèque":"📄 N° Chèque",
                   "Par virement bancaire":"🏦 N° Compte/RIB",
                   "Par prélèvement sur salaire":"💼 N° Matricule"}.get(st.session_state["f_mode"],"Référence")
            ti("f_mref",ref_l)

        b1,b2=st.columns(2)
        if b1.button("← Retour"): st.session_state["bia_step"]=4; st.rerun()
        if b2.button("Suivant ▶",type="primary"): st.session_state["bia_step"]=6; st.rerun()

    elif step==6:
        section("Étape 6 — Questionnaire Médical CIMA")
        alert("Art. 18 CIMA : Toute fausse déclaration est sanctionnée par la nullité du contrat.","warn")
        c1,c2,c3=st.columns(3)
        st.session_state["f_taille"]=c1.text_input("Taille (m)",value=st.session_state.get("f_taille",""),placeholder="1.72",key="taille_t")
        st.session_state["f_poids"]=c2.text_input("Poids (kg)",value=st.session_state.get("f_poids",""),placeholder="75",key="poids_t")
        per_m=["Non","Oui"]
        cur_pp=st.session_state.get("f_perte","Non")
        st.session_state["f_perte"]=c3.radio("Grossi/maigri >5 kg (6 mois) ?",per_m,horizontal=True,index=per_m.index(cur_pp) if cur_pp in per_m else 0,key="perte_r")
        MED=[
            ("q1","Maladie ou séquelles — surveillance médicale requise (10 ans) ?",False),
            ("q2","Arrêts de travail >21 jours (5 dernières années) ?",False),
            ("q3","Traitement médical >21 jours (5 ans, hors contraception) ?",False),
            ("q4","Actuellement en arrêt de travail sur prescription médicale ?",False),
            ("q5","Traitement médical en cours (hors contraception) ?",False),
            ("q6","Hospitalisation ou analyses dans les 12 prochains mois ?",True),
            ("q7","Méningite, hépatite B, VIH/Sida, cancer ou maladie grave ?",False),
        ]
        for qk,qtxt,special in MED:
            with st.container(border=True):
                qa,qb=st.columns([3.5,1])
                qa.markdown(f"<div style='font-size:11px;line-height:1.4'><b>{qk[1:]}.</b> {qtxt}</div>",unsafe_allow_html=True)
                r_o=["Non","Oui"]
                cur_r=st.session_state.get(f"f_{qk}","Non")
                st.session_state[f"f_{qk}"]=qb.radio("",r_o,horizontal=True,index=r_o.index(cur_r) if cur_r in r_o else 0,key=f"r_{qk}")
                if st.session_state[f"f_{qk}"]=="Oui":
                    st.session_state[f"f_{qk}d"]=st.text_input("Précisions :",value=st.session_state.get(f"f_{qk}d",""),placeholder="Soyez précis(e)",key=f"d_{qk}")
        b1,b2=st.columns(2)
        if b1.button("← Retour"): st.session_state["bia_step"]=5; st.rerun()
        if b2.button("Suivant ▶",type="primary"): st.session_state["bia_step"]=7; st.rerun()

    elif step==7:
        section("Étape 7 — Déclaration & Validation")
        st.markdown("""<div style="background:#f8f9fa;border:1px solid #ddd;border-radius:8px;padding:12px;
            font-size:11px;line-height:1.8;max-height:120px;overflow-y:auto;margin-bottom:12px">
            Je reconnais avoir reçu la notice d'information du produit et les conditions générales.
            Je certifie exactes et sincères toutes les informations renseignées.
            Conformément à l'article 18 du code CIMA, toute fausse déclaration
            entraîne la nullité du contrat.</div>""",unsafe_allow_html=True)
        st.session_state["f_dc"]=st.checkbox("☑ J'accepte les conditions de souscription *",value=st.session_state.get("f_dc",False))
        st.session_state["f_dd"]=st.checkbox("☑ J'accepte la politique de protection des données *",value=st.session_state.get("f_dd",False))
        c1,c2=st.columns(2)
        stat_o=["Brouillon","En cours","Validé"]
        cur_st=st.session_state.get("f_stat","Brouillon")
        st.session_state["f_stat"]=c1.selectbox("Statut",stat_o,index=stat_o.index(cur_st) if cur_st in stat_o else 0,key="stat_s")
        st.session_state["f_obs"]=c2.text_input("Observations",value=st.session_state.get("f_obs",""),key="obs_t")
        with st.expander("📋 Récapitulatif complet", expanded=True):
            cap_recap = int(st.session_state.get("f_cap",0))
            dur_recap = st.session_state.get("f_duree",1)
            # Pour VIGNINOU, afficher la durée en mois
            dur_label = f"{st.session_state.get('f_duree_mois_v',12)} mois" if is_vigninou else f"{dur_recap} an(s)"
            st.markdown(f"""| Champ | Valeur |
|---|---|
|**Souscripteur**|{st.session_state.get('f_c_tit','')} {st.session_state.get('f_c_nom','').upper()} {st.session_state.get('f_c_prn','')}|
|**Produit**|{prod['nom']} — code {prod['code']}|
|**Cotisation**|{st.session_state.get('f_coti',0):,} FCFA / {st.session_state.get('f_peri','—')}|
|**Capital garanti / au terme**|**{cap_recap:,} FCFA**|
|**Date d'effet**|{ds(st.session_state.get('f_deff',today))}|
|**Durée**|{dur_label}|
|**Mode règlement**|{st.session_state.get('f_mode','—')}|
|**Option garantie**|{st.session_state.get('f_gar','—')}|""")

        def save_bia(statut_ov=None):
            ass = st.session_state.get("f_ass_meme", True)
            data = {
                "numero_bia":       gen_bia(),
                "date_saisie":      today.isoformat(),
                "saisi_par":        user["nom"],
                "agence":           st.session_state.get("f_agence",""),
                "code_apporteur":   st.session_state.get("f_code_appo",""),
                "nom_apporteur":    st.session_state.get("f_nom_appo",""),
                "realisateur":      st.session_state.get("f_realis",""),
                "deja_assure":      st.session_state.get("f_deja","Non"),
                "num_ct_exist":     st.session_state.get("f_num_ct",""),
                "c_titre":          st.session_state.get("f_c_tit",""),
                "c_nom":            st.session_state.get("f_c_nom","").upper().strip(),
                "c_prenom":         st.session_state.get("f_c_prn","").strip(),
                "c_ddn":            str(st.session_state.get("f_c_ddn", date(1985,1,1))),
                "c_lieu":           st.session_state.get("f_c_lieu",""),
                "c_nat":            st.session_state.get("f_c_nat","Béninoise"),
                "c_mat":            st.session_state.get("f_c_mat",""),
                "c_prof":           st.session_state.get("f_c_prof",""),
                "c_adr":            st.session_state.get("f_c_adr",""),
                "c_bp":             st.session_state.get("f_c_bp",""),
                "c_email":          st.session_state.get("f_c_eml",""),
                "c_wapp":           st.session_state.get("f_c_wapp",""),
                "c_tel":            st.session_state.get("f_c_tel",""),
                "c_fixe":           st.session_state.get("f_c_fixe",""),
                "c_npi":            st.session_state.get("f_c_npi",""),
                "ass_meme":         1 if ass else 0,
                "a_titre":          "" if ass else st.session_state.get("f_a_tit",""),
                "a_nom":            "" if ass else st.session_state.get("f_a_nom","").upper(),
                "a_prenom":         "" if ass else st.session_state.get("f_a_prn",""),
                "a_ddn":            "" if ass else str(st.session_state.get("f_a_ddn","")),
                "a_npi":            "" if ass else st.session_state.get("f_a_npi",""),
                "benef_conj":       1 if st.session_state.get("f_bc", True) else 0,
                "benef_autres":     st.session_state.get("f_ba",""),
                "code_produit":     prod["code"],
                "produit":          prod["nom"],
                "groupe_produit":   prod["grp"],
                "cotisation":       float(st.session_state.get("f_coti", 0)),
                "cotisation_lettres": st.session_state.get("f_cotil",""),
                "periodicite":      st.session_state.get("f_peri","Mensuelle"),
                "date_effet":       str(st.session_state.get("f_deff", today)),
                "duree":            (st.session_state.get("f_duree_mois_v", 12)
                                     if is_vigninou
                                     else int(st.session_state.get("f_duree", 10))),
                "option_gar":       st.session_state.get("f_gar","Sans garantie décès"),
                "mode_reglement":   st.session_state.get("f_mode",""),
                "mode_ref":         st.session_state.get("f_mref",""),
                "capital_terme":    float(st.session_state.get("f_cap", 0) or 0),
                **{f"q{qi}":  st.session_state.get(f"f_q{qi}","Non") for qi in range(1,8)},
                **{f"q{qi}d": st.session_state.get(f"f_q{qi}d","")  for qi in range(1,8)},
                "decl_cond":        1 if st.session_state.get("f_dc") else 0,
                "decl_data":        1 if st.session_state.get("f_dd") else 0,
                "statut":           statut_ov or st.session_state.get("f_stat","Brouillon"),
                "obs":              st.session_state.get("f_obs",""),
            }
            # insert_bia() gère PG (%s) et SQLite (?) automatiquement
            ok = insert_bia(data)
            if ok:
                for k in [k for k in list(st.session_state.keys()) if k.startswith("f_")]:
                    del st.session_state[k]
                st.session_state.pop("bia_prod", None)
                st.session_state.pop("bia_step", None)
                return data["numero_bia"]
            return None
        b1,b2,b3=st.columns([1,1,1.4])
        if b1.button("← Retour"): st.session_state["bia_step"]=6; st.rerun()
        if b2.button("💾 Brouillon"):
            num=save_bia("Brouillon")
            if num: st.info(f"💾 Brouillon **{num}** enregistré. Retrouvez-le dans la Base BIA.")
        if b3.button("✅ VALIDER LE BIA",type="primary"):
            errs=[]
            if not st.session_state.get("f_c_nom","").strip(): errs.append("Nom souscripteur obligatoire")
            if not st.session_state.get("f_dc"): errs.append("Conditions de souscription requises")
            if not st.session_state.get("f_dd"): errs.append("Politique données requise")
            if errs:
                for e in errs: st.error(f"❌ {e}")
            else:
                num=save_bia("Validé")
                if num: st.balloons(); st.success(f"🎉 BIA **{num}** validé ! {st.session_state.get('f_c_tit','')} {st.session_state.get('f_c_nom','').upper()}")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — BASE BIA
# ═══════════════════════════════════════════════════════════════════════════════
elif "Base BIA" in page:
    df_bia=bia_all()
    section("🗂️ Base BIA — Registre des bulletins","CONSULTATION · GESTION · EXPORT")
    if df_bia.empty:
        alert("Aucun BIA enregistré. Utilisez l'onglet <b>Saisie BIA</b>.","info"); st.stop()
    nb_all=len(df_bia); nb_val=int((df_bia["statut"]=="Validé").sum())
    nb_bro=int((df_bia["statut"]=="Brouillon").sum()); cot_t=float(df_bia["cotisation"].fillna(0).astype(float).sum())
    c1,c2,c3,c4=st.columns(4)
    kpi(c1,"Total BIA",str(nb_all),"Base complète","teal",icon="📋")
    kpi(c2,"Cotisations",fmt(cot_t),"Total FCFA","",icon="💰")
    kpi(c3,"Validés",str(nb_val),f"{nb_val/max(nb_all,1)*100:.0f}%","",icon="✅")
    kpi(c4,"Brouillons",str(nb_bro),"À compléter","amber",icon="💾")
    # Graphiques
    g1,g2=st.columns(2)
    with g1:
        by_st=df_bia["statut"].value_counts().reset_index(); by_st.columns=["Statut","Nb"]
        fig=go.Figure(go.Pie(labels=by_st["Statut"],values=by_st["Nb"],hole=.44,
            marker_colors=[GREEN,AMBER,RED,BLUE],textinfo="percent+label+value",textfont_size=12))
        fig_style(fig,260,"📊 Répartition par statut"); st.plotly_chart(fig,use_container_width=True)
    with g2:
        if "produit" in df_bia.columns:
            by_p=df_bia.groupby("produit").agg(Nb=("produit","count"),Cot=("cotisation","sum")).reset_index().sort_values("Cot",ascending=False).head(8)
            fig2=go.Figure(go.Bar(x=by_p["Cot"],y=by_p["produit"].str[:22],orientation="h",
                marker_color=GREEN,text=[fmt(v) for v in by_p["Cot"]],textposition="outside",textfont_size=10))
            fig2.update_layout(yaxis=dict(autorange="reversed"))
            fig_style(fig2,260,"💰 Cotisations BIA par produit"); st.plotly_chart(fig2,use_container_width=True)
    # Valider brouillons
    brous=df_bia[df_bia["statut"]=="Brouillon"]
    if not brous.empty:
        alert(f"<b>{len(brous)} brouillon(s)</b> en attente de validation.","warn")
        with st.expander(f"📋 Valider un brouillon ({len(brous)} en attente)"):
            for _,br in brous.iterrows():
                cc1,cc2,cc3=st.columns([4,1,1])
                cc1.markdown(f"**{br['numero_bia']}** · {br.get('c_titre','')} {br.get('c_nom','')} {br.get('c_prenom','')} · {br.get('produit','')} · {fmt(br.get('cotisation',0))}")
                if cc2.button("✅",key=f"val_{br['id']}"):
                    update_bia_statut(int(br["id"]), "Validé")
                    st.balloons(); st.rerun()
                if cc3.button("🗑️",key=f"del_{br['id']}"):
                    delete_bia(int(br["id"])); st.rerun()
    # Filtres
    f1,f2,f3=st.columns(3)
    srch_b=f1.text_input("🔍 Rechercher",label_visibility="collapsed",placeholder="N° BIA, nom, produit…",key="srch_b")
    stat_o=["Tous"]+sorted(df_bia["statut"].dropna().unique().tolist())
    stat_b=f2.selectbox("Statut",stat_o,label_visibility="collapsed")
    prod_ob=["Tous"]+sorted(df_bia["produit"].dropna().unique().tolist())
    prod_b=f3.selectbox("Produit",prod_ob,label_visibility="collapsed")
    fi_b=df_bia.copy()
    if srch_b: fi_b=fi_b[fi_b.apply(lambda r:srch_b.lower() in str(r).lower(),axis=1)]
    if stat_b!="Tous": fi_b=fi_b[fi_b["statut"]==stat_b]
    if prod_b!="Tous": fi_b=fi_b[fi_b["produit"]==prod_b]
    st.caption(f"Affichage {len(fi_b):,} / {nb_all:,} bulletins")
    CB=["numero_bia","date_saisie","c_titre","c_nom","c_prenom","c_tel","nom_apporteur","produit","cotisation","periodicite","mode_reglement","date_effet","duree","statut","agence","saisi_par"]
    cs=[c for c in CB if c in fi_b.columns]
    di_b=fi_b[cs].copy()
    if "cotisation" in di_b.columns: di_b["cotisation"]=di_b["cotisation"].apply(lambda x:fmt(float(x)) if pd.notna(x) else "—")
    st.dataframe(di_b,use_container_width=True,hide_index=True,height=400)
    if not fi_b.empty:
        section("🔍 Détail d'un BIA")
        sel_b=st.selectbox("Sélectionnez",fi_b["numero_bia"].tolist(),key="sel_det")
        row=fi_b[fi_b["numero_bia"]==sel_b].iloc[0]
        t_i,t_m,t_c=st.tabs(["📋 Informations","🏥 Médical","📄 Contrat"])
        with t_i:
            c1,c2=st.columns(2)
            for f_,l_ in [("c_titre","Civilité"),("c_nom","Nom"),("c_prenom","Prénoms"),("c_ddn","Naissance"),("c_prof","Profession"),("c_tel","Tél."),("c_npi","NPI"),("c_adr","Adresse"),("c_email","Email"),("nom_apporteur","Apporteur"),("agence","Agence"),("saisi_par","Saisi par")]:
                v=row.get(f_,"")
                if pd.notna(v) and str(v).strip(): c1.markdown(f"**{l_}** : {v}")
        with t_m:
            for qn in range(1,8):
                rep=row.get(f"q{qn}",""); det=row.get(f"q{qn}d","")
                if pd.notna(rep) and rep:
                    cc_=RED if rep=="Oui" else GREEN
                    st.markdown(f"**Q{qn} :** <span style='color:{cc_};font-weight:700'>{rep}</span>{' — '+str(det) if det and pd.notna(det) else ''}",unsafe_allow_html=True)
        with t_c:
            c1,_=st.columns(2)
            for f_,l_ in [("produit","Produit"),("cotisation","Cotisation"),("periodicite","Périodicité"),("date_effet","Date effet"),("duree","Durée"),("option_gar","Option garantie"),("mode_reglement","Mode règlement"),("statut","Statut"),("obs","Observations")]:
                v=row.get(f_,"")
                if f_=="cotisation" and pd.notna(v): v=fmt(float(v))
                if pd.notna(v) and str(v).strip(): c1.markdown(f"**{l_}** : {v}")
    st.markdown("")
    d1,d2,d3=st.columns(3)
    d1.download_button("📥 CSV filtré",dl_csv(fi_b),f"bia_{today}.csv","text/csv",use_container_width=True,key="dl_bia_f")
    d2.download_button("📥 Excel filtré",dl_xlsx(fi_b[cs]),f"bia_{today}.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_bia_xl")
    d3.download_button("📥 CSV complet",dl_csv(df_bia),"bia_complet.csv","text/csv",use_container_width=True,key="dl_bia_full")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════
elif "Exports" in page:
    section(f"📤 Exports Complets — {period_lbl}","CSV · EXCEL · TOUTES BASES")
    alert("Chaque tableau de chaque onglet est aussi téléchargeable directement. Cette page = exports complets.","info")
    BEXP=[("pf",pf,"Portefeuille","DATESOUS","MONTENCA"),("ca",ca,"Base CA","DATECOMP","CHIFAFFA"),("sin",sin,"Prestations","Date Survenance","Réglement Total")]
    for sid,data,lbl,dc,amk in BEXP:
        df_f=filter_df(data,dc,sel_date,MODE) if data is not None else pd.DataFrame()
        with st.expander(f"📋 {lbl}",expanded=True):
            if data is None: st.warning("Base non chargée.")
            else:
                tot_v=float(data[amk].fillna(0).sum()) if amk in data.columns else 0
                c1,c2,c3=st.columns(3)
                c1.metric("Total lignes",f"{len(data):,}")
                c2.metric(f"Lignes · {period_lbl}",f"{len(df_f):,}")
                c3.metric("Montant total",fmt(tot_v))
                b1,b2,b3=st.columns(3)
                b1.download_button(f"📥 CSV complet",dl_csv(data),f"{sid}_complet.csv","text/csv",use_container_width=True,key=f"dl_{sid}_fc")
                b2.download_button(f"📥 CSV {period_lbl}",dl_csv(df_f),f"{sid}_{period_lbl}.csv","text/csv",use_container_width=True,key=f"dl_{sid}_fp")
                b3.download_button(f"📥 Excel {period_lbl}",dl_xlsx(df_f.head(50000)),f"{sid}_{period_lbl}.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key=f"dl_{sid}_xl")
    df_bia_e = bia_all()
    with st.expander("📋 Base BIA",expanded=True):
        c1,c2=st.columns(2); c1.metric("Total BIA",len(df_bia_e))
        c2.metric("Cotisations",fmt(float(df_bia_e["cotisation"].fillna(0).astype(float).sum())))
        b1,b2=st.columns(2)
        b1.download_button("📥 CSV BIA",dl_csv(df_bia_e),"bia_complet.csv","text/csv",use_container_width=True,key="dl_bia_e")
        b2.download_button("📥 Excel BIA",dl_xlsx(df_bia_e),"bia.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_bia_xl_e")

# ── FOOTER ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:{NAVY};color:rgba(255,255,255,.3);text-align:center;
     font-size:10px;padding:12px;border-radius:10px;margin-top:20px;border-top:3px solid {GREEN}">
  © 2025 <strong style="color:{MINT}">AFG Assurances Bénin Vie</strong>
  · Dashboard Actuariel Expert v3.0 · Conforme CIMA · 306 295 polices · Groupe AFG Holding
  · <em>Données confidentielles — Accès restreint</em>
</div>""", unsafe_allow_html=True)
