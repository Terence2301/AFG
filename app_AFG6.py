#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
AFG ASSURANCES BENIN VIE — TABLEAU DE BORD PDG v15.0
CORRECTIONS v15 (version définitive) :
  [OK] Signatures : 3 zones file_uploader HORS du st.form (corrige l erreur Streamlit)
  [OK] Base BIA : code apporteur + nom apporteur dans toutes les vues (liste + détail)
  [OK] dbg() : une seule définition propre au niveau module
  [OK] Accueil : suppression des blocs dupliqués (df, dbg, yr_acc)
  [OK] Validation BIA : signatures lues depuis session_state (pas de NameError)
  [OK] Reset signatures après enregistrement réussi
  [OK] Syntaxe Python 100% validée ast.parse
  FONCTIONNALITÉS CONSERVÉES (v14) :
  [OK] Données RÉELLES Excel portefeuille (42 323 polices au 31/12/2025)
  [OK] Questionnaire médical complet (7 questions CIMA) avec précisions conditionnelles
  [OK] Code et nom apporteur auto-remplis à la connexion commercial
  [OK] Connexion commerciaux : NOM PRÉNOM + code_agent
  [OK] KPIs BIA rechargés automatiquement (ttl=0)
  [OK] Import Excel externe pour portefeuille + KPIs mis à jour
  [OK] Surveillance risques compagnie AFG
NOUVELLES FONCTIONNALITÉS v14 :
  [OK] Données RÉELLES Excel portefeuille (42 323 polices au 31/12/2025) intégrées
  [OK] Questionnaire médical complet intégré dans le BIA (7 questions CIMA)
  [OK] Signatures stockées en BLOB + visualisables dans la base BIA (onglet Vérification)
  [OK] Code et nom apporteur sauvegardés en BD + auto-remplis à la connexion
  [OK] Connexion commerciaux : NOM PRÉNOM (majuscules) = identifiant, code = mot de passe
  [OK] Connexion direction/admin : création d'identifiant + mot de passe libre
  [OK] KPIs BIA rechargés automatiquement à chaque BIA validé (ttl=0)
  [OK] Import Excel externe pour mise à jour données portefeuille (+ portefeuille réel)
  [OK] Page Accueil PDG : KPIs portefeuille réel (42 323 polices, CA, actifs, etc.)
  [OK] Surveillance risques compagnie AFG (solvabilité, résiliation, sinistres)
  [OK] Lien partageable via Streamlit Cloud (mobile + desktop)
  [OK] Aucune erreur Python — Syntaxe validée ast.parse
================================================================================
DÉPLOIEMENT STREAMLIT CLOUD (lien partageable) :
  1. Poussez ce fichier sur GitHub (repo public ou privé)
  2. Allez sur https://share.streamlit.io → New app → votre repo → app_afg_v14.py
  3. Copiez le lien généré → partagez-le (fonctionne sur mobile et desktop)
  IDENTIFIANTS DIRECTION : PDG AFG / pdg2025AFG  |  ADMIN AFG / admin2025AFG
  COMMERCIAUX : NOM PRÉNOM EN MAJUSCULES / code_agent (ex: ADJOVI PAUL / AFG001)
================================================================================
"""

import streamlit as st

st.set_page_config(
    page_title="AFG Assurances Bénin Vie — PDG Dashboard v19",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "AFG Assurances Bénin Vie v22.0 — Conforme CIMA"}
)

import pandas as pd, numpy as np
import plotly.express as px, plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
from datetime import datetime, timedelta, date
import warnings, os, random, io, hashlib, base64
warnings.filterwarnings("ignore")

# ── COULEURS ──────────────────────────────────────────────────────────────────
NAVY="#003366"; BLUE="#004D99"; BLUEL="#0072CE"
GOLD="#C9A227"; GOLDL="#E8C84A"
WHITE="#FFFFFF"; LGRAY="#F4F6FA"; MGRAY="#DDE3EE"
DGRAY="#5A6478"; GREEN="#1A7A4A"; RED="#C0392B"
AMBER="#D35400"; TEAL="#0A7B6C"

# ── DONNÉES RÉELLES PORTEFEUILLE EXCEL (31/12/2025 — 42 323 polices) ─────────
PORT_REEL = {
    "total": 42323, "actif": 11623, "resilie": 25657, "inactif": 3367,
    "echu": 1660, "suspendu": 16,
    "tx_actif": 27.5, "tx_resil": 60.6,
    "ca_total": 24_396_246_131, "coti_total": 3_385_492_740,
    "ca_actifs": 11_285_025_424,
    "nb_comm": 1316,
    "genre": {"M": 31507, "F": 9903},
    "produits": [
        {"code":"244","nom":"Atlantique Horizon Retraite","total":16962,"actif":3587,"resilie":12101,"ca":6_868_751_000,"coti":268_591_600},
        {"code":"247","nom":"Atlantique Avenir Enfant","total":13856,"actif":4235,"resilie":7853,"ca":4_543_696_000,"coti":160_831_400},
        {"code":"240","nom":"Atlantique Epargne Crédit","total":4107,"actif":477,"resilie":3117,"ca":2_397_209_000,"coti":131_477_600},
        {"code":"210","nom":"Atl. Sécurité Famille","total":2248,"actif":936,"resilie":1291,"ca":1_344_662_000,"coti":0},
        {"code":"245","nom":"C.I.A","total":1304,"actif":769,"resilie":512,"ca":146_954_500,"coti":319_635_100},
        {"code":"255","nom":"DOKOUNTCHE MULTISUPPORTS","total":1241,"actif":864,"resilie":49,"ca":2_637_011_000,"coti":2_485_183_000},
        {"code":"242","nom":"MaRetraite","total":642,"actif":197,"resilie":442,"ca":161_109_400,"coti":11_799_000},
        {"code":"220","nom":"ASSURTOUS Vigninou","total":562,"actif":3,"resilie":0,"ca":361_600,"coti":0},
        {"code":"221","nom":"ASSURTOUS AVIGBO","total":503,"actif":315,"resilie":0,"ca":205_500,"coti":0},
        {"code":"243","nom":"CAPI Prestige","total":437,"actif":176,"resilie":236,"ca":5_962_636_000,"coti":1_300_000},
        {"code":"248","nom":"Service de Rente","total":330,"actif":0,"resilie":0,"ca":0,"coti":4_554_974},
        {"code":"252","nom":"EPARGNE ETUDE","total":111,"actif":48,"resilie":53,"ca":27_230_000,"coti":2_120_000},
        {"code":"246","nom":"CAPI Invest","total":20,"actif":16,"resilie":3,"ca":306_421_700,"coti":0},
    ],
    "villes_actif": {
        "COTONOU":4360,"ABOMEY-CALAVI":1141,"PORTO-NOVO":1097,"PARAKOU":920,
        "BOHICON":836,"ABOMEY":228,"LOKOSSA":191,"OUIDAH":180,"DJOUGOU":133,
        "KLOUEKANME":121,"KANDI":118,"SEME-KPODJI":118,"ALLADA":115,
    },
    "annuel": {
        2015:1569,2016:1094,2017:1862,2018:2362,2019:2021,
        2020:1797,2021:1671,2022:1176,2023:1908,2024:4995,2025:3425
    },
    "mensuel_2024_2025": {
        "2024-01":110,"2024-02":76,"2024-03":106,"2024-04":66,"2024-05":527,
        "2024-06":965,"2024-07":1052,"2024-08":675,"2024-09":484,"2024-10":339,
        "2024-11":336,"2024-12":259,"2025-01":164,"2025-02":241,"2025-03":230,
        "2025-04":367,"2025-05":323,"2025-06":280,"2025-07":431,"2025-08":257,
        "2025-09":428,"2025-10":394,"2025-11":247,"2025-12":63,
    },
    "periodicite": {"Mensuelle":40286,"Trimestrielle":984,"Annuelle":438,"Libre":372,"Semestrielle":141,"Unique":40},
    "banques": {"BOA":7504,"DCSCA":3899,"ECOBANK":2939,"CCP":1417,"UBA BENIN":1284,"BAB":1186,"NSIA BANQUE":1109},
    "top_comm": [
        ("GNANCADJA LÉOPOLD","2000",3327),("BOSSE FRANÇOIS","2005",1180),
        ("DESSO VIRGILE","2006",1101),("CAPO-CHICHI HYACINTHE","2010",811),
        ("SOTOHOU G. ALCESTE","2013",700),("FANOU-ATA DAVID","2004",699),
        ("TOSSOU GONTRAN EMMANUEL","2012",685),("AHOSSI BARTHÉLÉMY","2009",615),
        ("DANGBENON FRANCK","2014",603),("ANANI MEDARD","2016",552),
    ],
}

# ── PRODUITS & GROUPES ────────────────────────────────────────────────────────
PRODUITS_FR = [
    ("204","Décès Capital Constant","Prévoyance"),
    ("205","Décès Emprunteur","Crédit"),
    ("207","Décès Emprunteur Acceptation","Crédit"),
    ("209","Décès Emprunteur Groupe","Crédit"),
    ("210","Atlantique Sécurité Famille (ex CAVES)","Prévoyance"),
    ("219","Prévoyance Entreprise","Prévoyance"),
    ("220","ASSURTOUS Vigninou","Prévoyance"),
    ("221","ASSURTOUS AVIGBO","Prévoyance"),
    ("240","Atlantique Epargne Crédit","Épargne"),
    ("242","MaRetraite","Retraite"),
    ("243","CAPI Prestige","Capitalisation"),
    ("244","Atlantique Horizon Retraite","Retraite"),
    ("245","C.I.A","Crédit"),
    ("247","Atlantique Avenir Enfant","Épargne"),
    ("250","Retraite Complémentaire Groupe","Retraite"),
    ("255","DOKOUNTCHE MULTISUPPORTS","Épargne"),
    ("260","I.F.C","Épargne"),
    ("202","Atlantique Assistances Funéraires","Prévoyance"),
]
GROUPE_MAP = {
    "204":"Groupe 1 — Décès & Vie","205":"Groupe 1 — Décès & Vie",
    "207":"Groupe 1 — Décès & Vie","209":"Groupe 1 — Décès & Vie",
    "210":"Groupe 1 — Décès & Vie","219":"Groupe 1 — Décès & Vie",
    "220":"Groupe 1 — Décès & Vie","221":"Groupe 1 — Décès & Vie",
    "202":"Groupe 1 — Décès & Vie",
    "240":"Groupe 2 — Épargne & Capitalisation","242":"Groupe 2 — Épargne & Capitalisation",
    "243":"Groupe 2 — Épargne & Capitalisation","244":"Groupe 2 — Épargne & Capitalisation",
    "245":"Groupe 2 — Épargne & Capitalisation","250":"Groupe 2 — Épargne & Capitalisation",
    "255":"Groupe 2 — Épargne & Capitalisation","260":"Groupe 2 — Épargne & Capitalisation",
    "247":"Groupe 3 — Contrat Mixte",
}
GROUPE_COLORS = {
    "Groupe 1 — Décès & Vie":"#C0392B",
    "Groupe 2 — Épargne & Capitalisation":"#1A7A4A",
    "Groupe 3 — Contrat Mixte":"#0072CE",
}
GROUPE_ICONS = {
    "Groupe 1 — Décès & Vie":"🛡️",
    "Groupe 2 — Épargne & Capitalisation":"💰",
    "Groupe 3 — Contrat Mixte":"🔄",
}
def get_groupe(code): return GROUPE_MAP.get(str(code),"Groupe 2 — Épargne & Capitalisation")

# Agences officielles AFG Bénin
AGENCES_AFG = [
    "", "Siège Social — Cotonou", "Agence Cotonou Centre", "Agence Cotonou Littoral",
    "Agence Cotonou Cadjèhoun", "Agence Porto-Novo", "Agence Abomey-Calavi",
    "Agence Parakou", "Agence Bohicon", "Agence Natitingou",
    "Agence Ouidah", "Agence Lokossa", "Agence Kandi",
    "Agence Abomey", "Agence Djougou", "Agence Allada",
    "Agence Sèmè-Kpodji", "Agence Bembèrèkè",
]

BIA_SPECIFIQUES = {"242":"horizon","244":"horizon","243":"capi","255":"dokountche","247":"avenir"}
BIA_PAR_DEFAUT = "capi"

# ── BASE DE DONNÉES — chemin défini tôt (utilisé par auth) ───────────────────
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DB_DIR, exist_ok=True)
DB = os.path.join(DB_DIR, "afg_v13.db")

def gc():
    return sqlite3.connect(DB, check_same_thread=False)

# ── PORTEFEUILLE EXCEL — chargement automatique ──────────────────────────────
# Le fichier Excel du portefeuille (export logiciel métier) peut être placé :
#   1) à côté de ce script (./Portefeuille_non_deces_au_31_12_2025._princ.xlsx)
#   2) dans le dossier ./data/
#   3) dans /mnt/documents/ (déploiements cloud)
# Le code apporteur (CODEAPPO) et le nom apporteur (NOM_APP) servent
# notamment à l'authentification des commerciaux.
PORTEFEUILLE_FILENAMES = [
    "Portefeuille_non_deces_au_31_12_2025._princ.xlsx",
    "Portefeuille_non_deces.xlsx",
    "portefeuille.xlsx",
]
def _find_portefeuille_path():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    for name in PORTEFEUILLE_FILENAMES:
        candidates += [
            os.path.join(here, name),
            os.path.join(here, "data", name),
            os.path.join("/mnt/documents", name),
            os.path.join("/mnt/documents/data", name),
        ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None

# Chemin du cache pickle — survit aux déconnexions/rechargements
_PF_CACHE = os.path.join(DB_DIR, "afg_portefeuille_cache.pkl")
_PF_META  = os.path.join(DB_DIR, "afg_portefeuille_meta.json")

def save_portefeuille_cache(df: "pd.DataFrame", meta: dict = None):
    """Sauvegarde le portefeuille en cache pickle sur disque."""
    try:
        df.to_pickle(_PF_CACHE)
        import json
        info = meta or {}
        info["saved_at"] = datetime.now().isoformat()
        info["rows"] = len(df)
        info["cols"] = len(df.columns)
        with open(_PF_META, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def delete_portefeuille_cache():
    """Supprime le cache portefeuille du disque."""
    for p in [_PF_CACHE, _PF_META]:
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

def load_portefeuille_cache() -> "pd.DataFrame | None":
    """Charge le portefeuille depuis le cache pickle disque."""
    if not os.path.exists(_PF_CACHE):
        return None
    try:
        return pd.read_pickle(_PF_CACHE)
    except Exception:
        return None

def get_portefeuille_meta() -> dict:
    """Retourne les métadonnées du cache (date, taille)."""
    try:
        import json
        if os.path.exists(_PF_META):
            with open(_PF_META, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

@st.cache_data(show_spinner=False)
def load_portefeuille_auto():
    """Charge le portefeuille depuis le cache disque (pickle).
    Appelé au démarrage — survit aux déconnexions."""
    return load_portefeuille_cache()

@st.cache_data(show_spinner=False)
def get_apporteurs_index():
    """Retourne un dict {CODEAPPO_str_upper: NOM_APP} construit depuis le
    portefeuille Excel chargé en session ou auto-détecté.
    Sert à l'authentification commerciale : code apporteur = mot de passe,
    nom apporteur = identifiant."""
    df = st.session_state.get("portefeuille_ext")
    if df is None:
        df = load_portefeuille_auto()
    if df is None or "CODEAPPO" not in df.columns:
        return {}
    sub = df[["CODEAPPO", "NOM_APP"]].dropna(subset=["CODEAPPO"]).drop_duplicates()
    out = {}
    for _, r in sub.iterrows():
        code = str(r["CODEAPPO"]).strip().upper()
        nom = str(r.get("NOM_APP", "") or "").strip()
        if code and code not in out:
            out[code] = nom
    return out

# ── AUTH v13 ─────────────────────────────────────────────────────────────────
# Les commerciaux se connectent avec : NOM PRÉNOM EN MAJUSCULES + code_agent
# La direction/admin créent leur propre identifiant + mot de passe libre
# ─────────────────────────────────────────────────────────────────────────────

# Comptes direction (stockés dans session JSON-like dans session_state à init)
DIRECTION_USERS_DEFAULT = {
    "PDG AFG":        {"pwd": hashlib.sha256(b"pdg2025AFG").hexdigest(),    "role": "Direction",      "nom": "PDG AFG",              "init": "PDG", "code": "PDG001"},
    "DG AFG":         {"pwd": hashlib.sha256(b"dg2025AFG").hexdigest(),     "role": "Direction",      "nom": "DG AFG",               "init": "DGA", "code": "DGA001"},
    "ADMIN AFG":      {"pwd": hashlib.sha256(b"admin2025AFG").hexdigest(),  "role": "Administrateur", "nom": "Administrateur AFG",   "init": "ADM", "code": "ADM001"},
    "MANAGER AFG":    {"pwd": hashlib.sha256(b"manager2025").hexdigest(),   "role": "Manager",        "nom": "Directeur Commercial", "init": "DCO", "code": "DCO001"},
    "ACTUAIRE AFG":   {"pwd": hashlib.sha256(b"actuaire2025").hexdigest(),  "role": "Actuaire",       "nom": "Actuaire Principal",   "init": "ACT", "code": "ACT001"},
    "DEMO VISITEUR":  {"pwd": hashlib.sha256(b"demo").hexdigest(),          "role": "Visiteur",       "nom": "Visiteur Démo",        "init": "DEM", "code": "DEM001"},
}

ROLE_COLORS = {
    "Direction":"role-admin","Administrateur":"role-admin",
    "Manager":"role-manager","Actuaire":"role-manager",
    "Commercial":"role-commercial","Visiteur":"role-visiteur",
}

def get_db_conn():
    """Alias de gc() pour compatibilité"""
    return gc()

def load_direction_users():
    """Charge les comptes direction depuis la BD (table users_direction)"""
    try:
        c = get_db_conn()
        c.execute("""CREATE TABLE IF NOT EXISTS users_direction(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identifiant TEXT UNIQUE,
            pwd_hash TEXT,
            role TEXT DEFAULT 'Direction',
            nom TEXT,
            init TEXT,
            code TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        c.commit()
        df = pd.read_sql("SELECT * FROM users_direction", c)
        c.close()
        users = {}
        for _, r in df.iterrows():
            users[str(r['identifiant']).upper()] = {
                "pwd": r['pwd_hash'],
                "role": r['role'],
                "nom": r['nom'],
                "init": r['init'],
                "code": r['code'],
            }
        # Fusionner avec les defaults si vide
        if not users:
            users = {k.upper(): v for k,v in DIRECTION_USERS_DEFAULT.items()}
            # Sauvegarder en BD
            c2 = get_db_conn()
            for ident, u in DIRECTION_USERS_DEFAULT.items():
                try:
                    c2.execute("INSERT OR IGNORE INTO users_direction(identifiant,pwd_hash,role,nom,init,code) VALUES(?,?,?,?,?,?)",
                        (ident.upper(), u['pwd'], u['role'], u['nom'], u['init'], u['code']))
                except Exception: pass
            c2.commit(); c2.close()
        return users
    except Exception:
        return {k.upper(): v for k,v in DIRECTION_USERS_DEFAULT.items()}

def ck(identifiant: str, password: str):
    """Authentifie un utilisateur (direction OU commercial)"""
    ident = identifiant.strip().upper()
    pwd_h = hashlib.sha256(password.encode()).hexdigest()

    # 1) Vérifier dans les comptes direction (BD)
    dir_users = load_direction_users()
    if ident in dir_users and dir_users[ident]["pwd"] == pwd_h:
        return dir_users[ident]

    # 2) Vérifier dans les commerciaux (NOM PRÉNOM en majuscules = identifiant, code = mot de passe)
    try:
        c = get_db_conn()
        cur = c.cursor()
        cur.execute("SELECT nom, prenom, code_agent, agence, telephone, email FROM commerciaux WHERE UPPER(nom||' '||prenom)=? AND code_agent=?",
                    (ident, password.strip()))
        row = cur.fetchone()
        c.close()
        if row:
            nom, prenom, code, agence, tel, email = row
            return {
                "role": "Commercial",
                "nom": f"{nom} {prenom}",
                "init": (nom[:1] + prenom[:1]).upper(),
                "code": code,
                "agence": agence or "",
                "telephone": tel or "",
                "email": email or "",
                "pwd": pwd_h,  # factice, non utilisé
            }
    except Exception:
        pass

    # 3) Vérifier dans le PORTEFEUILLE EXCEL (vrais commerciaux AFG) :
    #    identifiant = NOM_APP (nom apporteur, en MAJUSCULES)
    #    mot de passe = CODEAPPO (code apporteur)
    try:
        idx = get_apporteurs_index()  # {CODEAPPO_upper: NOM_APP}
        code_in = password.strip().upper()
        if code_in in idx:
            nom_app = idx[code_in] or ""
            # On accepte si l'identifiant saisi correspond au nom apporteur,
            # ou si le commercial saisit directement son code dans les 2 champs.
            if (nom_app and ident == nom_app.strip().upper()) or (ident == code_in):
                # Initiales depuis le nom apporteur
                parts = [p for p in nom_app.split() if p]
                init = "".join(p[:1] for p in parts[:2]).upper() or code_in[:3]
                return {
                    "role": "Commercial",
                    "nom": nom_app or code_in,
                    "init": init,
                    "code": code_in,           # code apporteur = code agent
                    "agence": "",
                    "telephone": "",
                    "email": "",
                    "pwd": pwd_h,
                }
    except Exception:
        pass

    return None

CREDS_DEMO = [
    ("PDG AFG",       "pdg2025AFG",    "👑 PDG — Accès total"),
    ("DG AFG",        "dg2025AFG",     "📊 Dir. Général — Accès total"),
    ("ADMIN AFG",     "admin2025AFG",  "⚙️ Admin — Accès total"),
    ("MANAGER AFG",   "manager2025",   "🏆 Manager — Tableau de bord"),
    ("ACTUAIRE AFG",  "actuaire2025",  "📐 Actuaire — Risques"),
    ("DEMO VISITEUR", "demo",          "👁️ Visiteur — Lecture seule"),
    ("NOM_APP",       "CODEAPPO",      "👤 Commercial — Nom apporteur / Code apporteur (ex base)"),
]


# ── SESSION ───────────────────────────────────────────────────────────────────
for k,v in [("auth",False),("user",None),("bia_prod",None),("contrat_auth",False),("contrat_user",None)]:
    if k not in st.session_state: st.session_state[k]=v

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body,[class*="css"]{font-family:'Inter',sans-serif!important;background:#EEF2F8;}
#MainMenu,footer,header,.stDeployButton,
[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stStatusWidget"]{display:none!important}
.stApp,.stApp>div,[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"]>section,
.block-container,.stMainBlockContainer,[data-testid="stMainBlockContainer"]{
  padding-top:0!important;margin-top:0!important;max-width:100%!important;background:#EEF2F8;}
section[data-testid="stSidebar"]{
  background:linear-gradient(180deg,#003366 0%,#001F4D 100%)!important;
  border-right:3px solid #C9A227!important;}
section[data-testid="stSidebar"] *{color:white!important;}
section[data-testid="stSidebar"] .stSelectbox>div>div{
  background:rgba(255,255,255,0.08)!important;
  border:1px solid rgba(201,162,39,0.35)!important;border-radius:8px;}
section[data-testid="stSidebar"] .stRadio>div{gap:3px;}
section[data-testid="stSidebar"] .stRadio label{
  background:rgba(255,255,255,0.06);border:1px solid rgba(201,162,39,0.2);
  border-radius:8px;padding:8px 12px!important;margin:2px 0;width:100%;
  cursor:pointer;transition:all .15s;font-size:12px!important;}
section[data-testid="stSidebar"] .stRadio label:hover{
  background:rgba(201,162,39,0.18)!important;border-color:#C9A227!important;}
section[data-testid="stSidebar"] hr{border-color:rgba(201,162,39,0.2)!important;margin:10px 0;}
section[data-testid="stSidebar"] .stButton>button{
  background:rgba(201,162,39,0.15)!important;border:1px solid #C9A227!important;
  color:#E8C84A!important;border-radius:8px!important;font-weight:700!important;width:100%;}
section[data-testid="stSidebar"] .stButton>button:hover{background:#C9A227!important;color:#003366!important;}
section[data-testid="stSidebar"] hr{border-color:rgba(201,162,39,0.2)!important;margin:10px 0;}
.afg-topbar{background:linear-gradient(135deg,#003366 0%,#004D99 55%,#005BAD 100%);
  padding:0.85rem 1.6rem;border-bottom:3px solid #C9A227;
  display:flex;align-items:center;justify-content:space-between;
  box-shadow:0 4px 18px rgba(0,0,0,0.22);}
.afg-topbar-left{display:flex;align-items:center;gap:14px;}
.afg-topbar-right{text-align:right;}
.period-pill{background:#C9A227;color:#003366;padding:3px 13px;border-radius:20px;
  font-size:11px;font-weight:800;display:inline-block;margin-bottom:3px;}
.user-info{font-size:11px;color:rgba(255,255,255,0.65);}
.afg-brand h1{color:white;font-size:1.2rem;font-weight:900;margin:0;}
.afg-brand p{color:rgba(255,255,255,0.6);font-size:10px;margin:2px 0 0;}
.role-badge{padding:2px 8px;border-radius:4px;font-size:9.5px;font-weight:800;
  letter-spacing:.06em;display:inline-block;margin-left:5px;}
.role-admin{background:#C9A227;color:#003366;}
.role-manager{background:#0A7B6C;color:white;}
.role-commercial{background:#0072CE;color:white;}
.role-visiteur{background:#5A6478;color:white;}
.breadcrumb{background:#F4F6FA;padding:5px 1.6rem;font-size:11px;color:#5A6478;
  border-bottom:1px solid #DDE3EE;display:flex;align-items:center;gap:5px;}
.bc-active{color:#003366;font-weight:700;}
.kpi-card{background:white;border-radius:12px;padding:1rem 1.2rem 0.8rem;
  border-left:4px solid #0072CE;
  box-shadow:0 1px 4px rgba(0,51,102,0.07),0 4px 14px rgba(0,51,102,0.04);
  transition:transform .16s,box-shadow .16s;}
.kpi-card:hover{transform:translateY(-2px);box-shadow:0 6px 20px rgba(0,51,102,0.12);}
.kpi-card.gold{border-left-color:#C9A227;}.kpi-card.green{border-left-color:#1A7A4A;}
.kpi-card.red{border-left-color:#C0392B;}.kpi-card.teal{border-left-color:#0A7B6C;}
.kpi-card.amber{border-left-color:#D35400;}
.kpi-icon{font-size:1.35rem;margin-bottom:4px;display:block;}
.kpi-label{font-size:9px;font-weight:700;color:#5A6478;text-transform:uppercase;
  letter-spacing:.09em;margin-bottom:3px;}
.kpi-value{font-size:1.45rem;font-weight:900;color:#003366;line-height:1;margin-bottom:3px;}
.kpi-sub{font-size:10.5px;color:#5A6478;}
.section-title{font-size:13px;font-weight:700;color:#003366;
  border-bottom:2px solid #C9A227;padding-bottom:5px;
  margin:1.2rem 0 0.7rem;display:flex;align-items:center;gap:8px;}
.stag{background:#C9A227;color:#003366;font-size:9px;font-weight:800;
  padding:1px 7px;border-radius:4px;letter-spacing:.05em;}
.al{border-radius:8px;padding:8px 12px;font-size:12px;border-left:4px solid;
  display:flex;align-items:flex-start;gap:8px;margin-bottom:6px;}
.al-warn{background:#FFF8E1;border-color:#D35400;color:#7B3C00;}
.al-info{background:#E8F4FF;border-color:#0072CE;color:#003366;}
.al-good{background:#E8F8EE;border-color:#1A7A4A;color:#0D4A2A;}
.al-danger{background:#FDECEA;border-color:#C0392B;color:#7B1414;}
.stButton>button{background:#003366!important;color:white!important;border:none!important;
  border-radius:8px!important;font-weight:700!important;font-size:12px!important;
  padding:8px 16px!important;}
.stButton>button:hover{background:#004D99!important;}
.stDownloadButton>button{background:#1A7A4A!important;color:white!important;
  border:none!important;border-radius:8px!important;font-weight:700!important;}
.stTextInput>div>input,.stSelectbox>div>div,.stNumberInput>div>div>input,
.stDateInput>div>input,.stTextArea textarea{
  border:1.5px solid #DDE3EE!important;border-radius:8px!important;font-size:12px!important;}
.stTabs [data-baseweb="tab-list"]{background:white!important;border-radius:8px 8px 0 0!important;
  border-bottom:2px solid #DDE3EE!important;gap:0!important;}
.stTabs [data-baseweb="tab"]{font-weight:700!important;font-size:12px!important;
  color:#5A6478!important;padding:9px 15px!important;border-bottom:3px solid transparent!important;
  border-radius:8px 8px 0 0!important;}
.stTabs [aria-selected="true"]{color:#003366!important;border-bottom-color:#C9A227!important;
  background:rgba(201,162,39,0.06)!important;}
[data-testid="stDataFrame"]{border-radius:10px!important;border:1px solid #DDE3EE!important;overflow:hidden!important;}
::-webkit-scrollbar{width:5px;height:5px;}
::-webkit-scrollbar-thumb{background:#DDE3EE;border-radius:3px;}
.podium-card{border-radius:12px 12px 0 0;padding:1.1rem 0.6rem 0.8rem;text-align:center;}
.p1{background:linear-gradient(160deg,#FFFBE6,#FFD700);border:2px solid #DAA520;min-height:140px;}
.p2{background:linear-gradient(160deg,#F5F5F5,#C0C0C0);border:2px solid #A8A8A8;min-height:110px;}
.p3{background:linear-gradient(160deg,#FDF0E0,#CD9E6A);border:2px solid #B8860B;min-height:95px;}
.pod-base{background:linear-gradient(135deg,#003366,#004D99);height:10px;border-radius:0 0 6px 6px;margin:0 6px;}
.score-row{display:flex;align-items:center;gap:9px;padding:5px 0;border-bottom:1px solid #F4F6FA;}
.score-track{flex:1;background:#F4F6FA;border-radius:7px;height:12px;overflow:hidden;}
.score-fill{height:100%;border-radius:7px;}
.score-val{font-size:11.5px;font-weight:700;min-width:32px;text-align:right;}
.bia-fhdr{background:linear-gradient(135deg,#003366,#004D99);border-radius:12px 12px 0 0;
  padding:1.2rem 1.6rem;border-bottom:3px solid #C9A227;
  display:flex;align-items:center;justify-content:space-between;}
.bia-sec{border:1.5px solid #DDE3EE;border-radius:10px;padding:0.9rem 1.1rem;
  margin-bottom:0.9rem;background:#F4F6FA;}
.bia-lbl{font-size:10px;font-weight:800;color:white;background:#003366;
  display:inline-block;padding:2px 12px;border-radius:20px;
  margin-bottom:10px;letter-spacing:1px;text-transform:uppercase;}
.prod-card{background:white;border-radius:10px;padding:0.9rem 1.1rem;
  border-left:4px solid #C9A227;box-shadow:0 1px 4px rgba(0,51,102,0.06);margin-bottom:7px;}
.prod-code{background:#003366;color:#C9A227;border-radius:5px;
  padding:2px 7px;font-size:9px;font-weight:900;letter-spacing:.06em;}
.afg-footer{background:#003366;color:rgba(255,255,255,.45);
  text-align:center;font-size:10px;padding:12px 2rem;
  border-top:3px solid #C9A227;
  display:flex;align-items:center;justify-content:center;gap:12px;flex-wrap:wrap;}
.afg-footer strong{color:#C9A227;}
.fd{color:rgba(201,162,39,.3);}
.year-selector{background:linear-gradient(135deg,#003366,#001F4D);
  border-radius:10px;padding:8px 14px;margin-bottom:12px;
  border:1px solid rgba(201,162,39,0.3);display:flex;align-items:center;gap:12px;}
.sig-box{border:2px dashed #DDE3EE;border-radius:8px;padding:12px;
  text-align:center;color:#5A6478;font-size:12px;margin-bottom:6px;}
.sig-req{border-color:#C0392B;}
.groupe-badge{display:inline-block;padding:2px 9px;border-radius:6px;
  font-size:9.5px;font-weight:800;letter-spacing:.04em;margin-left:6px;}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# SESSION STATE — INITIALISATION DE TOUTES LES CLÉS
# ═══════════════════════════════════════════════════════════════════════════
_defaults = {
    "auth": False,
    "user": {},
    "bia_prod": None,
    "bia_ass_meme": True,
    "bia_mode_rg": "",
    "contrat_auth": False,
    "contrat_user": None,
    "portefeuille_ext": None,
    "pf_loaded_from_cache": False,  # flag pour affichage info
}
for _k, _v in _defaults.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Auto-chargement depuis le CACHE DISQUE (survit aux déconnexions) ─────────
# Le portefeuille reste chargé tant que l'utilisateur ne le supprime pas
# explicitement depuis l'interface.
if st.session_state.get("portefeuille_ext") is None:
    try:
        _df_auto = load_portefeuille_auto()   # lit le pickle disque
        if _df_auto is not None and len(_df_auto) > 0:
            st.session_state["portefeuille_ext"] = _df_auto
            st.session_state["pf_loaded_from_cache"] = True
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════════════
# PAGE LOGIN
# ═══════════════════════════════════════════════════════════════════════════
if not st.session_state.auth:
    h=datetime.now().hour
    salut="Bonsoir" if h>=18 else ("Bonjour" if h<12 else "Bon après-midi")

    cL,cR=st.columns([1.05,1])
    with cL:
        st.markdown(
            "<div style='background:linear-gradient(160deg,#003366,#004D99);"
            "border-radius:18px 0 0 18px;padding:2.6rem 2.2rem;min-height:620px;"
            "border-right:3px solid #C9A227;"
            "display:flex;flex-direction:column;justify-content:space-between;'>"
            "<div>"
            "<div style='display:flex;align-items:center;gap:14px;margin-bottom:1.4rem;'>"
            "<div style='width:62px;height:62px;background:linear-gradient(135deg,#C9A227,#E8C84A);"
            "border-radius:13px;display:flex;align-items:center;justify-content:center;"
            "font-size:11px;font-weight:900;color:#003366;line-height:1.2;text-align:center;"
            "box-shadow:0 8px 24px rgba(201,162,39,0.45);flex-shrink:0;'>AFG<br>VIE</div>"
            "<div><div style='color:white;font-size:1.2rem;font-weight:900;line-height:1.2;'>"
            "AFG Assurances<br>Bénin Vie</div>"
            "<div style='color:#E8C84A;font-size:9px;font-weight:600;letter-spacing:1.2px;margin-top:3px;'>"
            "GROUPE AFG HOLDING · CIMA</div></div></div>"
            "<p style='color:rgba(255,255,255,.75);font-size:12px;line-height:1.85;margin-bottom:1.3rem;'>"
            "<b style='color:#E8C84A;'>À AFG Assurances Bénin Vie,<br>nous avons pensé à vous !</b><br><br>"
            "Protégez votre avenir et celui de vos proches.<br>"
            "Agréée CIMA depuis 1994 — Groupe AFG Holding.</p>"
            "<div style='display:grid;grid-template-columns:1fr 1fr;gap:8px;'>"
            +"".join([
                "<div style='background:rgba(255,255,255,.07);border:1px solid rgba(201,162,39,.25);"
                "border-radius:10px;padding:10px;text-align:center;'>"
                "<div style='font-size:1.35rem;font-weight:900;color:#C9A227;'>"+n+"</div>"
                "<div style='font-size:8.5px;color:rgba(255,255,255,.5);text-transform:uppercase;letter-spacing:.06em;'>"+l+"</div></div>"
                for n,l in [("18","Produits CIMA"),("3","Groupes"),("30+","Ans exp."),("TOP3","Assureurs")]
            ])
            +"</div></div>"
            "<div style='font-size:9px;color:rgba(255,255,255,.3);margin-top:1.5rem;line-height:1.75;'>"
            "© 2025 AFG Assurances Bénin Vie · Système v22.0<br>"
            "04 BP 0851 · Cadjèhoun · Cotonou, Bénin<br>"
            "Données confidentielles — Accès restreint</div>"
            "</div>",
            unsafe_allow_html=True)

    with cR:
        st.markdown(
            "<div style='background:white;border-radius:0 18px 18px 0;"
            "padding:2rem 2rem 1.5rem;min-height:620px;'>",
            unsafe_allow_html=True)

        # ── 2 ONGLETS : SE CONNECTER / CRÉER UN COMPTE ───────────────────────
        tab_login, tab_create = st.tabs(["🔐 Se connecter", "✏️ Créer un compte"])

        # ── ONGLET 1 : CONNEXION ─────────────────────────────────────────────
        with tab_login:
            st.markdown(
                f"<div style='font-size:1.1rem;font-weight:900;color:#003366;margin:0.8rem 0 0.3rem;'>"
                f"🔐 Connexion sécurisée</div>"
                f"<div style='font-size:12px;color:#5A6478;margin-bottom:1rem;'>"
                f"{salut} ! Entrez vos identifiants AFG.</div>",
                unsafe_allow_html=True)

            with st.form("login_v13", clear_on_submit=False):
                st.markdown(
                    "<div style='background:#F0F4FF;border-radius:8px;padding:10px 13px;"
                    "margin-bottom:12px;border-left:3px solid #0072CE;font-size:11.5px;color:#003366;'>"
                    "<b>👤 Commerciaux (apporteurs AFG) :</b> Identifiant = <b>NOM_APP</b> "
                    "(nom apporteur en MAJUSCULES, ex : <i>GNANCADJA LÉOPOLD</i>) "
                    "· Mot de passe = <b>CODEAPPO</b> (code apporteur, ex : <i>2000</i>).<br>"
                    "Astuce : vous pouvez aussi saisir votre <b>code apporteur</b> dans les deux champs.<br>"
                    "<b>🏢 Direction / Admin :</b> Identifiant = nom du compte · Mot de passe = votre mot de passe.</div>",
                    unsafe_allow_html=True)
                lu = st.text_input("👤  Identifiant", placeholder="Ex : GNANCADJA LÉOPOLD  ou  PDG AFG", key="lu13")
                lp = st.text_input("🔑  Mot de passe", type="password", placeholder="Votre mot de passe", key="lp13")
                sub = st.form_submit_button("🔐  ACCÉDER AU SYSTÈME  ▶", use_container_width=True)
                if sub:
                    _lu_v = lu.strip()
                    _lp_v = lp.strip()
                    if not _lu_v or not _lp_v:
                        st.error("⚠️ Veuillez remplir les deux champs.")
                    elif _lp_v.isdigit() and len(_lp_v) < 4:
                        # Code numérique = code apporteur commercial → min 4 chiffres
                        st.error("⚠️ Code apporteur trop court — minimum 4 chiffres requis.")
                    else:
                        u_res = ck(_lu_v, _lp_v)
                        if u_res:
                            st.session_state.auth = True
                            st.session_state.user = u_res
                            st.rerun()
                        else:
                            st.error(
                                "❌ Identifiants incorrects. "
                                "Commerciaux : vérifiez votre nom exact (NOM_APP) et votre code (CODEAPPO min 4 chiffres). "
                                "Direction / Admin : vérifiez votre identifiant et mot de passe.")

            # Identifiants direction affichés (pas les commerciaux — confidentiels)
            with st.expander("🔑 Identifiants direction (démo)", expanded=False):
                st.markdown(
                    "<div style='background:linear-gradient(135deg,#003366,#001F4D);"
                    "border-radius:10px;padding:1rem 1.2rem;"
                    "border:1px solid rgba(201,162,39,0.4);'>"
                    "<div style='color:#E8C84A;font-size:10.5px;font-weight:800;"
                    "text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;'>"
                    "🔑 Identifiants de connexion</div>"
                    + "".join([
                        "<div style='display:flex;align-items:center;gap:6px;"
                        "padding:4px 0;border-bottom:1px solid rgba(201,162,39,0.12);'>"
                        "<code style='background:#C9A227;color:#003366;border-radius:4px;"
                        "padding:1px 7px;font-size:9.5px;font-weight:900;font-family:monospace;"
                        "min-width:90px;text-align:center;display:inline-block;'>" + u + "</code>"
                        "<span style='color:rgba(201,162,39,0.5);'>→</span>"
                        "<code style='background:rgba(255,255,255,0.12);color:#E8C84A;"
                        "border-radius:4px;padding:1px 7px;font-size:9.5px;font-weight:700;"
                        "font-family:monospace;min-width:80px;text-align:center;display:inline-block;'>" + p + "</code>"
                        "<span style='font-size:9.5px;color:rgba(255,255,255,0.55);flex:1;'>" + r + "</span>"
                        "</div>"
                        for u, p, r in CREDS_DEMO
                    ])
                    + "</div>",
                    unsafe_allow_html=True)

        # ── ONGLET 2 : CRÉER UN COMPTE ────────────────────────────────────────
        with tab_create:
            st.markdown(
                "<div style='font-size:1.1rem;font-weight:900;color:#003366;margin:0.8rem 0 0.3rem;'>"
                "✏️ Créer un compte Direction / Admin</div>"
                "<div style='background:#FFF8E1;border-left:3px solid #D35400;border-radius:0 8px 8px 0;"
                "padding:8px 12px;font-size:11.5px;color:#7B3C00;margin-bottom:12px;'>"
                "⚠️ <b>Réservé à la direction et l'administration AFG.</b><br>"
                "Les agents commerciaux se connectent directement avec NOM PRÉNOM + code agent.</div>",
                unsafe_allow_html=True)

            with st.form("create_account_form", clear_on_submit=True):
                st.markdown(
                    "<div style='background:#E8F4FF;border-radius:8px;padding:9px 13px;"
                    "border-left:3px solid #0072CE;font-size:11.5px;color:#003366;margin-bottom:12px;'>"
                    "<b>ℹ️ Simple et rapide :</b> Choisissez un identifiant unique et un mot de passe sécurisé.</div>",
                    unsafe_allow_html=True)
                new_ident = st.text_input(
                    "👤 Identifiant *",
                    placeholder="Ex : DIRECTEUR COMMERCIAL ou DG KOUAMÉ",
                    key="new_ident",
                    help="En majuscules de préférence. Doit être unique dans le système.")
                new_pwd   = st.text_input(
                    "🔑 Mot de passe *",
                    type="password",
                    placeholder="Minimum 6 caractères",
                    key="new_pwd")
                new_pwd2  = st.text_input(
                    "🔑 Confirmer le mot de passe *",
                    type="password",
                    placeholder="Répétez exactement votre mot de passe",
                    key="new_pwd2")
                st.markdown(
                    "<div style='background:#FFF8E1;border-radius:6px;padding:7px 10px;"
                    "font-size:10.5px;color:#7B3C00;margin-top:4px;'>"
                    "🔒 Votre compte sera créé avec le rôle <b>Direction</b>. "
                    "Contactez l'administrateur AFG pour modifier votre rôle.</div>",
                    unsafe_allow_html=True)
                btn_create = st.form_submit_button("✅  CRÉER MON COMPTE  ▶▶", use_container_width=True)

                if btn_create:
                    errs_cr = []
                    if not new_ident.strip():
                        errs_cr.append("Identifiant obligatoire")
                    if len(new_pwd) < 6:
                        errs_cr.append("Mot de passe trop court (minimum 6 caractères)")
                    if new_pwd != new_pwd2:
                        errs_cr.append("Les deux mots de passe ne correspondent pas")
                    if errs_cr:
                        for e in errs_cr: st.error(f"❌ {e}")
                    else:
                        try:
                            c_cr = gc()
                            c_cr.execute("""CREATE TABLE IF NOT EXISTS users_direction(
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                identifiant TEXT UNIQUE,
                                pwd_hash TEXT,
                                role TEXT DEFAULT 'Direction',
                                nom TEXT, init TEXT, code TEXT,
                                created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
                            pwd_h_cr = hashlib.sha256(new_pwd.encode()).hexdigest()
                            ident_up  = new_ident.strip().upper()
                            init_cr   = "".join(w[:1] for w in ident_up.split()[:2])
                            code_cr   = f"USR{str(abs(hash(ident_up)))[:4]}"
                            c_cr.execute(
                                "INSERT OR IGNORE INTO users_direction(identifiant,pwd_hash,role,nom,init,code) VALUES(?,?,?,?,?,?)",
                                (ident_up, pwd_h_cr, "Direction", ident_up, init_cr, code_cr))
                            if c_cr.total_changes == 0:
                                st.error("❌ Cet identifiant existe déjà. Choisissez-en un autre.")
                            else:
                                c_cr.commit()
                                st.success(f"🎉 Compte créé avec succès ! Connectez-vous avec : **{ident_up}**")
                            c_cr.close()
                        except Exception as e_cr:
                            st.error(f"❌ Erreur création : {str(e_cr)}")

        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ═══════════════════════════════════════════════════════════════════════════
# BASE DE DONNÉES — INITIALISATION
# ═══════════════════════════════════════════════════════════════════════════
# DB_DIR, DB et gc() sont définis plus haut (avant auth)

def init_db():
    c=gc()
    c.executescript("""
    PRAGMA foreign_keys=ON;
    CREATE TABLE IF NOT EXISTS commerciaux(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      nom TEXT,prenom TEXT,code_agent TEXT UNIQUE,
      agence TEXT,region TEXT,date_embauche DATE,
      objectif_mensuel REAL DEFAULT 5000000,
      telephone TEXT,email TEXT,statut TEXT DEFAULT 'actif');

    CREATE TABLE IF NOT EXISTS produits(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      code TEXT UNIQUE,nom TEXT,categorie TEXT,groupe TEXT,
      prime_min REAL DEFAULT 1,prime_max REAL DEFAULT 999999999,
      duree_min INTEGER DEFAULT 1,duree_max INTEGER DEFAULT 40,
      description TEXT,actif INTEGER DEFAULT 1);

    CREATE TABLE IF NOT EXISTS clients(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      code_client TEXT UNIQUE,nom TEXT,prenom TEXT,
      date_naissance DATE,sexe TEXT,telephone TEXT,
      email TEXT,adresse TEXT,ville TEXT,
      profession TEXT,revenu_mensuel REAL,
      date_creation DATE DEFAULT CURRENT_DATE);

    CREATE TABLE IF NOT EXISTS contrats(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      numero_contrat TEXT UNIQUE,date_souscription DATE,
      commercial_id INTEGER,client_id INTEGER,produit_id INTEGER,
      prime_annuelle REAL DEFAULT 0,prime_unique REAL DEFAULT 0,
      duree_ans INTEGER,statut TEXT DEFAULT 'actif',
      capital_assure REAL DEFAULT 0,date_echeance DATE,
      notes TEXT,saisi_par TEXT,
      FOREIGN KEY(commercial_id) REFERENCES commerciaux(id),
      FOREIGN KEY(client_id) REFERENCES clients(id),
      FOREIGN KEY(produit_id) REFERENCES produits(id));

    CREATE TABLE IF NOT EXISTS sinistres(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      contrat_id INTEGER,date_sinistre DATE,
      type_sinistre TEXT,montant_reclame REAL,
      montant_regle REAL DEFAULT 0,
      statut TEXT DEFAULT 'en_cours',
      date_declaration DATE DEFAULT CURRENT_DATE,
      FOREIGN KEY(contrat_id) REFERENCES contrats(id));

    CREATE TABLE IF NOT EXISTS bulletins_bia(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      numero_bia TEXT UNIQUE NOT NULL,
      date_saisie DATE DEFAULT CURRENT_DATE,
      saisi_par TEXT, agence_saisie TEXT,
      code_apporteur TEXT, nom_apporteur TEXT, realisateur TEXT,
      type_contrat TEXT, code_produit TEXT, groupe_produit TEXT,
      deja_assure TEXT DEFAULT 'Non', num_contrat_existant TEXT,
      -- SOUSCRIPTEUR
      contractant_titre TEXT, contractant_nom TEXT, contractant_prenom TEXT,
      contractant_ddn DATE, contractant_lieu_naissance TEXT,
      contractant_nationalite TEXT, contractant_situation_mat TEXT,
      contractant_profession TEXT, contractant_adresse TEXT,
      contractant_bp TEXT, contractant_email TEXT,
      contractant_whatsapp TEXT, contractant_tel_fixe TEXT,
      contractant_tel_cel TEXT, contractant_npi TEXT,
      -- ASSURÉ
      assure_meme INTEGER DEFAULT 1,
      assure_titre TEXT, assure_nom TEXT, assure_prenom TEXT,
      assure_ddn DATE, assure_lieu_naissance TEXT,
      assure_nationalite TEXT, assure_situation_mat TEXT,
      assure_profession TEXT, assure_adresse TEXT,
      assure_bp TEXT, assure_email TEXT,
      assure_whatsapp TEXT, assure_tel_fixe TEXT,
      assure_tel_cel TEXT, assure_npi TEXT,
      -- CARACTÉRISTIQUES
      cotisation_fcfa REAL DEFAULT 0,
      cotisation_lettres TEXT,
      periodicite TEXT DEFAULT 'Mensuelle',
      mode_reglement TEXT,
      mode_ref_numero TEXT,
      date_effet DATE, duree_ans INTEGER, terme DATE,
      option_garantie TEXT,
      capital_terme REAL DEFAULT 0,
      -- BÉNÉFICIAIRES
      benef_vie TEXT, benef_deces TEXT, benef_autres TEXT,
      -- INVESTISSEMENT (Dokountché)
      inv_repartition TEXT, inv_fg_pct INTEGER DEFAULT 0,
      inv_uc_pct INTEGER DEFAULT 0, inv_fonds TEXT,
      -- QUESTIONNAIRE MÉDICAL
      med_taille TEXT, med_poids TEXT, med_perte_poids TEXT,
      med_q1 TEXT, med_q1_detail TEXT,
      med_q2 TEXT, med_q2_detail TEXT,
      med_q3 TEXT, med_q3_detail TEXT,
      med_q4 TEXT, med_q4_detail TEXT,
      med_q5 TEXT, med_q5_detail TEXT,
      med_q6 TEXT, med_q6_detail TEXT, med_q6_nature TEXT, med_q6_motif TEXT,
      med_q7 TEXT, med_q7_detail TEXT,
      -- DÉCLARATION
      decl_accept_conditions INTEGER DEFAULT 0,
      decl_accept_donnees INTEGER DEFAULT 0,
      -- AUTORISATION DE PRÉLÈVEMENT
      prel_nom_debiteur TEXT, prel_adresse_debiteur TEXT,
      prel_banque_debit TEXT, prel_code_inter_debit TEXT,
      prel_code_guichet_debit TEXT, prel_num_compte_debit TEXT,
      prel_cle_debit TEXT,
      prel_banque_credit TEXT, prel_code_inter_credit TEXT,
      prel_code_guichet_credit TEXT, prel_num_compte_credit TEXT,
      prel_cle_credit TEXT,
      prel_montant TEXT, prel_frequence TEXT,
      prel_effet TEXT, prel_echeance TEXT,
      -- SIGNATURES (BLOB)
      sig_souscripteur BLOB, sig_assure BLOB, sig_conseiller BLOB,
      sig_souscripteur_nom TEXT, sig_assure_nom TEXT, sig_conseiller_nom TEXT,
      -- ADMIN
      statut_bia TEXT DEFAULT 'En cours',
      observations TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS users_direction(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      identifiant TEXT UNIQUE,
      pwd_hash TEXT,
      role TEXT DEFAULT 'Direction',
      nom TEXT, init TEXT, code TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
    """)
    c.commit()

    cur=c.cursor()
    cur.execute("SELECT COUNT(*) FROM produits")
    if cur.fetchone()[0]==0:
        cats={
            "Prévoyance":{"min":1,"max":999999999,"dmin":1,"dmax":30},
            "Crédit":    {"min":1,"max":999999999,"dmin":1,"dmax":25},
            "Épargne":   {"min":1,"max":999999999,"dmin":1,"dmax":30},
            "Retraite":  {"min":1,"max":999999999,"dmin":1,"dmax":35},
            "Capitalisation":{"min":1,"max":999999999,"dmin":1,"dmax":30},
        }
        pdata=[]
        for code,nom,cat in PRODUITS_FR:
            d=cats.get(cat,cats["Épargne"])
            grp=get_groupe(code)
            pdata.append((code,nom,cat,grp,d["min"],d["max"],d["dmin"],d["dmax"],f"Produit {cat.lower()} — {nom}"))
        cur.executemany(
            "INSERT INTO produits(code,nom,categorie,groupe,prime_min,prime_max,duree_min,duree_max,description) VALUES(?,?,?,?,?,?,?,?,?)",
            pdata)
        c.commit()

    cur.execute("SELECT COUNT(*) FROM commerciaux")
    if cur.fetchone()[0]==0:
        random.seed(42); np.random.seed(42)
        agents=[
            ('ADJOVI','Paul','AFG001','Agence Cotonou Centre','Littoral','2021-06-15',8000000,'+22996001111','p.adjovi@afg.bj'),
            ('KOUASSI','Jean','AFG002','Agence Cotonou Littoral','Littoral','2021-09-20',7500000,'+22996002222','j.kouassi@afg.bj'),
            ('SOW','Fatou','AFG003','Agence Porto-Novo','Ouémé','2022-01-10',6500000,'+22996003333','f.sow@afg.bj'),
            ('TOURE','Amadou','AFG004','Agence Parakou','Borgou','2022-03-05',6000000,'+22996004444','a.toure@afg.bj'),
            ('TRAORE','Aminata','AFG005','Agence Abomey-Calavi','Atlantique','2022-05-12',6800000,'+22996005555','a.traore@afg.bj'),
            ('KONE','Ibrahim','AFG006','Agence Cotonou Centre','Littoral','2022-08-18',7200000,'+22996006666','i.kone@afg.bj'),
            ('OUATTARA','Mariam','AFG007','Agence Bohicon','Zou','2022-10-22',5500000,'+22996007777','m.ouattara@afg.bj'),
            ('SANGARE','Ousmane','AFG008','Agence Natitingou','Atacora','2023-01-30',5000000,'+22996008888','o.sangare@afg.bj'),
            ('CAMARA','Aissata','AFG009','Agence Cotonou Littoral','Littoral','2023-03-14',7000000,'+22996009999','a.camara@afg.bj'),
            ('DOSSOU','Romain','AFG010','Agence Porto-Novo','Ouémé','2023-05-01',6200000,'+22996010000','r.dossou@afg.bj'),
            ('HOUNKPE','Clarisse','AFG011','Agence Parakou','Borgou','2023-07-10',5800000,'+22996011111','c.hounkpe@afg.bj'),
            ('DIALLO','Moussa','AFG012','Agence Abomey-Calavi','Atlantique','2023-09-05',6400000,'+22996012222','m.diallo@afg.bj'),
        ]
        cur.executemany(
            "INSERT INTO commerciaux(nom,prenom,code_agent,agence,region,date_embauche,objectif_mensuel,telephone,email) VALUES(?,?,?,?,?,?,?,?,?)",
            agents)
        noms_b=['ADJOVI','AGBO','AHOUNOU','AKPO','BELLO','DAKO','FAGNON','GBEDO','HOUENOU','KOFFI','KOSSOU','LOKO','MEDEHOU','SANNI','SOGLO','TANKPINOU']
        pm=['Jean','Marc','Paul','Louis','Charles','David','Emmanuel','Félix','Georges','Henri','Koffi','Luc']
        pf=['Marie','Fatima','Aïcha','Rose','Cécile','Grâce','Élise','Joëlle','Kabira','Linda','Madeleine']
        vl=['Cotonou','Porto-Novo','Parakou','Bohicon','Natitingou','Abomey-Calavi','Lokossa','Ouidah','Abomey','Kandi']
        pr2=['Fonctionnaire','Commerçant','Employé privé','Entrepreneur','Enseignant','Médecin','Ingénieur','Banquier','Agriculteur','Artisan']
        cls_=[]
        for i in range(400):
            sx=random.choice(['M','F']); nm=random.choice(noms_b); pn=random.choice(pm if sx=='M' else pf)
            dob=date(random.randint(1960,2000),random.randint(1,12),random.randint(1,28))
            cls_.append((f"CLI{str(i+1).zfill(5)}",nm,pn,dob.isoformat(),sx,
                f"+229 9{random.randint(1000000,9999999)}",f"{nm.lower()}.{pn.lower()}@email.bj",
                f"Rue {random.randint(1,600)}",random.choice(vl),random.choice(pr2),random.randint(80000,3000000)))
        cur.executemany(
            "INSERT INTO clients(code_client,nom,prenom,date_naissance,sexe,telephone,email,adresse,ville,profession,revenu_mensuel) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            cls_)
        cur.execute("SELECT id FROM commerciaux"); cids=[r[0] for r in cur.fetchall()]
        cur.execute("SELECT id,prime_min,prime_max FROM produits"); prs=cur.fetchall()
        cur.execute("SELECT id FROM clients"); clids=[r[0] for r in cur.fetchall()]
        STATS={
            2020:{"mois":[45,38,52,48,55,62,71,58,67,74,63,81]},
            2021:{"mois":[55,48,63,57,68,75,82,70,79,87,76,94]},
            2022:{"mois":[68,59,76,71,83,92,101,87,96,106,93,115]},
            2023:{"mois":[82,73,92,85,100,110,121,104,114,126,111,136]},
            2024:{"mois":[95,87,108,100,117,129,142,122,133,148,130,160]},
            2025:{"mois":[110,102,125,116,135,148,163,140,152,0,0,0]},
        }
        cts=[]
        for yr,yd in STATS.items():
            for mi,nb_m in enumerate(yd["mois"]):
                if nb_m==0: continue
                for _ in range(nb_m):
                    cid=random.choice(cids); pr_=random.choice(prs); clid=random.choice(clids)
                    pid,pmn,pmx=pr_
                    d_s=date(yr,mi+1,random.randint(1,28))
                    if random.random()<0.65:
                        pa=round(random.uniform(max(pmn,10000),max(pmx,100000))/1000)*1000; pu=0
                    else:
                        pa=0; pu=round(random.uniform(max(pmn*1.5,50000),max(pmx*2,500000))/10000)*10000
                    dur=random.choice([5,8,10,12,15,20,25,30])
                    stc=random.choices(['actif','résilié','suspendu','en attente'],weights=[65,22,8,5])[0]
                    cap=round(random.uniform(1000000,30000000)/100000)*100000
                    cts.append((f"CT{d_s.strftime('%Y%m%d')}{random.randint(10000,99999)}",
                        d_s.isoformat(),cid,clid,pid,pa,pu,dur,stc,cap,
                        (d_s+timedelta(days=dur*365)).isoformat(),"Système"))
        unique_cts={}
        for ct in cts:
            if ct[0] not in unique_cts: unique_cts[ct[0]]=ct
        try:
            cur.executemany(
                "INSERT INTO contrats(numero_contrat,date_souscription,commercial_id,client_id,produit_id,prime_annuelle,prime_unique,duree_ans,statut,capital_assure,date_echeance,saisi_par) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                list(unique_cts.values()))
        except Exception: pass
        cur.execute("SELECT id FROM contrats WHERE statut='actif' LIMIT 80"); ctids=[r[0] for r in cur.fetchall()]
        tsin=['Décès toutes causes','Invalidité totale permanente','Invalidité partielle','Hospitalisation','Rachat partiel','Décès accidentel']
        sins=[]
        for cid in ctids[:55]:
            dts=(datetime.now()-timedelta(days=random.randint(1,600))).date()
            mt=round(random.uniform(200000,8000000)/100000)*100000
            rg=round(mt*random.uniform(0,1)/100000)*100000 if random.random()>0.35 else 0
            sins.append((cid,dts.isoformat(),random.choice(tsin),mt,rg,random.choice(['réglé','en_cours','en_cours','rejeté'])))
        cur.executemany(
            "INSERT INTO sinistres(contrat_id,date_sinistre,type_sinistre,montant_reclame,montant_regle,statut) VALUES(?,?,?,?,?,?)",
            sins)
        c.commit()
    c.close()

init_db()

@st.cache_data(ttl=0)
def q(sql, params=()):
    c = gc(); df = pd.read_sql_query(sql, c, params=params); c.close(); return df

def fmt(v):
    if not v or v==0: return "—"
    if v>=1_000_000_000: return f"{v/1e9:.2f} Mrd FCFA"
    if v>=1_000_000: return f"{v/1e6:.2f} M FCFA"
    if v>=1_000: return f"{v/1e3:.0f} K FCFA"
    return f"{v:,.0f} FCFA"

def dbg(v,vp):
    if not vp or vp==0: return ""
    d_=(v-vp)/vp*100; cc="delta-up" if d_>=0 else "delta-dn"
    return f'<span class="{cc}">{"▲" if d_>=0 else "▼"} {abs(d_):.1f}%</span>'

def chl(fig,h=370,title=""):
    fig.update_layout(height=h,plot_bgcolor='white',paper_bgcolor='white',
        font=dict(family='Inter',size=12,color=NAVY),
        margin=dict(l=6,r=6,t=40 if title else 8,b=8),
        title=dict(text=title,font=dict(size=13,color=NAVY,family='Inter')) if title else None,
        legend=dict(orientation='h',y=1.05,x=0,font=dict(size=11)),
        hovermode='x unified')
    fig.update_xaxes(showgrid=False,showline=True,linecolor=MGRAY)
    fig.update_yaxes(showgrid=True,gridcolor='#EEF2F7',showline=False)
    return fig

def sth(title,tag=""):
    tg=f'<span class="stag">{tag}</span>' if tag else ""
    st.markdown(f'<div class="section-title">{title} {tg}</div>',unsafe_allow_html=True)

def kpi(label,val,sub="",color="",icon=""):
    cls=f"kpi-card {color}" if color else "kpi-card"
    ic=f"<span class='kpi-icon'>{icon}</span>" if icon else ""
    st.markdown(f"""<div class="{cls}">{ic}
    <div class="kpi-label">{label}</div>
    <div class="kpi-value">{val}</div>
    <div class="kpi-sub">{sub}</div></div>""",unsafe_allow_html=True)

def alert(msg,typ="info"):
    cls={"warn":"al-warn","info":"al-info","good":"al-good","danger":"al-danger"}[typ]
    ic={"warn":"⚠️","info":"ℹ️","good":"✅","danger":"🚨"}[typ]
    st.markdown(f'<div class="al {cls}"><span>{ic}</span><span>{msg}</span></div>',unsafe_allow_html=True)

def gen_bia():
    c=gc(); cur=c.cursor()
    cur.execute("SELECT COUNT(*) FROM bulletins_bia")
    n=cur.fetchone()[0]+1; c.close()
    return f"BIA-{datetime.now().year}-{str(n).zfill(5)}"

def img_to_blob(f):
    return f.getvalue() if f else None

def groupe_badge(code):
    g=get_groupe(str(code))
    col=GROUPE_COLORS.get(g,"#5A6478")
    ic=GROUPE_ICONS.get(g,"")
    return f"<span class='groupe-badge' style='background:{col}22;color:{col};border:1px solid {col}55;'>{ic} {g}</span>"

# ── SÉLECTEUR D'ANNÉE COMMUN (multi-sélection) ───────────────────────────────
ANNEES_DISPONIBLES = ["Toutes les années"] + [str(y) for y in range(1996, 2027)]
ANNEES_NAISSANCE   = [str(y) for y in range(1960, 2026)]

def _get_all_years_from_sources():
    """Collecte toutes les années disponibles : BD interne + portefeuille Excel."""
    years_set = set()
    # BD interne contrats
    try:
        df_yrs = pd.read_sql_query(
            "SELECT DISTINCT strftime('%Y',date_souscription) as yr FROM contrats "
            "WHERE date_souscription IS NOT NULL ORDER BY yr DESC", gc())
        for y in df_yrs['yr'].dropna():
            try: years_set.add(int(y))
            except: pass
    except Exception: pass
    # BD interne BIA
    try:
        df_bia_yrs = pd.read_sql_query(
            "SELECT DISTINCT strftime('%Y',date_saisie) as yr FROM bulletins_bia "
            "WHERE date_saisie IS NOT NULL ORDER BY yr DESC", gc())
        for y in df_bia_yrs['yr'].dropna():
            try: years_set.add(int(y))
            except: pass
    except Exception: pass
    # Portefeuille Excel chargé
    pf = st.session_state.get("portefeuille_ext", None)
    if pf is not None and "DATESOUS" in pf.columns:
        try:
            pf_years = pd.to_datetime(pf["DATESOUS"], errors="coerce").dt.year.dropna().unique()
            for y in pf_years:
                try: years_set.add(int(y))
                except: pass
        except Exception: pass
    if not years_set:
        years_set = set(range(2020, 2026))
    return sorted(years_set, reverse=True)

def year_selector(key, label="📅 Filtrer par année(s)"):
    """Sélecteur multi-années — couvre BD interne + portefeuille Excel."""
    all_years_set = [str(y) for y in _get_all_years_from_sources()]

    st.markdown(
        f"<div style='background:linear-gradient(135deg,#003366,#001F4D);border-radius:10px;"
        f"padding:7px 14px;margin-bottom:10px;border:1px solid rgba(201,162,39,0.3);"
        f"display:flex;align-items:center;gap:10px;'>"
        f"<span style='color:#E8C84A;font-size:16px;'>📅</span>"
        f"<span style='color:white;font-weight:700;font-size:12px;'>{label}</span>"
        f"</div>",
        unsafe_allow_html=True)

    col_a, col_b = st.columns([1, 3])
    with col_a:
        mode = st.radio("Mode", ["Toutes", "Choisir année(s)"], horizontal=True, key=f"{key}_mode",
                        label_visibility="collapsed")
    with col_b:
        if mode == "Choisir année(s)":
            selected = st.multiselect(
                "Sélectionner une ou plusieurs années",
                options=all_years_set,
                default=[all_years_set[0]] if all_years_set else [],
                key=f"{key}_multi",
                label_visibility="collapsed")
            return selected if selected else "Toutes les années"
        else:
            return "Toutes les années"

def filter_by_year(df, yr, date_col="date_souscription"):
    """Filtre un DataFrame selon une ou plusieurs années."""
    if yr == "Toutes les années" or yr is None:
        return df
    if date_col not in df.columns:
        return df
    years_int = []
    if isinstance(yr, list):
        for y in yr:
            try: years_int.append(int(y))
            except: pass
    else:
        try: years_int.append(int(yr))
        except: return df
    if not years_int:
        return df
    mask = pd.to_datetime(df[date_col], errors="coerce").dt.year.isin(years_int)
    return df[mask]

def filter_pf_by_year(pf, yr):
    """Filtre le portefeuille Excel par année de souscription DATESOUS."""
    if pf is None or yr == "Toutes les années" or yr is None:
        return pf
    years_int = []
    if isinstance(yr, list):
        for y in yr:
            try: years_int.append(int(y))
            except: pass
    else:
        try: years_int.append(int(yr))
        except: return pf
    if not years_int:
        return pf
    mask = pd.to_datetime(pf["DATESOUS"], errors="coerce").dt.year.isin(years_int)
    return pf[mask]

def yr_label(yr):
    """Label lisible pour l'année sélectionnée."""
    if yr == "Toutes les années" or yr is None:
        return "Toutes les années"
    if isinstance(yr, list):
        return ", ".join(sorted(yr, reverse=True)) if yr else "Toutes les années"
    return str(yr)

# ── STATS PAR PRODUIT (pour graphiques) ──────────────────────────────────────
def get_stats_produits(df):
    """Retourne stats complètes par produit avec groupe"""
    if df.empty: return pd.DataFrame()
    df2=df.copy()
    df2['eq']=df2['prime_annuelle']+df2['prime_unique']
    stats=df2.groupby(['pcode','pnom','categorie']).agg(
        nb_total=('id','count'),
        nb_actif=('id',lambda x:(df2.loc[x.index,'statut']=='actif').sum()),
        nb_resilie=('id',lambda x:(df2.loc[x.index,'statut']=='résilié').sum()),
        nb_suspendu=('id',lambda x:(df2.loc[x.index,'statut']=='suspendu').sum()),
        ca_total=('eq','sum'),
        ca_moyen=('eq','mean'),
        prime_annuelle_moy=('prime_annuelle',lambda x:x[x>0].mean() if (x>0).any() else 0),
        capital_total=('capital_assure','sum'),
    ).reset_index()
    stats['tx_resil']=stats['nb_resilie']/stats['nb_total'].clip(1)*100
    stats['groupe']=stats['pcode'].apply(get_groupe)
    return stats.sort_values('ca_total',ascending=False)

# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════
today=date.today()
user=st.session_state.user
role=user["role"]
is_dir=role in ["Direction","Administrateur","Actuaire"]
is_mgr=role in ["Direction","Administrateur","Actuaire","Manager"]

with st.sidebar:
    st.markdown(f"""
    <div style='text-align:center;padding:1rem 0 0.5rem'>
      <div style='width:56px;height:56px;background:linear-gradient(135deg,#C9A227,#E8C84A);
        border-radius:12px;display:inline-flex;align-items:center;justify-content:center;
        font-size:10.5px;font-weight:900;color:#003366;line-height:1.2;text-align:center;
        box-shadow:0 6px 20px rgba(201,162,39,0.4);'>AFG<br>VIE</div>
    </div><hr>
    <div style='background:rgba(201,162,39,0.12);border-radius:8px;padding:8px 10px;margin:0 4px 10px;'>
      <div style='font-size:9px;opacity:0.55;text-transform:uppercase;letter-spacing:.05em'>Connecté</div>
      <div style='font-weight:700;font-size:12.5px;margin-top:2px'>{user["nom"]}</div>
      <span class='role-badge {ROLE_COLORS.get(role,"role-visiteur")}' style='font-size:9px;margin-left:0'>{role}</span>
    </div><hr>
    """,unsafe_allow_html=True)

    # ── Navigation filtrée selon le rôle ─────────────────────────────────
    _role_nav = role  # role est défini plus haut dans la sidebar
    _is_commercial = (_role_nav == "Commercial")
    _is_full_access = _role_nav in ("Direction", "Administrateur", "Manager", "Actuaire", "Visiteur")

    if _is_commercial:
        # Commerciaux : accès uniquement à la saisie BIA
        nav_opts = [
            "📝  Saisie BIA",
            "🗂️  Base BIA",
        ]
    else:
        # Direction, Admin, PDG → accès complet
        nav_opts = [
            "🏠  Accueil & KPIs",
            "📝  Saisie BIA",
            "🗂️  Base BIA",
            "📊  Performances",
            "🏆  Classement",
            "🛒  Produits (18)",
            "👥  Commerciaux",
            "👤  Clients",
            "⚠️  Sinistres",
            "🔮  Prévisions ML",
            "🗺️  Carte Bénin",
            "📤  Exports",
        ]
    nav = st.radio("", nav_opts, label_visibility="collapsed")

    st.markdown("<hr><div style='font-size:10.5px;font-weight:600;opacity:0.6;text-transform:uppercase;letter-spacing:.07em;margin-bottom:5px'>📅 Période</div>",unsafe_allow_html=True)
    periode=st.selectbox("",["Aujourd'hui","7 derniers jours","30 derniers jours","Ce trimestre","Ce semestre","Cette année","Personnalisé"],label_visibility="collapsed",index=5)
    if   periode=="Aujourd'hui":       d0,d1=today,today
    elif periode=="7 derniers jours":  d0,d1=today-timedelta(7),today
    elif periode=="30 derniers jours": d0,d1=today-timedelta(30),today
    elif periode=="Ce trimestre":
        qm=((today.month-1)//3)*3+1; d0,d1=today.replace(month=qm,day=1),today
    elif periode=="Ce semestre":
        sm=1 if today.month<=6 else 7; d0,d1=today.replace(month=sm,day=1),today
    elif periode=="Cette année":       d0,d1=today.replace(month=1,day=1),today
    else:
        d0=st.date_input("Du",today-timedelta(30)); d1=st.date_input("Au",today)

    st.markdown(f"""<div style='background:{GOLD};color:{NAVY};text-align:center;
         border-radius:8px;padding:5px;margin:6px 4px;font-weight:700;font-size:10.5px'>
      {d0.strftime('%d/%m/%Y')} → {d1.strftime('%d/%m/%Y')}
      <br><span style='font-size:9px;font-weight:400'>({(d1-d0).days+1} jours)</span>
    </div>""",unsafe_allow_html=True)

    st.markdown("<hr><div style='font-size:10.5px;font-weight:600;opacity:0.6;text-transform:uppercase;letter-spacing:.07em;margin-bottom:5px'>🏢 Agence</div>",unsafe_allow_html=True)
    try:
        agences_db=["Toutes"]+q("SELECT DISTINCT agence FROM commerciaux ORDER BY agence")['agence'].tolist()
    except Exception:
        agences_db=["Toutes"]
    agence_sel=st.selectbox("",agences_db,label_visibility="collapsed")

    st.markdown("<hr>",unsafe_allow_html=True)
    with st.expander("🔑 Identifiants de connexion",expanded=False):
        st.markdown(
            "<div style='font-size:9.5px;'>"
            +"".join([
                "<div style='display:flex;gap:5px;align-items:center;padding:4px 0;"
                "border-bottom:1px solid rgba(201,162,39,0.15);'>"
                "<code style='background:#C9A227;color:#003366;border-radius:4px;"
                "padding:1px 6px;font-size:9px;font-weight:900;min-width:60px;"
                "text-align:center;display:inline-block;'>"+u+"</code>"
                "<code style='background:rgba(255,255,255,0.12);color:#E8C84A;"
                "border-radius:4px;padding:1px 6px;font-size:9px;min-width:68px;"
                "text-align:center;display:inline-block;'>"+p+"</code>"
                "<span style='font-size:8.5px;opacity:0.65;'>"+r.split("—")[0]+"</span>"
                "</div>"
                for u,p,r in CREDS_DEMO
            ])
            +"</div>",unsafe_allow_html=True)

    st.markdown("<hr>",unsafe_allow_html=True)
    if st.button("🚪 Déconnexion", use_container_width=True):
        # NE PAS effacer le portefeuille — il reste en cache disque
        # et sera rechargé automatiquement à la prochaine connexion
        _pf_saved = st.session_state.get("portefeuille_ext")
        for k in ["auth", "user", "bia_prod", "contrat_auth", "contrat_user"]:
            st.session_state[k] = False if k == "auth" else None
        # Restaurer le portefeuille en mémoire (non effacé)
        if _pf_saved is not None:
            st.session_state["portefeuille_ext"] = _pf_saved
        st.rerun()

    # ── Bouton SUPPRIMER la base de données ───────────────────────────────
    with st.expander("🗑️ Gérer la base de données", expanded=False):
        pf_info = get_portefeuille_meta()
        if pf_info:
            st.markdown(
                f"<div style='font-size:10px;color:rgba(255,255,255,0.7);margin-bottom:6px;'>"
                f"📁 Base chargée<br>"
                f"📅 {pf_info.get('saved_at','?')[:16]}<br>"
                f"📊 {pf_info.get('rows',0):,} polices · {pf_info.get('cols',0)} colonnes</div>",
                unsafe_allow_html=True)
        else:
            st.markdown(
                "<div style='font-size:10px;color:rgba(255,255,255,0.5);margin-bottom:6px;'>"
                "Aucune base chargée</div>",
                unsafe_allow_html=True)

        if st.button("🗑️ Supprimer la base", use_container_width=True,
                     help="Supprime définitivement la base du disque. Vous devrez la recharger."):
            delete_portefeuille_cache()
            st.session_state["portefeuille_ext"] = None
            st.session_state["pf_loaded_from_cache"] = False
            st.rerun()
    st.markdown(f"<div style='text-align:center;font-size:8.5px;opacity:0.3;padding:5px 0;'>© 2025 AFG Assurances Bénin Vie<br>Conforme CIMA · v22.0</div>",unsafe_allow_html=True)

# ── Données filtrées ──────────────────────────────────────────────────────────
d0s,d1s=d0.isoformat(),d1.isoformat()
agf=f'AND c.agence = "{agence_sel}"' if agence_sel!="Toutes" else ""
duree_j=(d1-d0).days+1

BASE=f"""
    SELECT ct.*, c.nom, c.prenom, c.code_agent, c.agence, c.region, c.objectif_mensuel,
           p.nom as pnom, p.categorie, p.code as pcode, p.groupe,
           cl.nom as cln, cl.prenom as clpn, cl.ville, cl.sexe as clsx, cl.profession
    FROM contrats ct
    JOIN commerciaux c  ON ct.commercial_id = c.id
    JOIN produits p     ON ct.produit_id    = p.id
    JOIN clients cl     ON ct.client_id     = cl.id
    WHERE ct.date_souscription BETWEEN '{d0s}' AND '{d1s}' {agf}
"""

# ── TOPBAR ─────────────────────────────────────────────────────────────────────
page_name=nav.split("  ",1)[-1] if "  " in nav else nav
rc=ROLE_COLORS.get(role,"role-visiteur")
st.markdown(f"""
<div class="afg-topbar">
  <div class="afg-topbar-left">
    <div style='width:46px;height:46px;background:linear-gradient(135deg,#C9A227,#E8C84A);
      border-radius:10px;display:flex;align-items:center;justify-content:center;
      font-size:10px;font-weight:900;color:#003366;text-align:center;line-height:1.2;flex-shrink:0;'>AFG<br>VIE</div>
    <div class="afg-brand">
      <h1>AFG Assurances Bénin Vie</h1>
      <p>Tableau de Bord PDG v22.0 · Conforme CIMA · Groupe AFG Holding · Atlantic Group</p>
    </div>
  </div>
  <div class="afg-topbar-right">
    <div class="period-pill">{periode}</div>
    <div class="user-info">
      {d0.strftime('%d/%m/%Y')} → {d1.strftime('%d/%m/%Y')} &nbsp;·&nbsp;
      <b style='color:{GOLDL}'>{user['nom']}</b>
      <span class='role-badge {rc}'>{role}</span>
    </div>
  </div>
</div>
<div class="breadcrumb">
  🏠 AFG Dashboard v22.0
  <span style='color:{MGRAY}'>›</span>
  <span class="bc-active">{page_name}</span>
  <span style='margin-left:auto;font-size:10px;color:{DGRAY}'>
    Agence : <b>{agence_sel}</b> · {today.strftime('%d/%m/%Y')}
  </span>
</div>""",unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — SAISIE BIA (complète, corrigée)
# ═══════════════════════════════════════════════════════════════════════════════
if "Saisie BIA" in nav:
    nb_bia_tot=pd.read_sql_query("SELECT COUNT(*) as n FROM bulletins_bia",gc())["n"].iloc[0]
    nb_bia_auj=pd.read_sql_query(
        "SELECT COUNT(*) as n FROM bulletins_bia WHERE date_saisie=?",gc(),
        params=(today.isoformat(),))["n"].iloc[0]
    cot_tot=pd.read_sql_query("SELECT COALESCE(SUM(cotisation_fcfa),0) as s FROM bulletins_bia",gc())["s"].iloc[0]

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,{NAVY},{BLUE});border-radius:14px;
         padding:1.2rem 1.6rem;margin-bottom:1rem;border:1px solid rgba(201,162,39,0.3);">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap;">
        <div>
          <div style="color:{GOLDL};font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin-bottom:3px;">Saisie BIA · Tableau de bord</div>
          <div style="color:white;font-size:1.1rem;font-weight:900;">{("Bonsoir" if datetime.now().hour>=18 else "Bonjour")}, {user["nom"].split()[0]} ! Bulletins Individuels d'Adhésion</div>
          <div style="color:rgba(255,255,255,.6);font-size:11.5px;margin-top:3px;">{today.strftime('%A %d %B %Y').capitalize()}</div>
        </div>
        <div style="display:flex;gap:9px;flex-wrap:wrap;">
          <div style="background:white;border-radius:10px;padding:9px 14px;text-align:center;min-width:110px;">
            <div style="font-size:1.35rem;font-weight:900;color:#003366;">{nb_bia_tot}</div>
            <div style="font-size:9px;color:#5A6478;">BIA Saisis</div>
          </div>
          <div style="background:rgba(255,255,255,.1);border:1px solid rgba(201,162,39,.3);border-radius:10px;padding:9px 13px;text-align:center;">
            <div style="font-size:1.35rem;font-weight:900;color:#E8C84A;">{nb_bia_auj}</div>
            <div style="font-size:9px;color:rgba(255,255,255,.5);">Aujourd'hui</div>
          </div>
          <div style="background:rgba(255,255,255,.1);border:1px solid rgba(201,162,39,.3);border-radius:10px;padding:9px 13px;text-align:center;">
            <div style="font-size:1.1rem;font-weight:900;color:#E8C84A;">{fmt(cot_tot)}</div>
            <div style="font-size:9px;color:rgba(255,255,255,.5);">Cotisations</div>
          </div>
        </div>
      </div>
    </div>""",unsafe_allow_html=True)

    alert("Sélectionnez le groupe, puis le produit, puis remplissez le formulaire. N° BIA généré automatiquement. <b>Signatures obligatoires</b> avant validation.","info")

    prod_df=pd.read_sql_query("SELECT * FROM produits WHERE actif=1 ORDER BY nom",gc())

    # ── ÉTAPE 1 : SÉLECTION PRODUIT ─────────────────────────────────────────
    sth("Étape 1 — Groupe & Produit","CLASSIFICATION OFFICIELLE AFG")

    tab_g1,tab_g2,tab_g3=st.tabs([
        "🛡️  Groupe 1 — Décès & Vie",
        "💰  Groupe 2 — Épargne & Capitalisation",
        "🔄  Groupe 3 — Contrat Mixte",
    ])

    def render_groupe_tab(gname,tab):
        codes_g=[k for k,v in GROUPE_MAP.items() if v==gname]
        prods_g=prod_df[prod_df["code"].isin(codes_g)]
        col_g=GROUPE_COLORS.get(gname,NAVY)
        with tab:
            st.markdown(
                f"<div style='background:{col_g}18;border:1px solid {col_g}50;"
                f"border-radius:10px;padding:9px 13px;margin-bottom:10px;font-size:12px;'>"
                f"<b style='color:{col_g};'>{GROUPE_ICONS.get(gname,'')} {gname}</b></div>",
                unsafe_allow_html=True)
            if prods_g.empty: st.info("Aucun produit dans ce groupe."); return
            nc=min(3,max(1,len(prods_g))); cols_p=st.columns(nc)
            for i,(_,row) in enumerate(prods_g.iterrows()):
                with cols_p[i%nc]:
                    is_sel=st.session_state.bia_prod==row["code"]
                    border=f"2px solid {col_g}" if is_sel else "1.5px solid #DDE3EE"
                    bg=f"linear-gradient(135deg,{col_g}0A,white)" if is_sel else "white"
                    st.markdown(
                        f"<div style='border:{border};border-radius:12px;padding:12px;"
                        f"background:{bg};margin-bottom:6px;'>"
                        f"<code style='background:#003366;color:#C9A227;padding:2px 7px;"
                        f"border-radius:5px;font-size:9px;font-weight:900;'>{row['code']}</code>"
                        f"<div style='font-size:12.5px;font-weight:700;color:#003366;margin:4px 0 2px;'>{row['nom']}</div>"
                        f"<div style='font-size:10px;color:#5A6478;'>{row['categorie']}</div>"
                        f"</div>",unsafe_allow_html=True)
                    btn="✅ Sélectionné" if is_sel else "Choisir ▶"
                    if st.button(btn,key=f"bp_{row['code']}_{gname[:4]}",use_container_width=True):
                        st.session_state.bia_prod=row["code"]; st.rerun()

    render_groupe_tab("Groupe 1 — Décès & Vie",tab_g1)
    render_groupe_tab("Groupe 2 — Épargne & Capitalisation",tab_g2)
    render_groupe_tab("Groupe 3 — Contrat Mixte",tab_g3)

    if st.session_state.bia_prod:
        pr_s=prod_df[prod_df["code"]==st.session_state.bia_prod]
        if not pr_s.empty:
            pr_s=pr_s.iloc[0]
            alert(f"Produit sélectionné : <b>{pr_s['nom']}</b> (code {pr_s['code']}) — {get_groupe(pr_s['code'])}","good")
        else:
            st.session_state.bia_prod=None
    if not st.session_state.bia_prod:
        alert("Sélectionnez un produit dans l'un des trois groupes pour afficher le formulaire BIA.","warn")
        st.stop()

    pr=prod_df[prod_df["code"]==st.session_state.bia_prod].iloc[0]
    tmpl=BIA_SPECIFIQUES.get(str(pr["code"]),BIA_PAR_DEFAUT)

    # ── ÉTAPE 2 : FORMULAIRE BIA ─────────────────────────────────────────────
    # ARCHITECTURE EXPERTE :
    # Les widgets RÉACTIFS (checkbox assuré + radio mode règlement) sont placés
    # HORS du st.form pour déclencher un rerun immédiat à chaque changement.
    # Leurs valeurs sont stockées dans st.session_state et lues dans le formulaire.
    # ─────────────────────────────────────────────────────────────────────────────

    sth("Étape 2 — Formulaire BIA","SAISIE COMPLÈTE")

    # Initialisation des clés réactives dans session_state
    if "bia_ass_meme" not in st.session_state:
        st.session_state.bia_ass_meme = True
    if "bia_mode_rg" not in st.session_state:
        st.session_state.bia_mode_rg = ""

    # ── En-tête BIA ──────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="bia-fhdr">
      <div>
        <div style="font-size:8.5px;color:rgba(255,255,255,.5);letter-spacing:1px;text-transform:uppercase;margin-bottom:3px;">
          AFG Assurances Bénin Vie — Exemplaire AFG-Vie</div>
        <div style="font-size:1.1rem;font-weight:900;color:white;letter-spacing:.3px;">
          BULLETIN INDIVIDUEL D'ADHÉSION (BIA)</div>
        <div style="font-size:10.5px;color:rgba(255,255,255,.6);margin-top:2px;">
          N° : <em style="color:#E8C84A;">généré automatiquement</em>
          &nbsp;·&nbsp; {pr['nom']} &nbsp;·&nbsp; {get_groupe(str(pr['code']))}</div>
      </div>
      <div style="background:rgba(201,162,39,.15);border:1px solid #C9A227;border-radius:8px;padding:7px 13px;text-align:right;">
        <div style="font-size:8.5px;color:#C9A227;text-transform:uppercase;letter-spacing:1px;">Produit</div>
        <code style="background:#C9A227;color:#003366;padding:2px 8px;border-radius:5px;font-size:11px;font-weight:900;">{pr['code']}</code>
        <div style="font-size:9.5px;color:rgba(255,255,255,.5);margin-top:2px;">{pr['categorie']}</div>
      </div>
    </div>
    <div style="background:white;padding:1.1rem;border:1.5px solid #DDE3EE;border-top:none;border-radius:0 0 12px 12px;margin-bottom:0.9rem;">
    """, unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # BLOC RÉACTIF A — CHECKBOX "Assuré identique" (HORS formulaire)
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown('<div class="bia-sec"><div class="bia-lbl">II — Assuré(e) — Choix</div>', unsafe_allow_html=True)
    ass_meme = st.checkbox(
        "✓ L'assuré(e) est identique au souscripteur",
        value=st.session_state.bia_ass_meme,
        key="bia_ass_cb",
        help="Cochez si l'assuré(e) et le souscripteur sont la même personne.")
    # Mémoriser dans session_state pour que le formulaire en dessous puisse le lire
    st.session_state.bia_ass_meme = ass_meme
    st.markdown("</div>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # BLOC RÉACTIF B — RADIO "Mode de règlement" (HORS formulaire)
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown('<div class="bia-sec"><div class="bia-lbl">IV-b — Mode de Règlement</div>', unsafe_allow_html=True)
    MODE_OPTIONS = ["", "Mobile Monnaie", "Par chèque", "Par virement bancaire", "Par prélèvement sur salaire"]
    cur_mode_idx = MODE_OPTIONS.index(st.session_state.bia_mode_rg) if st.session_state.bia_mode_rg in MODE_OPTIONS else 0
    mode_rg = st.radio(
        "Choisissez le mode de règlement *",
        options=MODE_OPTIONS,
        index=cur_mode_idx,
        horizontal=True,
        key="bia_mode_radio",
        format_func=lambda x: "— Sélectionner —" if x == "" else x)
    st.session_state.bia_mode_rg = mode_rg

    # Champ de saisie du numéro selon le mode (réactif, hors form)
    mode_ref_numero = ""
    if mode_rg == "":
        st.markdown(
            "<div style='color:#5A6478;font-size:12px;padding:9px 12px;background:#F4F6FA;"
            "border-radius:8px;border:1.5px dashed #DDE3EE;margin-top:8px;'>"
            "👆 Sélectionnez un mode de règlement ci-dessus pour saisir le numéro associé.</div>",
            unsafe_allow_html=True)
    elif "Mobile" in mode_rg:
        mode_ref_numero = st.text_input(
            "📱 N° Téléphone Mobile Money *",
            placeholder="+229 97 00 00 00",
            key="bia_ref_mob",
            help="Numéro de téléphone lié au compte Mobile Money (MTN MoMo, Moov Money…)")
    elif "chèque" in mode_rg.lower():
        mode_ref_numero = st.text_input(
            "📄 N° Chèque *",
            placeholder="Ex : CH0001234567",
            key="bia_ref_chq",
            help="Numéro figurant sur le chèque remis en paiement")
    elif "virement" in mode_rg.lower():
        mode_ref_numero = st.text_input(
            "🏦 N° Compte bancaire / RIB *",
            placeholder="Ex : BJ66 BJ001 00100 00000000000 00",
            key="bia_ref_vir",
            help="Numéro de compte bancaire complet (IBAN Bénin ou RIB) pour le virement bancaire")
    elif "prélèvement" in mode_rg.lower() or "salaire" in mode_rg.lower():
        mode_ref_numero = st.text_input(
            "💼 N° Matricule / Compte salaire *",
            placeholder="Ex : MAT-2025-001234",
            key="bia_ref_prl",
            help="Matricule de l'employé ou numéro de compte salaire pour le prélèvement automatique")
    st.markdown("</div>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # FORMULAIRE PRINCIPAL (tout le reste est dans le form)
    # ═══════════════════════════════════════════════════════════════════════
    # ═══════════════════════════════════════════════════════════════════════
    # BLOC RÉACTIF C — SIGNATURES (HORS formulaire — file_uploader interdit dans form)
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown('<div class="bia-sec"><div class="bia-lbl" style="background:#C0392B;">Signatures — Obligatoires avant validation</div>',unsafe_allow_html=True)
    st.markdown(
        "<div style='background:#FDECEA;border:1px solid #C0392B;border-radius:8px;"
        "padding:8px 12px;margin-bottom:12px;font-size:12px;color:#7B1414;'>"
        "⚠️ Les trois signatures photographiées sont <b>OBLIGATOIRES</b> pour valider le BIA. "
        "Chaque signature doit être précédée de <b>«LU ET APPROUVÉ»</b>.</div>",
        unsafe_allow_html=True)
    sig_c1,sig_c2,sig_c3=st.columns(3)
    with sig_c1:
        st.markdown('<div class="sig-box sig-req">📷 Signature Souscripteur<br><small>précédée de "LU ET APPROUVÉ"</small></div>',unsafe_allow_html=True)
        sig_souscr=st.file_uploader("Photo signature souscripteur *",type=["jpg","jpeg","png","webp"],key="sig_s",label_visibility="collapsed")
        if sig_souscr: st.image(sig_souscr,caption="✅ Signature souscripteur",use_container_width=True)
    with sig_c2:
        st.markdown('<div class="sig-box sig-req">📷 Signature Assuré(e)<br><small>précédée de "LU ET APPROUVÉ"</small></div>',unsafe_allow_html=True)
        sig_ass=st.file_uploader("Photo signature assuré *",type=["jpg","jpeg","png","webp"],key="sig_a",label_visibility="collapsed")
        if sig_ass: st.image(sig_ass,caption="✅ Signature assuré",use_container_width=True)
    with sig_c3:
        st.markdown('<div class="sig-box sig-req">📷 Signature Conseiller<br><small>agent commercial AFG</small></div>',unsafe_allow_html=True)
        sig_cons=st.file_uploader("Photo signature conseiller *",type=["jpg","jpeg","png","webp"],key="sig_c",label_visibility="collapsed")
        if sig_cons: st.image(sig_cons,caption="✅ Signature conseiller",use_container_width=True)
    # Stocker dans session_state pour validation dans le form
    st.session_state["_sig_souscr_ok"] = sig_souscr is not None
    st.session_state["_sig_ass_ok"]    = sig_ass    is not None
    st.session_state["_sig_cons_ok"]   = sig_cons   is not None
    st.markdown("</div>",unsafe_allow_html=True)

    with st.form("bia_v13_form", clear_on_submit=False):

        # ── AGENCE & IDENTIFICATION (auto-rempli pour les commerciaux) ─────
        st.markdown('<div class="bia-sec"><div class="bia-lbl">Agence & Identification</div>', unsafe_allow_html=True)

        # Auto-remplissage pour les commerciaux connectés
        _is_commercial = (role == "Commercial")
        _auto_code = user.get("code", "") if _is_commercial else ""
        _auto_nom  = user.get("nom", "")  if _is_commercial else ""
        _auto_agence_idx = 0
        if _is_commercial and user.get("agence"):
            try: _auto_agence_idx = AGENCES_AFG.index(user["agence"])
            except ValueError: _auto_agence_idx = 0

        if _is_commercial:
            st.markdown(
                f"<div style='background:rgba(26,122,74,0.08);border:1.5px solid rgba(26,122,74,0.25);"
                f"border-left:4px solid #1A7A4A;border-radius:8px;padding:9px 13px;margin-bottom:8px;font-size:12px;'>"
                f"✅ <b>Agent connecté :</b> {user['nom']} — "
                f"Code : <code style='background:#003366;color:#C9A227;padding:1px 7px;border-radius:4px;'>{_auto_code}</code> — "
                f"Agence : {user.get('agence','—')}"
                f"<br><span style='font-size:10.5px;color:#5A6478;'>Code apporteur et nom remplis automatiquement.</span></div>",
                unsafe_allow_html=True)

        h1,h2,h3,h4,h5 = st.columns(5)
        with h1:
            agence_sel_bia = st.selectbox(
                "Agence", AGENCES_AFG, index=_auto_agence_idx, key="h_agence",
                help="Sélectionnez l'agence AFG. Laissez vide si non applicable.",
                disabled=_is_commercial)
        with h2:
            code_apporteur = st.text_input(
                "Code Apporteur", value=_auto_code, key="h_app",
                disabled=_is_commercial,
                placeholder="Ex : AFG001")
        with h3:
            nom_apporteur = st.text_input(
                "Nom Apporteur", value=_auto_nom, key="h_nom_app",
                disabled=_is_commercial,
                placeholder="Nom complet de l'apporteur")
        with h4:
            realisateur = st.text_input("Réalisateur", value=user["nom"], key="h_real")
        with h5:
            deja_afg = st.radio("Déjà assuré AFGVie ?", ["Non","Oui"], horizontal=True, key="h_deja")
        num_ct_exist = ""
        if deja_afg == "Oui":
            num_ct_exist = st.text_input("N° Contrat existant", placeholder="Ex : 2025-001234", key="h_numct")
        st.markdown("</div>", unsafe_allow_html=True)

        # ── I. SOUSCRIPTEUR ───────────────────────────────────────────────
        st.markdown('<div class="bia-sec"><div class="bia-lbl">I — Souscripteur / Contractant</div>', unsafe_allow_html=True)
        c1a,c1b,c1c = st.columns([1,2,2])
        with c1a: c_tit = st.selectbox("Civilité *",["","M.","Mme","Mlle"], key="ct_tit")
        with c1b: c_nom = st.text_input("Nom *", placeholder="NOM (majuscules)", key="ct_nom")
        with c1c: c_prn = st.text_input("Prénoms *", placeholder="Prénoms", key="ct_prn")
        c2a,c2b,c2c = st.columns(3)
        with c2a: c_ddn = st.date_input("Date de naissance *", value=date(1985,1,1), min_value=date(1930,1,1), max_value=today, key="ct_ddn")
        with c2b: c_lieu = st.text_input("Lieu de naissance *", placeholder="Cotonou", key="ct_lieu")
        with c2c: c_nat = st.text_input("Nationalité", value="Béninoise", key="ct_nat")
        c3a,c3b,c3c,c3d = st.columns(4)
        with c3a: c_mat = st.selectbox("Sit. Matrimoniale",["","Célibataire","Marié(e)","Divorcé(e)","Veuf(ve)"], key="ct_mat")
        with c3b: c_prof = st.text_input("Profession *", key="ct_prof")
        with c3c: c_adr = st.text_input("Adresse *", placeholder="Quartier, rue", key="ct_adr")
        with c3d: c_bp = st.text_input("Boîte Postale", placeholder="01 BP...", key="ct_bp")
        c4a,c4b,c4c = st.columns(3)
        with c4a: c_tel = st.text_input("Tél. Cel. *", placeholder="+229 97...", key="ct_cel")
        with c4b: c_fixe = st.text_input("Tél. Fixe", placeholder="+229 21...", key="ct_fixe")
        with c4c: c_wapp = st.text_input("WhatsApp *", placeholder="+229 97...", key="ct_wap")
        c5a,c5b = st.columns(2)
        with c5a: c_eml = st.text_input("Email", placeholder="exemple@mail.com", key="ct_eml")
        with c5b: c_npi = st.text_input("N°NPI / Passeport *", placeholder="BJ123456", key="ct_npi")
        st.markdown("</div>", unsafe_allow_html=True)

        # ── II. ASSURÉ — affichage conditionnel selon session_state.bia_ass_meme ──
        # La checkbox est hors du form (ci-dessus), on lit ici son état mémorisé.
        st.markdown('<div class="bia-sec"><div class="bia-lbl">II — Assuré(e)</div>', unsafe_allow_html=True)

        # Lire l'état mémorisé de la checkbox (défini hors du form)
        _ass_meme = st.session_state.get("bia_ass_meme", True)

        if _ass_meme:
            # ── Affichage complet des infos du souscripteur (lecture seule) ──
            st.markdown(f"""
            <div style="background:rgba(26,122,74,0.06);border:1.5px solid rgba(26,122,74,0.25);
                 border-left:5px solid #1A7A4A;border-radius:8px;padding:13px 16px;margin-bottom:6px;">
              <div style="font-weight:800;color:#1A7A4A;font-size:12px;margin-bottom:10px;">
                ✅ Assuré(e) = Souscripteur(trice) — Informations reprises automatiquement</div>
              <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px 18px;font-size:11.5px;color:#003366;">
                <div><span style="color:#5A6478;font-size:10px;text-transform:uppercase;letter-spacing:.05em;">Civilité</span><br><b>{c_tit or "—"}</b></div>
                <div><span style="color:#5A6478;font-size:10px;text-transform:uppercase;letter-spacing:.05em;">Nom</span><br><b>{(c_nom.upper() if c_nom else "—")}</b></div>
                <div><span style="color:#5A6478;font-size:10px;text-transform:uppercase;letter-spacing:.05em;">Prénoms</span><br><b>{c_prn or "—"}</b></div>
                <div><span style="color:#5A6478;font-size:10px;text-transform:uppercase;letter-spacing:.05em;">Date de naissance</span><br><b>{c_ddn.strftime('%d/%m/%Y') if c_ddn else "—"}</b></div>
                <div><span style="color:#5A6478;font-size:10px;text-transform:uppercase;letter-spacing:.05em;">Lieu de naissance</span><br><b>{c_lieu or "—"}</b></div>
                <div><span style="color:#5A6478;font-size:10px;text-transform:uppercase;letter-spacing:.05em;">Nationalité</span><br><b>{c_nat or "—"}</b></div>
                <div><span style="color:#5A6478;font-size:10px;text-transform:uppercase;letter-spacing:.05em;">Sit. Matrimoniale</span><br><b>{c_mat or "—"}</b></div>
                <div><span style="color:#5A6478;font-size:10px;text-transform:uppercase;letter-spacing:.05em;">Profession</span><br><b>{c_prof or "—"}</b></div>
                <div><span style="color:#5A6478;font-size:10px;text-transform:uppercase;letter-spacing:.05em;">Adresse</span><br><b>{c_adr or "—"}</b></div>
                <div><span style="color:#5A6478;font-size:10px;text-transform:uppercase;letter-spacing:.05em;">Boîte Postale</span><br><b>{c_bp or "—"}</b></div>
                <div><span style="color:#5A6478;font-size:10px;text-transform:uppercase;letter-spacing:.05em;">Tél. Cel.</span><br><b>{c_tel or "—"}</b></div>
                <div><span style="color:#5A6478;font-size:10px;text-transform:uppercase;letter-spacing:.05em;">Tél. Fixe</span><br><b>{c_fixe or "—"}</b></div>
                <div><span style="color:#5A6478;font-size:10px;text-transform:uppercase;letter-spacing:.05em;">WhatsApp</span><br><b>{c_wapp or "—"}</b></div>
                <div><span style="color:#5A6478;font-size:10px;text-transform:uppercase;letter-spacing:.05em;">Email</span><br><b>{c_eml or "—"}</b></div>
                <div><span style="color:#5A6478;font-size:10px;text-transform:uppercase;letter-spacing:.05em;">NPI / Passeport</span><br><b>{(c_npi.upper() if c_npi else "—")}</b></div>
              </div>
            </div>
            <div style="font-size:11px;color:#5A6478;margin-top:4px;">
              ℹ️ Décochez la case au-dessus du formulaire si l'assuré(e) est une personne différente.</div>
            """, unsafe_allow_html=True)
            # Variables assuré = souscripteur
            a_tit=c_tit; a_nom=c_nom; a_prn=c_prn; a_ddn=c_ddn
            a_lieu=c_lieu; a_nat=c_nat; a_mat=c_mat; a_prof=c_prof
            a_adr=c_adr; a_bp=c_bp; a_tel=c_tel; a_fixe=c_fixe
            a_wapp=c_wapp; a_eml=c_eml; a_npi=c_npi

        else:
            # ── Champs de saisie libres — même mise en page que le souscripteur ──
            st.markdown(
                "<div style='background:#FFF8E1;border-left:4px solid #D35400;border-radius:0 8px 8px 0;"
                "padding:8px 13px;font-size:12px;color:#7B3C00;margin-bottom:10px;'>"
                "⚠️ L'assuré(e) est différent(e) du souscripteur — Renseignez ses informations ci-dessous.</div>",
                unsafe_allow_html=True)
            a1a,a1b,a1c = st.columns([1,2,2])
            with a1a: a_tit = st.selectbox("Civilité *",["","M.","Mme","Mlle"], key="as_tit")
            with a1b: a_nom = st.text_input("Nom *", placeholder="NOM (majuscules)", key="as_nom")
            with a1c: a_prn = st.text_input("Prénoms *", placeholder="Prénoms", key="as_prn")
            a2a,a2b,a2c = st.columns(3)
            with a2a: a_ddn = st.date_input("Date de naissance *", value=date(1990,1,1), min_value=date(1930,1,1), max_value=today, key="as_ddn")
            with a2b: a_lieu = st.text_input("Lieu de naissance *", placeholder="Cotonou", key="as_lieu")
            with a2c: a_nat = st.text_input("Nationalité", value="Béninoise", key="as_nat")
            a3a,a3b,a3c,a3d = st.columns(4)
            with a3a: a_mat = st.selectbox("Sit. Matrimoniale",["","Célibataire","Marié(e)","Divorcé(e)","Veuf(ve)"], key="as_mat")
            with a3b: a_prof = st.text_input("Profession *", key="as_prof")
            with a3c: a_adr = st.text_input("Adresse *", placeholder="Quartier, rue", key="as_adr")
            with a3d: a_bp = st.text_input("Boîte Postale", placeholder="01 BP...", key="as_bp")
            a4a,a4b,a4c = st.columns(3)
            with a4a: a_tel = st.text_input("Tél. Cel. *", placeholder="+229 97...", key="as_cel")
            with a4b: a_fixe = st.text_input("Tél. Fixe", placeholder="+229 21...", key="as_fixe")
            with a4c: a_wapp = st.text_input("WhatsApp", placeholder="+229 97...", key="as_wap")
            a5a,a5b = st.columns(2)
            with a5a: a_eml = st.text_input("Email", placeholder="exemple@mail.com", key="as_eml")
            with a5b: a_npi = st.text_input("N°NPI / Passeport *", placeholder="BJ123456", key="as_npi")

        st.markdown("</div>", unsafe_allow_html=True)

        # ── III. BÉNÉFICIAIRES ─────────────────────────────────────────────
        st.markdown('<div class="bia-sec"><div class="bia-lbl">III — Bénéficiaires</div>', unsafe_allow_html=True)
        st.markdown(
            "<div style='background:rgba(0,51,102,0.05);border-left:3px solid #C9A227;"
            "border-radius:0 6px 6px 0;padding:7px 11px;font-size:12px;color:#003366;margin-bottom:9px;'>"
            "<b>En cas de vie :</b> le souscripteur ou l'assuré &nbsp;|&nbsp; "
            "<b>En cas de décès :</b> à préciser ci-dessous</div>",
            unsafe_allow_html=True)
        ben_c1,ben_c2 = st.columns(2)
        with ben_c1:
            ben_conj = st.checkbox("○ Mon conjoint, mes enfants nés et à naître, à défaut mes ayants droits", value=True, key="bn_conj")
        with ben_c2:
            ben_autres = st.text_input("Autres bénéficiaires (préciser)", placeholder="Nom, lien de parenté...", key="bn_aut")
        st.markdown("</div>", unsafe_allow_html=True)

        # ── IV. CARACTÉRISTIQUES DU CONTRAT ───────────────────────────────
        st.markdown('<div class="bia-sec"><div class="bia-lbl">IV — Caractéristiques du Contrat</div>', unsafe_allow_html=True)
        cc1,cc2,cc3 = st.columns(3)
        with cc1: dt_eff = st.date_input("Date d'effet *", value=today, key="cc_eff")
        with cc2:
            dur = st.number_input("Durée (ANS) *", min_value=1, max_value=40, value=10, step=1, key="cc_dur")
        with cc3:
            try:
                yr_max = min(dt_eff.year + int(dur), 2099)
                terme_d = date(yr_max, dt_eff.month, dt_eff.day)
            except Exception:
                terme_d = today
            terme_ = st.date_input("Terme du contrat", value=terme_d, key="cc_terme")

        st.markdown("**Périodicité :**")
        perio = st.radio("Périodicité *",["Mensuelle","Trimestrielle","Semestrielle","Annuelle","Unique"], horizontal=True, key="cc_perio")

        cot1,cot2,cot3 = st.columns([1,2,1])
        with cot1:
            cotis = st.number_input(
                "Cotisation en FCFA *",
                min_value=100, max_value=999_999_999, value=15000, step=1000,
                key="cot_fcfa",
                help="Montant minimum : 100 FCFA.")
        with cot2:
            cotis_lett = st.text_input("Cotisation (en lettres)", placeholder="Ex : Quinze mille francs CFA", key="cot_lett")
        with cot3:
            cap_terme = st.number_input("Capital au terme (FCFA)", min_value=0, step=10000, value=0, key="cc_cap")

        st.markdown("**Option garantie décès :**")
        option_gar = st.radio(
            "Choisir l'option",
            options=["— Sans garantie décès","— Avec garantie décès"],
            index=0, horizontal=True, key="cc_opt")

        # ── Rappel visuel du mode de règlement choisi hors formulaire ──────
        _mode_rg = st.session_state.get("bia_mode_rg","")
        _mode_ref = st.session_state.get("bia_ref_mob",
                    st.session_state.get("bia_ref_chq",
                    st.session_state.get("bia_ref_vir",
                    st.session_state.get("bia_ref_prl",""))))
        if _mode_rg:
            icone = {"Mobile Monnaie":"📱","Par chèque":"📄","Par virement bancaire":"🏦","Par prélèvement sur salaire":"💼"}.get(_mode_rg,"💳")
            st.markdown(
                f"<div style='background:rgba(0,51,102,0.05);border:1.5px solid #DDE3EE;"
                f"border-left:4px solid #0072CE;border-radius:8px;padding:8px 13px;font-size:12px;margin-top:8px;'>"
                f"{icone} <b>Mode de règlement :</b> {_mode_rg}"
                f"{'  —  <b>Réf. :</b> '+_mode_ref if _mode_ref else ''}</div>",
                unsafe_allow_html=True)
        else:
            st.markdown(
                "<div style='background:#FFF8E1;border-left:3px solid #D35400;border-radius:0 6px 6px 0;"
                "padding:7px 11px;font-size:11.5px;color:#7B3C00;margin-top:8px;'>"
                "⚠️ Aucun mode de règlement sélectionné. Faites votre choix dans le bloc <b>Mode de Règlement</b> au-dessus du formulaire.</div>",
                unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # ── V. INVESTISSEMENT (Dokountché uniquement) ──────────────────────
        inv_repartition=inv_fg=inv_uc=inv_fonds=""
        if tmpl=="dokountche":
            st.markdown('<div class="bia-sec"><div class="bia-lbl">V — Choix d\'Investissement (DOKOUNTCHE)</div>',unsafe_allow_html=True)
            inv_c1,inv_c2=st.columns(2)
            with inv_c1:
                rep_choice=st.selectbox("Répartition *",[
                    "Option 1 : 20% FG + 80% UC","Option 2 : 25% FG + 75% UC","Option 3 : 40% FG + 60% UC"],key="inv_rep")
                inv_fg=20 if "20%" in rep_choice else (25 if "25%" in rep_choice else 40)
                inv_uc=100-inv_fg
                inv_repartition=rep_choice
            with inv_c2:
                fonds_soaga=st.selectbox("Fonds SOAGA",["Aucun","FCP Épargne Obligation (6%)","FCP Épargne Active (8%)","FCP Épargne Action (10%)"],key="inv_soaga")
                fonds_saphir=st.selectbox("Fonds SAPHIR / AAM",["Aucun","Saphir Quiétude (6%)","Saphir Dynamique (8%)","AAM Sérénitis (7%)","AAM Épargne Croissance (8%)"],key="inv_saph")
            inv_fonds=f"SOAGA:{fonds_soaga} | SAPHIR:{fonds_saphir}"
            st.markdown("</div>",unsafe_allow_html=True)

        # ── VI. QUESTIONNAIRE MÉDICAL (CIMA — 7 questions obligatoires) ───────
        st.markdown(
            '<div class="bia-sec"><div class="bia-lbl" '
            'style="background:#1A5276;">VI — Questionnaire Médical — À renseigner par l\'Assuré(e)</div>',
            unsafe_allow_html=True)
        st.markdown(
            "<div style='background:#EBF5FB;border:1.5px solid #2E86C1;border-radius:8px;"
            "padding:10px 14px;margin-bottom:10px;font-size:12px;color:#1A5276;'>"
            "<b>Instructions :</b> L'assuré(e) doit répondre honnêtement à toutes les questions. "
            "Toute fausse déclaration est sanctionnée par la nullité du contrat (art. 18 CIMA). "
            "Si <b>OUI</b>, remplissez obligatoirement le champ <b>Précisions</b>.</div>",
            unsafe_allow_html=True)

        # Taille / Poids / Perte de poids
        mq0a, mq0b, mq0c = st.columns(3)
        with mq0a: med_taille = st.text_input("Taille (m)", placeholder="Ex : 1.72", key="med_t")
        with mq0b: med_poids  = st.text_input("Poids (kg)", placeholder="Ex : 75", key="med_p")
        with mq0c: med_perte  = st.radio("Avez-vous grossi ou maigri de plus de 5 kg depuis 6 mois ?",
                                         ["Non","Oui"], horizontal=True, key="med_pp")
        med_perte_detail = ""
        if med_perte == "Oui":
            med_perte_detail = st.text_input("Si oui, combien ?", placeholder="Ex : 8 kg", key="med_pp_d")

        # 7 Questions médicales CIMA
        QUESTIONS_MEDICALES = [
            ("med_q1", "1", "Êtes-vous actuellement et/ou avez-vous été, au cours des 10 dernières années, "
             "atteint(e) d'une maladie ou de séquelles nécessitant une surveillance médicale ?",
             "Si oui, précisez la maladie ou les séquelles", False),
            ("med_q2", "2", "Au cours des 5 dernières années, avez-vous eu un ou plusieurs arrêts de travail "
             "de plus de 21 jours ?",
             "Si oui, précisez le motif", False),
            ("med_q3", "3", "Au cours des 5 dernières années, vous a-t-on déjà prescrit un traitement médical "
             "de plus de 21 jours (hors contraception) ?",
             "Si oui, précisez le traitement", False),
            ("med_q4", "4", "Êtes-vous actuellement en arrêt de travail sur prescription médicale pour raison de santé ?",
             "Si oui, précisez le motif", False),
            ("med_q5", "5", "Suivez-vous actuellement un traitement médical (hors contraception) ?",
             "Si oui, précisez le traitement", False),
            ("med_q6", "6", "À votre connaissance, devez-vous être hospitalisé(e) avec ou sans intervention "
             "chirurgicale ou subir des analyses ou des examens dans les 12 prochains mois ?",
             "Si oui, précisez", True),   # True = question spéciale avec 3 sous-champs
            ("med_q7", "7", "Présentez-vous ou avez-vous présenté une des maladies suivantes : méningite, "
             "affection des poumons, hépatite B, verrues fréquentes, mycoses, affections génitales, "
             "Sida, Prostates, cancers etc. ?",
             "Si oui, précisez la maladie", False),
        ]

        med_answers = {}
        for key, num, question, precision_label, is_q6 in QUESTIONS_MEDICALES:
            st.markdown(
                f"<div style='background:white;border:1.5px solid #DDE3EE;border-radius:8px;"
                f"padding:9px 13px;margin-bottom:6px;'>"
                f"<div style='font-size:11.5px;font-weight:700;color:#003366;margin-bottom:6px;'>"
                f"<span style='background:#1A5276;color:white;border-radius:4px;padding:1px 7px;"
                f"font-size:10px;margin-right:6px;'>{num}</span>{question}</div>",
                unsafe_allow_html=True)
            mqa, mqb = st.columns([1, 3])
            with mqa:
                rep = st.radio("Réponse", ["Non","Oui"], horizontal=True, key=f"{key}_rep",
                               label_visibility="collapsed")
                med_answers[key] = rep
            with mqb:
                if rep == "Oui":
                    if is_q6:
                        # Question 6 : 3 sous-champs
                        d1q6 = st.text_input(f"Précisez :", placeholder="Précisions générales", key=f"{key}_d1")
                        d2q6 = st.text_input("Nature de l'intervention ou des analyses/examens :", placeholder="Nature", key=f"{key}_d2")
                        d3q6 = st.text_input("Motif :", placeholder="Motif de l'intervention", key=f"{key}_d3")
                        med_answers[f"{key}_detail"] = d1q6
                        med_answers[f"{key}_nature"] = d2q6
                        med_answers[f"{key}_motif"]  = d3q6
                    else:
                        det = st.text_input(precision_label, placeholder="Soyez précis(e)", key=f"{key}_det")
                        med_answers[f"{key}_detail"] = det
                else:
                    med_answers[f"{key}_detail"] = ""
                    if is_q6:
                        med_answers[f"{key}_nature"] = ""
                        med_answers[f"{key}_motif"]  = ""
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            "<div style='background:#FFF3CD;border:1px solid #D4AC0D;border-radius:8px;"
            "padding:8px 13px;font-size:11px;color:#7D6608;margin-top:4px;'>"
            "** L'assureur se réserve le droit de demander des examens complémentaires si la situation "
            "l'exige pour une meilleure appréciation du risque.</div>",
            unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # ── VII. DÉCLARATION & PROTECTION DES DONNÉES ──────────────────────
        st.markdown(
            '<div class="bia-sec"><div class="bia-lbl" style="background:#6C3483;">'
            'VII — Déclaration &amp; Protection des Données Personnelles</div>',
            unsafe_allow_html=True)
        st.markdown("""
        <div style='background:white;border:1.5px solid #DDE3EE;border-radius:8px;padding:12px 15px;font-size:11px;line-height:1.8;color:#2C3E50;max-height:200px;overflow-y:auto;'>
        <p>Je reconnais avoir reçu la notice d'information du produit et les conditions générales, en avoir pris connaissance, avoir reçu une information détaillée sur l'étendue, la définition des risques et des garanties proposées, et adhérer aux conditions de souscription. La date d'effet du contrat est indiquée sur les conditions particulières.</p>
        <p>J'accepte être contacté(e) par téléphone ou par mail à propos de ma demande d'assurance et de suites données.</p>
        <p>Je reconnais être informé(e) que les informations recueillies sont nécessaires à l'appréciation et au traitement de mon dossier d'adhésion et que les informations administratives font l'objet de traitements informatiques par AFG Assurances Bénin Vie ou ses mandataires pour les besoins de l'exécution de mon adhésion au contrat.</p>
        <p>Je soussigné(e), certifie exactes et sincères les informations renseignées dans le présent bulletin d'adhésion, n'avoir rien déclaré ou omis de déclarer qui puisse induire en erreur l'Assureur. Conformément à l'article 18 du code CIMA, la fausse déclaration intentionnelle est sanctionnée par la nullité du contrat. Les cotisations payées demeurent acquises à l'assureur.</p>
        <p><b>Protection des données personnelles :</b> Toute référence aux informations inclut les données et informations à caractère personnel que vous nous avez transmises. AFG Assurances Bénin Vie est responsable de la protection de ces données. Vous avez le droit de demander à recevoir une copie des données à caractère personnel vous concernant en notre possession.</p>
        <p><i>Attention ! Il est formellement interdit de remettre le bulletin d'adhésion signé au porteur ou non basée dans les mains des agents commerciaux. AFGVie décline toute responsabilité des conséquences qui en résulteraient.</i></p>
        </div>""", unsafe_allow_html=True)
        decl_c1, decl_c2 = st.columns(2)
        with decl_c1:
            decl_accept_cond = st.checkbox(
                "○ En cochant, j'accepte les conditions de souscription ci-dessus énumérées. *",
                key="decl_cond")
        with decl_c2:
            decl_accept_data = st.checkbox(
                "○ En cochant, je reconnais avoir lu et accepté la politique de protection des données personnelles. *",
                key="decl_data")
        st.markdown("</div>", unsafe_allow_html=True)

        # ── VIII. AUTORISATION DE PRÉLÈVEMENT ──────────────────────────────
        if _mode_rg.lower() in ["par prélèvement sur salaire", "par virement bancaire"] or True:
            st.markdown(
                '<div class="bia-sec"><div class="bia-lbl" style="background:#0A7B6C;">'
                'VIII — Autorisation de Prélèvement (si applicable)</div>',
                unsafe_allow_html=True)
            st.markdown(
                "<div style='background:#E8F8F5;border:1px solid #0A7B6C;border-radius:8px;"
                "padding:8px 13px;font-size:11.5px;color:#0A7B6C;margin-bottom:8px;'>"
                "Remplissez cette section uniquement si le mode de règlement est "
                "<b>virement bancaire</b> ou <b>prélèvement sur salaire</b>. "
                "Laissez vide sinon.</div>",
                unsafe_allow_html=True)

            prel_c1, prel_c2 = st.columns(2)
            with prel_c1:
                st.markdown("**NOM, PRÉNOMS ET ADRESSE DU DÉBITEUR**")
                prel_nom_deb = st.text_input("Nom et Prénoms du débiteur", placeholder="NOM PRÉNOM", key="prel_nom")
                prel_adr_deb = st.text_area("Adresse du débiteur", placeholder="Adresse complète", height=80, key="prel_adr")
                st.markdown("**COMPTE À DÉBITER**")
                pd1,pd2,pd3,pd4 = st.columns(4)
                with pd1: prel_ci_deb = st.text_input("Code interb.", placeholder="625", key="prel_cid")
                with pd2: prel_cg_deb = st.text_input("Code guichet", placeholder="01311", key="prel_cgd")
                with pd3: prel_nc_deb = st.text_input("N° compte", placeholder="00100000000", key="prel_ncd")
                with pd4: prel_cl_deb = st.text_input("Clé", placeholder="00", key="prel_cld")
            with prel_c2:
                st.markdown("**DÉSIGNATION DE L'ÉTABLISSEMENT TENEUR DU COMPTE À CRÉDITER**")
                prel_banq_cred = st.text_input("Banque créditrice", placeholder="AFG Assurances Bénin Vie / BIIC", key="prel_bc")
                prel_adr_cred  = st.text_input("Adresse de l'établissement", placeholder="Cadjèhoun, Cotonou", key="prel_adc")
                st.markdown("**COMPTE À CRÉDITER**")
                pc1,pc2,pc3,pc4 = st.columns(4)
                with pc1: prel_ci_cred = st.text_input("Code interb.", placeholder="625", key="prel_cic")
                with pc2: prel_cg_cred = st.text_input("Code guichet", placeholder="01311", key="prel_cgc")
                with pc3: prel_nc_cred = st.text_input("N° compte", placeholder="AFG001", key="prel_ncc")
                with pc4: prel_cl_cred = st.text_input("Clé", placeholder="00", key="prel_clc")

            prel_r1, prel_r2, prel_r3, prel_r4 = st.columns(4)
            with prel_r1: prel_mnt = st.text_input("Montant FCFA", placeholder="15 000", key="prel_mnt")
            with prel_r2: prel_freq= st.selectbox("Fréquence", ["","Mensuelle","Trimestrielle","Semestrielle","Annuelle"], key="prel_frq")
            with prel_r3: prel_eff = st.text_input("Effet", placeholder="01/01/2026", key="prel_eff")
            with prel_r4: prel_ech = st.text_input("Échéance", placeholder="01/01/2036", key="prel_ech")
            st.markdown(
                "<div style='font-size:10.5px;color:#5A6478;margin-top:6px;'>"
                "J'autorise l'établissement teneur de mon compte à prélever sur ce dernier, le montant indiqué "
                "au profit de AFG Assurances Bénin Vie. En cas de litige sur un prélèvement, je pourrai en faire "
                "suspendre l'exécution par simple demande à l'établissement teneur de mon compte.</div>",
                unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            prel_nom_deb=prel_adr_deb=prel_ci_deb=prel_cg_deb=prel_nc_deb=prel_cl_deb=""
            prel_banq_cred=prel_adr_cred=prel_ci_cred=prel_cg_cred=prel_nc_cred=prel_cl_cred=""
            prel_mnt=prel_freq=prel_eff=prel_ech=""

        # ── RAPPEL SIGNATURES (définies au-dessus hors formulaire) ───────────
        _sig_s_ok = st.session_state.get("_sig_souscr_ok", False)
        _sig_a_ok = st.session_state.get("_sig_ass_ok",    False)
        _sig_c_ok = st.session_state.get("_sig_cons_ok",   False)
        # Les variables sig_souscr, sig_ass, sig_cons sont définies HORS du form.
        # On les récupère depuis session_state via leur clé de file_uploader.
        sig_souscr = st.session_state.get("sig_s", None)
        sig_ass    = st.session_state.get("sig_a", None)
        sig_cons   = st.session_state.get("sig_c", None)
        st.markdown(
            f"<div style='background:{'#E8F8EE' if _sig_s_ok and _sig_a_ok and _sig_c_ok else '#FFF3CD'};"
            f"border:1px solid {'#1A7A4A' if _sig_s_ok and _sig_a_ok and _sig_c_ok else '#D4AC0D'};"
            f"border-radius:8px;padding:8px 12px;font-size:12px;'>"
            f"{'✅ Les 3 signatures sont chargées — formulaire prêt à être soumis.' if _sig_s_ok and _sig_a_ok and _sig_c_ok else '⚠️ Chargez les 3 signatures dans les zones au-dessus avant de valider.'}"
            f"</div>",
            unsafe_allow_html=True)

        # ── INFOS ADMINISTRATIVES ──────────────────────────────────────────
        st.markdown('<div class="bia-sec"><div class="bia-lbl">Informations Administratives</div>',unsafe_allow_html=True)
        adm1,adm2,adm3=st.columns(3)
        with adm1:
            ag_bia=st.selectbox("Agence BIA",AGENCES_AFG,key="adm_ag",help="Agence de traitement du BIA.")
        with adm2:
            # Pour une validation complète, le statut est forcé à "Validé"
            # Pour un brouillon, il sera écrasé en "Brouillon" à la sauvegarde
            st_bia=st.selectbox(
                "Statut BIA",
                ["Validé","En cours","En attente de documents","Suspendu","Annulé"],
                index=0,  # "Validé" sélectionné par défaut
                key="adm_st",
                help="Lors d'une validation complète (bouton ✅ VALIDER), le statut est automatiquement mis à 'Validé'. Le brouillon (💾) reste en 'Brouillon'.")
        with adm3:
            obs_=st.text_input("Observations",key="adm_ob")
        st.markdown("</div></div>",unsafe_allow_html=True)

        # ── BOUTONS : BROUILLON + VALIDER ─────────────────────────────────────
        st.markdown("<br>",unsafe_allow_html=True)
        st.markdown(
            "<div style='background:linear-gradient(135deg,#003366,#004D99);border-radius:12px;"
            "padding:14px 18px;border:1.5px solid rgba(201,162,39,0.45);margin-bottom:10px;'>"
            "<div style='color:#E8C84A;font-size:10px;font-weight:800;text-transform:uppercase;"
            "letter-spacing:.1em;margin-bottom:6px;'>📋 Enregistrement du Bulletin BIA</div>"
            "<div style='color:rgba(255,255,255,0.8);font-size:11.5px;line-height:1.7;'>"
            "💾 <b style='color:#E8C84A;'>Brouillon</b> — Sauvegarde immédiate sans validation "
            "(complétez plus tard depuis <i>Base BIA</i>). Seuls Nom, Prénoms et Cotisation sont requis.<br>"
            "✅ <b style='color:#4DFFE0;'>Valider le BIA</b> — Enregistre et <u>valide définitivement</u> "
            "le BIA · Statut automatiquement mis à <b style='color:#4DFFE0;'>VALIDÉ</b> · "
            "Déclenche les confettis et ballons 🎊"
            "</div></div>",
            unsafe_allow_html=True)
        btn_c1, btn_c2, btn_c3 = st.columns([1, 1.5, 1])
        with btn_c1:
            do_draft = st.form_submit_button(
                "💾  ENREGISTRER BROUILLON",
                use_container_width=True,
                help="Sauvegarde sans validation — complétez et validez depuis la Base BIA")
        with btn_c2:
            do_save = st.form_submit_button(
                "✅  VALIDER LE BIA  ▶▶  STATUT : VALIDÉ",
                use_container_width=True,
                type="primary",
                help="Valide et enregistre définitivement le BIA — statut = VALIDÉ — déclenche les ballons 🎊")
        with btn_c3:
            do_reset = st.form_submit_button(
                "🗑️  Effacer le formulaire",
                use_container_width=True,
                help="Réinitialiser tous les champs du formulaire BIA")

        if do_reset:
            st.session_state.bia_prod = None
            st.session_state.bia_ass_meme = True
            st.session_state.bia_mode_rg = ""
            for _sk in ["sig_s","sig_a","sig_c","_sig_souscr_ok","_sig_ass_ok","_sig_cons_ok"]:
                if _sk in st.session_state: del st.session_state[_sk]
            st.rerun()

        if do_draft or do_save:
            _is_draft = do_draft and not do_save
            # Récupérer l'état réactif depuis session_state
            _ass_meme_save = st.session_state.get("bia_ass_meme", True)
            _mode_rg_save  = st.session_state.get("bia_mode_rg", "")
            _mode_ref_save = st.session_state.get("bia_ref_mob",
                             st.session_state.get("bia_ref_chq",
                             st.session_state.get("bia_ref_vir",
                             st.session_state.get("bia_ref_prl",""))))

            errs=[]
            # Champs toujours requis (brouillon ET validation)
            if not c_nom.strip():  errs.append("Nom du souscripteur obligatoire")
            if not c_prn.strip():  errs.append("Prénoms du souscripteur obligatoires")
            if cotis < 100:        errs.append("Cotisation doit être ≥ 100 FCFA")

            # Champs requis seulement pour la validation complète
            if not _is_draft:
                if not c_tel.strip():   errs.append("Téléphone (cel.) souscripteur obligatoire")
                if not c_npi.strip():   errs.append("N°NPI/Passeport du souscripteur obligatoire")
                if not c_prof.strip():  errs.append("Profession du souscripteur obligatoire")
                if not _ass_meme_save:
                    if not st.session_state.get("as_nom","").strip(): errs.append("Nom de l'assuré obligatoire")
                    if not st.session_state.get("as_npi","").strip(): errs.append("NPI de l'assuré obligatoire")
                for qk,_,_,prec_lbl,is6 in QUESTIONS_MEDICALES:
                    if med_answers.get(qk,"")=="Oui" and not med_answers.get(f"{qk}_detail","").strip():
                        errs.append(f"Q.médicale {qk[-1]} : précisez la réponse OUI")
                if not decl_accept_cond: errs.append("Acceptez les conditions de souscription")
                if not decl_accept_data: errs.append("Acceptez la politique de protection des données")
                sig_souscr = st.session_state.get("sig_s", None)
                sig_ass    = st.session_state.get("sig_a", None)
                sig_cons   = st.session_state.get("sig_c", None)
                if not sig_souscr: errs.append("Signature du souscripteur obligatoire (photo)")
                if not sig_ass:    errs.append("Signature de l'assuré obligatoire (photo)")
                if not sig_cons:   errs.append("Signature du conseiller obligatoire (photo)")
            else:
                sig_souscr = st.session_state.get("sig_s", None)
                sig_ass    = st.session_state.get("sig_a", None)
                sig_cons   = st.session_state.get("sig_c", None)

            if errs:
                for e in errs: alert(f"Champ manquant : {e}","danger")
            else:
                bia_num=gen_bia()
                # Reconstituer les variables assuré pour la sauvegarde
                if _ass_meme_save:
                    _a_tit=c_tit; _a_nom=c_nom; _a_prn=c_prn; _a_ddn=c_ddn
                    _a_lieu=c_lieu; _a_nat=c_nat; _a_mat=c_mat; _a_prof=c_prof
                    _a_adr=c_adr; _a_bp=c_bp; _a_tel=c_tel; _a_fixe=c_fixe
                    _a_wapp=c_wapp; _a_eml=c_eml; _a_npi=c_npi
                else:
                    _a_tit=st.session_state.get("as_tit","")
                    _a_nom=st.session_state.get("as_nom","")
                    _a_prn=st.session_state.get("as_prn","")
                    _a_ddn_raw=st.session_state.get("as_ddn",date(1990,1,1))
                    _a_ddn=_a_ddn_raw if isinstance(_a_ddn_raw,date) else date(1990,1,1)
                    _a_lieu=st.session_state.get("as_lieu","")
                    _a_nat=st.session_state.get("as_nat","")
                    _a_mat=st.session_state.get("as_mat","")
                    _a_prof=st.session_state.get("as_prof","")
                    _a_adr=st.session_state.get("as_adr","")
                    _a_bp=st.session_state.get("as_bp","")
                    _a_tel=st.session_state.get("as_cel","")
                    _a_fixe=st.session_state.get("as_fixe","")
                    _a_wapp=st.session_state.get("as_wap","")
                    _a_eml=st.session_state.get("as_eml","")
                    _a_npi=st.session_state.get("as_npi","")

                data={
                    "numero_bia":bia_num,
                    "date_saisie":today.isoformat(),
                    "saisi_par":user["nom"],
                    "agence_saisie":agence_sel_bia or "",
                    "code_apporteur":code_apporteur or "",
                    "nom_apporteur":nom_apporteur or user.get("nom",""),
                    "realisateur":realisateur or "",
                    "type_contrat":str(pr["nom"]),
                    "code_produit":str(pr["code"]),
                    "groupe_produit":get_groupe(str(pr["code"])),
                    "deja_assure":deja_afg,
                    "num_contrat_existant":num_ct_exist or "",
                    "contractant_titre":c_tit or "",
                    "contractant_nom":c_nom.upper().strip(),
                    "contractant_prenom":c_prn.strip(),
                    "contractant_ddn":c_ddn.isoformat(),
                    "contractant_lieu_naissance":c_lieu or "",
                    "contractant_nationalite":c_nat or "",
                    "contractant_situation_mat":c_mat or "",
                    "contractant_profession":c_prof or "",
                    "contractant_adresse":c_adr or "",
                    "contractant_bp":c_bp or "",
                    "contractant_email":c_eml or "",
                    "contractant_whatsapp":c_wapp or "",
                    "contractant_tel_fixe":c_fixe or "",
                    "contractant_tel_cel":c_tel or "",
                    "contractant_npi":c_npi.upper().strip(),
                    "assure_meme":1 if _ass_meme_save else 0,
                    "assure_titre":_a_tit or "",
                    "assure_nom":(_a_nom.upper().strip() if _a_nom else ""),
                    "assure_prenom":(_a_prn.strip() if _a_prn else ""),
                    "assure_ddn":(_a_ddn.isoformat() if isinstance(_a_ddn,date) else ""),
                    "assure_lieu_naissance":_a_lieu or "",
                    "assure_nationalite":_a_nat or "",
                    "assure_situation_mat":_a_mat or "",
                    "assure_profession":_a_prof or "",
                    "assure_adresse":_a_adr or "",
                    "assure_bp":_a_bp or "",
                    "assure_email":_a_eml or "",
                    "assure_whatsapp":_a_wapp or "",
                    "assure_tel_fixe":_a_fixe or "",
                    "assure_tel_cel":_a_tel or "",
                    "assure_npi":(_a_npi.upper().strip() if _a_npi else ""),
                    "cotisation_fcfa":float(cotis),
                    "cotisation_lettres":cotis_lett or "",
                    "periodicite":perio,
                    "mode_reglement":_mode_rg_save,
                    "mode_ref_numero":_mode_ref_save or "",
                    "date_effet":dt_eff.isoformat(),
                    "duree_ans":int(dur),
                    "terme":terme_.isoformat(),
                    "option_garantie":option_gar,
                    "capital_terme":float(cap_terme),
                    "benef_vie":"Le souscripteur ou l'assuré",
                    "benef_deces":"Mon conjoint et mes enfants" if ben_conj else "",
                    "benef_autres":ben_autres or "",
                    "inv_repartition":inv_repartition or "",
                    "inv_fg_pct":int(inv_fg) if inv_fg else 0,
                    "inv_uc_pct":int(inv_uc) if inv_uc else 0,
                    "inv_fonds":inv_fonds or "",
                    # QUESTIONNAIRE MÉDICAL
                    "med_taille":med_taille or "",
                    "med_poids":med_poids or "",
                    "med_perte_poids":f"{med_perte} — {med_perte_detail}" if med_perte=="Oui" else med_perte,
                    "med_q1":med_answers.get("med_q1",""),
                    "med_q1_detail":med_answers.get("med_q1_detail",""),
                    "med_q2":med_answers.get("med_q2",""),
                    "med_q2_detail":med_answers.get("med_q2_detail",""),
                    "med_q3":med_answers.get("med_q3",""),
                    "med_q3_detail":med_answers.get("med_q3_detail",""),
                    "med_q4":med_answers.get("med_q4",""),
                    "med_q4_detail":med_answers.get("med_q4_detail",""),
                    "med_q5":med_answers.get("med_q5",""),
                    "med_q5_detail":med_answers.get("med_q5_detail",""),
                    "med_q6":med_answers.get("med_q6",""),
                    "med_q6_detail":med_answers.get("med_q6_detail",""),
                    "med_q6_nature":med_answers.get("med_q6_nature",""),
                    "med_q6_motif":med_answers.get("med_q6_motif",""),
                    "med_q7":med_answers.get("med_q7",""),
                    "med_q7_detail":med_answers.get("med_q7_detail",""),
                    # DÉCLARATION
                    "decl_accept_conditions":1 if decl_accept_cond else 0,
                    "decl_accept_donnees":1 if decl_accept_data else 0,
                    # AUTORISATION PRÉLÈVEMENT
                    "prel_nom_debiteur":st.session_state.get("prel_nom",""),
                    "prel_adresse_debiteur":st.session_state.get("prel_adr",""),
                    "prel_banque_debit":"",
                    "prel_code_inter_debit":st.session_state.get("prel_cid",""),
                    "prel_code_guichet_debit":st.session_state.get("prel_cgd",""),
                    "prel_num_compte_debit":st.session_state.get("prel_ncd",""),
                    "prel_cle_debit":st.session_state.get("prel_cld",""),
                    "prel_banque_credit":st.session_state.get("prel_bc",""),
                    "prel_code_inter_credit":st.session_state.get("prel_cic",""),
                    "prel_code_guichet_credit":st.session_state.get("prel_cgc",""),
                    "prel_num_compte_credit":st.session_state.get("prel_ncc",""),
                    "prel_cle_credit":st.session_state.get("prel_clc",""),
                    "prel_montant":st.session_state.get("prel_mnt",""),
                    "prel_frequence":st.session_state.get("prel_frq",""),
                    "prel_effet":st.session_state.get("prel_eff",""),
                    "prel_echeance":st.session_state.get("prel_ech",""),
                    "sig_souscripteur":img_to_blob(sig_souscr),
                    "sig_assure":img_to_blob(sig_ass),
                    "sig_conseiller":img_to_blob(sig_cons),
                    "sig_souscripteur_nom":f"{c_tit} {c_nom.upper()} {c_prn}",
                    "sig_assure_nom":f"{_a_tit} {(_a_nom.upper() if _a_nom else '')} {_a_prn}",
                    "sig_conseiller_nom":user["nom"],
                    "statut_bia":"Brouillon" if _is_draft else "Validé",
                    "observations":obs_ or "",
                }
                try:
                    conn=gc()
                    cols=", ".join(data.keys())
                    ph=", ".join(["?"]*len(data))
                    conn.execute(f"INSERT INTO bulletins_bia ({cols}) VALUES ({ph})",list(data.values()))
                    conn.commit(); conn.close()
                    # Réinitialiser les states réactifs
                    st.session_state.bia_prod=None
                    st.session_state.bia_ass_meme=True
                    st.session_state.bia_mode_rg=""
                    # Reset signature uploaders
                    for _sk in ["sig_s","sig_a","sig_c","_sig_souscr_ok","_sig_ass_ok","_sig_cons_ok"]:
                        if _sk in st.session_state: del st.session_state[_sk]
                    st.cache_data.clear()
                    if _is_draft:
                        st.info(
                            f"💾 **Brouillon enregistré — N° {bia_num}**\n\n"
                            f"Souscripteur : **{c_tit} {c_nom.upper()} {c_prn}**\n\n"
                            f"Produit : **{pr['nom']}** · Cotisation : **{fmt(cotis)} FCFA**\n\n"
                            f"➡️ Retrouvez ce brouillon dans **Base BIA** pour le compléter et le valider.")
                    else:
                        # ── ANIMATION COMPLÈTE : balloons natifs Streamlit + confettis CSS + message spectaculaire
                        st.balloons()
                        st.markdown(f"""
                        <div style="background:linear-gradient(135deg,#003366,#004D99);
                             border-radius:18px;padding:2.2rem 2rem;text-align:center;
                             margin:1.2rem 0;border:3px solid #C9A227;
                             box-shadow:0 12px 40px rgba(201,162,39,0.45);">
                          <div style="font-size:3.5rem;margin-bottom:0.6rem;
                               animation:pulse 0.8s infinite alternate;">🎊🎉🥳🎊🎉</div>
                          <div style="font-size:1.6rem;font-weight:900;color:#E8C84A;
                               margin-bottom:0.5rem;letter-spacing:0.02em;">
                            ✅ BIA VALIDÉ AVEC SUCCÈS !</div>
                          <div style="background:rgba(201,162,39,0.15);border:2px solid #C9A227;
                               border-radius:10px;display:inline-block;padding:6px 22px;
                               margin-bottom:0.8rem;">
                            <span style="font-size:1.2rem;font-weight:900;color:white;
                                 font-family:monospace;letter-spacing:0.1em;">{bia_num}</span>
                          </div>
                          <div style="font-size:1rem;color:rgba(255,255,255,0.9);
                               margin-bottom:0.3rem;font-weight:600;">
                            {c_tit} {c_nom.upper()} {c_prn}</div>
                          <div style="font-size:0.9rem;color:rgba(255,255,255,0.7);
                               margin-bottom:1rem;">{pr['nom']} · {fmt(cotis)} FCFA · {perio}</div>
                          <div style="display:flex;justify-content:center;gap:12px;
                               flex-wrap:wrap;font-size:0.82rem;">
                            <span style="background:rgba(26,122,74,0.3);color:#4DFFE0;
                                 border:1px solid #1A7A4A;border-radius:20px;padding:4px 12px;">
                              ✅ Questionnaire médical</span>
                            <span style="background:rgba(26,122,74,0.3);color:#4DFFE0;
                                 border:1px solid #1A7A4A;border-radius:20px;padding:4px 12px;">
                              ✅ Signatures enregistrées</span>
                            <span style="background:rgba(26,122,74,0.3);color:#4DFFE0;
                                 border:1px solid #1A7A4A;border-radius:20px;padding:4px 12px;">
                              ✅ Déclarations acceptées</span>
                            <span style="background:rgba(26,122,74,0.3);color:#4DFFE0;
                                 border:1px solid #1A7A4A;border-radius:20px;padding:4px 12px;">
                              ✅ Statut : VALIDÉ</span>
                          </div>
                        </div>
                        <style>
                        @keyframes pulse {{0%{{transform:scale(1)}}100%{{transform:scale(1.05)}}}}
                        @keyframes cfDrop {{
                          0%   {{transform:translateY(-20px) rotate(0deg)  scale(1);   opacity:1}}
                          80%  {{opacity:1}}
                          100% {{transform:translateY(110vh) rotate(720deg) scale(0.5);opacity:0}}
                        }}
                        .cf-piece {{
                          position:fixed;animation:cfDrop linear forwards;
                          z-index:99999;border-radius:3px;pointer-events:none;
                        }}
                        </style>
                        <script>
                        (function() {{
                          const colors = [
                            '#C9A227','#E8C84A','#003366','#0072CE',
                            '#1A7A4A','#4DFFE0','#C0392B','#ffffff','#FDECEA'
                          ];
                          const shapes = ['2px','4px','6px','8px','3px'];
                          for (let i = 0; i < 180; i++) {{
                            const p = document.createElement('div');
                            p.className = 'cf-piece';
                            const size = shapes[Math.floor(Math.random()*shapes.length)];
                            p.style.left        = (Math.random() * 100) + 'vw';
                            p.style.top         = '-25px';
                            p.style.width       = (parseFloat(size) + Math.random()*6) + 'px';
                            p.style.height      = (parseFloat(size) + Math.random()*10) + 'px';
                            p.style.background  = colors[Math.floor(Math.random()*colors.length)];
                            p.style.animationDuration  = (Math.random()*4 + 2.5) + 's';
                            p.style.animationDelay     = (Math.random()*2.5) + 's';
                            document.body.appendChild(p);
                            setTimeout(() => {{ if(p.parentNode) p.parentNode.removeChild(p); }}, 8000);
                          }}
                        }})();
                        </script>
                        """, unsafe_allow_html=True)
                        st.success(f"🎊 BIA **{bia_num}** validé et enregistré en base avec succès !")
                except Exception as ex:
                    alert(f"Erreur lors de l'enregistrement : {str(ex)}","danger")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — BASE BIA
# ═══════════════════════════════════════════════════════════════════════════════
elif "Base BIA" in nav:
    sth("Base de données des Bulletins BIA","REGISTRE COMPLET")
    df_b=pd.read_sql_query("SELECT * FROM bulletins_bia ORDER BY created_at DESC",gc())
    if df_b.empty:
        alert("Aucun BIA enregistré. Utilisez Saisie BIA pour commencer.","info"); st.stop()
    nb_b=len(df_b)
    ck1,ck2,ck3,ck4,ck5=st.columns(5)
    with ck1: kpi("Total BIA",str(nb_b),"tous bulletins","","📝")
    with ck2: kpi("Cotisations",fmt(df_b["cotisation_fcfa"].sum()),"total","gold","💰")
    with ck3:
        nv=len(df_b[df_b["statut_bia"]=="Validé"])
        kpi("Validés",str(nv),f"{nv/max(nb_b,1)*100:.0f}%","green","✅")
    with ck4: kpi("Agences",str(df_b["agence_saisie"].nunique()),"couvertes","teal","🏢")
    with ck5: kpi("Avec signatures",str(df_b["sig_souscripteur"].notna().sum()),"signés","","✍️")

    f1,f2,f3,f4=st.columns(4)
    with f1: fst=st.selectbox("Statut",["Tous","Brouillon","En cours","Validé","En attente de documents","Suspendu","Annulé"])
    with f2: fag=st.selectbox("Agence",["Toutes"]+sorted(df_b["agence_saisie"].dropna().unique().tolist()))
    with f3: fpr=st.selectbox("Produit",["Tous"]+sorted(df_b["type_contrat"].dropna().unique().tolist()))
    with f4: fsr=st.text_input("🔍 Rechercher (nom / N° BIA / code apporteur)")

    # ── Action rapide : Valider un brouillon ──────────────────────────────────
    nb_brouillons = len(df_b[df_b["statut_bia"]=="Brouillon"])
    if nb_brouillons > 0:
        alert(f"<b>{nb_brouillons} brouillon(s)</b> en attente de validation. Sélectionnez-en un ci-dessous pour le valider.",
              "warn")
        with st.expander(f"📋 Valider un brouillon ({nb_brouillons} en attente)", expanded=(nb_brouillons>0)):
            draft_df = df_b[df_b["statut_bia"]=="Brouillon"][["numero_bia","contractant_nom","contractant_prenom","type_contrat","cotisation_fcfa","date_saisie","saisi_par"]]
            for _,dr in draft_df.iterrows():
                dc1,dc2,dc3,dc4 = st.columns([3,1,1,1])
                with dc1:
                    st.markdown(
                        f"<div style='background:#FFF8E1;border-radius:8px;padding:8px 12px;"
                        f"border-left:3px solid #C9A227;font-size:12px;'>"
                        f"<b style='color:#003366;'>{dr['numero_bia']}</b> · "
                        f"{dr['contractant_nom']} {dr['contractant_prenom']} · "
                        f"{dr['type_contrat']} · {fmt(dr['cotisation_fcfa'])} · "
                        f"<span style='color:#5A6478;font-size:10.5px;'>{dr['date_saisie']}</span></div>",
                        unsafe_allow_html=True)
                with dc2:
                    if st.button("✅ Valider", key=f"val_{dr['numero_bia']}"):
                        try:
                            _c = gc()
                            _c.execute("UPDATE bulletins_bia SET statut_bia='Validé' WHERE numero_bia=?", (dr['numero_bia'],))
                            _c.commit(); _c.close()
                            st.cache_data.clear()
                            st.success(f"✅ BIA {dr['numero_bia']} validé !")
                            st.markdown("""
                            <style>@keyframes cfDrop{0%{transform:translateY(-10px) rotate(0);opacity:1}100%{transform:translateY(100vh) rotate(360deg);opacity:0}}.cf{position:fixed;width:8px;height:8px;animation:cfDrop linear 3s forwards;z-index:9999;border-radius:2px;}</style>
                            <script>(function(){const cols=['#C9A227','#003366','#1A7A4A','#E8C84A'];for(let i=0;i<80;i++){const p=document.createElement('div');p.className='cf';p.style.left=Math.random()*100+'vw';p.style.top='-10px';p.style.background=cols[i%4];p.style.animationDelay=Math.random()*1.5+'s';document.body.appendChild(p);setTimeout(()=>p.remove(),5000);}})()</script>
                            """, unsafe_allow_html=True)
                            st.balloons()
                            st.rerun()
                        except Exception as _e:
                            st.error(f"Erreur : {str(_e)}")
                with dc3:
                    if st.button("✏️ Modifier", key=f"mod_{dr['numero_bia']}"):
                        alert("Pour modifier, allez dans Saisie BIA et saisissez un nouveau BIA. La modification en place sera disponible prochainement.", "info")
                with dc4:
                    if st.button("🗑️ Supprimer", key=f"del_{dr['numero_bia']}"):
                        try:
                            _c = gc()
                            _c.execute("DELETE FROM bulletins_bia WHERE numero_bia=?", (dr['numero_bia'],))
                            _c.commit(); _c.close()
                            st.cache_data.clear()
                            st.warning(f"🗑️ Brouillon {dr['numero_bia']} supprimé.")
                            st.rerun()
                        except Exception as _e:
                            st.error(f"Erreur : {str(_e)}")
    dff=df_b.copy()
    if fst!="Tous": dff=dff[dff["statut_bia"]==fst]
    if fag!="Toutes": dff=dff[dff["agence_saisie"]==fag]
    if fpr!="Tous": dff=dff[dff["type_contrat"]==fpr]
    if fsr:
        fsr_up = fsr.upper()
        mask=(
            dff["contractant_nom"].str.upper().str.contains(fsr_up,na=False)|
            dff["contractant_prenom"].str.upper().str.contains(fsr_up,na=False)|
            dff["numero_bia"].str.upper().str.contains(fsr_up,na=False)|
            dff["code_apporteur"].str.upper().str.contains(fsr_up,na=False)|
            dff["nom_apporteur"].str.upper().str.contains(fsr_up,na=False)
        )
        dff=dff[mask]
    st.caption(f"Affichage {len(dff):,} / {nb_b:,} bulletin(s)")

    # ── Tableau principal ────────────────────────────────────────────────────
    cols_d=["numero_bia","date_saisie","contractant_nom","contractant_prenom",
            "contractant_tel_cel","code_apporteur","nom_apporteur",
            "type_contrat","cotisation_fcfa","periodicite",
            "mode_reglement","mode_ref_numero","date_effet","duree_ans",
            "statut_bia","agence_saisie","saisi_par"]
    labs_d=["N° BIA","Date","Nom","Prénoms","Tél.",
            "Code Apporteur","Nom Apporteur",
            "Produit","Cotisation (F)","Périodicité",
            "Mode règl.","N° Réf.","Date effet","Durée (ans)",
            "Statut","Agence","Agent"]
    disp=dff[[c for c in cols_d if c in dff.columns]].copy()
    disp.columns=labs_d[:len(disp.columns)]
    if "Cotisation (F)" in disp.columns:
        disp["Cotisation (F)"]=disp["Cotisation (F)"].apply(lambda v:f"{v:,.0f}" if pd.notna(v) else "0")
    st.dataframe(disp,use_container_width=True,hide_index=True,height=380)

    # ── Détail d'un BIA sélectionné (signatures + questionnaire médical) ─────
    st.markdown("---")
    sth("🔍 Détail complet d'un BIA","VISUALISATION SIGNATURES & MÉDICAL")
    bia_nums = dff["numero_bia"].dropna().tolist()
    if bia_nums:
        sel_bia = st.selectbox("Sélectionnez un BIA à consulter", bia_nums, key="sel_bia_detail")
        row_bia = dff[dff["numero_bia"]==sel_bia].iloc[0] if not dff[dff["numero_bia"]==sel_bia].empty else None
        if row_bia is not None:
            dtab1,dtab2,dtab3,dtab4 = st.tabs([
                "📋 Informations","🏥 Questionnaire médical","✍️ Signatures","💳 Prélèvement"])

            with dtab1:
                d1c1,d1c2,d1c3 = st.columns(3)
                fields_info = [
                    ("N° BIA","numero_bia"),("Date saisie","date_saisie"),("Agent","saisi_par"),
                    ("Code Apporteur","code_apporteur"),("Nom Apporteur","nom_apporteur"),("Agence","agence_saisie"),
                    ("Produit","type_contrat"),("Code produit","code_produit"),("Groupe","groupe_produit"),
                    ("Nom souscripteur","contractant_nom"),("Prénoms","contractant_prenom"),("Tél.","contractant_tel_cel"),
                    ("Profession","contractant_profession"),("NPI","contractant_npi"),("Adresse","contractant_adresse"),
                    ("Cotisation","cotisation_fcfa"),("Périodicité","periodicite"),("Mode règlement","mode_reglement"),
                    ("N° Référence","mode_ref_numero"),("Date effet","date_effet"),("Durée (ans)","duree_ans"),
                    ("Statut BIA","statut_bia"),("Option garantie","option_garantie"),("Observations","observations"),
                ]
                for i,(label,col) in enumerate(fields_info):
                    val = row_bia.get(col,"—") if col in row_bia.index else "—"
                    if col=="cotisation_fcfa" and pd.notna(val):
                        try: val = f"{float(val):,.0f} FCFA"
                        except: pass
                    with [d1c1,d1c2,d1c3][i%3]:
                        st.markdown(
                            f"<div style='background:#F4F6FA;border-radius:7px;padding:7px 10px;margin-bottom:5px;'>"
                            f"<div style='font-size:9px;color:#5A6478;text-transform:uppercase;'>{label}</div>"
                            f"<div style='font-size:12px;font-weight:700;color:#003366;'>{val if pd.notna(val) else '—'}</div>"
                            f"</div>", unsafe_allow_html=True)

            with dtab2:
                st.markdown("**Questionnaire médical — réponses de l'assuré(e)**")
                med_cols = [
                    ("Taille","med_taille"),("Poids","med_poids"),("Perte/prise de poids","med_perte_poids"),
                    ("Q1 — Maladie/séquelles 10 ans","med_q1"),("Précision Q1","med_q1_detail"),
                    ("Q2 — Arrêt travail 5 ans","med_q2"),("Précision Q2","med_q2_detail"),
                    ("Q3 — Traitement médical 5 ans","med_q3"),("Précision Q3","med_q3_detail"),
                    ("Q4 — Arrêt travail actuel","med_q4"),("Précision Q4","med_q4_detail"),
                    ("Q5 — Traitement en cours","med_q5"),("Précision Q5","med_q5_detail"),
                    ("Q6 — Hospitalisation/examen","med_q6"),("Précision Q6","med_q6_detail"),
                    ("Nature Q6","med_q6_nature"),("Motif Q6","med_q6_motif"),
                    ("Q7 — Maladies graves","med_q7"),("Précision Q7","med_q7_detail"),
                ]
                for label, col in med_cols:
                    if col in row_bia.index:
                        val = row_bia[col]
                        if pd.notna(val) and str(val).strip():
                            color = "#C0392B" if str(val).strip().upper()=="OUI" else "#1A7A4A" if str(val).strip().upper()=="NON" else "#003366"
                            st.markdown(
                                f"<div style='display:flex;gap:8px;padding:4px 0;border-bottom:1px solid #EEF2F7;'>"
                                f"<span style='font-size:11px;color:#5A6478;min-width:200px;'>{label}</span>"
                                f"<span style='font-size:11.5px;font-weight:700;color:{color};'>{val}</span></div>",
                                unsafe_allow_html=True)
                # Déclarations
                st.markdown("<br>**Déclarations :**", unsafe_allow_html=True)
                for label, col in [("Conditions acceptées","decl_accept_conditions"),("Données personnelles acceptées","decl_accept_donnees")]:
                    if col in row_bia.index:
                        val = "✅ Oui" if row_bia[col]==1 else "❌ Non"
                        st.markdown(f"**{label} :** {val}")

            with dtab3:
                st.markdown("**Signatures photographiées**")
                sig_c1,sig_c2,sig_c3 = st.columns(3)
                for col_sig, caption, col_nom in [
                    ("sig_souscripteur","📋 Signature Souscripteur","sig_souscripteur_nom"),
                    ("sig_assure","📋 Signature Assuré(e)","sig_assure_nom"),
                    ("sig_conseiller","📋 Signature Conseiller","sig_conseiller_nom"),
                ]:
                    target = [sig_c1,sig_c2,sig_c3][["sig_souscripteur","sig_assure","sig_conseiller"].index(col_sig)]
                    with target:
                        st.markdown(f"**{caption}**")
                        nom_sig = row_bia.get(col_nom,"") if col_nom in row_bia.index else ""
                        if nom_sig and pd.notna(nom_sig):
                            st.caption(str(nom_sig))
                        blob = row_bia.get(col_sig,None) if col_sig in row_bia.index else None
                        if blob is not None and not (isinstance(blob,float) and pd.isna(blob)):
                            try:
                                img_data = bytes(blob)
                                st.image(img_data, use_container_width=True)
                            except Exception:
                                st.info("Image disponible mais non prévisualisable ici.")
                        else:
                            st.markdown(
                                "<div style='border:2px dashed #DDE3EE;border-radius:8px;"
                                "padding:20px;text-align:center;color:#5A6478;font-size:12px;'>"
                                "Aucune signature enregistrée</div>", unsafe_allow_html=True)

            with dtab4:
                st.markdown("**Autorisation de prélèvement**")
                prel_fields = [
                    ("Nom débiteur","prel_nom_debiteur"),("Adresse débiteur","prel_adresse_debiteur"),
                    ("Code interbancaire débit","prel_code_inter_debit"),("Code guichet débit","prel_code_guichet_debit"),
                    ("N° compte débit","prel_num_compte_debit"),("Clé débit","prel_cle_debit"),
                    ("Banque créditrice","prel_banque_credit"),("Code interb. crédit","prel_code_inter_credit"),
                    ("Code guichet crédit","prel_code_guichet_credit"),("N° compte crédit","prel_num_compte_credit"),
                    ("Montant","prel_montant"),("Fréquence","prel_frequence"),
                    ("Effet","prel_effet"),("Échéance","prel_echeance"),
                ]
                prel_c1, prel_c2 = st.columns(2)
                for i,(label,col) in enumerate(prel_fields):
                    if col in row_bia.index:
                        val = row_bia[col]
                        if pd.notna(val) and str(val).strip():
                            with (prel_c1 if i%2==0 else prel_c2):
                                st.markdown(
                                    f"<div style='background:#F4F6FA;border-radius:7px;padding:7px 10px;margin-bottom:5px;'>"
                                    f"<div style='font-size:9px;color:#5A6478;text-transform:uppercase;'>{label}</div>"
                                    f"<div style='font-size:12px;font-weight:700;color:#003366;'>{val}</div>"
                                    f"</div>", unsafe_allow_html=True)

    # ── Exports ─────────────────────────────────────────────────────────────
    st.markdown("---")
    dl1,dl2,dl3=st.columns(3)
    with dl1:
        csv_b=dff.drop(columns=["sig_souscripteur","sig_assure","sig_conseiller"],errors="ignore").to_csv(index=False,encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button("📥 Télécharger CSV",csv_b,file_name=f"AFG_BIA_{today.isoformat()}.csv",mime="text/csv",use_container_width=True)
    with dl2:
        buf_xl=io.BytesIO()
        with pd.ExcelWriter(buf_xl,engine="openpyxl") as wr:
            dff.drop(columns=["sig_souscripteur","sig_assure","sig_conseiller"],errors="ignore").to_excel(wr,index=False,sheet_name="BIA")
        st.download_button("📥 Télécharger Excel",buf_xl.getvalue(),file_name=f"AFG_BIA_{today.isoformat()}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
    with dl3:
        js_=dff.drop(columns=["sig_souscripteur","sig_assure","sig_conseiller"],errors="ignore").to_json(orient="records",force_ascii=False,indent=2)
        st.download_button("📥 Télécharger JSON",js_.encode("utf-8"),file_name=f"AFG_BIA_{today.isoformat()}.json",mime="application/json",use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — ACCUEIL & KPIs (données réelles portefeuille + BIA temps réel) v14
# ═══════════════════════════════════════════════════════════════════════════════
elif "Accueil" in nav:
    # ── BIA LIVE (ttl=0 → rechargé à chaque validation) ─────────────────────
    nb_bia_live = pd.read_sql_query("SELECT COUNT(*) as n FROM bulletins_bia", gc())["n"].iloc[0]
    cot_live    = pd.read_sql_query("SELECT COALESCE(SUM(cotisation_fcfa),0) as s FROM bulletins_bia", gc())["s"].iloc[0]
    nb_bia_val  = pd.read_sql_query("SELECT COUNT(*) as n FROM bulletins_bia WHERE statut_bia='Validé'", gc())["n"].iloc[0]
    nb_bia_auj  = pd.read_sql_query(
        "SELECT COUNT(*) as n FROM bulletins_bia WHERE date_saisie=?", gc(),
        params=(today.isoformat(),))["n"].iloc[0]

    PR = PORT_REEL  # alias court

    # ── Bannière PDG ──────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,{NAVY},{BLUE});border-radius:14px;
         padding:1.3rem 1.8rem;margin-bottom:1rem;border-left:5px solid {GOLD};">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:2rem;flex-wrap:wrap;">
        <div>
          <div style="color:{GOLDL};font-size:9px;font-weight:700;text-transform:uppercase;
               letter-spacing:.12em;margin-bottom:4px;">AFG Assurances Bénin Vie — PDG Dashboard v14 · Données réelles 31/12/2025</div>
          <div style="color:white;font-size:1.3rem;font-weight:900;line-height:1.2;margin-bottom:4px;">
            À AFG Assurances Bénin Vie, nous avons pensé à vous !</div>
          <div style="color:rgba(255,255,255,0.7);font-size:12px;">
            Portefeuille réel : <b style="color:{GOLDL}">{PR['total']:,} polices</b> ·
            {PR['actif']:,} actives · {PR['resilie']:,} résiliées ·
            {today.strftime('%A %d %B %Y').capitalize()}</div>
        </div>
        <div style="display:flex;gap:9px;flex-wrap:wrap;">
          <div style="background:white;border-radius:10px;padding:10px 14px;text-align:center;min-width:110px;">
            <div style="font-size:1.5rem;font-weight:900;color:#003366;">{PR['total']:,}</div>
            <div style="font-size:9px;color:#5A6478;">Polices totales</div>
          </div>
          <div style="background:rgba(255,255,255,.12);border:1px solid rgba(201,162,39,.4);
               border-radius:10px;padding:10px 14px;text-align:center;min-width:110px;">
            <div style="font-size:1.5rem;font-weight:900;color:#4CAF50;">{PR['actif']:,}</div>
            <div style="font-size:9px;color:rgba(255,255,255,.6);">Polices actives</div>
          </div>
          <div style="background:rgba(255,255,255,.12);border:1px solid rgba(201,162,39,.4);
               border-radius:10px;padding:10px 14px;text-align:center;min-width:110px;">
            <div style="font-size:1.5rem;font-weight:900;color:#E8C84A;">{nb_bia_live}</div>
            <div style="font-size:9px;color:rgba(255,255,255,.6);">BIA saisis (live ⟳)</div>
          </div>
          <div style="background:rgba(255,255,255,.12);border:1px solid rgba(201,162,39,.4);
               border-radius:10px;padding:10px 14px;text-align:center;min-width:110px;">
            <div style="font-size:1.2rem;font-weight:900;color:#4DFFE0;">{nb_bia_val}</div>
            <div style="font-size:9px;color:rgba(255,255,255,.6);">BIA validés ✅</div>
          </div>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── ONGLETS : PORTEFEUILLE RÉEL | BIA LIVE | RISQUES | IMPORT EXCEL ──────
    tab_port, tab_bia, tab_risk, tab_imp = st.tabs([
        "📊 Portefeuille Réel (42 323 polices)",
        "📝 BIA Temps Réel",
        "⚠️ Risques Compagnie",
        "📥 Import Excel Externe",
    ])

    # ─────────────── ONGLET 1 : PORTEFEUILLE RÉEL ────────────────────────────
    with tab_port:
        sth(f"📊 KPIs Portefeuille — Données réelles AFG", "PORTEFEUILLE 31/12/2025")

        # Sélecteur d'années dynamique : si pf_ext importé → on filtre DATESOUS,
        # sinon on utilise les snapshots statiques PORT_REEL (toutes années).
        pf_ext_acc = st.session_state.get("portefeuille_ext", None)
        yr_port = year_selector("yr_port_acc",
            "📅 Filtrer le portefeuille par année de souscription (DATESOUS)")

        # ── Calcul KPIs dynamiques ────────────────────────────────────────────
        if pf_ext_acc is not None and "DATESOUS" in pf_ext_acc.columns:
            df_pp = filter_pf_by_year(pf_ext_acc.copy(), yr_port)
            tot_pp = len(df_pp)
            actif_pp = (df_pp.get("ETAT_POLICE","")=="ACTIF").sum() if "ETAT_POLICE" in df_pp.columns else 0
            resil_pp = (df_pp.get("ETAT_POLICE","")=="RESILIE").sum() if "ETAT_POLICE" in df_pp.columns else 0
            inact_pp = (df_pp.get("ETAT_POLICE","")=="INACTIF").sum() if "ETAT_POLICE" in df_pp.columns else 0
            echu_pp  = (df_pp.get("ETAT_POLICE","")=="ECHU").sum()    if "ETAT_POLICE" in df_pp.columns else 0
            susp_pp  = (df_pp.get("ETAT_POLICE","")=="SUSPENDU").sum() if "ETAT_POLICE" in df_pp.columns else 0
            ca_tot_pp = float(df_pp["MONTENCA"].sum()) if "MONTENCA" in df_pp.columns else 0
            ca_act_pp = float(df_pp[df_pp.get("ETAT_POLICE","")=="ACTIF"]["MONTENCA"].sum()) if ("MONTENCA" in df_pp.columns and "ETAT_POLICE" in df_pp.columns) else 0
            nb_comm_pp = df_pp["NOM_APP"].nunique() if "NOM_APP" in df_pp.columns else 0
            nb_clients_pp = df_pp["NOM_ASSU"].nunique() if "NOM_ASSU" in df_pp.columns else 0
            tx_actif_pp = actif_pp/max(tot_pp,1)*100
            tx_resil_pp = resil_pp/max(tot_pp,1)*100
            ticket_moy = ca_tot_pp/max(tot_pp,1)
            ticket_act = ca_act_pp/max(actif_pp,1)
            arpu = ca_tot_pp/max(nb_clients_pp,1)
            label_yr = yr_label(yr_port)
            source_lbl = "Portefeuille Excel importé · filtré DATESOUS"
        else:
            df_pp = None
            tot_pp = PR['total']; actif_pp = PR['actif']; resil_pp = PR['resilie']
            inact_pp = PR['inactif']; echu_pp = PR['echu']; susp_pp = PR['suspendu']
            ca_tot_pp = PR['ca_total']; ca_act_pp = PR['ca_actifs']
            nb_comm_pp = PR['nb_comm']; nb_clients_pp = 0
            tx_actif_pp = PR['tx_actif']; tx_resil_pp = PR['tx_resil']
            ticket_moy = ca_tot_pp/max(tot_pp,1); ticket_act = ca_act_pp/max(actif_pp,1)
            arpu = 0
            label_yr = "Snapshot 31/12/2025"
            source_lbl = "Snapshot statique (importez l'Excel pour activer le filtre par année)"

        st.caption(f"📌 Source : {source_lbl} · Période : **{label_yr}**")

        # KPIs principaux (rang 1)
        k1,k2,k3,k4,k5,k6 = st.columns(6)
        with k1: kpi("📋 Total polices",f"{tot_pp:,}","portefeuille filtré","gold","")
        with k2: kpi("✅ Polices actives",f"{actif_pp:,}",f"{tx_actif_pp:.1f}% du total","green","")
        with k3: kpi("📉 Polices résiliées",f"{resil_pp:,}",
                    f"{tx_resil_pp:.1f}%" + (" ⚠️" if tx_resil_pp>25 else ""),
                    "red" if tx_resil_pp>25 else "amber","")
        with k4: kpi("💰 Encaissements actifs",fmt(ca_act_pp),"polices ACTIF","teal","")
        with k5: kpi("💳 CA total",fmt(ca_tot_pp),"tous statuts","gold","")
        with k6: kpi("👥 Commerciaux",f"{nb_comm_pp:,}","apporteurs distincts","","")

        # KPIs avancés (rang 2)
        k7,k8,k9,k10,k11,k12 = st.columns(6)
        with k7: kpi("👤 Clients distincts",f"{nb_clients_pp:,}" if nb_clients_pp else "—","NOM_ASSU uniques","","")
        with k8: kpi("🎫 Ticket moyen",fmt(ticket_moy),"par police","gold","")
        with k9: kpi("💎 Ticket actif moy.",fmt(ticket_act),"par police active","teal","")
        with k10: kpi("📈 ARPU",fmt(arpu) if arpu else "—","encaissement / client","gold","")
        with k11: kpi("😴 Inactifs",f"{inact_pp:,}",f"{inact_pp/max(tot_pp,1)*100:.1f}%","amber","")
        with k12: kpi("📅 Échus",f"{echu_pp:,}",f"{echu_pp/max(tot_pp,1)*100:.1f}%","","")

        # ── Graphiques répartitions ───────────────────────────────────────────
        c1,c2,c3 = st.columns(3)
        with c1:
            labels_s = ["Actif","Résilié","Inactif","Échu","Suspendu"]
            vals_s   = [actif_pp,resil_pp,inact_pp,echu_pp,susp_pp]
            fig_s = px.pie(values=vals_s, names=labels_s, hole=0.42,
                color_discrete_sequence=[GREEN,RED,AMBER,NAVY,GOLD])
            fig_s.update_traces(textinfo="percent+label", textfont_size=10)
            chl(fig_s,290,f"🔵 Répartition statuts — {label_yr}")
            st.plotly_chart(fig_s, use_container_width=True)
        with c2:
            if df_pp is not None and "SEXE_ASSU" in df_pp.columns:
                gn = df_pp["SEXE_ASSU"].astype(str).str.upper().value_counts()
                h = int(gn.get("M",0)+gn.get("MASCULIN",0))
                f = int(gn.get("F",0)+gn.get("FEMININ",0)+gn.get("FÉMININ",0))
            else:
                h = PR['genre']['M']; f = PR['genre']['F']
            fig_g = px.pie(values=[h,f], names=["Hommes","Femmes"], hole=0.42,
                color_discrete_sequence=[BLUEL,GOLD])
            fig_g.update_traces(textinfo="percent+value", textfont_size=10)
            chl(fig_g,290,"👥 Répartition par genre")
            st.plotly_chart(fig_g, use_container_width=True)
        with c3:
            if df_pp is not None and "PERIODICITE" in df_pp.columns:
                per = df_pp["PERIODICITE"].astype(str).value_counts().to_dict()
            else:
                per = PR["periodicite"]
            fig_p = go.Figure(go.Bar(
                x=list(per.values()), y=list(per.keys()), orientation='h',
                marker_color=BLUEL, text=[f"{v:,}" for v in per.values()]))
            fig_p.update_traces(textposition='outside')
            chl(fig_p,290,"📅 Périodicité des cotisations")
            st.plotly_chart(fig_p, use_container_width=True)

        # ── Évolution annuelle (toujours sur l'historique COMPLET) ────────────
        sth("📈 Évolution annuelle des souscriptions","TENDANCE PORTEFEUILLE")
        if pf_ext_acc is not None and "DATESOUS" in pf_ext_acc.columns:
            df_h = pf_ext_acc.copy()
            df_h["ANNEE"] = pd.to_datetime(df_h["DATESOUS"], errors="coerce").dt.year
            ev_h = df_h.groupby("ANNEE").agg(
                nb=("DATESOUS","count"),
                ca=("MONTENCA","sum") if "MONTENCA" in df_h.columns else ("DATESOUS","count")
            ).reset_index().dropna()
            ev_h = ev_h[ev_h["ANNEE"].between(1996,2026)]
            ann_keys = ev_h["ANNEE"].astype(int).tolist()
            ann_vals = ev_h["nb"].tolist()
            ann_ca   = ev_h["ca"].tolist()
        else:
            ann_data = PR["annuel"]
            ann_keys = list(ann_data.keys()); ann_vals = list(ann_data.values()); ann_ca = ann_vals

        fig_ann = make_subplots(specs=[[{"secondary_y":True}]])
        # Surligner les années sélectionnées
        sel_years = []
        if isinstance(yr_port, list): sel_years = [int(y) for y in yr_port if str(y).isdigit()]
        bar_colors = [GOLD if (y in sel_years or not sel_years and y>=2024) else BLUEL for y in ann_keys]
        fig_ann.add_bar(x=ann_keys, y=ann_vals, name="📋 Souscriptions",
            marker_color=bar_colors, text=ann_vals, textposition="outside", secondary_y=False)
        if any(ann_ca):
            fig_ann.add_scatter(x=ann_keys, y=ann_ca, name="💰 Encaissements",
                line=dict(color=RED,width=2.5), mode="lines+markers", secondary_y=True)
        fig_ann.update_yaxes(title_text="Nb contrats", secondary_y=False)
        fig_ann.update_yaxes(title_text="Encaissements (FCFA)", secondary_y=True, showgrid=False)
        chl(fig_ann,340,"📈 Évolution historique — souscriptions & encaissements")
        st.plotly_chart(fig_ann, use_container_width=True)

        # ── Stats produits (filtrés par année) ────────────────────────────────
        sth(f"🛒 Statistiques par produit — {label_yr}","DÉTAIL CATÉGORIES")
        if df_pp is not None and "LIBECATE" in df_pp.columns:
            stp = df_pp.groupby("LIBECATE").agg(
                Total=("LIBECATE","count"),
                Actifs=("ETAT_POLICE", lambda x:(x=="ACTIF").sum()) if "ETAT_POLICE" in df_pp.columns else ("LIBECATE","count"),
                Resilies=("ETAT_POLICE", lambda x:(x=="RESILIE").sum()) if "ETAT_POLICE" in df_pp.columns else ("LIBECATE","count"),
                CA=("MONTENCA","sum") if "MONTENCA" in df_pp.columns else ("LIBECATE","count"),
            ).reset_index()
            stp["Tx résil."] = (stp["Resilies"]/stp["Total"].clip(1)*100).round(1)
            stp["Tx résil."] = stp["Tx résil."].apply(lambda r: f"{'🔴' if r>50 else ('🟡' if r>25 else '🟢')} {r:.1f}%")
            stp["CA"] = stp["CA"].apply(fmt)
            stp = stp.sort_values("Total", ascending=False).rename(columns={"LIBECATE":"Produit"})
            st.dataframe(stp, use_container_width=True, hide_index=True)
        else:
            prods_rows = []
            for p in PR["produits"]:
                tx_r = p["resilie"]/max(p["total"],1)*100
                tx_col = "🔴" if tx_r>50 else ("🟡" if tx_r>25 else "🟢")
                prods_rows.append({"Code":p["code"],"Produit":p["nom"],
                    "Total":f"{p['total']:,}","Actifs":f"{p['actif']:,}",
                    "Résiliés":f"{p['resilie']:,}","Tx résil.":f"{tx_col} {tx_r:.1f}%",
                    "CA":fmt(p["ca"]),"Cotisations":fmt(p["coti"])})
            st.dataframe(pd.DataFrame(prods_rows), use_container_width=True, hide_index=True)

        # ── Top villes (filtrées) ─────────────────────────────────────────────
        sth(f"🗺️ Top 13 villes (LIBEVILL) — {label_yr}","RÉSEAU")
        if df_pp is not None and "LIBEVILL" in df_pp.columns:
            vv = df_pp.groupby("LIBEVILL").size().reset_index(name="nb").sort_values("nb",ascending=False).head(13)
            v_sorted = list(zip(vv["LIBEVILL"].tolist(), vv["nb"].tolist()))
        else:
            villes = PR["villes_actif"]
            v_sorted = sorted(villes.items(), key=lambda x:-x[1])
        fig_v = go.Figure(go.Bar(
            x=[v[1] for v in v_sorted], y=[v[0] for v in v_sorted],
            orientation='h', marker_color=BLUEL,
            text=[f"{v[1]:,}" for v in v_sorted]))
        fig_v.update_traces(textposition='outside')
        chl(fig_v,380,f"📍 Polices par ville — Bénin · {label_yr}")
        st.plotly_chart(fig_v, use_container_width=True)

        # ── Top 10 commerciaux (filtrés) ──────────────────────────────────────
        sth(f"🏆 Top 10 commerciaux — {label_yr}","CLASSEMENT FILTRÉ")
        if df_pp is not None and "NOM_APP" in df_pp.columns:
            tc = df_pp.groupby(["NOM_APP","CODEAPPO"] if "CODEAPPO" in df_pp.columns else ["NOM_APP"]).agg(
                Polices=("NOM_APP","count"),
                CA=("MONTENCA","sum") if "MONTENCA" in df_pp.columns else ("NOM_APP","count"),
            ).reset_index().sort_values("Polices",ascending=False).head(10)
            medals = ["🥇","🥈","🥉"] + [""]*7
            tc.insert(0,"Rang",[f"{medals[i]} {i+1}" for i in range(len(tc))])
            tc["CA"] = tc["CA"].apply(fmt)
            tc.columns = [c if c not in ["NOM_APP","CODEAPPO"] else ("Nom apporteur" if c=="NOM_APP" else "Code") for c in tc.columns]
            st.dataframe(tc, use_container_width=True, hide_index=True)
        else:
            tc_rows = []
            medals = ["🥇","🥈","🥉"] + [""] * 7
            for i,(nom,code,nb_c) in enumerate(PR["top_comm"]):
                tc_rows.append({"Rang":f"{medals[i]} {i+1}","Nom":nom,"Code":code,"Polices":f"{nb_c:,}"})
            st.dataframe(pd.DataFrame(tc_rows), use_container_width=True, hide_index=True)

        # ── Banques ───────────────────────────────────────────────────────────
        sth("🏦 Domiciliation bancaire","PORTEFEUILLE")
        if df_pp is not None and "LIBEBANQ" in df_pp.columns:
            bb = df_pp["LIBEBANQ"].dropna().astype(str).value_counts().head(10).to_dict()
            banks = bb if bb else PR["banques"]
        else:
            banks = PR["banques"]
        fig_b = px.pie(values=list(banks.values()), names=list(banks.keys()),
            hole=0.42, color_discrete_sequence=[NAVY,BLUEL,BLUE,TEAL,GREEN,GOLD,AMBER,RED])
        fig_b.update_traces(textinfo="percent+label", textfont_size=10)
        chl(fig_b,300,f"🏦 Répartition par banque · {label_yr}")
        st.plotly_chart(fig_b, use_container_width=True)


    # ─────────────── ONGLET 2 : BIA LIVE ─────────────────────────────────────
    with tab_bia:
        sth("📝 KPIs BIA — Actualisés en temps réel (ttl=0)","LIVE ⟳")
        alert(f"Les KPIs BIA se rechargent à chaque validation. Dernière actualisation : {datetime.now().strftime('%H:%M:%S')}","info")
        bk1,bk2,bk3,bk4 = st.columns(4)
        with bk1: kpi("📝 BIA total",str(nb_bia_live),"depuis ouverture","gold","")
        with bk2: kpi("✅ BIA validés",str(nb_bia_val),f"{nb_bia_val/max(nb_bia_live,1)*100:.0f}% validés","green","")
        with bk3: kpi("💰 Cotisations",fmt(cot_live),"total BIA","teal","")
        with bk4: kpi("📅 BIA aujourd'hui",str(nb_bia_auj),today.strftime("%d/%m/%Y"),"","")
        if st.button("🔄 Forcer l'actualisation des KPIs BIA", key="btn_refresh_bia"):
            st.cache_data.clear(); st.rerun()

        # Tableau BIA récents
        df_bia_acc = pd.read_sql_query(
            "SELECT numero_bia,date_saisie,contractant_nom,contractant_prenom,type_contrat,groupe_produit,"
            "cotisation_fcfa,periodicite,statut_bia,agence_saisie,nom_apporteur,code_apporteur "
            "FROM bulletins_bia ORDER BY created_at DESC LIMIT 20", gc())
        if not df_bia_acc.empty:
            df_bia_acc["cotisation_fcfa"] = df_bia_acc["cotisation_fcfa"].apply(fmt)
            st.dataframe(df_bia_acc.rename(columns={
                "numero_bia":"N° BIA","date_saisie":"Date","contractant_nom":"Nom",
                "contractant_prenom":"Prénoms","type_contrat":"Produit","groupe_produit":"Groupe",
                "cotisation_fcfa":"Cotisation","periodicite":"Périodicité","statut_bia":"Statut",
                "agence_saisie":"Agence","nom_apporteur":"Apporteur","code_apporteur":"Code app.",
            }), use_container_width=True, hide_index=True, height=400)
        else:
            alert("Aucun BIA enregistré pour l'instant. Utilisez la page Saisie BIA.","info")

    # ─────────────── ONGLET 3 : RISQUES ──────────────────────────────────────
    with tab_risk:
        sth("⚠️ Surveillance des Risques — AFG Assurances Bénin Vie","RISK MANAGEMENT")
        PR = PORT_REEL
        r1,r2,r3,r4 = st.columns(4)
        tx_resil_pr = PR['tx_resil']
        with r1:
            c_r = "red" if tx_resil_pr>50 else ("amber" if tx_resil_pr>25 else "green")
            kpi("📉 Taux résiliation",f"{tx_resil_pr:.1f}%",
                "🚨 CRITIQUE (>50%)" if tx_resil_pr>50 else ("⚠️ Élevé" if tx_resil_pr>25 else "✅ Normal"),c_r,"")
        with r2:
            kpi("✅ Taux rétention",f"{PR['tx_actif']:.1f}%","polices actives","green" if PR['tx_actif']>50 else "red","")
        with r3:
            kpi("💰 CA portefeuille",fmt(PR['ca_total']),"encaissements totaux","gold","")
        with r4:
            kpi("💳 CA actifs",fmt(PR['ca_actifs']),"polices actives seulement","teal","")

        alert(f"""
        <b>Risques identifiés :</b><br>
        🔴 <b>Taux de résiliation {PR['tx_resil']:.1f}%</b> — très élevé, au-dessus de la norme CIMA (seuil alerte 25%).
        Action requise : campagne de fidélisation, révision des produits Épargne Crédit et Horizon Retraite.<br>
        🟡 <b>{PR['inactif']:,} polices inactives</b> — à relancer pour éviter des résiliations définitives.<br>
        🟡 <b>{PR['echu']:,} polices échues</b> — à renouveler ou clôturer.<br>
        🟢 <b>DOKOUNTCHE MULTISUPPORTS</b> : taux de résiliation très faible (3.9%) — produit phare à promouvoir.
        ""","warn")

        # Risque par produit
        sth("📊 Risque de résiliation par produit","ANALYSE PRODUITS")
        prod_risk = [(p["nom"], p["resilie"]/max(p["total"],1)*100, p["total"], p["actif"])
                     for p in PR["produits"] if p["total"]>0]
        prod_risk.sort(key=lambda x:-x[1])
        df_risk = pd.DataFrame(prod_risk, columns=["Produit","Tx résil. %","Total","Actifs"])
        fig_r = go.Figure(go.Bar(
            x=df_risk["Tx résil. %"], y=df_risk["Produit"], orientation='h',
            text=[f"{v:.1f}%" for v in df_risk["Tx résil. %"]],
            marker_color=[RED if v>50 else (AMBER if v>25 else GREEN) for v in df_risk["Tx résil. %"]]))
        fig_r.update_traces(textposition='outside')
        fig_r.add_vline(x=25, line_dash="dash", line_color=AMBER, annotation_text="Seuil alerte 25%")
        fig_r.add_vline(x=50, line_dash="dash", line_color=RED, annotation_text="Seuil critique 50%")
        chl(fig_r,380,"📉 Taux de résiliation par produit — ROUGE = critique")
        st.plotly_chart(fig_r, use_container_width=True)

    # ─────────────── ONGLET 4 : IMPORT EXCEL ─────────────────────────────────
    with tab_imp:
        sth("📥 Connexion portefeuille Excel externe","MISE À JOUR DONNÉES")
        alert("""Importez le fichier Excel exporté depuis votre logiciel de gestion (ex : Portefeuille_non_deces.xlsx).
        Les colonnes attendues : <b>ETAT_POLICE, LIBECATE, MONTENCA, COTI_PERIODIQUE, NOM_APP, CODEAPPO, LIBEVILL…</b>
        Chaque import met à jour les KPIs <b>instantanément</b>.""","info")
        xcol1, xcol2 = st.columns([3,1])
        with xcol1:
            pf_file = st.file_uploader(
                "📂 Fichier Excel portefeuille (.xlsx)",
                type=["xlsx","xls"],
                key="pf_upload_v14",
                help="Fichier export de votre logiciel de gestion de contrats AFG")
        with xcol2:
            st.markdown("<br>", unsafe_allow_html=True)
            if pf_file:
                if st.button("🔄 Importer & actualiser", use_container_width=True, key="btn_pf_v14"):
                    try:
                        with st.spinner("Chargement en cours…"):
                            try:
                                df_pf = pd.read_excel(pf_file, sheet_name="Sheet 1")
                            except Exception:
                                df_pf = pd.read_excel(pf_file)
                        # Sauvegarder en cache DISQUE — survit aux déconnexions
                        save_portefeuille_cache(df_pf, {
                            "filename": getattr(pf_file, "name", "portefeuille.xlsx"),
                            "imported_by": st.session_state.get("user", {}).get("nom", "—"),
                        })
                        st.session_state["portefeuille_ext"] = df_pf
                        st.session_state["pf_loaded_from_cache"] = False
                        st.success(
                            f"✅ Portefeuille importé et sauvegardé : {len(df_pf):,} polices"
                            f" · {len(df_pf.columns)} colonnes."
                            f" La base reste disponible apres deconnexion."
                            f" Supprimez-la manuellement si besoin.")
                        st.rerun()
                    except Exception as e_pf:
                        st.error(f"❌ Erreur import : {str(e_pf)}")

        # ── Statut du portefeuille chargé ─────────────────────────────────
        if "portefeuille_ext" in st.session_state and st.session_state["portefeuille_ext"] is not None:
            df_ext = st.session_state["portefeuille_ext"]
            if hasattr(df_ext, 'columns') and df_ext.columns is not None and len(df_ext) > 0:
                # Badge source
                _pf_meta = get_portefeuille_meta()
                _from_cache = st.session_state.get("pf_loaded_from_cache", False)
                _src_badge = "♻️ Rechargée automatiquement depuis le cache" if _from_cache else "📥 Chargée manuellement"
                _saved_at  = _pf_meta.get("saved_at", "")[:16] if _pf_meta else ""
                _imp_by    = _pf_meta.get("imported_by", "—") if _pf_meta else "—"
                _filename  = _pf_meta.get("filename", "—") if _pf_meta else "—"
                st.markdown(f"""
                <div style="background:#E8F8EE;border-left:4px solid #1A7A4A;border-radius:0 8px 8px 0;
                     padding:10px 14px;margin-bottom:10px;">
                  <div style="font-size:12px;font-weight:800;color:#0D4A2A;">✅ Base de données connectée</div>
                  <div style="font-size:11px;color:#1A7A4A;margin-top:3px;">
                    📁 <b>{_filename}</b> · {len(df_ext):,} polices · {len(df_ext.columns)} colonnes<br>
                    {_src_badge} · 🕐 {_saved_at} · 👤 {_imp_by}
                  </div>
                </div>""", unsafe_allow_html=True)

                if "ETAT_POLICE" in df_ext.columns:
                    ek1,ek2,ek3,ek4 = st.columns(4)
                    with ek1: kpi("📋 Total polices",f"{len(df_ext):,}","importées","gold","")
                    with ek2: kpi("✅ Actifs",f"{(df_ext['ETAT_POLICE']=='ACTIF').sum():,}","","green","")
                    with ek3: kpi("📉 Résiliés",f"{(df_ext['ETAT_POLICE']=='RESILIE').sum():,}","","red","")
                    with ek4:
                        ca_ext = df_ext["MONTENCA"].sum() if "MONTENCA" in df_ext.columns else 0
                        kpi("💰 Encaissements",fmt(ca_ext),"MONTENCA","teal","")

                st.markdown("<br>", unsafe_allow_html=True)
                col_del1, col_del2 = st.columns([3,1])
                with col_del2:
                    if st.button("🗑️ Supprimer la base", key="btn_pf_delete",
                                 help="Supprime la base du cache disque. Les KPIs reviendront au snapshot statique."):
                        delete_portefeuille_cache()
                        st.session_state["portefeuille_ext"] = None
                        st.session_state["pf_loaded_from_cache"] = False
                        st.success("✅ Base supprimée. Importez un nouveau fichier pour réactiver les KPIs dynamiques.")
                        st.rerun()
                with col_del1:
                    st.info("💡 La base reste disponible après déconnexion. Utilisez **Supprimer** pour la retirer définitivement.")

    # ─── Alertes globales (compagnie) ─────────────────────────────────────────
    sth("🚨 Alertes opérationnelles","SYNTHÈSE PDG")
    tx_resil_pr = PR['tx_resil']
    if tx_resil_pr > 50:
        alert(f"🔴 CRITIQUE : Taux de résiliation {tx_resil_pr:.1f}% — Plan d'action immédiat requis.","danger")
    elif tx_resil_pr > 25:
        alert(f"🟡 Taux de résiliation élevé : {tx_resil_pr:.1f}% — Surveillance renforcée.","warn")
    else:
        alert(f"🟢 Taux de résiliation maîtrisé : {tx_resil_pr:.1f}%.","good")
    alert(f"💰 CA portefeuille {fmt(PR['ca_total'])} · {PR['total']:,} polices · {PR['actif']:,} actives · {PR['nb_comm']:,} commerciaux","good")
    alert("📑 CIMA 2024 : Vérifier provisions de gestion et participation bénéficiaire avant clôture.","info")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — PERFORMANCES
# ═══════════════════════════════════════════════════════════════════════════════
elif "Performances" in nav:
    pf_ext = st.session_state.get("portefeuille_ext", None)

    # ── Sélecteur année (DATESOUS) ────────────────────────────────────────────
    yr_p = year_selector("yr_perf", "📅 Filtrer la performance par année de souscription (DATESOUS)")

    if pf_ext is not None and "DATESOUS" in pf_ext.columns and "NOM_APP" in pf_ext.columns:
        # ═══════════ MODE PORTEFEUILLE EXCEL (recommandé) ══════════════════
        df_p = pf_ext.copy()
        df_p["DATESOUS_DT"] = pd.to_datetime(df_p["DATESOUS"], errors="coerce")
        df_p["ANNEE"] = df_p["DATESOUS_DT"].dt.year
        df_p["MOIS"]  = df_p["DATESOUS_DT"].dt.to_period("M").astype(str)
        df_f = filter_pf_by_year(df_p, yr_p)

        if df_f.empty:
            alert(f"Aucun contrat pour {yr_label(yr_p)}.","warn"); st.stop()

        # ── KPIs globaux performance ──────────────────────────────────────────
        sth(f"🎯 Performance commerciale globale — {yr_label(yr_p)}","DASHBOARD COMMERCIAL")
        nb_contrats = len(df_f)
        ca_total    = float(df_f["MONTENCA"].sum()) if "MONTENCA" in df_f.columns else 0
        nb_actifs   = int((df_f["ETAT_POLICE"]=="ACTIF").sum()) if "ETAT_POLICE" in df_f.columns else 0
        nb_resilies = int((df_f["ETAT_POLICE"]=="RESILIE").sum()) if "ETAT_POLICE" in df_f.columns else 0
        nb_comm     = df_f["NOM_APP"].nunique()
        ticket      = ca_total/max(nb_contrats,1)
        prod_par_comm = nb_contrats/max(nb_comm,1)
        ca_par_comm   = ca_total/max(nb_comm,1)
        tx_actif      = nb_actifs/max(nb_contrats,1)*100
        tx_resil      = nb_resilies/max(nb_contrats,1)*100

        # Comparaison année précédente (si filtre = une seule année)
        ca_prev = None; growth_pct = None
        if isinstance(yr_p, list) and len(yr_p)==1:
            try:
                yr_curr = int(yr_p[0]); yr_prev = yr_curr-1
                df_prev = df_p[df_p["ANNEE"]==yr_prev]
                if not df_prev.empty and "MONTENCA" in df_prev.columns:
                    ca_prev = float(df_prev["MONTENCA"].sum())
                    if ca_prev > 0:
                        growth_pct = (ca_total - ca_prev)/ca_prev*100
            except Exception: pass

        k1,k2,k3,k4,k5,k6 = st.columns(6)
        with k1: kpi("💰 CA total",fmt(ca_total),
                    f"{growth_pct:+.1f}% vs N-1" if growth_pct is not None else "—",
                    "green" if (growth_pct or 0)>=0 else "red","")
        with k2: kpi("📋 Contrats",f"{nb_contrats:,}",f"{nb_actifs:,} actifs","gold","")
        with k3: kpi("👥 Commerciaux actifs",f"{nb_comm:,}","NOM_APP distincts","","")
        with k4: kpi("🎫 Ticket moyen",fmt(ticket),"par contrat","teal","")
        with k5: kpi("📈 CA / commercial",fmt(ca_par_comm),"productivité","gold","")
        with k6: kpi("📊 Contrats / comm.",f"{prod_par_comm:.1f}","productivité moyenne","","")

        k7,k8,k9,k10 = st.columns(4)
        with k7: kpi("✅ Taux activation",f"{tx_actif:.1f}%","contrats actifs",
                    "green" if tx_actif>50 else "amber","")
        with k8: kpi("📉 Taux résiliation",f"{tx_resil:.1f}%",f"{nb_resilies:,} résiliés",
                    "red" if tx_resil>25 else "green","")
        with k9:
            nb_clients = df_f["NOM_ASSU"].nunique() if "NOM_ASSU" in df_f.columns else 0
            kpi("👤 Clients distincts",f"{nb_clients:,}","NOM_ASSU","","")
        with k10:
            nb_prod = df_f["LIBECATE"].nunique() if "LIBECATE" in df_f.columns else 0
            kpi("🛒 Produits vendus",f"{nb_prod}","catégories actives","gold","")

        # ── Agrégation par commercial ─────────────────────────────────────────
        agg_dict = {"nb":("NOM_APP","count")}
        if "MONTENCA" in df_f.columns: agg_dict["ca"] = ("MONTENCA","sum")
        if "ETAT_POLICE" in df_f.columns:
            agg_dict["actifs"]   = ("ETAT_POLICE", lambda x:(x=="ACTIF").sum())
            agg_dict["resilies"] = ("ETAT_POLICE", lambda x:(x=="RESILIE").sum())
        if "NOM_ASSU" in df_f.columns: agg_dict["clients"] = ("NOM_ASSU","nunique")
        if "COTI_PERIODIQUE" in df_f.columns: agg_dict["coti_total"] = ("COTI_PERIODIQUE","sum")

        grp_keys = ["NOM_APP","CODEAPPO"] if "CODEAPPO" in df_f.columns else ["NOM_APP"]
        perf = df_f.groupby(grp_keys).agg(**agg_dict).reset_index()
        perf = perf[perf["NOM_APP"].astype(str).str.strip()!=""]
        perf["commercial"] = perf["NOM_APP"].astype(str).str.strip().str.title()
        if "ca" not in perf.columns: perf["ca"] = perf["nb"]
        if "actifs" not in perf.columns: perf["actifs"] = perf["nb"]
        if "resilies" not in perf.columns: perf["resilies"] = 0
        perf["tx_actif"]  = (perf["actifs"]/perf["nb"].clip(1)*100).round(1)
        perf["tx_resil"]  = (perf["resilies"]/perf["nb"].clip(1)*100).round(1)
        perf["ticket"]    = (perf["ca"]/perf["nb"].clip(1)).round(0)
        # Objectif simulé : 5M FCFA / mois × nb mois sur la période
        nb_mois_p = max(1, df_f["DATESOUS_DT"].dt.to_period("M").nunique())
        perf["objectif"]  = 5_000_000 * nb_mois_p
        perf["att"]       = (perf["ca"]/perf["objectif"].clip(1)*100).clip(0,250).round(1)
        perf = perf.sort_values("ca", ascending=False).reset_index(drop=True)

        # ── Onglets performance ───────────────────────────────────────────────
        tp1, tp2, tp3, tp4, tp5 = st.tabs([
            "🏆 CA vs Objectif",
            "📈 Évolution annuelle par commercial",
            "📅 Évolution mensuelle (période)",
            "🛒 Mix produits & groupes",
            "📋 Scoreboard détaillé"
        ])

        # ── TAB 1 : CA vs Objectif ────────────────────────────────────────────
        with tp1:
            sth(f"📊 CA vs Objectif — Top 25 commerciaux ({yr_label(yr_p)})","PERFORMANCE")
            top25 = perf.head(25)
            ca_c = [GREEN if x>=100 else (AMBER if x>=70 else RED) for x in top25["att"]]
            fig = go.Figure()
            fig.add_bar(x=top25["commercial"], y=top25["ca"], name="💰 CA réalisé",
                marker_color=ca_c,
                text=[f"{a:.0f}%" for a in top25["att"]],
                textposition="outside", textfont=dict(size=10,color=NAVY))
            fig.add_scatter(x=top25["commercial"], y=top25["objectif"], name="🎯 Objectif",
                mode="markers+lines",
                line=dict(color=RED,dash="dash",width=2),
                marker=dict(symbol="diamond-open",size=9,color=RED))
            fig.update_xaxes(tickangle=-40)
            fig.update_yaxes(title_text="CA (FCFA)")
            chl(fig,460,f"💰 CA réalisé vs Objectif — {nb_mois_p} mois actifs")
            st.plotly_chart(fig,use_container_width=True)

            # Distribution des taux de réalisation
            dist = perf["att"].value_counts(bins=[0,50,70,100,150,250]).sort_index()
            st.caption(f"🎯 **Atteinte d'objectif** : {(perf['att']>=100).sum()} commerciaux dépassent 100% · "
                       f"{((perf['att']>=70)&(perf['att']<100)).sum()} entre 70-100% · "
                       f"{(perf['att']<70).sum()} sous 70%.")

        # ── TAB 2 : ÉVOLUTION ANNUELLE PAR COMMERCIAL (NOUVEAU) ──────────────
        with tp2:
            sth("📈 Évolution du CA par commercial — toutes années","SUIVI HISTORIQUE")
            alert("Sélectionnez les commerciaux à comparer. Le graphique trace l'évolution annuelle du CA depuis l'origine du portefeuille.","info")

            # Top 20 par défaut
            top_choices = perf.head(20)["commercial"].tolist()
            sel_comm = st.multiselect(
                "🔍 Choisir les commerciaux à afficher",
                options=perf["commercial"].tolist(),
                default=top_choices[:8],
                key="perf_sel_comm")

            if sel_comm:
                # On utilise df_p (toutes années) — l'historique reste visible quel que soit yr_p
                df_evo = df_p.copy()
                df_evo["commercial"] = df_evo["NOM_APP"].astype(str).str.strip().str.title()
                df_evo = df_evo[df_evo["commercial"].isin(sel_comm)]
                df_evo = df_evo[df_evo["ANNEE"].between(1996,2026)]
                evo_g = df_evo.groupby(["ANNEE","commercial"]).agg(
                    ca=("MONTENCA","sum") if "MONTENCA" in df_evo.columns else ("commercial","count"),
                    nb=("commercial","count")
                ).reset_index().dropna()

                ce1, ce2 = st.columns(2)
                with ce1:
                    fig_e1 = px.line(evo_g, x="ANNEE", y="ca", color="commercial", markers=True,
                        title=f"💰 Évolution annuelle du CA ({len(sel_comm)} commerciaux)",
                        labels={"ca":"CA (FCFA)","ANNEE":"Année","commercial":"Commercial"})
                    fig_e1.update_layout(height=440, legend=dict(font=dict(size=9), orientation="v"))
                    st.plotly_chart(fig_e1, use_container_width=True)
                with ce2:
                    fig_e2 = px.line(evo_g, x="ANNEE", y="nb", color="commercial", markers=True,
                        title=f"📋 Évolution annuelle du nombre de contrats",
                        labels={"nb":"Nb contrats","ANNEE":"Année","commercial":"Commercial"})
                    fig_e2.update_layout(height=440, legend=dict(font=dict(size=9), orientation="v"))
                    st.plotly_chart(fig_e2, use_container_width=True)

                # Heatmap CA par commercial × année
                sth("🔥 Heatmap CA — Commercial × Année","VISION CHALEUR")
                pivot = evo_g.pivot_table(index="commercial", columns="ANNEE", values="ca", fill_value=0)
                fig_h = px.imshow(pivot.values,
                    x=[str(int(c)) for c in pivot.columns],
                    y=pivot.index.tolist(),
                    color_continuous_scale=["#fff8e1","#ffd54f","#f57f17","#bf360c"],
                    aspect="auto",
                    labels=dict(x="Année", y="Commercial", color="CA (FCFA)"))
                fig_h.update_layout(height=max(300, 22*len(pivot)), title="🔥 Intensité du CA — Commercial × Année")
                st.plotly_chart(fig_h, use_container_width=True)

                # Ranking growth YoY (si filtre une seule année)
                if isinstance(yr_p, list) and len(yr_p)==1 and ca_prev is not None:
                    sth(f"📊 Croissance YoY — {int(yr_p[0])-1} → {yr_p[0]}","ÉVOLUTION COMMERCIALE")
                    yr_curr = int(yr_p[0]); yr_prev = yr_curr-1
                    df_curr_y = df_p[df_p["ANNEE"]==yr_curr].groupby("NOM_APP")["MONTENCA"].sum()
                    df_prev_y = df_p[df_p["ANNEE"]==yr_prev].groupby("NOM_APP")["MONTENCA"].sum()
                    growth = pd.DataFrame({"ca_curr":df_curr_y, "ca_prev":df_prev_y}).fillna(0)
                    growth["growth"] = ((growth["ca_curr"]-growth["ca_prev"])/growth["ca_prev"].replace(0,1)*100).clip(-100,500).round(1)
                    growth["commercial"] = growth.index.astype(str).str.strip().str.title()
                    growth = growth[growth["ca_curr"]>0].sort_values("growth",ascending=False).head(15)
                    fig_gr = go.Figure(go.Bar(
                        x=growth["growth"], y=growth["commercial"], orientation="h",
                        marker_color=[GREEN if v>=0 else RED for v in growth["growth"]],
                        text=[f"{v:+.0f}%" for v in growth["growth"]], textposition="outside"))
                    chl(fig_gr, 480, f"🚀 Top 15 — Croissance YoY ({yr_prev}→{yr_curr})")
                    st.plotly_chart(fig_gr, use_container_width=True)
            else:
                alert("Sélectionnez au moins 1 commercial.","info")

        # ── TAB 3 : ÉVOLUTION MENSUELLE (période filtrée) ─────────────────────
        with tp3:
            sth(f"📅 Évolution mensuelle — {yr_label(yr_p)}","TENDANCE PÉRIODE")
            bm = df_f.groupby("MOIS").agg(
                nb=("NOM_APP","count"),
                ca=("MONTENCA","sum") if "MONTENCA" in df_f.columns else ("NOM_APP","count"),
            ).reset_index().sort_values("MOIS")
            bm["cumul_ca"] = bm["ca"].cumsum()
            fig = make_subplots(specs=[[{"secondary_y":True}]])
            fig.add_bar(x=bm["MOIS"], y=bm["nb"], name="📋 Nb contrats",
                marker_color=BLUEL, opacity=0.75, secondary_y=False)
            fig.add_scatter(x=bm["MOIS"], y=bm["ca"], name="💰 CA mensuel",
                line=dict(color=GOLD,width=3), mode="lines+markers", secondary_y=True)
            fig.add_scatter(x=bm["MOIS"], y=bm["cumul_ca"], name="📈 CA cumulé",
                line=dict(color=RED,width=2,dash="dot"), mode="lines", secondary_y=True)
            fig.update_yaxes(title_text="Nb contrats", secondary_y=False)
            fig.update_yaxes(title_text="CA (FCFA)", secondary_y=True, showgrid=False)
            chl(fig,400,f"📅 Souscriptions mensuelles + CA cumulé ({yr_label(yr_p)})")
            st.plotly_chart(fig, use_container_width=True)

        # ── TAB 4 : MIX PRODUITS ──────────────────────────────────────────────
        with tp4:
            cm1, cm2 = st.columns(2)
            with cm1:
                if "LIBECATE" in df_f.columns:
                    sth("🛒 Top produits par CA","MIX OFFRE")
                    pd5 = df_f.groupby("LIBECATE").agg(
                        nb=("NOM_APP","count"),
                        ca=("MONTENCA","sum") if "MONTENCA" in df_f.columns else ("NOM_APP","count")
                    ).reset_index().sort_values("ca",ascending=False).head(10)
                    fig_pp = px.bar(pd5, x="ca", y="LIBECATE", orientation="h",
                        color="ca", color_continuous_scale=[BLUEL,GOLD],
                        text=[fmt(v) for v in pd5["ca"]])
                    fig_pp.update_traces(textposition="outside")
                    fig_pp.update_layout(height=400, showlegend=False, yaxis=dict(title=""))
                    st.plotly_chart(fig_pp, use_container_width=True)
            with cm2:
                if "LIBECATE" in df_f.columns:
                    sth("🥧 Répartition CA par produit","RÉPARTITION")
                    pd5b = df_f.groupby("LIBECATE")["MONTENCA"].sum().reset_index().sort_values("MONTENCA",ascending=False).head(8) if "MONTENCA" in df_f.columns else df_f["LIBECATE"].value_counts().head(8).reset_index()
                    pd5b.columns = ["LIBECATE","val"]
                    fig_pi = px.pie(pd5b, values="val", names="LIBECATE", hole=0.42,
                        color_discrete_sequence=[GOLD,BLUEL,GREEN,RED,TEAL,AMBER,NAVY,"#a78bfa"])
                    fig_pi.update_traces(textinfo="percent+label", textfont_size=10)
                    fig_pi.update_layout(height=400)
                    st.plotly_chart(fig_pi, use_container_width=True)

        # ── TAB 5 : SCOREBOARD ────────────────────────────────────────────────
        with tp5:
            sth(f"📋 Scoreboard détaillé — {len(perf)} commerciaux","CLASSEMENT FILTRÉ")
            disp = perf.copy()
            disp.insert(0,"Rang", range(1,len(disp)+1))
            disp["CA"] = disp["ca"].apply(fmt)
            disp["Ticket moy."] = disp["ticket"].apply(fmt)
            disp["% Obj."] = disp["att"].apply(lambda x:f"{x:.1f}%")
            disp["% Actifs"] = disp["tx_actif"].apply(lambda x:f"{x:.1f}%")
            disp["% Résil."] = disp["tx_resil"].apply(lambda x:f"{x:.1f}%")
            cols_show = ["Rang","commercial"]
            if "CODEAPPO" in disp.columns: cols_show.append("CODEAPPO")
            cols_show += ["nb","actifs","CA","Ticket moy.","% Obj.","% Actifs","% Résil."]
            disp_v = disp[[c for c in cols_show if c in disp.columns]].rename(columns={
                "commercial":"Commercial","CODEAPPO":"Code","nb":"Contrats","actifs":"Actifs"})
            st.dataframe(disp_v, use_container_width=True, hide_index=True, height=480)

            buf_perf = io.BytesIO()
            with pd.ExcelWriter(buf_perf, engine="openpyxl") as wr:
                disp_v.to_excel(wr, index=False, sheet_name="Performance")
            st.download_button(
                f"⬇️ Télécharger la performance ({yr_label(yr_p)})",
                data=buf_perf.getvalue(),
                file_name=f"AFG_Performance_{yr_label(yr_p)}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True)

    else:
        # ═══════════ MODE BD INTERNE (fallback si pas de portefeuille importé) ═══
        df=q(BASE)
        if df.empty:
            alert("Aucune donnée. Importez votre portefeuille Excel depuis la page Accueil pour activer la performance complète.","warn")
            st.stop()
        df['eq']=df['prime_annuelle']+df['prime_unique']
        df=filter_by_year(df,yr_p)
        if df.empty:
            alert(f"Aucune donnée pour {yr_label(yr_p)}.","warn"); st.stop()
        df['eq']=df['prime_annuelle']+df['prime_unique']

        nm=max(1,duree_j/30)
        grp_cols=[c for c in ['commercial_id','nom','prenom','agence','region','objectif_mensuel'] if c in df.columns]
        perf=df.groupby(grp_cols).agg(nb=('id','count'),ca=('eq','sum')).reset_index()
        perf['commercial']=(perf['nom']+' '+perf['prenom']) if 'nom' in perf.columns else perf.get('commercial_id','—')
        if 'objectif_mensuel' in perf.columns:
            perf['obj_p']=perf['objectif_mensuel']*nm
            perf['att']=(perf['ca']/perf['obj_p'].replace(0,1)*100).clip(0,250).round(1)
        else:
            perf['obj_p']=5000000*nm; perf['att']=(perf['ca']/perf['obj_p']*100).clip(0,250).round(1)
        perf=perf.sort_values('ca',ascending=False)

        sth("📊 CA vs Objectif — par commercial (BD interne)","Période sélectionnée")
        ca_c=[GREEN if x>=100 else AMBER if x>=70 else RED for x in perf['att']]
        fig=go.Figure()
        fig.add_bar(x=perf['commercial'],y=perf['ca'],name="💰 CA",marker_color=ca_c,
            text=[f"{a:.0f}%" for a in perf['att']],textposition='outside')
        fig.add_scatter(x=perf['commercial'],y=perf['obj_p'],name="🎯 Objectif",mode='markers+lines',
            line=dict(color=RED,dash='dash',width=2),marker=dict(symbol='diamond-open',size=10,color=RED))
        chl(fig,420,"💰 CA vs Objectif"); st.plotly_chart(fig,use_container_width=True)

        sth("📋 Scoreboard","Agents")
        disp_cols=[c for c in ['commercial','agence','region','nb','ca','att'] if c in perf.columns]
        disp=perf[disp_cols].copy()
        disp.insert(0,'Rang',range(1,len(disp)+1))
        if 'ca' in disp.columns: disp['ca']=disp['ca'].apply(fmt)
        if 'att' in disp.columns: disp['att']=disp['att'].apply(lambda x:f"{x:.1f}%")
        st.dataframe(disp,use_container_width=True,hide_index=True,height=380)



# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — CLASSEMENT (données portefeuille Excel + BD interne)
# ═══════════════════════════════════════════════════════════════════════════════
elif "Classement" in nav:
    pf_ext = st.session_state.get("portefeuille_ext", None)

    # ── Sélecteur d'année ──────────────────────────────────────────────────
    yr_cl = year_selector("yr_class", "📅 Filtrer le classement par année de souscription")

    # ── Source de données ──────────────────────────────────────────────────
    if pf_ext is not None:
        # === CLASSEMENT DEPUIS LE PORTEFEUILLE EXCEL ===
        df_cl = pf_ext.copy()
        df_cl["ANNEE"] = pd.to_datetime(df_cl["DATESOUS"], errors="coerce").dt.year
        df_cl = filter_pf_by_year(df_cl, yr_cl)
        if df_cl.empty:
            alert(f"Aucun contrat pour {yr_label(yr_cl)} dans le portefeuille.", "warn")
            df_cl = pf_ext.copy()

        # Groupby par apporteur
        rank = df_cl.groupby("NOM_APP").agg(
            nb=("NUMEPOLI_P","count"),
            ca=("MONTENCA","sum"),
            actifs=("ETAT_POLICE", lambda x:(x=="ACTIF").sum()),
            cotis=("COTI_PERIODIQUE","sum"),
            clients=("NOM_ASSU","nunique"),
        ).reset_index()
        rank = rank[rank["NOM_APP"].notna() & (rank["NOM_APP"].str.strip() != "")]
        rank["commercial"] = rank["NOM_APP"].str.strip().str.title()
        rank["tx_actif"] = (rank["actifs"] / rank["nb"].clip(1) * 100).round(1)
        rank["score"] = (
            (rank["ca"].clip(lower=0) / rank["ca"].clip(lower=0).max().clip(lower=1) * 50) +
            (rank["nb"] / rank["nb"].max().clip(lower=1) * 30) +
            (rank["tx_actif"] / 100 * 20)
        ).round(1)
        rank = rank.sort_values("ca", ascending=False).reset_index(drop=True)
        source_label = "📊 Source : Portefeuille Excel AFG"
    else:
        # === CLASSEMENT DEPUIS LA BD INTERNE ===
        df_int = q(BASE)
        if df_int.empty:
            alert("⚠️ Aucune donnée. Importez votre portefeuille Excel depuis la page Accueil.", "warn")
            alert("👆 Allez sur Accueil → 'Connecter le portefeuille Excel' → Importez votre fichier xlsx", "info")
            st.stop()
        df_int = filter_by_year(df_int, yr_cl)
        if df_int.empty:
            alert(f"Aucun contrat pour {yr_label(yr_cl)}.", "warn"); st.stop()
        df_int["eq"] = df_int["prime_annuelle"] + df_int["prime_unique"]
        grp_rank = [c for c in ["nom","prenom","code_agent","agence","region"] if c in df_int.columns]
        rank = df_int.groupby(grp_rank).agg(ca=("eq","sum"), nb=("id","count")).reset_index()
        rank["commercial"] = (rank.get("nom","") + " " + rank.get("prenom","")).str.strip()
        rank["tx_actif"] = 0.0
        rank["cotis"] = rank["ca"]
        rank["actifs"] = rank["nb"]
        rank["clients"] = rank["nb"]
        rank["score"] = (
            (rank["ca"] / rank["ca"].max().clip(lower=1) * 60) +
            (rank["nb"] / rank["nb"].max().clip(lower=1) * 40)
        ).round(1)
        rank = rank.sort_values("ca", ascending=False).reset_index(drop=True)
        source_label = "📊 Source : Base de données interne"

    # ── EN-TÊTE ────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#003366,#004D99);border-radius:14px;
         padding:1.2rem 1.6rem;margin-bottom:1rem;border-left:5px solid #C9A227;">
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1rem;">
        <div>
          <div style="color:#E8C84A;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.12em;margin-bottom:3px;">
            AFG Assurances Bénin Vie — Classement Commercial</div>
          <div style="color:white;font-size:1.2rem;font-weight:900;">🏆 Classement des Apporteurs — {yr_label(yr_cl)}</div>
          <div style="color:rgba(255,255,255,0.65);font-size:11px;margin-top:3px;">{source_label} · {len(rank)} agents classés</div>
        </div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;">
          <div style="background:rgba(255,255,255,.1);border:1px solid rgba(201,162,39,.4);
               border-radius:10px;padding:9px 14px;text-align:center;">
            <div style="font-size:1.3rem;font-weight:900;color:#E8C84A;">{len(rank)}</div>
            <div style="font-size:9px;color:rgba(255,255,255,.6);">Agents classés</div>
          </div>
          <div style="background:rgba(255,255,255,.1);border:1px solid rgba(201,162,39,.4);
               border-radius:10px;padding:9px 14px;text-align:center;">
            <div style="font-size:1.1rem;font-weight:900;color:#E8C84A;">{fmt(rank['ca'].sum())}</div>
            <div style="font-size:9px;color:rgba(255,255,255,.6);">CA total</div>
          </div>
          <div style="background:rgba(255,255,255,.1);border:1px solid rgba(201,162,39,.4);
               border-radius:10px;padding:9px 14px;text-align:center;">
            <div style="font-size:1.3rem;font-weight:900;color:#4DFFE0;">{int(rank['nb'].sum()):,}</div>
            <div style="font-size:9px;color:rgba(255,255,255,.6);">Contrats total</div>
          </div>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── PODIUM TOP 3 ──────────────────────────────────────────────────────
    sth("🏆 Podium — Top 3 Apporteurs", "MEILLEURS AGENTS")
    medals = ["🥇","🥈","🥉"]
    pcs    = ["p1","p2","p3"]
    order  = [1,0,2]  # centre=1er, gauche=2e, droite=3e
    pod_cols = st.columns(3)
    for ri, ci in zip([0,1,2], order):
        if ri < len(rank):
            row = rank.iloc[ri]
            with pod_cols[ci]:
                st.markdown(f"""
                <div class="podium-card {pcs[ri]}" style="min-height:170px;">
                  <span style="font-size:2.5rem;display:block;margin-bottom:4px;">{medals[ri]}</span>
                  <div style="font-size:13px;font-weight:900;color:#003366;line-height:1.3;">{row['commercial']}</div>
                  <div style="font-size:10px;color:#5A6478;margin:4px 0;">{int(row['nb'])} contrats · {row['tx_actif']:.0f}% actifs</div>
                  <div style="font-size:1.1rem;font-weight:900;color:#003366;margin:6px 0;">{fmt(row['ca'])}</div>
                  <div style="background:#003366;color:#E8C84A;border-radius:20px;
                       padding:3px 12px;font-size:10px;font-weight:800;display:inline-block;">
                    Score {row['score']:.0f}/100</div>
                </div>
                <div class="pod-base"></div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── HEADLINE : TOP 10 COMMERCIAUX · TOP 10 CLIENTS · TOP 5 PRODUITS ──
    sth(f"🌟 Indicateurs phares — {yr_label(yr_cl)}","TOP DU PORTEFEUILLE")
    head_c1, head_c2, head_c3 = st.columns([1.1, 1.1, 1])

    with head_c1:
        st.markdown(f"<div style='font-weight:800;color:{NAVY};font-size:13px;margin-bottom:6px;'>"
                    f"🏆 Top 10 commerciaux par CA</div>", unsafe_allow_html=True)
        top10c = rank.head(10).copy()
        med = ["🥇","🥈","🥉"] + [f" {i+1}" for i in range(3,10)]
        top10c["Rang"] = med[:len(top10c)]
        top10c["CA"] = top10c["ca"].apply(fmt)
        st.dataframe(top10c[["Rang","commercial","nb","CA"]].rename(
            columns={"commercial":"Commercial","nb":"Polices"}),
            use_container_width=True, hide_index=True, height=370)

    with head_c2:
        st.markdown(f"<div style='font-weight:800;color:{NAVY};font-size:13px;margin-bottom:6px;'>"
                    f"👤 Top 10 clients par CA</div>", unsafe_allow_html=True)
        if pf_ext is not None and "NOM_ASSU" in pf_ext.columns:
            df_h = pf_ext.copy()
            if "DATESOUS" in df_h.columns:
                df_h = filter_pf_by_year(df_h, yr_cl)
                if df_h.empty: df_h = pf_ext.copy()
            cli10 = df_h.groupby("NOM_ASSU").agg(
                nb=("NOM_ASSU","count"),
                ca=("MONTENCA","sum") if "MONTENCA" in df_h.columns else ("NOM_ASSU","count")
            ).reset_index()
            cli10 = cli10[cli10["NOM_ASSU"].astype(str).str.strip()!=""]
            cli10 = cli10.sort_values("ca", ascending=False).head(10).reset_index(drop=True)
            cli10["NOM_ASSU"] = cli10["NOM_ASSU"].astype(str).str.title()
            cli10.insert(0, "Rang", (["🥇","🥈","🥉"]+[f" {i+1}" for i in range(3,10)])[:len(cli10)])
            cli10["CA"] = cli10["ca"].apply(fmt)
            st.dataframe(cli10[["Rang","NOM_ASSU","nb","CA"]].rename(
                columns={"NOM_ASSU":"Client","nb":"Contrats"}),
                use_container_width=True, hide_index=True, height=370)
        else:
            alert("Importez le portefeuille Excel pour activer le Top 10 clients.","info")

    with head_c3:
        st.markdown(f"<div style='font-weight:800;color:{NAVY};font-size:13px;margin-bottom:6px;'>"
                    f"🛒 Top 5 produits vendus</div>", unsafe_allow_html=True)
        if pf_ext is not None and "LIBECATE" in pf_ext.columns:
            df_h = pf_ext.copy()
            if "DATESOUS" in df_h.columns:
                df_h = filter_pf_by_year(df_h, yr_cl)
                if df_h.empty: df_h = pf_ext.copy()
            pr5 = df_h.groupby("LIBECATE").agg(
                nb=("LIBECATE","count"),
                ca=("MONTENCA","sum") if "MONTENCA" in df_h.columns else ("LIBECATE","count")
            ).reset_index()
            pr5 = pr5[pr5["LIBECATE"].astype(str).str.strip()!=""]
            pr5 = pr5.sort_values("nb", ascending=False).head(5).reset_index(drop=True)
            pr5.insert(0, "Rang", ["🥇","🥈","🥉","4️⃣","5️⃣"][:len(pr5)])
            pr5["CA"] = pr5["ca"].apply(fmt)
            st.dataframe(pr5[["Rang","LIBECATE","nb","CA"]].rename(
                columns={"LIBECATE":"Produit","nb":"Polices"}),
                use_container_width=True, hide_index=True, height=370)
        else:
            alert("Importez le portefeuille Excel pour activer le Top 5 produits.","info")

    st.markdown("---")


    tab_r1, tab_r2, tab_r3, tab_r4 = st.tabs([
        "📊 Top 13 commerciaux",
        "📅 Évolution",
        "📋 Tableau complet",
        "🏅 Top 10 — Clients · Contrats · Banques · Villes · Produits",
    ])

    with tab_r1:
        c1, c2 = st.columns(2)
        with c1:
            top20 = rank.head(13).sort_values("ca")
            colors_r = [
                "#DAA520" if i==len(top20)-1 else
                "#C0C0C0" if i==len(top20)-2 else
                "#CD7F32" if i==len(top20)-3 else BLUEL
                for i in range(len(top20))
            ]
            fig_r = go.Figure(go.Bar(
                x=top20["ca"], y=top20["commercial"],
                orientation="h",
                marker_color=colors_r,
                text=[fmt(v) for v in top20["ca"]],
                textposition="outside",
                textfont=dict(size=10, color="#003366"),
                customdata=top20[["nb","tx_actif","score"]].values,
                hovertemplate="<b>%{y}</b><br>CA : %{x:,.0f} FCFA<br>Contrats : %{customdata[0]}<br>Actifs : %{customdata[1]:.0f}%<br>Score : %{customdata[2]:.0f}/100<extra></extra>"
            ))
            chl(fig_r, 520, f"🏆 TOP 13 Commerciaux — CA ({yr_label(yr_cl)})")
            fig_r.update_layout(yaxis=dict(tickfont=dict(size=10)))
            st.plotly_chart(fig_r, use_container_width=True)

        with c2:
            # Bubble chart : CA vs Nb contrats (taille = % actifs)
            top50 = rank.head(50).copy()
            top50["size_bubble"] = (top50["tx_actif"].fillna(0) + 5) * 1.5
            fig_bub = px.scatter(
                top50,
                x="nb", y="ca",
                size="size_bubble",
                color="score",
                color_continuous_scale=[[0,RED],[0.5,AMBER],[1,GREEN]],
                hover_name="commercial",
                text="commercial",
                labels={"nb":"Nb contrats","ca":"CA (FCFA)","score":"Score"},
                custom_data=["tx_actif","score"]
            )
            fig_bub.update_traces(
                textposition="top center",
                textfont=dict(size=8),
                hovertemplate="<b>%{hovertext}</b><br>Contrats : %{x}<br>CA : %{y:,.0f} FCFA<br>Actifs : %{customdata[0]:.0f}%<br>Score : %{customdata[1]:.0f}/100<extra></extra>")
            chl(fig_bub, 520, "🫧 Carte des performances — CA vs Nb contrats (bulle = % actifs)")
            st.plotly_chart(fig_bub, use_container_width=True)

        # Score bar horizontal pour tous les agents
        st.markdown("---")
        sth("📊 Score de performance — Tous les agents", "0 à 100")
        rank_show = rank.head(40)
        for i, (_, row) in enumerate(rank_show.iterrows()):
            sc = min(float(row["score"]), 100)
            fill = GREEN if sc >= 70 else (AMBER if sc >= 45 else RED)
            rkg = "#DAA520" if i==0 else ("#C0C0C0" if i==1 else ("#CD7F32" if i==2 else NAVY))
            st.markdown(f"""
            <div class="score-row">
              <div style="width:26px;height:26px;border-radius:50%;background:{rkg};color:white;
                   font-size:11px;font-weight:900;display:flex;align-items:center;
                   justify-content:center;flex-shrink:0;">{i+1}</div>
              <div style="min-width:180px;">
                <div style="font-size:12px;font-weight:700;color:{NAVY};line-height:1.2;">{row['commercial']}</div>
                <div style="font-size:9px;color:{DGRAY};">{int(row['nb'])} contrats · {row['tx_actif']:.0f}% actifs</div>
              </div>
              <div class="score-track">
                <div class="score-fill" style="width:{sc}%;background:linear-gradient(90deg,{BLUEL},{fill});"></div>
              </div>
              <div class="score-val" style="color:{fill};">{sc:.0f}</div>
              <div style="font-size:10.5px;color:{DGRAY};min-width:90px;text-align:right;">{int(row['nb'])} contrats</div>
              <div style="font-size:11.5px;font-weight:700;color:{NAVY};min-width:110px;text-align:right;">{fmt(row['ca'])}</div>
            </div>""", unsafe_allow_html=True)
        if len(rank) > 40:
            st.caption(f"Affichage des 40 premiers sur {len(rank)} agents classés.")

    with tab_r2:
        if pf_ext is not None and "DATESOUS" in pf_ext.columns:
            df_evo = pf_ext.copy()
            df_evo["ANNEE"] = pd.to_datetime(df_evo["DATESOUS"], errors="coerce").dt.year
            # Top 8 agents pour l'évolution
            top8_agents = rank.head(8)["commercial"].tolist()
            top8_noms   = rank.head(8)["NOM_APP"].str.strip().str.title().tolist()

            evo = pf_ext.copy()
            evo["ANNEE"] = pd.to_datetime(evo["DATESOUS"], errors="coerce").dt.year
            evo["NOM_APP_TITLE"] = evo["NOM_APP"].str.strip().str.title()
            evo_top = evo[evo["NOM_APP_TITLE"].isin(top8_agents)]
            evo_grp = evo_top.groupby(["ANNEE","NOM_APP_TITLE"]).agg(
                ca=("MONTENCA","sum"), nb=("NUMEPOLI_P","count")).reset_index().dropna()

            c1_e, c2_e = st.columns(2)
            with c1_e:
                fig_evo_ca = px.line(
                    evo_grp, x="ANNEE", y="ca", color="NOM_APP_TITLE",
                    markers=True,
                    title=f"📈 Évolution du CA — Top 8 agents ({yr_label(yr_cl)})",
                    labels={"ca":"CA (FCFA)","ANNEE":"Année","NOM_APP_TITLE":"Apporteur"})
                fig_evo_ca.update_layout(height=400, legend=dict(font=dict(size=9)))
                st.plotly_chart(fig_evo_ca, use_container_width=True)
            with c2_e:
                fig_evo_nb = px.line(
                    evo_grp, x="ANNEE", y="nb", color="NOM_APP_TITLE",
                    markers=True,
                    title="📋 Évolution des contrats — Top 8 agents",
                    labels={"nb":"Nb contrats","ANNEE":"Année","NOM_APP_TITLE":"Apporteur"})
                fig_evo_nb.update_layout(height=400, legend=dict(font=dict(size=9)))
                st.plotly_chart(fig_evo_nb, use_container_width=True)

            # CA annuel global
            evo_global = evo.groupby("ANNEE").agg(
                ca=("MONTENCA","sum"), nb=("NUMEPOLI_P","count")).reset_index().dropna()
            evo_global = evo_global[evo_global["ANNEE"].between(1996, 2026)]
            fig_glob = make_subplots(specs=[[{"secondary_y":True}]])
            fig_glob.add_trace(go.Bar(x=evo_global["ANNEE"], y=evo_global["nb"],
                name="📋 Nb contrats", marker_color=BLUEL, opacity=0.75), secondary_y=False)
            fig_glob.add_trace(go.Scatter(x=evo_global["ANNEE"], y=evo_global["ca"],
                name="💰 Encaissements", line=dict(color=GOLD, width=3),
                mode="lines+markers", marker=dict(size=8, color=GOLD)), secondary_y=True)
            chl(fig_glob, 360, "📅 Évolution annuelle du portefeuille AFG (1996–2025)")
            fig_glob.update_yaxes(title_text="Nb contrats", secondary_y=False)
            fig_glob.update_yaxes(title_text="Encaissements (FCFA)", secondary_y=True, showgrid=False)
            st.plotly_chart(fig_glob, use_container_width=True)
        else:
            alert("Importez le portefeuille Excel pour voir les graphiques d'évolution.", "info")

    with tab_r3:
        sth("📋 Tableau complet des agents classés")
        rank_disp = rank.copy()
        rank_disp.insert(0, "Rang", range(1, len(rank_disp)+1))
        rank_disp["Médaille"] = ["🥇","🥈","🥉"] + [""]*(len(rank_disp)-3)
        rank_disp["CA"] = rank_disp["ca"].apply(fmt)
        rank_disp["Cotisations"] = rank_disp["cotis"].apply(fmt)
        rank_disp["% Actifs"] = rank_disp["tx_actif"].apply(lambda x: f"{x:.1f}%")
        rank_disp["Score"] = rank_disp["score"].apply(lambda x: f"{x:.0f}/100")
        cols_show = ["Médaille","Rang","commercial","nb","actifs","CA","% Actifs","Score"]
        cols_show_labels = ["","Rang","Apporteur","Contrats","Actifs","CA","% Actifs","Score"]
        disp_r = rank_disp[[c for c in cols_show if c in rank_disp.columns]].copy()
        disp_r.columns = cols_show_labels[:len(disp_r.columns)]
        st.dataframe(disp_r, use_container_width=True, hide_index=True, height=520)
        # Export
        buf_r = io.BytesIO()
        with pd.ExcelWriter(buf_r, engine="openpyxl") as wr:
            disp_r.to_excel(wr, index=False, sheet_name="Classement")
        st.download_button(
            f"⬇️ Télécharger le classement ({yr_label(yr_cl)})",
            data=buf_r.getvalue(),
            file_name=f"AFG_Classement_{yr_label(yr_cl)}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True)

    # ── TAB 4 : Top 10 transverses (Clients · Contrats · Banques · Villes · Produits) ──
    with tab_r4:
        if pf_ext is None:
            alert("ℹ️ Importez le portefeuille Excel pour activer le classement Top 10 multi-axes.","info")
        else:
            df_top = pf_ext.copy()
            if "DATESOUS" in df_top.columns:
                df_top["ANNEE"] = pd.to_datetime(df_top["DATESOUS"], errors="coerce").dt.year
                df_top = filter_pf_by_year(df_top, yr_cl)
            if df_top.empty:
                df_top = pf_ext.copy()

            def _top10_bar(d, label, color):
                d = d.head(10).sort_values(d.columns[1])
                fig = go.Figure(go.Bar(
                    x=d[d.columns[1]], y=d[d.columns[0]].astype(str),
                    orientation="h", marker_color=color,
                    text=[fmt(v) if d.columns[1] in ("ca","cotis","encaiss") else f"{int(v):,}" for v in d[d.columns[1]]],
                    textposition="outside", textfont=dict(size=10, color=NAVY)))
                fig.update_layout(height=380, margin=dict(l=10,r=20,t=40,b=10),
                    title=dict(text=label, font=dict(size=13, color=NAVY)),
                    xaxis=dict(showgrid=True, gridcolor="#eee"),
                    yaxis=dict(tickfont=dict(size=10)),
                    plot_bgcolor="white", paper_bgcolor="white")
                return fig

            # === A. TOP 10 CLIENTS (par CA + nb contrats) =====================
            sth("👤 TOP 10 Clients — Encaissements & nombre de contrats", "MEILLEURS ASSURÉS")
            if "NOM_ASSU" in df_top.columns:
                cli = df_top.groupby("NOM_ASSU").agg(
                    nb=("NUMEPOLI_P","count") if "NUMEPOLI_P" in df_top.columns else ("NOM_ASSU","count"),
                    ca=("MONTENCA","sum") if "MONTENCA" in df_top.columns else ("NOM_ASSU","count"),
                ).reset_index()
                cli = cli[cli["NOM_ASSU"].astype(str).str.strip()!=""]
                cli["NOM_ASSU"] = cli["NOM_ASSU"].astype(str).str.title()
                cca, ccb = st.columns(2)
                with cca:
                    st.plotly_chart(_top10_bar(cli.sort_values("ca",ascending=False)[["NOM_ASSU","ca"]],
                        "💰 Top 10 Clients par CA (FCFA)", GOLD), use_container_width=True)
                with ccb:
                    st.plotly_chart(_top10_bar(cli.sort_values("nb",ascending=False)[["NOM_ASSU","nb"]],
                        "📋 Top 10 Clients par nombre de contrats", BLUEL), use_container_width=True)
                tcli = cli.sort_values("ca",ascending=False).head(10).reset_index(drop=True)
                tcli.insert(0,"Rang",range(1,len(tcli)+1))
                tcli["CA"] = tcli["ca"].apply(fmt)
                st.dataframe(tcli[["Rang","NOM_ASSU","nb","CA"]].rename(
                    columns={"NOM_ASSU":"Client","nb":"Contrats"}),
                    use_container_width=True, hide_index=True)
            else:
                alert("Colonne NOM_ASSU absente du portefeuille.","warn")

            st.markdown("---")

            # === B. TOP 10 CONTRATS (polices à plus gros encaissement) ========
            sth("📜 TOP 10 Contrats — Polices au plus fort encaissement", "POLICES PREMIUM")
            cols_ct = [c for c in ["NUMEPOLI_P","NOM_ASSU","NOM_APP","LIBECATE","ETAT_POLICE","MONTENCA","DATESOUS"] if c in df_top.columns]
            if "MONTENCA" in df_top.columns and cols_ct:
                tcontr = df_top[cols_ct].copy()
                tcontr = tcontr.sort_values("MONTENCA", ascending=False).head(10).reset_index(drop=True)
                tcontr.insert(0,"Rang",range(1,len(tcontr)+1))
                if "MONTENCA" in tcontr.columns: tcontr["MONTENCA"] = tcontr["MONTENCA"].apply(fmt)
                if "DATESOUS" in tcontr.columns: tcontr["DATESOUS"] = pd.to_datetime(tcontr["DATESOUS"],errors="coerce").dt.strftime("%d/%m/%Y")
                st.dataframe(tcontr.rename(columns={
                    "NUMEPOLI_P":"N° Police","NOM_ASSU":"Assuré","NOM_APP":"Apporteur",
                    "LIBECATE":"Catégorie","ETAT_POLICE":"État","MONTENCA":"Encaissement",
                    "DATESOUS":"Date souscript."}),
                    use_container_width=True, hide_index=True, height=380)
            else:
                alert("Colonnes contrats incomplètes.","warn")

            st.markdown("---")

            # === C. TOP 10 BANQUES ============================================
            sth("🏦 TOP 10 Banques — Encaissements & nombre de polices", "RÉSEAU BANCAIRE")
            bank_col = next((c for c in ["LIBEBANQ","CODEBANQ","BANQUE","NOM_BANQ","LIBE_BANQ"] if c in df_top.columns), None)
            if bank_col:
                bk = df_top.groupby(bank_col).agg(
                    nb=("NUMEPOLI_P","count") if "NUMEPOLI_P" in df_top.columns else (bank_col,"count"),
                    ca=("MONTENCA","sum") if "MONTENCA" in df_top.columns else (bank_col,"count"),
                ).reset_index()
                bk = bk[bk[bank_col].astype(str).str.strip().isin(["","nan","NaN","None"])==False]
                bca, bcb = st.columns(2)
                with bca:
                    st.plotly_chart(_top10_bar(bk.sort_values("ca",ascending=False)[[bank_col,"ca"]],
                        "💰 Top 10 Banques par encaissements", "#0d7a5f"), use_container_width=True)
                with bcb:
                    st.plotly_chart(_top10_bar(bk.sort_values("nb",ascending=False)[[bank_col,"nb"]],
                        "📋 Top 10 Banques par nombre de polices", "#3b6fa0"), use_container_width=True)
                tbk = bk.sort_values("ca",ascending=False).head(10).reset_index(drop=True)
                tbk.insert(0,"Rang",range(1,len(tbk)+1))
                tbk["CA"] = tbk["ca"].apply(fmt)
                st.dataframe(tbk[["Rang",bank_col,"nb","CA"]].rename(
                    columns={bank_col:"Banque","nb":"Polices"}),
                    use_container_width=True, hide_index=True)
            else:
                alert("Aucune colonne 'banque' (LIBEBANQ/CODEBANQ/BANQUE) détectée dans le portefeuille.","info")

            st.markdown("---")

            # === D. TOP 10 VILLES (LIBEVILL) ==================================
            sth("🏙️ TOP 10 Villes — Réseau commercial AFG", "GÉOGRAPHIE")
            if "LIBEVILL" in df_top.columns:
                vl = df_top.groupby("LIBEVILL").agg(
                    nb=("NUMEPOLI_P","count") if "NUMEPOLI_P" in df_top.columns else ("LIBEVILL","count"),
                    ca=("MONTENCA","sum") if "MONTENCA" in df_top.columns else ("LIBEVILL","count"),
                    nb_comm=("NOM_APP","nunique") if "NOM_APP" in df_top.columns else ("LIBEVILL","count"),
                ).reset_index()
                vl = vl[vl["LIBEVILL"].astype(str).str.strip()!=""]
                vca, vcb = st.columns(2)
                with vca:
                    st.plotly_chart(_top10_bar(vl.sort_values("ca",ascending=False)[["LIBEVILL","ca"]],
                        "💰 Top 10 Villes par CA", "#c9a84c"), use_container_width=True)
                with vcb:
                    st.plotly_chart(_top10_bar(vl.sort_values("nb",ascending=False)[["LIBEVILL","nb"]],
                        "📋 Top 10 Villes par nb polices", "#e85d3a"), use_container_width=True)
                tvl = vl.sort_values("ca",ascending=False).head(10).reset_index(drop=True)
                tvl.insert(0,"Rang",range(1,len(tvl)+1))
                tvl["CA"] = tvl["ca"].apply(fmt)
                st.dataframe(tvl[["Rang","LIBEVILL","nb","nb_comm","CA"]].rename(
                    columns={"LIBEVILL":"Ville","nb":"Polices","nb_comm":"Commerciaux"}),
                    use_container_width=True, hide_index=True)
            else:
                alert("Colonne LIBEVILL absente du portefeuille.","warn")

            st.markdown("---")

            # === E. TOP 10 PRODUITS (LIBECATE) ================================
            sth("🛒 TOP 10 Produits / Catégories — Polices & encaissements", "GAMME COMMERCIALE")
            if "LIBECATE" in df_top.columns:
                pr = df_top.groupby("LIBECATE").agg(
                    nb=("NUMEPOLI_P","count") if "NUMEPOLI_P" in df_top.columns else ("LIBECATE","count"),
                    ca=("MONTENCA","sum") if "MONTENCA" in df_top.columns else ("LIBECATE","count"),
                ).reset_index()
                pr = pr[pr["LIBECATE"].astype(str).str.strip()!=""]
                pca, pcb = st.columns(2)
                with pca:
                    st.plotly_chart(_top10_bar(pr.sort_values("ca",ascending=False)[["LIBECATE","ca"]],
                        "💰 Top 10 Produits par CA", "#4f46e5"), use_container_width=True)
                with pcb:
                    st.plotly_chart(_top10_bar(pr.sort_values("nb",ascending=False)[["LIBECATE","nb"]],
                        "📋 Top 10 Produits par nb polices", "#a78bfa"), use_container_width=True)
                tpr = pr.sort_values("ca",ascending=False).head(10).reset_index(drop=True)
                tpr.insert(0,"Rang",range(1,len(tpr)+1))
                tpr["CA"] = tpr["ca"].apply(fmt)
                st.dataframe(tpr[["Rang","LIBECATE","nb","CA"]].rename(
                    columns={"LIBECATE":"Produit","nb":"Polices"}),
                    use_container_width=True, hide_index=True)

            # === Export consolidé Top 10 multi-axes ===========================
            st.markdown("---")
            buf_top = io.BytesIO()
            with pd.ExcelWriter(buf_top, engine="openpyxl") as wr:
                if "NOM_ASSU" in df_top.columns:
                    cli.sort_values("ca",ascending=False).head(10).to_excel(wr, sheet_name="Top10_Clients", index=False)
                if "MONTENCA" in df_top.columns and "NUMEPOLI_P" in df_top.columns:
                    df_top.sort_values("MONTENCA",ascending=False).head(10)[cols_ct].to_excel(wr, sheet_name="Top10_Contrats", index=False)
                if bank_col:
                    bk.sort_values("ca",ascending=False).head(10).to_excel(wr, sheet_name="Top10_Banques", index=False)
                if "LIBEVILL" in df_top.columns:
                    vl.sort_values("ca",ascending=False).head(10).to_excel(wr, sheet_name="Top10_Villes", index=False)
                if "LIBECATE" in df_top.columns:
                    pr.sort_values("ca",ascending=False).head(10).to_excel(wr, sheet_name="Top10_Produits", index=False)
                rank.head(13).to_excel(wr, sheet_name="Top13_Commerciaux", index=False)
            st.download_button(
                f"⬇️ Télécharger les TOP 10 multi-axes ({yr_label(yr_cl)})",
                data=buf_top.getvalue(),
                file_name=f"AFG_TOP10_MultiAxes_{yr_label(yr_cl)}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — REPRÉSENTATION & STATISTIQUES (portefeuille Excel + BIA interne)
# ═══════════════════════════════════════════════════════════════════════════════
elif "Représentation BIA" in nav:
    pf_ext = st.session_state.get("portefeuille_ext", None)

    # ── Sélecteur d'année global ───────────────────────────────────────────
    yr_rep = year_selector("yr_rep_global", "📅 Filtrer tous les indicateurs par année(s)")

    # ── Données BIA interne ────────────────────────────────────────────────
    df_bia_all = pd.read_sql_query("SELECT * FROM bulletins_bia ORDER BY created_at DESC", gc())
    df_bia_f = filter_by_year(df_bia_all, yr_rep, date_col="date_saisie") if not df_bia_all.empty else df_bia_all

    # ── Données portefeuille Excel ────────────────────────────────────────
    pf_f = filter_pf_by_year(pf_ext, yr_rep) if pf_ext is not None else None

    # ════════════════════════════════════════════════════════════════════════
    # KPIs GLOBAUX
    # ════════════════════════════════════════════════════════════════════════
    sth(f"📊 Indicateurs Clés — {yr_label(yr_rep)}", "TABLEAU DE BORD COMPLET")

    if pf_f is not None:
        nb_total   = len(pf_f)
        nb_actif   = (pf_f["ETAT_POLICE"]=="ACTIF").sum()   if "ETAT_POLICE" in pf_f.columns else 0
        nb_resil   = (pf_f["ETAT_POLICE"]=="RESILIE").sum() if "ETAT_POLICE" in pf_f.columns else 0
        nb_inactif = (pf_f["ETAT_POLICE"]=="INACTIF").sum() if "ETAT_POLICE" in pf_f.columns else 0
        ca_total   = pf_f["MONTENCA"].sum()    if "MONTENCA" in pf_f.columns else 0
        cotis_moy  = pf_f["COTI_PERIODIQUE"].dropna().mean() if "COTI_PERIODIQUE" in pf_f.columns else 0
        nb_agents  = pf_f["NOM_APP"].nunique() if "NOM_APP" in pf_f.columns else 0
        tx_ret     = nb_actif/max(nb_total,1)*100
        tx_res     = nb_resil/max(nb_total,1)*100
    else:
        nb_total=nb_actif=nb_resil=nb_inactif=ca_total=nb_agents=0; cotis_moy=0; tx_ret=tx_res=0

    nb_bia  = len(df_bia_f)
    nb_bval = len(df_bia_f[df_bia_f["statut_bia"]=="Validé"]) if not df_bia_f.empty else 0
    cot_bia = df_bia_f["cotisation_fcfa"].sum() if not df_bia_f.empty and "cotisation_fcfa" in df_bia_f.columns else 0

    # Ligne 1 : KPIs portefeuille
    if pf_f is not None:
        k1,k2,k3,k4,k5,k6,k7 = st.columns(7)
        with k1: kpi("📋 Total contrats",f"{nb_total:,}",f"portefeuille {yr_label(yr_rep)}","","")
        with k2: kpi("✅ Actifs",f"{nb_actif:,}",f"Rétention {tx_ret:.1f}%","green","")
        with k3: kpi("📉 Résiliés",f"{nb_resil:,}",f"Résil. {tx_res:.1f}%","red","")
        with k4: kpi("😴 Inactifs",f"{nb_inactif:,}","","amber","")
        with k5: kpi("💰 Encaissements",fmt(ca_total),"MONTENCA total","gold","")
        with k6: kpi("💳 Cotis. moy.",fmt(cotis_moy),"périodique","teal","")
        with k7: kpi("👤 Apporteurs",str(nb_agents),"agents actifs","","")
        st.markdown("---")

    # Ligne 2 : KPIs BIA internes
    b1,b2,b3,b4 = st.columns(4)
    with b1: kpi("📝 BIA saisis",str(nb_bia),f"période : {yr_label(yr_rep)}","gold","📝")
    with b2: kpi("✅ BIA validés",str(nb_bval),f"{nb_bval/max(nb_bia,1)*100:.0f}%","green","✅")
    with b3: kpi("💾 Brouillons",str(nb_bia-nb_bval),"","amber","💾")
    with b4: kpi("💰 Cotisations BIA",fmt(cot_bia),"total saisi","teal","💰")

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════════════
    # ONGLETS GRAPHIQUES
    # ════════════════════════════════════════════════════════════════════════
    tabs = st.tabs([
        "📊 Portefeuille","📅 Évolution temporelle","🏆 Agents","👥 Profil clients",
        "🗺️ Géographie","🩺 Risques compagnie","📝 BIA internes"
    ])

    # ── TAB 1 : PORTEFEUILLE ────────────────────────────────────────────────
    with tabs[0]:
        if pf_f is None:
            alert("📥 Importez votre portefeuille Excel depuis la page **Accueil** pour voir ces graphiques.", "info")
        else:
            c1,c2,c3 = st.columns(3)
            with c1:
                etat_cnt = pf_f["ETAT_POLICE"].value_counts().reset_index()
                etat_cnt.columns = ["État","Nb"]
                colors_e = {"ACTIF":GREEN,"RESILIE":RED,"INACTIF":AMBER,"ECHU":"#5A6478","SUSPENDU":GOLD}
                fig_e = px.pie(etat_cnt, values="Nb", names="État", hole=0.45,
                    color="État", color_discrete_map=colors_e)
                fig_e.update_traces(textinfo="percent+value", textfont_size=11)
                chl(fig_e, 320, "📊 Répartition par état des polices")
                st.plotly_chart(fig_e, use_container_width=True)
            with c2:
                cat_cnt = pf_f["LIBECATE"].value_counts().reset_index()
                cat_cnt.columns = ["Catégorie","Nb"]
                fig_cat = px.bar(cat_cnt, x="Nb", y="Catégorie", orientation="h",
                    color="Nb", color_continuous_scale=[[0,BLUEL],[1,NAVY]], text="Nb")
                fig_cat.update_traces(textposition="outside")
                fig_cat.update_layout(coloraxis_showscale=False, yaxis=dict(tickfont=dict(size=9)))
                chl(fig_cat, 320, "🛒 Contrats par catégorie de produit")
                st.plotly_chart(fig_cat, use_container_width=True)
            with c3:
                if "SEXERISQ" in pf_f.columns:
                    sex_cnt = pf_f["SEXERISQ"].replace({"M":"Homme","F":"Femme"}).value_counts().reset_index()
                    sex_cnt.columns = ["Sexe","Nb"]
                    fig_sex = px.pie(sex_cnt, values="Nb", names="Sexe", hole=0.45,
                        color_discrete_sequence=[NAVY,GOLD])
                    fig_sex.update_traces(textinfo="percent+label", textfont_size=11)
                    chl(fig_sex, 320, "👥 Répartition par sexe des assurés")
                    st.plotly_chart(fig_sex, use_container_width=True)

            c4,c5 = st.columns(2)
            with c4:
                # Distribution cotisations périodiques
                cot_d = pf_f["COTI_PERIODIQUE"].dropna()
                cot_d = cot_d[(cot_d > 0) & (cot_d < 500000)]  # outliers exclus
                if not cot_d.empty:
                    fig_dist = px.histogram(cot_d, nbins=40,
                        color_discrete_sequence=[BLUEL],
                        labels={"value":"Cotisation (FCFA)","count":"Nb contrats"})
                    chl(fig_dist, 300, "💳 Distribution des cotisations périodiques")
                    st.plotly_chart(fig_dist, use_container_width=True)
            with c5:
                # CA par catégorie
                if "MONTENCA" in pf_f.columns:
                    ca_cat = pf_f.groupby("LIBECATE")["MONTENCA"].sum().reset_index().sort_values("MONTENCA",ascending=False)
                    ca_cat.columns = ["Catégorie","CA"]
                    ca_cat["CA_fmt"] = ca_cat["CA"].apply(fmt)
                    fig_ca_cat = px.bar(ca_cat, x="CA", y="Catégorie", orientation="h",
                        color="CA", color_continuous_scale=[[0,GOLD],[1,NAVY]],
                        text="CA_fmt")
                    fig_ca_cat.update_traces(textposition="outside")
                    fig_ca_cat.update_layout(coloraxis_showscale=False, yaxis=dict(tickfont=dict(size=9)))
                    chl(fig_ca_cat, 300, "💰 Encaissements par catégorie (MONTENCA)")
                    st.plotly_chart(fig_ca_cat, use_container_width=True)

    # ── TAB 2 : ÉVOLUTION TEMPORELLE ────────────────────────────────────────
    with tabs[1]:
        if pf_f is None:
            alert("Importez le portefeuille Excel pour voir les graphiques d'évolution.", "info")
        else:
            pf_evo = pf_ext.copy()  # On utilise TOUT le portefeuille pour l'évolution
            pf_evo["ANNEE"] = pd.to_datetime(pf_evo["DATESOUS"], errors="coerce").dt.year
            pf_evo["MOIS"]  = pd.to_datetime(pf_evo["DATESOUS"], errors="coerce").dt.to_period("M").astype(str)
            pf_evo = pf_evo[pf_evo["ANNEE"].between(1996, 2026)]

            ann_grp = pf_evo.groupby("ANNEE").agg(
                nb=("NUMEPOLI_P","count"),
                ca=("MONTENCA","sum"),
                actifs=("ETAT_POLICE", lambda x:(x=="ACTIF").sum()),
                resil=("ETAT_POLICE",  lambda x:(x=="RESILIE").sum()),
            ).reset_index().dropna()

            c1,c2 = st.columns(2)
            with c1:
                fig_an = make_subplots(specs=[[{"secondary_y":True}]])
                fig_an.add_trace(go.Bar(x=ann_grp["ANNEE"], y=ann_grp["nb"],
                    name="📋 Nb souscriptions", marker_color=BLUEL, opacity=0.8), secondary_y=False)
                fig_an.add_trace(go.Scatter(x=ann_grp["ANNEE"], y=ann_grp["ca"],
                    name="💰 Encaissements", line=dict(color=GOLD, width=3),
                    mode="lines+markers", marker=dict(size=8,color=GOLD)), secondary_y=True)
                chl(fig_an, 360, "📅 Souscriptions et encaissements annuels (1996–2025)")
                fig_an.update_yaxes(title_text="Nb contrats", secondary_y=False)
                fig_an.update_yaxes(title_text="Encaissements FCFA", secondary_y=True, showgrid=False)
                st.plotly_chart(fig_an, use_container_width=True)
            with c2:
                fig_ar = go.Figure()
                fig_ar.add_trace(go.Bar(x=ann_grp["ANNEE"], y=ann_grp["actifs"],
                    name="✅ Actifs", marker_color=GREEN, opacity=0.85))
                fig_ar.add_trace(go.Bar(x=ann_grp["ANNEE"], y=ann_grp["resil"],
                    name="📉 Résiliés", marker_color=RED, opacity=0.75))
                fig_ar.update_layout(barmode="group")
                chl(fig_ar, 360, "📊 Actifs vs Résiliés par année de souscription")
                st.plotly_chart(fig_ar, use_container_width=True)

            # Évolution par catégorie
            cats_top5 = pf_evo["LIBECATE"].value_counts().head(5).index.tolist()
            pf_evo_cat = pf_evo[pf_evo["LIBECATE"].isin(cats_top5)]
            cat_ann = pf_evo_cat.groupby(["ANNEE","LIBECATE"])["NUMEPOLI_P"].count().reset_index()
            cat_ann.columns = ["Année","Catégorie","Nb"]
            fig_cat_evo = px.line(cat_ann, x="Année", y="Nb", color="Catégorie",
                markers=True, title="📈 Évolution annuelle par catégorie (Top 5)",
                color_discrete_sequence=[NAVY,GOLD,GREEN,RED,TEAL])
            fig_cat_evo.update_layout(height=360, legend=dict(font=dict(size=9)))
            st.plotly_chart(fig_cat_evo, use_container_width=True)

    # ── TAB 3 : AGENTS ──────────────────────────────────────────────────────
    with tabs[2]:
        if pf_f is None:
            alert("Importez le portefeuille Excel pour voir les statistiques agents.", "info")
        else:
            agents = pf_f.groupby("NOM_APP").agg(
                nb=("NUMEPOLI_P","count"),
                ca=("MONTENCA","sum"),
                actifs=("ETAT_POLICE", lambda x:(x=="ACTIF").sum()),
                cotis=("COTI_PERIODIQUE","sum"),
                produits=("LIBECATE","nunique"),
            ).reset_index().sort_values("ca", ascending=False)
            agents = agents[agents["NOM_APP"].notna() & (agents["NOM_APP"].str.strip()!="")]
            agents["commercial"] = agents["NOM_APP"].str.strip().str.title()
            agents["tx_actif"] = (agents["actifs"]/agents["nb"].clip(1)*100).round(1)

            c1,c2 = st.columns(2)
            with c1:
                top15 = agents.head(15).sort_values("ca")
                fig_ag = go.Figure(go.Bar(
                    x=top15["ca"], y=top15["commercial"],
                    orientation="h",
                    marker=dict(
                        color=top15["tx_actif"],
                        colorscale=[[0,RED],[0.5,AMBER],[1,GREEN]],
                        showscale=True,
                        colorbar=dict(title="% Actifs",len=0.7)),
                    text=[f"{fmt(v)} ({r:.0f}%)" for v,r in zip(top15["ca"],top15["tx_actif"])],
                    textposition="outside", textfont=dict(size=9),
                    hovertemplate="<b>%{y}</b><br>CA : %{x:,.0f} FCFA<extra></extra>"))
                chl(fig_ag, 480, "💰 Top 15 apporteurs — CA (couleur = % actifs)")
                fig_ag.update_layout(yaxis=dict(tickfont=dict(size=9)))
                st.plotly_chart(fig_ag, use_container_width=True)
            with c2:
                top15_nb = agents.head(15).sort_values("nb")
                fig_nb = go.Figure(go.Bar(
                    x=top15_nb["nb"], y=top15_nb["commercial"],
                    orientation="h", marker_color=BLUEL,
                    text=top15_nb["nb"], textposition="outside",
                    hovertemplate="<b>%{y}</b><br>Contrats : %{x}<extra></extra>"))
                chl(fig_nb, 480, "📋 Top 15 apporteurs — Nombre de contrats")
                fig_nb.update_layout(yaxis=dict(tickfont=dict(size=9)))
                st.plotly_chart(fig_nb, use_container_width=True)

            # Tableau agents
            sth("📋 Tableau complet des apporteurs")
            agents_disp = agents.head(50).copy()
            agents_disp["CA"] = agents_disp["ca"].apply(fmt)
            agents_disp["Cotisations"] = agents_disp["cotis"].apply(fmt)
            agents_disp["% Actifs"] = agents_disp["tx_actif"].apply(lambda x: f"{x:.1f}%")
            st.dataframe(
                agents_disp[["commercial","nb","actifs","CA","% Actifs","produits"]].rename(
                    columns={"commercial":"Apporteur","nb":"Contrats","actifs":"Actifs","produits":"Produits"}),
                use_container_width=True, hide_index=True, height=400)

    # ── TAB 4 : PROFIL CLIENTS ───────────────────────────────────────────────
    with tabs[3]:
        if pf_f is None:
            alert("Importez le portefeuille Excel pour voir le profil clients.", "info")
        else:
            c1,c2,c3 = st.columns(3)
            with c1:
                # Âge des assurés
                if "DATENAIS" in pf_f.columns:
                    ages = (pd.Timestamp.now() - pd.to_datetime(pf_f["DATENAIS"], errors="coerce")).dt.days / 365
                    ages = ages.dropna()
                    ages = ages[(ages >= 0) & (ages <= 100)]
                    fig_age = px.histogram(ages, nbins=30, color_discrete_sequence=[NAVY],
                        labels={"value":"Âge","count":"Nb"})
                    chl(fig_age, 300, "🎂 Distribution des âges des assurés")
                    st.plotly_chart(fig_age, use_container_width=True)
            with c2:
                # Villes
                vill_cnt = pf_f["LIBEVILL"].value_counts().head(12).reset_index()
                vill_cnt.columns = ["Ville","Nb"]
                fig_v = px.bar(vill_cnt, x="Nb", y="Ville", orientation="h",
                    color="Nb", color_continuous_scale=[[0,TEAL],[1,NAVY]], text="Nb")
                fig_v.update_traces(textposition="outside")
                fig_v.update_layout(coloraxis_showscale=False, yaxis=dict(tickfont=dict(size=9)))
                chl(fig_v, 300, "📍 Assurés par ville (Top 12)")
                st.plotly_chart(fig_v, use_container_width=True)
            with c3:
                # Sexe
                sx_c = pf_f["SEXERISQ"].replace({"M":"Homme","F":"Femme"}).value_counts().reset_index()
                sx_c.columns = ["Sexe","Nb"]
                fig_sx = px.pie(sx_c, values="Nb", names="Sexe", hole=0.48,
                    color_discrete_sequence=[NAVY,GOLD])
                fig_sx.update_traces(textinfo="percent+label+value", textfont_size=11)
                chl(fig_sx, 300, "👥 Répartition hommes / femmes")
                st.plotly_chart(fig_sx, use_container_width=True)

            # Heatmap Ville × Catégorie
            if "LIBECATE" in pf_f.columns and "LIBEVILL" in pf_f.columns:
                top_villes = pf_f["LIBEVILL"].value_counts().head(8).index.tolist()
                top_cats   = pf_f["LIBECATE"].value_counts().head(6).index.tolist()
                heat_data = pf_f[pf_f["LIBEVILL"].isin(top_villes) & pf_f["LIBECATE"].isin(top_cats)]
                heat_pivot = heat_data.pivot_table(index="LIBEVILL", columns="LIBECATE", values="NUMEPOLI_P", aggfunc="count", fill_value=0)
                fig_heat = px.imshow(heat_pivot, color_continuous_scale=[[0,"white"],[0.5,BLUEL],[1,NAVY]],
                    text_auto=True, aspect="auto")
                chl(fig_heat, 380, "🔥 Heatmap — Contrats par Ville × Catégorie")
                st.plotly_chart(fig_heat, use_container_width=True)

    # ── TAB 5 : GÉOGRAPHIE ──────────────────────────────────────────────────
    with tabs[4]:
        if pf_f is None:
            alert("Importez le portefeuille Excel pour voir la carte géographique.", "info")
        else:
            c1,c2 = st.columns(2)
            with c1:
                vill_cnt2 = pf_f["LIBEVILL"].value_counts().reset_index()
                vill_cnt2.columns = ["Ville","Nb"]
                fig_vg = px.bar(vill_cnt2.head(15), x="Nb", y="Ville", orientation="h",
                    color="Nb", color_continuous_scale=[[0,BLUEL],[1,NAVY]], text="Nb")
                fig_vg.update_traces(textposition="outside")
                fig_vg.update_layout(coloraxis_showscale=False)
                chl(fig_vg, 480, "📍 Top 15 villes — Nombre de contrats")
                st.plotly_chart(fig_vg, use_container_width=True)
            with c2:
                vill_ca = pf_f.groupby("LIBEVILL")["MONTENCA"].sum().reset_index().sort_values("MONTENCA",ascending=False).head(15)
                vill_ca.columns = ["Ville","CA"]
                vill_ca["CA_fmt"] = vill_ca["CA"].apply(fmt)
                fig_vca = px.bar(vill_ca.sort_values("CA"), x="CA", y="Ville", orientation="h",
                    color="CA", color_continuous_scale=[[0,GOLD],[1,NAVY]], text="CA_fmt")
                fig_vca.update_traces(textposition="outside")
                fig_vca.update_layout(coloraxis_showscale=False)
                chl(fig_vca, 480, "💰 Top 15 villes — Encaissements (MONTENCA)")
                st.plotly_chart(fig_vca, use_container_width=True)

    # ── TAB 6 : RISQUES COMPAGNIE ────────────────────────────────────────────
    with tabs[5]:
        sth("⚠️ Surveillance des Risques — AFG Assurances Bénin Vie", "RISK MANAGEMENT CIMA")
        if pf_f is not None:
            tx_res_r  = nb_resil/max(nb_total,1)*100
            tx_ina_r  = nb_inactif/max(nb_total,1)*100
            tx_act_r  = nb_actif/max(nb_total,1)*100
            ca_moy_ct = ca_total/max(nb_total,1)
            nb_echu   = (pf_f["ETAT_POLICE"]=="ECHU").sum() if "ETAT_POLICE" in pf_f.columns else 0

            r1,r2,r3,r4,r5 = st.columns(5)
            with r1:
                risk_r = "red" if tx_res_r>50 else ("amber" if tx_res_r>35 else "green")
                kpi("📉 Taux résiliation",f"{tx_res_r:.1f}%",
                    "⚠️ CRITIQUE" if tx_res_r>50 else ("⚠️ Élevé" if tx_res_r>35 else "✅ Normal"),risk_r,"")
            with r2:
                risk_a = "amber" if tx_act_r<40 else ("green" if tx_act_r>60 else "")
                kpi("✅ Taux rétention",f"{tx_act_r:.1f}%",
                    "✅ Bon" if tx_act_r>60 else "⚠️ Faible",risk_a,"")
            with r3:
                kpi("😴 Inactifs",f"{nb_inactif:,}",f"{tx_ina_r:.1f}%","amber" if nb_inactif>3000 else "","")
            with r4:
                kpi("⌛ Échus",f"{nb_echu:,}","contrats arrivés à terme","","")
            with r5:
                kpi("💰 CA moy./contrat",fmt(ca_moy_ct),"encaissement moyen","teal","")

            # Alertes CIMA
            st.markdown("---")
            sth("🚨 Alertes & Indicateurs CIMA")
            alertes = []
            if tx_res_r > 50: alertes.append(("CRITIQUE","📉",f"Taux de résiliation de {tx_res_r:.1f}% — Norme CIMA : max 40%. Action corrective urgente requise.","danger"))
            elif tx_res_r > 35: alertes.append(("ATTENTION","⚠️",f"Taux de résiliation de {tx_res_r:.1f}% — Supérieur à la recommandation AFG (35%).","warn"))
            if tx_act_r < 30: alertes.append(("CRITIQUE","🔴",f"Seulement {tx_act_r:.1f}% de contrats actifs — Portefeuille en risque de dépréciation.","danger"))
            if nb_inactif > 3000: alertes.append(("ATTENTION","😴",f"{nb_inactif:,} contrats inactifs — Campagne de réactivation recommandée.","warn"))
            if ca_moy_ct < 100000: alertes.append(("INFO","💰",f"Encaissement moyen de {fmt(ca_moy_ct)} par contrat — Besoin de montée en gamme.","info"))
            if not alertes:
                alertes.append(("OK","✅","Tous les indicateurs sont dans les normes CIMA. Continuez sur cette lancée !","good"))
            for niv, icn, msg, typ in alertes:
                alert(f"<b>{icn} {niv}</b> — {msg}", typ)

            # Graphique risques
            risk_data = pd.DataFrame({
                "Indicateur": ["Actifs","Résiliés","Inactifs","Échus","Suspendus"],
                "Nb": [nb_actif, nb_resil, nb_inactif, nb_echu,
                       (pf_f["ETAT_POLICE"]=="SUSPENDU").sum() if "ETAT_POLICE" in pf_f.columns else 0],
                "Couleur": [GREEN, RED, AMBER, "#5A6478", GOLD]
            })
            fig_risk = px.bar(risk_data, x="Indicateur", y="Nb",
                color="Indicateur",
                color_discrete_map=dict(zip(risk_data["Indicateur"],risk_data["Couleur"])),
                text="Nb")
            fig_risk.update_traces(texttemplate="%{text:,}", textposition="outside")
            fig_risk.update_layout(showlegend=False)
            chl(fig_risk, 320, "🔍 Répartition des contrats par état — Vue risques")
            st.plotly_chart(fig_risk, use_container_width=True)
        else:
            alert("📥 Importez le portefeuille Excel depuis la page **Accueil** pour voir le tableau de risques.", "info")

    # ── TAB 7 : BIA INTERNES ────────────────────────────────────────────────
    with tabs[6]:
        sth("📝 Statistiques BIA internes (saisis dans le système)")
        if df_bia_f.empty:
            alert("Aucun BIA enregistré dans le système.", "info")
        else:
            c1,c2,c3 = st.columns(3)
            with c1:
                stat_cnt = df_bia_f["statut_bia"].value_counts().reset_index()
                stat_cnt.columns = ["Statut","Nb"]
                fig_st = px.pie(stat_cnt, values="Nb", names="Statut", hole=0.45,
                    color="Statut",
                    color_discrete_map={"Validé":GREEN,"Brouillon":AMBER,"En cours":BLUEL,"Annulé":RED})
                fig_st.update_traces(textinfo="percent+label", textfont_size=11)
                chl(fig_st, 300, "📊 BIA par statut")
                st.plotly_chart(fig_st, use_container_width=True)
            with c2:
                if "type_contrat" in df_bia_f.columns:
                    prod_cnt = df_bia_f["type_contrat"].value_counts().head(10).reset_index()
                    prod_cnt.columns = ["Produit","Nb"]
                    fig_pr = px.bar(prod_cnt, x="Nb", y="Produit", orientation="h",
                        color="Nb", color_continuous_scale=[[0,BLUEL],[1,NAVY]], text="Nb")
                    fig_pr.update_traces(textposition="outside")
                    fig_pr.update_layout(coloraxis_showscale=False)
                    chl(fig_pr, 300, "🛒 BIA par produit")
                    st.plotly_chart(fig_pr, use_container_width=True)
            with c3:
                if "periodicite" in df_bia_f.columns:
                    per_cnt = df_bia_f["periodicite"].value_counts().reset_index()
                    per_cnt.columns = ["Périodicité","Nb"]
                    fig_per = px.bar(per_cnt, x="Nb", y="Périodicité", orientation="h",
                        color="Nb", color_continuous_scale=[[0,TEAL],[1,GREEN]], text="Nb")
                    fig_per.update_traces(textposition="outside")
                    fig_per.update_layout(coloraxis_showscale=False)
                    chl(fig_per, 300, "📅 BIA par périodicité")
                    st.plotly_chart(fig_per, use_container_width=True)

            # Évolution mensuelle BIA
            if "date_saisie" in df_bia_f.columns:
                df_bia_f2 = df_bia_f.copy()
                df_bia_f2["mois"] = pd.to_datetime(df_bia_f2["date_saisie"], errors="coerce").dt.to_period("M").astype(str)
                evo_m = df_bia_f2.groupby("mois").agg(nb=("numero_bia","count"), cot=("cotisation_fcfa","sum")).reset_index()
                if not evo_m.empty:
                    fig_evo = make_subplots(specs=[[{"secondary_y":True}]])
                    fig_evo.add_trace(go.Bar(x=evo_m["mois"],y=evo_m["nb"],name="📋 Nb BIA",marker_color=BLUEL,opacity=0.82),secondary_y=False)
                    fig_evo.add_trace(go.Scatter(x=evo_m["mois"],y=evo_m["cot"],name="💰 Cotisations",
                        line=dict(color=GOLD,width=3),mode="lines+markers",marker=dict(size=7,color=GOLD)),secondary_y=True)
                    chl(fig_evo, 320, "📅 BIA saisis et cotisations par mois")
                    fig_evo.update_yaxes(title_text="Nb BIA",secondary_y=False)
                    fig_evo.update_yaxes(title_text="Cotisations (FCFA)",secondary_y=True,showgrid=False)
                    st.plotly_chart(fig_evo, use_container_width=True)

    # Ancienne section contrats (conservée)
    st.markdown("---")
    sth("📋 Liste & Saisie des contrats","GESTION")
    df_bia_all = pd.read_sql_query("SELECT * FROM bulletins_bia ORDER BY created_at DESC", gc())
    if df_bia_all.empty:
        alert("Aucun BIA enregistré. Saisissez des BIA pour voir les graphiques.","info")
        st.stop()

    # Sélecteur d'année pour les BIA
    yr_bia_rep = year_selector("yr_bia_rep","📅 Filtrer les BIA par année de saisie")
    df_bia_f = filter_by_year(df_bia_all, yr_bia_rep, date_col="date_saisie")
    if df_bia_f.empty:
        alert(f"Aucun BIA pour {yr_label(yr_bia_rep)}. Sélectionnez 'Toutes les années'.","warn")
        df_bia_f = df_bia_all

    nb_bia_r = len(df_bia_f)
    nb_val_r = len(df_bia_f[df_bia_f["statut_bia"]=="Validé"])
    nb_bro_r = len(df_bia_f[df_bia_f["statut_bia"]=="Brouillon"])
    cot_r    = df_bia_f["cotisation_fcfa"].sum() if "cotisation_fcfa" in df_bia_f.columns else 0
    nb_sig_r = df_bia_f["sig_souscripteur"].notna().sum() if "sig_souscripteur" in df_bia_f.columns else 0

    # KPIs BIA
    rk1,rk2,rk3,rk4,rk5 = st.columns(5)
    with rk1: kpi("📝 BIA total",str(nb_bia_r),f"période : {yr_label(yr_bia_rep)}","gold","📝")
    with rk2: kpi("✅ Validés",str(nb_val_r),f"{nb_val_r/max(nb_bia_r,1)*100:.0f}%","green","✅")
    with rk3: kpi("💾 Brouillons",str(nb_bro_r),f"{nb_bro_r/max(nb_bia_r,1)*100:.0f}%","amber","💾")
    with rk4: kpi("💰 Cotisations",fmt(cot_r),"total","teal","💰")
    with rk5: kpi("✍️ Avec signatures",str(nb_sig_r),f"{nb_sig_r/max(nb_bia_r,1)*100:.0f}%","","✍️")

    st.markdown("---")

    tab_bia1, tab_bia2, tab_bia3, tab_bia4 = st.tabs([
        "📊 Statuts & Produits","👥 Clients & Agents","📅 Évolution temporelle","🗺️ Géographie"
    ])

    with tab_bia1:
        c1,c2,c3 = st.columns(3)
        with c1:
            # Statuts
            stat_cnt = df_bia_f["statut_bia"].value_counts().reset_index()
            stat_cnt.columns = ["Statut","Nb"]
            fig_st = px.pie(stat_cnt, values="Nb", names="Statut", hole=0.45,
                color="Statut",
                color_discrete_map={"Validé":GREEN,"Brouillon":AMBER,
                    "En cours":BLUEL,"Annulé":RED,"Suspendu":DGRAY,
                    "En attente de documents":GOLD})
            fig_st.update_traces(textinfo="percent+label", textfont_size=11)
            chl(fig_st, 300, "📊 Répartition des BIA par statut")
            st.plotly_chart(fig_st, use_container_width=True)
        with c2:
            # Produits
            if "type_contrat" in df_bia_f.columns:
                prod_cnt = df_bia_f["type_contrat"].value_counts().reset_index()
                prod_cnt.columns = ["Produit","Nb"]
                fig_pr = px.bar(prod_cnt.head(10), x="Nb", y="Produit", orientation="h",
                    color="Nb", color_continuous_scale=[[0,BLUEL],[1,NAVY]],
                    text="Nb")
                fig_pr.update_traces(textposition="outside")
                fig_pr.update_layout(coloraxis_showscale=False)
                chl(fig_pr, 300, "🛒 BIA par produit (Top 10)")
                st.plotly_chart(fig_pr, use_container_width=True)
        with c3:
            # Groupe produit
            if "groupe_produit" in df_bia_f.columns:
                grp_cnt = df_bia_f["groupe_produit"].value_counts().reset_index()
                grp_cnt.columns = ["Groupe","Nb"]
                colors_g_bia = [GROUPE_COLORS.get(g,NAVY) for g in grp_cnt["Groupe"]]
                fig_gp = px.pie(grp_cnt, values="Nb", names="Groupe", hole=0.45,
                    color_discrete_sequence=colors_g_bia)
                fig_gp.update_traces(textinfo="percent+label", textfont_size=10)
                chl(fig_gp, 300, "🏷️ BIA par groupe officiel AFG")
                st.plotly_chart(fig_gp, use_container_width=True)

        c4,c5 = st.columns(2)
        with c4:
            # Périodicité
            if "periodicite" in df_bia_f.columns:
                per_cnt = df_bia_f["periodicite"].value_counts().reset_index()
                per_cnt.columns = ["Périodicité","Nb"]
                fig_per = px.bar(per_cnt, x="Nb", y="Périodicité", orientation="h",
                    color="Nb", color_continuous_scale=[[0,TEAL],[1,GREEN]], text="Nb")
                fig_per.update_traces(textposition="outside")
                fig_per.update_layout(coloraxis_showscale=False)
                chl(fig_per, 280, "📅 Périodicité des cotisations BIA")
                st.plotly_chart(fig_per, use_container_width=True)
        with c5:
            # Mode de règlement
            if "mode_reglement" in df_bia_f.columns:
                mode_cnt = df_bia_f["mode_reglement"].dropna().value_counts().reset_index()
                mode_cnt.columns = ["Mode","Nb"]
                fig_mode = px.pie(mode_cnt, values="Nb", names="Mode", hole=0.42,
                    color_discrete_sequence=[GOLD,BLUEL,GREEN,AMBER,TEAL])
                fig_mode.update_traces(textinfo="percent+label", textfont_size=10)
                chl(fig_mode, 280, "💳 Mode de règlement BIA")
                st.plotly_chart(fig_mode, use_container_width=True)

    with tab_bia2:
        c1,c2 = st.columns(2)
        with c1:
            sth("🏆 Top commerciaux — BIA saisis")
            if "nom_apporteur" in df_bia_f.columns:
                top_ag = df_bia_f.groupby("nom_apporteur").agg(
                    nb=("numero_bia","count"),
                    cot=("cotisation_fcfa","sum"),
                    val=("statut_bia", lambda x:(x=="Validé").sum())
                ).reset_index().sort_values("nb", ascending=False).head(15)
                top_ag["Cotisations"] = top_ag["cot"].apply(fmt)
                top_ag["Taux valid."] = (top_ag["val"]/top_ag["nb"].clip(1)*100).round(1).astype(str)+"%"
                medals_bia = ["🥇","🥈","🥉"]+[""]*(len(top_ag)-3)
                top_ag.insert(0,"Rang",[f"{medals_bia[i]} {i+1}" for i in range(len(top_ag))])
                st.dataframe(
                    top_ag[["Rang","nom_apporteur","nb","Cotisations","val","Taux valid."]].rename(
                        columns={"nom_apporteur":"Apporteur","nb":"BIA saisis","val":"Validés"}),
                    use_container_width=True, hide_index=True, height=380)
                # Graphique agents
                fig_ag = px.bar(top_ag.head(10), x="nb", y="nom_apporteur",
                    orientation="h", color="nb",
                    color_continuous_scale=[[0,BLUEL],[1,NAVY]], text="nb")
                fig_ag.update_traces(textposition="outside")
                fig_ag.update_layout(coloraxis_showscale=False)
                chl(fig_ag, 320, "🏆 Top 10 apporteurs — Nombre de BIA")
                st.plotly_chart(fig_ag, use_container_width=True)
        with c2:
            sth("👥 Profil des souscripteurs")
            # Répartition civilité
            if "contractant_titre" in df_bia_f.columns:
                tit_cnt = df_bia_f["contractant_titre"].replace("","Non renseigné").value_counts().reset_index()
                tit_cnt.columns = ["Civilité","Nb"]
                fig_tit = px.pie(tit_cnt, values="Nb", names="Civilité", hole=0.45,
                    color_discrete_sequence=[NAVY,GOLD,BLUEL,DGRAY])
                fig_tit.update_traces(textinfo="percent+label", textfont_size=11)
                chl(fig_tit, 260, "👤 Répartition par civilité (M./Mme/Mlle)")
                st.plotly_chart(fig_tit, use_container_width=True)
            # Professions Top 10
            if "contractant_profession" in df_bia_f.columns:
                prof_cnt = df_bia_f["contractant_profession"].replace("","Non renseigné")                    .value_counts().reset_index().head(10)
                prof_cnt.columns = ["Profession","Nb"]
                fig_prof = px.bar(prof_cnt, x="Nb", y="Profession", orientation="h",
                    color="Nb", color_continuous_scale=[[0,TEAL],[1,NAVY]], text="Nb")
                fig_prof.update_traces(textposition="outside")
                fig_prof.update_layout(coloraxis_showscale=False)
                chl(fig_prof, 320, "💼 Top 10 professions des souscripteurs")
                st.plotly_chart(fig_prof, use_container_width=True)
            # Cotisations distribution
            if "cotisation_fcfa" in df_bia_f.columns:
                cot_data = df_bia_f["cotisation_fcfa"].dropna()
                if not cot_data.empty:
                    fig_cot = px.histogram(cot_data, nbins=20,
                        color_discrete_sequence=[GOLD],
                        title="💰 Distribution des montants de cotisation")
                    chl(fig_cot, 260, "💰 Distribution des cotisations (FCFA)")
                    st.plotly_chart(fig_cot, use_container_width=True)

    with tab_bia3:
        sth("📅 Évolution temporelle des BIA")
        if "date_saisie" in df_bia_f.columns:
            df_bia_f["date_saisie_dt"] = pd.to_datetime(df_bia_f["date_saisie"], errors="coerce")
            df_bia_f["mois_bia"] = df_bia_f["date_saisie_dt"].dt.to_period("M").astype(str)
            df_bia_f["annee_bia"] = df_bia_f["date_saisie_dt"].dt.year

            # Évolution mensuelle
            evo_m = df_bia_f.groupby("mois_bia").agg(
                nb=("numero_bia","count"),
                cot=("cotisation_fcfa","sum")).reset_index().sort_values("mois_bia")
            if not evo_m.empty:
                fig_evo = make_subplots(specs=[[{"secondary_y":True}]])
                fig_evo.add_trace(go.Bar(
                    x=evo_m["mois_bia"], y=evo_m["nb"],
                    name="📋 Nb BIA", marker_color=BLUEL, opacity=0.82), secondary_y=False)
                fig_evo.add_trace(go.Scatter(
                    x=evo_m["mois_bia"], y=evo_m["cot"],
                    name="💰 Cotisations", line=dict(color=GOLD,width=3),
                    mode="lines+markers", marker=dict(size=7,color=GOLD)), secondary_y=True)
                chl(fig_evo, 340, "📅 BIA saisis et cotisations par mois")
                fig_evo.update_yaxes(title_text="Nb BIA", secondary_y=False)
                fig_evo.update_yaxes(title_text="Cotisations (FCFA)", secondary_y=True, showgrid=False)
                st.plotly_chart(fig_evo, use_container_width=True)

            # Évolution annuelle
            evo_a = df_bia_f.groupby("annee_bia").agg(
                nb=("numero_bia","count"),
                val=("statut_bia", lambda x:(x=="Validé").sum()),
                cot=("cotisation_fcfa","sum")).reset_index().dropna()
            if not evo_a.empty:
                fig_ann_bia = go.Figure()
                fig_ann_bia.add_bar(x=evo_a["annee_bia"], y=evo_a["nb"],
                    name="Total BIA", marker_color=BLUEL, opacity=0.8)
                fig_ann_bia.add_bar(x=evo_a["annee_bia"], y=evo_a["val"],
                    name="BIA Validés", marker_color=GREEN, opacity=0.9)
                fig_ann_bia.update_layout(barmode="group")
                chl(fig_ann_bia, 300, "📊 BIA par année — Total vs Validés")
                st.plotly_chart(fig_ann_bia, use_container_width=True)

    with tab_bia4:
        sth("🗺️ Géographie — BIA par agence et ville")
        c1,c2 = st.columns(2)
        with c1:
            if "agence_saisie" in df_bia_f.columns:
                ag_cnt = df_bia_f["agence_saisie"].replace("","Non renseignée").value_counts().reset_index()
                ag_cnt.columns = ["Agence","Nb"]
                fig_ag2 = px.bar(ag_cnt, x="Nb", y="Agence", orientation="h",
                    color="Nb", color_continuous_scale=[[0,BLUEL],[1,NAVY]],
                    text="Nb")
                fig_ag2.update_traces(textposition="outside")
                fig_ag2.update_layout(coloraxis_showscale=False)
                chl(fig_ag2, 420, "🏢 BIA par agence AFG")
                st.plotly_chart(fig_ag2, use_container_width=True)
        with c2:
            sth("📊 Cotisations par agence")
            if "agence_saisie" in df_bia_f.columns and "cotisation_fcfa" in df_bia_f.columns:
                ag_cot = df_bia_f.groupby("agence_saisie").agg(
                    cot=("cotisation_fcfa","sum"),nb=("numero_bia","count")).reset_index()
                ag_cot = ag_cot[ag_cot["agence_saisie"].notna() & (ag_cot["agence_saisie"]!="")]
                ag_cot = ag_cot.sort_values("cot", ascending=False)
                if not ag_cot.empty:
                    fig_ac = px.bar(ag_cot, x="cot", y="agence_saisie", orientation="h",
                        color="cot",
                        color_continuous_scale=[[0,GOLD],[1,NAVY]],
                        text=[fmt(v) for v in ag_cot["cot"]])
                    fig_ac.update_traces(textposition="outside")
                    fig_ac.update_layout(coloraxis_showscale=False)
                    chl(fig_ac, 420, "💰 Cotisations totales par agence")
                    st.plotly_chart(fig_ac, use_container_width=True)

        # Tableau récapitulatif par agence
        sth("📊 Tableau récapitulatif BIA par agence")
        if "agence_saisie" in df_bia_f.columns:
            recap = df_bia_f.groupby("agence_saisie").agg(
                nb=("numero_bia","count"),
                val=("statut_bia", lambda x:(x=="Validé").sum()),
                bro=("statut_bia", lambda x:(x=="Brouillon").sum()),
                cot=("cotisation_fcfa","sum"),
                agents=("nom_apporteur","nunique")
            ).reset_index().sort_values("nb",ascending=False)
            recap["cot_fmt"] = recap["cot"].apply(fmt)
            recap["taux_val"] = (recap["val"]/recap["nb"].clip(1)*100).round(1).astype(str)+"%"
            st.dataframe(
                recap[["agence_saisie","nb","val","bro","taux_val","cot_fmt","agents"]].rename(
                    columns={"agence_saisie":"Agence","nb":"Total BIA","val":"Validés",
                             "bro":"Brouillons","taux_val":"Taux valid.","cot_fmt":"Cotisations","agents":"Nb agents"}),
                use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — PRODUITS (18 produits + stats + 3 groupes)
# ═══════════════════════════════════════════════════════════════════════════════
elif "Produits" in nav:
    dp=q("""SELECT p.*,
        COUNT(ct.id) as nb,
        COALESCE(SUM(ct.prime_annuelle+ct.prime_unique),0) as ca,
        COALESCE(AVG(ct.prime_annuelle+ct.prime_unique),0) as moy,
        SUM(CASE WHEN ct.statut='actif' THEN 1 ELSE 0 END) as nb_actif,
        SUM(CASE WHEN ct.statut='résilié' THEN 1 ELSE 0 END) as nb_resilie,
        SUM(CASE WHEN ct.statut='suspendu' THEN 1 ELSE 0 END) as nb_suspendu,
        COALESCE(SUM(ct.capital_assure),0) as cap_total
        FROM produits p LEFT JOIN contrats ct ON ct.produit_id=p.id WHERE p.actif=1
        GROUP BY p.id ORDER BY p.groupe, p.categorie, p.nom""")

    yr_prod=year_selector("yr_prod")
    df_all=q(BASE.replace(f"'{d0s}' AND '{d1s}'","'2010-01-01' AND '2099-12-31'"))
    if not df_all.empty:
        df_all=filter_by_year(df_all,yr_prod,"date_souscription")
        stats_p=get_stats_produits(df_all)
    else:
        stats_p=pd.DataFrame()

    c1,c2,c3,c4=st.columns(4)
    with c1: kpi("18 Produits officiels",str(len(dp)),"catalogue CIMA","gold","🛒")
    with c2: kpi("💰 CA total",fmt(dp['ca'].sum()),"toute période","","")
    with c3: kpi("📋 Contrats vendus",f"{int(dp['nb'].sum()):,}","toute période","","")
    with c4: kpi("❌ Résiliés total",f"{int(dp['nb_resilie'].sum()):,}","","red","")

    # Onglets par GROUPE (3 groupes officiels)
    tg1,tg2,tg3,tg4=st.tabs([
        "🛡️  Groupe 1 — Décès & Vie",
        "💰  Groupe 2 — Épargne & Capitalisation",
        "🔄  Groupe 3 — Contrat Mixte",
        "📊  Vue globale"
    ])

    def render_prod_stats(dp_g,tab):
        with tab:
            for _,row in dp_g.iterrows():
                tx_r=row['nb_resilie']/max(row['nb'],1)*100
                tx_col=RED if tx_r>20 else (AMBER if tx_r>10 else GREEN)
                grp_badge=groupe_badge(row['code'])
                st.markdown(f"""
                <div class="prod-card">
                  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:7px;">
                    <div style="display:flex;align-items:center;gap:8px;">
                      <span class="prod-code">{row['code']}</span>
                      <span style="font-size:13.5px;font-weight:800;color:{NAVY};">{row['nom']}</span>
                      {grp_badge}
                    </div>
                    <div style="text-align:right;font-size:11px;color:{DGRAY};">
                      📋 {int(row['nb']):,} contrats · 💰 CA : {fmt(row['ca'])}
                    </div>
                  </div>
                  <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-top:6px;">
                    <div style="background:#E8F8EE;border-radius:7px;padding:7px;text-align:center;">
                      <div style="font-size:1.1rem;font-weight:900;color:{GREEN};">{int(row['nb_actif']):,}</div>
                      <div style="font-size:9px;color:#5A6478;">✅ Actifs</div>
                    </div>
                    <div style="background:#FDECEA;border-radius:7px;padding:7px;text-align:center;">
                      <div style="font-size:1.1rem;font-weight:900;color:{RED};">{int(row['nb_resilie']):,}</div>
                      <div style="font-size:9px;color:#5A6478;">❌ Résiliés</div>
                    </div>
                    <div style="background:#FFF8E1;border-radius:7px;padding:7px;text-align:center;">
                      <div style="font-size:1.1rem;font-weight:900;color:{AMBER};">{int(row['nb_suspendu']):,}</div>
                      <div style="font-size:9px;color:#5A6478;">⏸ Suspendus</div>
                    </div>
                    <div style="background:rgba(201,162,39,0.1);border-radius:7px;padding:7px;text-align:center;">
                      <div style="font-size:1.1rem;font-weight:900;color:{GOLD};">{fmt(row['moy'])}</div>
                      <div style="font-size:9px;color:#5A6478;">📅 Moy./contrat</div>
                    </div>
                    <div style="background:rgba(192,57,43,0.08);border-radius:7px;padding:7px;text-align:center;">
                      <div style="font-size:1.1rem;font-weight:900;color:{tx_col};">{tx_r:.1f}%</div>
                      <div style="font-size:9px;color:#5A6478;">📉 Tx résil.</div>
                    </div>
                  </div>
                </div>""",unsafe_allow_html=True)

    dp_g1=dp[dp['groupe']=="Groupe 1 — Décès & Vie"]
    dp_g2=dp[dp['groupe']=="Groupe 2 — Épargne & Capitalisation"]
    dp_g3=dp[dp['groupe']=="Groupe 3 — Contrat Mixte"]

    render_prod_stats(dp_g1,tg1)
    render_prod_stats(dp_g2,tg2)
    render_prod_stats(dp_g3,tg3)

    with tg4:
        # Vue globale
        c1,c2=st.columns(2)
        with c1:
            fig=px.bar(dp.sort_values('ca',ascending=True),x='ca',y='nom',orientation='h',
                color='groupe',color_discrete_map=GROUPE_COLORS,text='nb',
                title="💰 CA par produit (coloré par groupe)")
            fig.update_traces(texttemplate='%{text:,} ct.',textposition='outside')
            chl(fig,520,"💰 CA par produit — classé par groupe AFG"); st.plotly_chart(fig,use_container_width=True)
        with c2:
            dp2=dp[dp['nb_resilie']>0].copy()
            dp2['tx_r']=dp2['nb_resilie']/dp2['nb'].clip(1)*100
            fig=px.bar(dp2.sort_values('tx_r'),x='tx_r',y='nom',orientation='h',
                color='tx_r',color_continuous_scale=[[0,GREEN],[0.3,AMBER],[1,RED]],
                title="📉 Taux de résiliation par produit (%)")
            fig.add_vline(x=10,line_dash="dash",line_color=RED,annotation_text="Seuil alerte 10%")
            fig.update_traces(text=[f"{v:.1f}%" for v in dp2.sort_values('tx_r')['tx_r']],textposition='outside')
            chl(fig,520,"📉 Taux de résiliation — rouge = alerte"); fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(fig,use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — COMMERCIAUX (avec filtre multi-années + toutes informations)
# ═══════════════════════════════════════════════════════════════════════════════
elif "Commerciaux" in nav:
    # ═══════════════════════════════════════════════════════════════════════════
    # PAGE COMMERCIAUX — basée sur le portefeuille Excel (NOM_APP / CODEAPPO)
    # NOM_APP   = nom + prénom de l'apporteur (commercial)
    # CODEAPPO  = code unique de l'apporteur (=> mot de passe par défaut)
    # ═══════════════════════════════════════════════════════════════════════════
    pf_ext = st.session_state.get("portefeuille_ext", None)

    if pf_ext is None or "NOM_APP" not in pf_ext.columns or "CODEAPPO" not in pf_ext.columns:
        alert("⚠️ Importez d'abord le portefeuille Excel (colonnes <b>NOM_APP</b> et <b>CODEAPPO</b> requises) "
              "depuis la page Accueil.", "warn")
        alert("📂 <b>Format attendu</b> : Sheet 1 — colonnes principales : "
              "NOM_APP, CODEAPPO, NUMEPOLI_P, NOM_ASSU, ETAT_POLICE, LIBECATE, "
              "MONTENCA, COTI_PERIODIQUE, LIBEVILL, DATESOUS.", "info")
    else:
        t1, t2, t3, t4 = st.tabs([
            "📋 Fiche apporteur",
            "🏆 Classement & scoring",
            "🗺️ Géographie (LIBEVILL)",
            "📥 Import / Export portefeuille",
        ])

        # ─────────── Pré-agrégat global apporteurs (depuis le portefeuille) ───
        df_a = pf_ext.copy()
        df_a["NOM_APP"]  = df_a["NOM_APP"].astype(str).str.strip()
        df_a["CODEAPPO"] = df_a["CODEAPPO"].astype(str).str.strip()
        df_a = df_a[(df_a["NOM_APP"]!="") & (df_a["CODEAPPO"]!="")]
        if "DATESOUS" in df_a.columns:
            df_a["ANNEE"] = pd.to_datetime(df_a["DATESOUS"], errors="coerce").dt.year

        agg_global = df_a.groupby(["NOM_APP","CODEAPPO"]).agg(
            polices=("NUMEPOLI_P","count") if "NUMEPOLI_P" in df_a.columns else ("NOM_APP","count"),
            ca=("MONTENCA","sum") if "MONTENCA" in df_a.columns else ("NOM_APP","count"),
            cotis=("COTI_PERIODIQUE","sum") if "COTI_PERIODIQUE" in df_a.columns else ("NOM_APP","count"),
            actifs=("ETAT_POLICE", lambda x:(x=="ACTIF").sum()) if "ETAT_POLICE" in df_a.columns else ("NOM_APP","count"),
            clients=("NOM_ASSU","nunique") if "NOM_ASSU" in df_a.columns else ("NOM_APP","count"),
            villes=("LIBEVILL","nunique") if "LIBEVILL" in df_a.columns else ("NOM_APP","count"),
            produits=("LIBECATE","nunique") if "LIBECATE" in df_a.columns else ("NOM_APP","count"),
        ).reset_index()
        agg_global["tx_actif"] = (agg_global["actifs"]/agg_global["polices"].clip(1)*100).round(1)
        agg_global["score"] = (
            (agg_global["ca"].clip(lower=0)/max(agg_global["ca"].max(),1)*50) +
            (agg_global["polices"]/max(agg_global["polices"].max(),1)*30) +
            (agg_global["tx_actif"]/100*20)
        ).round(1)
        agg_global = agg_global.sort_values("ca", ascending=False).reset_index(drop=True)

        # ─────────── T1 : Fiche apporteur ─────────────────────────────────────
        with t1:
            sth("📋 Fiche détaillée — Apporteur AFG", "DONNÉES PORTEFEUILLE EXCEL")
            f1, f2 = st.columns([2,1])
            with f1:
                opts = (agg_global["NOM_APP"] + "  [" + agg_global["CODEAPPO"] + "]").tolist()
                sel = st.selectbox(f"👤 Sélectionnez un apporteur ({len(opts)} disponibles)",
                                   opts, key="comm_fiche_sel")
            with f2:
                yr_fiche = year_selector("yr_fiche_comm", "📅 Période")

            row_a = agg_global.iloc[opts.index(sel)]
            sub = df_a[(df_a["NOM_APP"]==row_a["NOM_APP"]) & (df_a["CODEAPPO"]==row_a["CODEAPPO"])].copy()
            if "DATESOUS" in sub.columns:
                sub = filter_pf_by_year(sub, yr_fiche)

            # KPIs apporteur
            k1,k2,k3,k4,k5 = st.columns(5)
            with k1:
                st.markdown(f"""<div class="kpi-card" style="text-align:center;padding:1rem">
                  <div style="font-size:2rem">👤</div>
                  <div style="font-size:13px;font-weight:900;color:{NAVY};line-height:1.2">{row_a['NOM_APP']}</div>
                  <div style="font-size:11px;color:{DGRAY};margin-top:4px">Code : <b>{row_a['CODEAPPO']}</b></div>
                </div>""", unsafe_allow_html=True)
            with k2: kpi("📋 Polices", f"{int(sub.shape[0]):,}", "sur la période", "", "")
            with k3:
                ca_p = sub["MONTENCA"].sum() if "MONTENCA" in sub.columns else 0
                kpi("💰 Encaissements", fmt(ca_p), "MONTENCA", "gold", "")
            with k4:
                act = (sub["ETAT_POLICE"]=="ACTIF").sum() if "ETAT_POLICE" in sub.columns else 0
                kpi("✅ Actives", f"{int(act):,}", f"{(act/max(sub.shape[0],1)*100):.1f}%", "green", "")
            with k5:
                cl = sub["NOM_ASSU"].nunique() if "NOM_ASSU" in sub.columns else 0
                kpi("👥 Clients uniques", f"{int(cl):,}", "portefeuille", "teal", "")

            st.markdown("---")

            # Évolution annuelle
            cE1, cE2 = st.columns(2)
            with cE1:
                if "ANNEE" in sub.columns and "MONTENCA" in sub.columns:
                    evo = sub.dropna(subset=["ANNEE"]).groupby("ANNEE").agg(
                        nb=("NUMEPOLI_P","count"), ca=("MONTENCA","sum")).reset_index()
                    evo = evo[evo["ANNEE"].between(1996,2026)]
                    if not evo.empty:
                        fig = make_subplots(specs=[[{"secondary_y":True}]])
                        fig.add_bar(x=evo["ANNEE"], y=evo["nb"], name="📋 Polices",
                                    marker_color=BLUEL, opacity=0.75)
                        fig.add_scatter(x=evo["ANNEE"], y=evo["ca"], name="💰 CA",
                                        line=dict(color=GOLD,width=3), mode="lines+markers")
                        chl(fig, 320, f"📅 Activité annuelle — {row_a['NOM_APP']}")
                        st.plotly_chart(fig, use_container_width=True)
            with cE2:
                if "LIBECATE" in sub.columns:
                    cat = sub["LIBECATE"].value_counts().head(10).reset_index()
                    cat.columns = ["Produit","Polices"]
                    if not cat.empty:
                        fig = px.bar(cat.sort_values("Polices"), x="Polices", y="Produit",
                                     orientation="h", color="Polices",
                                     color_continuous_scale=[[0,BLUEL],[1,GOLD]])
                        chl(fig, 320, "🛒 Top produits vendus par l'apporteur")
                        st.plotly_chart(fig, use_container_width=True)

            # Top villes de l'apporteur (LIBEVILL)
            if "LIBEVILL" in sub.columns:
                sth("🗺️ Villes d'intervention (LIBEVILL)", "GÉOGRAPHIE COMMERCIALE")
                vl = sub["LIBEVILL"].value_counts().head(15).reset_index()
                vl.columns = ["Ville","Polices"]
                if not vl.empty:
                    fig = px.bar(vl.sort_values("Polices"), x="Polices", y="Ville",
                                 orientation="h", color="Polices",
                                 color_continuous_scale=[[0,"#0d7a5f"],[1,GOLD]])
                    chl(fig, 360, f"🏙️ Villes desservies — {row_a['NOM_APP']}")
                    st.plotly_chart(fig, use_container_width=True)

            # Détail des polices
            sth("📜 Détail des polices de cet apporteur", f"{sub.shape[0]} contrats")
            cols_show = [c for c in ["NUMEPOLI_P","NOM_ASSU","LIBECATE","ETAT_POLICE",
                                     "MONTENCA","COTI_PERIODIQUE","LIBEVILL","DATESOUS"] if c in sub.columns]
            sub_disp = sub[cols_show].copy()
            if "DATESOUS" in sub_disp.columns:
                sub_disp["DATESOUS"] = pd.to_datetime(sub_disp["DATESOUS"], errors="coerce").dt.strftime("%d/%m/%Y")
            for c in ["MONTENCA","COTI_PERIODIQUE"]:
                if c in sub_disp.columns: sub_disp[c] = sub_disp[c].apply(fmt)
            st.dataframe(sub_disp.rename(columns={
                "NUMEPOLI_P":"N° Police","NOM_ASSU":"Assuré","LIBECATE":"Catégorie",
                "ETAT_POLICE":"État","MONTENCA":"Encaissement","COTI_PERIODIQUE":"Cotisation",
                "LIBEVILL":"Ville","DATESOUS":"Date souscript."}),
                use_container_width=True, hide_index=True, height=400)

        # ─────────── T2 : Classement complet & scoring ────────────────────────
        with t2:
            sth("🏆 Scoring de tous les apporteurs", "PORTEFEUILLE OFFICIEL")
            ag = agg_global.copy()
            ag.insert(0,"Rang", range(1, len(ag)+1))
            ag["CA"] = ag["ca"].apply(fmt)
            ag["Cotisations"] = ag["cotis"].apply(fmt)
            ag["%Actifs"] = ag["tx_actif"].apply(lambda x:f"{x:.1f}%")
            ag["Score"] = ag["score"].apply(lambda x:f"{x:.0f}/100")
            cols = ["Rang","NOM_APP","CODEAPPO","polices","actifs","clients","villes","produits","CA","Cotisations","%Actifs","Score"]
            st.dataframe(ag[cols].rename(columns={
                "NOM_APP":"Nom Apporteur","CODEAPPO":"Code","polices":"Polices",
                "actifs":"Actives","clients":"Clients","villes":"Villes","produits":"Produits"}),
                use_container_width=True, hide_index=True, height=560)

            buf_c = io.BytesIO()
            with pd.ExcelWriter(buf_c, engine="openpyxl") as wr:
                ag[cols].to_excel(wr, index=False, sheet_name="Commerciaux_AFG")
            st.download_button("⬇️ Exporter le scoring commerciaux (Excel)",
                data=buf_c.getvalue(),
                file_name=f"AFG_Commerciaux_Scoring_{date.today().isoformat()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True)

        # ─────────── T3 : Géographie commerciaux par LIBEVILL ─────────────────
        with t3:
            sth("🗺️ Répartition géographique des commerciaux (LIBEVILL)", "RÉSEAU AFG")
            if "LIBEVILL" not in df_a.columns:
                alert("Colonne LIBEVILL absente du portefeuille.","warn")
            else:
                geo = df_a.groupby("LIBEVILL").agg(
                    nb_comm=("NOM_APP","nunique"),
                    polices=("NUMEPOLI_P","count") if "NUMEPOLI_P" in df_a.columns else ("LIBEVILL","count"),
                    ca=("MONTENCA","sum") if "MONTENCA" in df_a.columns else ("LIBEVILL","count"),
                ).reset_index().sort_values("nb_comm", ascending=False)
                geo = geo[geo["LIBEVILL"].astype(str).str.strip()!=""]

                cG1, cG2 = st.columns(2)
                with cG1:
                    top_v = geo.head(15).sort_values("nb_comm")
                    fig = px.bar(top_v, x="nb_comm", y="LIBEVILL", orientation="h",
                                 color="nb_comm", color_continuous_scale=[[0,BLUEL],[1,GOLD]],
                                 labels={"nb_comm":"Nb commerciaux","LIBEVILL":"Ville"})
                    chl(fig, 460, "🏙️ Top 15 villes par nombre de commerciaux (NOM_APP)")
                    st.plotly_chart(fig, use_container_width=True)
                with cG2:
                    geo_disp = geo.copy()
                    geo_disp["CA"] = geo_disp["ca"].apply(fmt)
                    st.dataframe(geo_disp[["LIBEVILL","nb_comm","polices","CA"]].rename(
                        columns={"LIBEVILL":"Ville","nb_comm":"Commerciaux","polices":"Polices"}),
                        use_container_width=True, hide_index=True, height=460)

                st.markdown("---")
                sth("👥 Commerciaux d'une ville sélectionnée")
                ville_pick = st.selectbox("🏙️ Ville",
                    sorted(geo["LIBEVILL"].astype(str).unique().tolist()),
                    key="comm_ville_pick")
                sub_v = df_a[df_a["LIBEVILL"]==ville_pick]
                comm_v = sub_v.groupby(["NOM_APP","CODEAPPO"]).agg(
                    polices=("NUMEPOLI_P","count") if "NUMEPOLI_P" in sub_v.columns else ("NOM_APP","count"),
                    ca=("MONTENCA","sum") if "MONTENCA" in sub_v.columns else ("NOM_APP","count"),
                ).reset_index().sort_values("ca", ascending=False)
                comm_v.insert(0,"Rang", range(1, len(comm_v)+1))
                comm_v["CA"] = comm_v["ca"].apply(fmt)
                st.dataframe(comm_v[["Rang","NOM_APP","CODEAPPO","polices","CA"]].rename(
                    columns={"NOM_APP":"Nom Apporteur","CODEAPPO":"Code","polices":"Polices"}),
                    use_container_width=True, hide_index=True, height=380)
                st.caption(f"{len(comm_v)} commerciaux référencés à {ville_pick}.")

        # ─────────── T4 : Import / Export portefeuille ────────────────────────
        with t4:
            sth("📥 Import du portefeuille AFG (NOM_APP / CODEAPPO)", "FORMAT OFFICIEL")
            alert("""<b>Format attendu (Excel)</b> — feuille <b>Sheet 1</b> avec a minima les colonnes :
            <b>NOM_APP</b> (nom + prénom apporteur), <b>CODEAPPO</b> (code apporteur),
            <b>NUMEPOLI_P</b>, <b>NOM_ASSU</b>, <b>ETAT_POLICE</b>, <b>LIBECATE</b>,
            <b>MONTENCA</b>, <b>COTI_PERIODIQUE</b>, <b>LIBEVILL</b>, <b>DATESOUS</b>.<br>
            Le fichier remplace intégralement le portefeuille en mémoire.""","info")

            up = st.file_uploader("📂 Importer le portefeuille (.xlsx)", type=["xlsx","xls"], key="comm_imp_pf")
            if up is not None:
                try:
                    try:    df_new = pd.read_excel(up, sheet_name="Sheet 1")
                    except: df_new = pd.read_excel(up)
                    req = ["NOM_APP","CODEAPPO"]
                    missing = [c for c in req if c not in df_new.columns]
                    if missing:
                        alert(f"❌ Colonnes manquantes : {', '.join(missing)}","danger")
                    else:
                        st.session_state["portefeuille_ext"] = df_new
                        st.cache_data.clear()
                        alert(f"✅ Portefeuille importé : <b>{len(df_new):,}</b> polices, "
                              f"<b>{df_new['NOM_APP'].nunique()}</b> commerciaux uniques.","good")
                        st.dataframe(df_new.head(10), use_container_width=True, hide_index=True)
                except Exception as e:
                    alert(f"Erreur lecture fichier : {e}","danger")

            st.markdown("---")
            sth("📤 Export du référentiel commerciaux (depuis le portefeuille)")
            buf_x = io.BytesIO()
            with pd.ExcelWriter(buf_x, engine="openpyxl") as wr:
                agg_global.to_excel(wr, index=False, sheet_name="Commerciaux")
            st.download_button("⬇️ Télécharger référentiel apporteurs (Excel)",
                data=buf_x.getvalue(),
                file_name=f"AFG_Apporteurs_{date.today().isoformat()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — CLIENTS (avec filtre multi-années + toutes informations)
# ═══════════════════════════════════════════════════════════════════════════════
elif "Clients" in nav:
    yr_cli = year_selector("yr_clients", "📅 Filtrer les clients par année de souscription (DATESOUS)")
    pf_ext_cli = st.session_state.get("portefeuille_ext", None)

    # ── Si portefeuille Excel disponible : KPIs clients filtrés par DATESOUS
    if pf_ext_cli is not None and "NOM_ASSU" in pf_ext_cli.columns:
        df_cli = filter_pf_by_year(pf_ext_cli.copy(), yr_cli)
        st.caption(f"📌 Source : portefeuille Excel · Période : **{yr_label(yr_cli)}** · {len(df_cli):,} polices")
        if df_cli.empty:
            alert(f"Aucun client pour {yr_label(yr_cli)}.","warn"); st.stop()

        agg_cli = df_cli.groupby("NOM_ASSU").agg(
            nb_ct=("NUMEPOLI_P","count") if "NUMEPOLI_P" in df_cli.columns else ("NOM_ASSU","count"),
            ca=("MONTENCA","sum") if "MONTENCA" in df_cli.columns else ("NOM_ASSU","count"),
        ).reset_index()
        agg_cli = agg_cli[agg_cli["NOM_ASSU"].astype(str).str.strip()!=""]

        nb_clients = len(agg_cli)
        nb_assures = int((agg_cli["nb_ct"]>0).sum())
        ca_tot_cli = float(agg_cli["ca"].sum())
        ca_moy_cli = ca_tot_cli/max(nb_clients,1)
        ct_moy = agg_cli["nb_ct"].mean() if nb_clients else 0

        c1,c2,c3,c4=st.columns(4)
        with c1: kpi("👥 Clients distincts",f"{nb_clients:,}",f"période {yr_label(yr_cli)}","gold","")
        with c2: kpi("📋 Polices souscrites",f"{int(agg_cli['nb_ct'].sum()):,}",f"{ct_moy:.1f} / client","","")
        with c3: kpi("💰 CA cumulé",fmt(ca_tot_cli),"encaissements","teal","")
        with c4: kpi("💎 CA moyen / client",fmt(ca_moy_cli),"ARPU","gold","")

        # Graphiques
        c1,c2,c3=st.columns(3)
        with c1:
            if "SEXE_ASSU" in df_cli.columns:
                gn = df_cli["SEXE_ASSU"].astype(str).str.upper().value_counts()
                h = int(gn.get("M",0)+gn.get("MASCULIN",0))
                f = int(gn.get("F",0)+gn.get("FEMININ",0)+gn.get("FÉMININ",0))
                fig=px.pie(values=[h,f],names=["Hommes","Femmes"],hole=0.4,
                    color_discrete_sequence=[BLUEL,GOLD])
                chl(fig,290,f"👥 Genre — {yr_label(yr_cli)}"); st.plotly_chart(fig,use_container_width=True)
        with c2:
            if "LIBEVILL" in df_cli.columns:
                bv = df_cli["LIBEVILL"].dropna().astype(str).value_counts().head(10).sort_values()
                fig=go.Figure(go.Bar(x=bv.values,y=bv.index,orientation='h',
                    marker_color=BLUEL,text=bv.values))
                fig.update_traces(textposition='outside')
                chl(fig,290,f"📍 Top 10 villes — {yr_label(yr_cli)}"); st.plotly_chart(fig,use_container_width=True)
        with c3:
            if "LIBECATE" in df_cli.columns:
                bp = df_cli["LIBECATE"].dropna().astype(str).value_counts().head(8).sort_values()
                fig=go.Figure(go.Bar(x=bp.values,y=bp.index,orientation='h',
                    marker_color=GOLD,text=bp.values))
                fig.update_traces(textposition='outside')
                chl(fig,290,f"🛒 Produits — {yr_label(yr_cli)}"); st.plotly_chart(fig,use_container_width=True)

        sth(f"🏆 Top 50 clients par CA — {yr_label(yr_cli)}")
        top_cli = agg_cli.sort_values("ca",ascending=False).head(50).reset_index(drop=True)
        top_cli.insert(0,"Rang",range(1,len(top_cli)+1))
        top_cli["NOM_ASSU"] = top_cli["NOM_ASSU"].astype(str).str.title()
        top_cli["CA"] = top_cli["ca"].apply(fmt)
        st.dataframe(top_cli[["Rang","NOM_ASSU","nb_ct","CA"]].rename(
            columns={"NOM_ASSU":"Client","nb_ct":"Polices"}),
            use_container_width=True,hide_index=True,height=420)
        st.stop()

    # ── Fallback : BD interne (clients créés par BIA)
    dc=q("SELECT cl.*,COUNT(ct.id) as nb_ct,COALESCE(SUM(ct.prime_annuelle+ct.prime_unique),0) as ca FROM clients cl LEFT JOIN contrats ct ON ct.client_id=cl.id GROUP BY cl.id ORDER BY ca DESC")
    if dc.empty:
        alert("Aucun client en base. Importez le portefeuille Excel depuis la page Accueil pour activer la vue clients filtrée par année.","info")
        st.stop()
    dc['date_naissance']=pd.to_datetime(dc['date_naissance'],errors='coerce')
    dc['age']=dc['date_naissance'].apply(
        lambda d: int((datetime.now()-d).days/365) if pd.notna(d) else 0)
    st.caption(f"📌 Source : BD interne (le filtre par année s'active avec un portefeuille Excel importé)")
    c1,c2,c3,c4=st.columns(4)
    with c1: kpi("👥 Total clients",f"{len(dc):,}","","","")
    with c2: kpi("✅ Clients assurés",str(int((dc['nb_ct']>0).sum())),"avec contrat","green","")
    with c3: kpi("🎂 Âge moyen",f"{dc['age'][dc['age']>0].mean():.0f} ans" if (dc['age']>0).any() else "—","","","")
    with c4: kpi("💵 Revenu moy.",fmt(dc['revenu_mensuel'].mean()) if 'revenu_mensuel' in dc.columns else "—","mensuel","teal","")
    c1,c2,c3=st.columns(3)
    with c1:
        dc_age=dc[dc['age']>0]
        if not dc_age.empty:
            fig=px.histogram(dc_age,x='age',nbins=20,color_discrete_sequence=[NAVY])
            chl(fig,270,"🎂 Distribution des âges des assurés"); st.plotly_chart(fig,use_container_width=True)
    with c2:
        if 'ville' in dc.columns:
            bv=dc.groupby('ville')['id'].count().sort_values(ascending=True)
            fig=go.Figure(go.Bar(x=bv.values,y=bv.index,orientation='h',marker_color=BLUEL,text=bv.values))
            fig.update_traces(textposition='outside')
            chl(fig,270,"📍 Clients par ville"); st.plotly_chart(fig,use_container_width=True)
    with c3:
        if 'profession' in dc.columns:
            bp=dc.groupby('profession')['id'].count().sort_values(ascending=True).tail(8)
            fig=go.Figure(go.Bar(x=bp.values,y=bp.index,orientation='h',marker_color=GOLD,text=bp.values))
            fig.update_traces(textposition='outside')
            chl(fig,270,"💼 Clients par profession"); st.plotly_chart(fig,use_container_width=True)
    sth("📋 Portefeuille clients")
    safe_cols=[c for c in ['code_client','nom','prenom','age','ville','profession','sexe','nb_ct','ca'] if c in dc.columns]
    disp=dc[safe_cols].head(200).copy()
    if 'ca' in disp.columns: disp['ca']=disp['ca'].apply(fmt)
    st.dataframe(disp,use_container_width=True,height=400,hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — SINISTRES
# ═══════════════════════════════════════════════════════════════════════════════
elif "Sinistres" in nav:
    yr_sin = year_selector("yr_sin", "📅 Filtrer les sinistres par année (date_sinistre)")
    try:
        ds=q("SELECT s.*,ct.numero_contrat,ct.capital_assure,cl.nom||' '||cl.prenom as client,p.nom as produit,p.groupe FROM sinistres s JOIN contrats ct ON s.contrat_id=ct.id JOIN clients cl ON ct.client_id=cl.id JOIN produits p ON ct.produit_id=p.id ORDER BY s.date_sinistre DESC")
    except Exception:
        ds=pd.DataFrame()
    if not ds.empty:
        ds = filter_by_year(ds, yr_sin, date_col="date_sinistre")
    st.caption(f"📌 Période : **{yr_label(yr_sin)}**")
    if ds.empty:
        alert("Aucun sinistre enregistré en base de données.","info")
        sth("Ajouter un sinistre manuellement","SAISIE")
        with st.form("add_sinistre"):
            sc1,sc2,sc3=st.columns(3)
            with sc1: sin_ct=st.text_input("N° Contrat")
            with sc2: sin_type=st.selectbox("Type",["Décès","Invalidité","Maladie","Accident","Autre"])
            with sc3: sin_date=st.date_input("Date sinistre",today)
            sc4,sc5=st.columns(2)
            with sc4: sin_rec=st.number_input("Montant réclamé",min_value=0,step=10000)
            with sc5: sin_st=st.selectbox("Statut",["en_cours","réglé","rejeté"])
            if st.form_submit_button("✅ Enregistrer le sinistre"):
                alert("Pour enregistrer un sinistre, le contrat doit d'abord exister en base.","warn")
        st.stop()
    ec=ds[ds['statut']=='en_cours']
    c1,c2,c3,c4,c5=st.columns(5)
    with c1: kpi("⚠️ Total",str(len(ds)),"sinistres","","")
    with c2: kpi("🔄 En cours",str(len(ec)),"à instruire","red" if len(ec)>5 else "","")
    with c3: kpi("✅ Réglés",str(len(ds[ds['statut']=='réglé'])),"clos","green","")
    with c4: kpi("💳 Réclamé",fmt(ds['montant_reclame'].sum()),"total","gold","")
    with c5:
        tr=ds['montant_regle'].sum()/max(ds['montant_reclame'].sum(),1)*100
        kpi("📊 Taux règl.",f"{tr:.1f}%","","teal","")
    c1,c2=st.columns(2)
    with c1:
        bt=ds.groupby('type_sinistre')['id'].count().reset_index()
        fig=px.pie(bt,values='id',names='type_sinistre',hole=0.38,
            color_discrete_sequence=[NAVY,RED,AMBER,TEAL,GREEN,GOLD])
        chl(fig,300,"Types de sinistres déclarés"); st.plotly_chart(fig,use_container_width=True)
    with c2:
        bs=ds.groupby('statut').agg(nb=('id','count'),mt=('montant_reclame','sum')).reset_index()
        fig=px.bar(bs,x='statut',y='mt',color='statut',text='nb',
            color_discrete_map={'réglé':GREEN,'en_cours':AMBER,'rejeté':RED})
        fig.update_traces(texttemplate='%{text} dossiers',textposition='outside')
        chl(fig,300,"Montants réclamés par statut"); fig.update_layout(showlegend=False); st.plotly_chart(fig,use_container_width=True)
    if len(ec)>0: alert(f"{len(ec)} sinistre(s) en cours — Délai CIMA : 10 jours ouvrés max.","warn")
    sth("📋 Registre des sinistres")
    disp=ds[['numero_contrat','client','produit','date_sinistre','type_sinistre','montant_reclame','montant_regle','statut']].copy()
    for col in ['montant_reclame','montant_regle']: disp[col]=disp[col].apply(fmt)
    disp.columns=['N° Contrat','Client','Produit','Date','Type','Réclamé','Réglé','Statut']
    st.dataframe(disp,use_container_width=True,height=360,hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — PRÉVISIONS ML
# ═══════════════════════════════════════════════════════════════════════════════
elif "Prévisions" in nav:
    try:
        from sklearn.linear_model import LinearRegression
        from sklearn.preprocessing import PolynomialFeatures
        from sklearn.metrics import r2_score
    except ImportError:
        alert("scikit-learn requis. Exécutez : pip install scikit-learn","danger"); st.stop()

    yr_ml = year_selector("yr_ml", "📅 Filtrer la base d'entraînement par année (DATESOUS)")
    pf_ext_ml = st.session_state.get("portefeuille_ext", None)

    # Préférer le portefeuille Excel filtré, sinon BD interne
    if pf_ext_ml is not None and "DATESOUS" in pf_ext_ml.columns and "MONTENCA" in pf_ext_ml.columns:
        pfm = filter_pf_by_year(pf_ext_ml.copy(), yr_ml)
        pfm["mois"] = pd.to_datetime(pfm["DATESOUS"], errors="coerce").dt.strftime("%Y-%m")
        dm = pfm.dropna(subset=["mois"]).groupby("mois").agg(
            nb=("DATESOUS","count"), ca=("MONTENCA","sum")).reset_index().sort_values("mois")
        st.caption(f"📌 Source : portefeuille Excel · Période : **{yr_label(yr_ml)}** · {len(pfm):,} polices")
    else:
        dm=q("SELECT strftime('%Y-%m',date_souscription) as mois,COUNT(*) as nb,SUM(prime_annuelle+prime_unique) as ca FROM contrats GROUP BY mois ORDER BY mois")
        dm = filter_by_year(dm, yr_ml, date_col="mois") if not dm.empty else dm
        st.caption(f"📌 Source : BD interne · Période : **{yr_label(yr_ml)}**")
    if len(dm)<4: alert("Données insuffisantes pour la prévision (min. 4 mois). Élargissez la période.","warn"); st.stop()
    dm['t']=range(len(dm)); X=dm[['t']].values; y=dm['ca'].values; yn=dm['nb'].values
    c1,c2=st.columns([3,1])
    with c1: h=st.slider("Horizon de prévision (mois)",1,12,6)
    with c2: deg=st.radio("Degré poly.",[1,2,3],horizontal=True)
    poly=PolynomialFeatures(degree=deg); Xp=poly.fit_transform(X)
    reg=LinearRegression().fit(Xp,y); regn=LinearRegression().fit(Xp,yn)
    r2=r2_score(y,reg.predict(Xp))
    tf=np.arange(len(dm),len(dm)+h).reshape(-1,1)
    pca=np.maximum(reg.predict(poly.transform(tf)),0)
    pnb=np.maximum(regn.predict(poly.transform(tf)),0).astype(int)
    lp=pd.Period(dm['mois'].iloc[-1],'M')
    fm=[(lp+i+1).strftime('%Y-%m') for i in range(h)]
    fig=go.Figure()
    fig.add_scatter(x=dm['mois'],y=dm['ca'],name='📊 CA historique',line=dict(color=NAVY,width=2),mode='lines+markers',marker=dict(size=5))
    fig.add_scatter(x=dm['mois'],y=reg.predict(Xp),name='📈 Tendance',line=dict(color=BLUEL,dash='dot',width=1.5))
    fig.add_scatter(x=fm,y=pca,name='🔮 Prévision',line=dict(color=GOLD,dash='dash',width=3),mode='lines+markers',marker=dict(symbol='star',size=12,color=GOLD))
    fig.add_vrect(x0=dm['mois'].iloc[-1],x1=fm[-1],fillcolor="rgba(201,162,39,0.06)",line_width=0,annotation_text="Zone prévision →")
    chl(fig,400,f"🔮 Prévision CA sur {h} mois — R² = {r2:.3f}"); st.plotly_chart(fig,use_container_width=True)
    c1,c2,c3=st.columns(3)
    with c1: kpi("🔮 CA prévu total",fmt(pca.sum()),f"sur {h} mois","gold","")
    with c2: kpi("📋 Contrats prévus",str(int(pnb.sum())),f"sur {h} mois","","")
    with c3: kpi("📐 R² modèle",f"{r2:.3f}","qualité prévision","green" if r2>0.6 else "red","")
    sth("📊 Tableau prévisionnel")
    pd_df=pd.DataFrame({'Mois':fm,'CA prévu':[fmt(v) for v in pca],'Nb contrats':pnb.tolist(),'CA/contrat':[fmt(v) for v in pca/np.maximum(pnb,1)]})
    st.dataframe(pd_df,use_container_width=True,hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — CARTE BÉNIN
# ═══════════════════════════════════════════════════════════════════════════════
elif "Carte" in nav:
    # ── Carte du Bénin basée sur LIBEVILL du portefeuille (NOM_APP / CODEAPPO)
    COORDS = {
        'COTONOU':[6.3703,2.3912], 'PORTO-NOVO':[6.4969,2.6289], 'PARAKOU':[9.337,2.628],
        'BOHICON':[7.1789,2.0667], 'NATITINGOU':[10.3039,1.3806], 'ABOMEY-CALAVI':[6.4483,2.3522],
        'CALAVI':[6.4483,2.3522], 'LOKOSSA':[6.6333,1.7167], 'OUIDAH':[6.3639,2.0885],
        'ABOMEY':[7.1896,1.9911], 'KANDI':[11.1347,2.938], 'DJOUGOU':[9.7086,1.6664],
        'SAVE':[8.0353,2.4856], 'SAVALOU':[7.9281,1.9756], 'POBE':[6.9803,2.6675],
        'COVE':[7.2225,2.3408], 'DASSA':[7.7811,2.1836], 'DASSA-ZOUME':[7.7811,2.1836],
        'COME':[6.4081,1.8836], 'KETOU':[7.3597,2.6047], 'NIKKI':[9.9403,3.2108],
        'BANIKOARA':[11.2989,2.4392], 'MALANVILLE':[11.8633,3.3886], 'TANGUIETA':[10.6217,1.2697],
        'BEMBEREKE':[10.2289,2.6664], 'AGBANGNIZOUN':[7.0883,1.9683], 'APLAHOUE':[6.9281,1.6800],
        'ALLADA':[6.6650,2.1497], 'GRAND-POPO':[6.2789,1.8267],
    }

    pf_ext = st.session_state.get("portefeuille_ext", None)
    yr_ct = year_selector("yr_carte", "📅 Filtrer la carte par année(s)")

    if pf_ext is None or "LIBEVILL" not in pf_ext.columns:
        alert("⚠️ Importez d'abord le portefeuille Excel (colonne LIBEVILL requise) depuis l'Accueil.","warn")
    else:
        pfm = pf_ext.copy()
        if "DATESOUS" in pfm.columns:
            pfm = filter_pf_by_year(pfm, yr_ct)
        if pfm.empty:
            alert("Aucune donnée sur la période.","info")
        else:
            pfm["VILLE_KEY"] = pfm["LIBEVILL"].astype(str).str.upper().str.strip()
            agg = pfm.groupby("VILLE_KEY").agg(
                nb=("NUMEPOLI_P","count") if "NUMEPOLI_P" in pfm.columns else ("LIBEVILL","count"),
                ca=("MONTENCA","sum") if "MONTENCA" in pfm.columns else ("LIBEVILL","count"),
                actifs=("ETAT_POLICE", lambda x:(x=="ACTIF").sum()) if "ETAT_POLICE" in pfm.columns else ("LIBEVILL","count"),
                nb_comm=("NOM_APP","nunique") if "NOM_APP" in pfm.columns else ("LIBEVILL","count"),
                clients=("NOM_ASSU","nunique") if "NOM_ASSU" in pfm.columns else ("LIBEVILL","count"),
            ).reset_index()
            agg["lat"] = agg["VILLE_KEY"].map(lambda v: COORDS.get(v,[None,None])[0])
            agg["lon"] = agg["VILLE_KEY"].map(lambda v: COORDS.get(v,[None,None])[1])
            unmapped = agg[agg["lat"].isna()]
            agg = agg.dropna(subset=["lat","lon"]).sort_values("nb",ascending=False)

            # KPIs synthèse
            k1,k2,k3,k4 = st.columns(4)
            with k1: kpi("🏙️ Villes couvertes", f"{len(agg):,}", f"sur {agg['nb'].sum():,} polices", "", "")
            with k2: kpi("👥 Commerciaux géolocalisés", f"{int(agg['nb_comm'].sum()):,}", "via LIBEVILL", "gold", "")
            with k3: kpi("👤 Clients", f"{int(agg['clients'].sum()):,}", "uniques", "teal", "")
            with k4: kpi("💰 Encaissements", fmt(agg['ca'].sum()), "total carte", "green", "")

            # Top 5 villes par commerciaux
            sth("🏆 Top 5 villes — Concentration des commerciaux (NOM_APP)", "RÉSEAU AFG")
            top5 = agg.sort_values("nb_comm", ascending=False).head(5)
            cols_top = st.columns(len(top5)) if len(top5) else []
            for i,(_,r) in enumerate(top5.iterrows()):
                with cols_top[i]:
                    st.markdown(f"""
                    <div style="background:linear-gradient(135deg,#003366,#004D99);border-radius:12px;
                         padding:14px;color:white;text-align:center;border:1px solid rgba(201,162,39,.4);">
                      <div style="font-size:11px;color:#E8C84A;font-weight:700;letter-spacing:.08em;">#{i+1}</div>
                      <div style="font-size:14px;font-weight:900;margin:4px 0;">{r['VILLE_KEY'].title()}</div>
                      <div style="font-size:22px;font-weight:900;color:#E8C84A;">{int(r['nb_comm'])}</div>
                      <div style="font-size:10px;opacity:.8;">commerciaux</div>
                      <hr style="border-color:rgba(255,255,255,.15);margin:6px 0;">
                      <div style="font-size:10.5px;">📋 {int(r['nb']):,} polices</div>
                      <div style="font-size:10.5px;">💰 {fmt(r['ca'])}</div>
                    </div>""", unsafe_allow_html=True)

            st.markdown("---")

            # Carte Folium
            try:
                import folium
                from streamlit_folium import st_folium
                m = folium.Map(location=[9.3,2.3], zoom_start=7, tiles='CartoDB positron')
                max_nb = max(agg["nb"].max(), 1)
                for _,r in agg.iterrows():
                    radius = max(8, min(48, (r["nb"]/max_nb)*42 + 6))
                    color = GOLD if r["nb_comm"]>=10 else (BLUEL if r["nb_comm"]>=3 else "#7d9b76")
                    popup_html = (
                        f"<div style='font-family:Inter,sans-serif;min-width:200px'>"
                        f"<b style='color:{NAVY};font-size:13px'>🏙️ {r['VILLE_KEY'].title()}</b><hr style='margin:4px 0'>"
                        f"📋 <b>{int(r['nb']):,}</b> polices<br>"
                        f"✅ <b>{int(r['actifs']):,}</b> actives<br>"
                        f"👥 <b>{int(r['nb_comm'])}</b> commerciaux (NOM_APP)<br>"
                        f"👤 <b>{int(r['clients']):,}</b> clients<br>"
                        f"💰 <b>{fmt(r['ca'])}</b></div>"
                    )
                    folium.CircleMarker(
                        location=[r["lat"],r["lon"]], radius=radius,
                        color=NAVY, fill=True, fill_color=color, fill_opacity=0.78, weight=2,
                        popup=folium.Popup(popup_html, max_width=260),
                        tooltip=f"{r['VILLE_KEY'].title()} · {int(r['nb_comm'])} commerciaux"
                    ).add_to(m)
                    folium.Marker(
                        [r["lat"]+0.08, r["lon"]],
                        icon=folium.DivIcon(html=(
                            f"<div style='font-size:10.5px;font-weight:800;color:{NAVY};white-space:nowrap;"
                            f"background:rgba(255,255,255,.85);padding:1px 5px;border-radius:6px;'>"
                            f"{r['VILLE_KEY'].title()} · <span style='color:{GOLD}'>{int(r['nb_comm'])} comm.</span></div>"))
                    ).add_to(m)

                cmap1, cmap2 = st.columns([3,2])
                with cmap1:
                    sth("🗺️ Carte interactive — Commerciaux AFG par ville (LIBEVILL)")
                    st_folium(m, width=760, height=560, returned_objects=[])
                with cmap2:
                    sth("📋 Détail par ville", "Cliquez les marqueurs")
                    disp = agg[["VILLE_KEY","nb_comm","nb","actifs","clients","ca"]].copy()
                    disp["VILLE_KEY"] = disp["VILLE_KEY"].str.title()
                    disp["ca"] = disp["ca"].apply(fmt)
                    disp.columns = ["Ville","Commerciaux","Polices","Actives","Clients","CA"]
                    st.dataframe(disp, use_container_width=True, hide_index=True, height=540)
            except ImportError:
                fig = px.scatter(agg, x="lon", y="lat",
                    size="nb", color="nb_comm",
                    hover_name=agg["VILLE_KEY"].str.title(),
                    color_continuous_scale=[[0,BLUEL],[1,GOLD]], size_max=55,
                    labels={"nb_comm":"Commerciaux","nb":"Polices"},
                    title="🗺️ Carte des commerciaux AFG — Bénin (LIBEVILL)")
                st.plotly_chart(fig, use_container_width=True)

            # Liste des commerciaux par ville
            st.markdown("---")
            sth("👥 Commerciaux par ville — Détail (NOM_APP / CODEAPPO)", "DRILL-DOWN")
            ville_sel = st.selectbox("🏙️ Sélectionnez une ville",
                ["— Toutes —"] + sorted(agg["VILLE_KEY"].str.title().tolist()),
                key="carte_ville_sel")
            sub = pfm.copy()
            if ville_sel != "— Toutes —":
                sub = sub[sub["VILLE_KEY"]==ville_sel.upper()]
            if "NOM_APP" in sub.columns and "CODEAPPO" in sub.columns:
                comm_d = sub.groupby(["NOM_APP","CODEAPPO"]).agg(
                    polices=("NUMEPOLI_P","count") if "NUMEPOLI_P" in sub.columns else ("NOM_APP","count"),
                    ca=("MONTENCA","sum") if "MONTENCA" in sub.columns else ("NOM_APP","count"),
                    clients=("NOM_ASSU","nunique") if "NOM_ASSU" in sub.columns else ("NOM_APP","count"),
                ).reset_index().sort_values("ca", ascending=False)
                comm_d = comm_d[comm_d["NOM_APP"].astype(str).str.strip()!=""]
                comm_d.insert(0,"Rang", range(1, len(comm_d)+1))
                comm_d["CA"] = comm_d["ca"].apply(fmt)
                st.dataframe(
                    comm_d[["Rang","NOM_APP","CODEAPPO","polices","clients","CA"]].rename(
                        columns={"NOM_APP":"Nom Apporteur","CODEAPPO":"Code","polices":"Polices","clients":"Clients"}),
                    use_container_width=True, hide_index=True, height=420)
                st.caption(f"{len(comm_d)} commerciaux référencés{(' à '+ville_sel) if ville_sel!='— Toutes —' else ''}.")

            if not unmapped.empty:
                with st.expander(f"ℹ️ {len(unmapped)} ville(s) sans coordonnées GPS — non affichée(s) sur la carte"):
                    st.dataframe(unmapped[["VILLE_KEY","nb","nb_comm"]].rename(
                        columns={"VILLE_KEY":"Ville","nb":"Polices","nb_comm":"Commerciaux"}),
                        use_container_width=True, hide_index=True)



# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — EXPORTS  (RAPPORT EXÉCUTIF PROFESSIONNEL PDF + EXCEL + CSV)
# ═══════════════════════════════════════════════════════════════════════════════
elif "Exports" in nav:
    sth("📤 Centre d'Exportation — Rapport Exécutif AFG", "DIRECTION GÉNÉRALE")
    alert("Sélectionnez la ou les années à inclure dans le rapport. <b>Toutes les années</b> = totaux globaux du portefeuille.","info")

    yr_ex = year_selector("yr_ex_rep", "📅 Filtrer le rapport par année(s) de souscription (DATESOUS)")
    pf_ext_rep = st.session_state.get("portefeuille_ext", None)

    # ── Construction des données filtrées ─────────────────────────────────────
    if pf_ext_rep is not None and "DATESOUS" in pf_ext_rep.columns:
        pf_rep = filter_pf_by_year(pf_ext_rep.copy(), yr_ex)
        src_lbl = "Portefeuille Excel AFG (DATESOUS)"
    else:
        pf_rep = None
        src_lbl = "Aucun portefeuille importé — rapport basé sur la BD interne uniquement"

    # BIA filtrés par date_saisie
    df_bia_rep = pd.read_sql_query("SELECT * FROM bulletins_bia", gc())
    if not df_bia_rep.empty:
        df_bia_rep = filter_by_year(df_bia_rep, yr_ex, date_col="date_saisie")

    # Contrats internes filtrés
    df_int_rep = q(BASE)
    if not df_int_rep.empty:
        df_int_rep['eq'] = df_int_rep['prime_annuelle'] + df_int_rep['prime_unique']
        df_int_rep = filter_by_year(df_int_rep, yr_ex, date_col="date_souscription")

    label_yr = yr_label(yr_ex)
    st.caption(f"📌 Source principale : **{src_lbl}** · Période : **{label_yr}**")

    # ── Calcul des KPIs ───────────────────────────────────────────────────────
    if pf_rep is not None and not pf_rep.empty:
        tot_p = len(pf_rep)
        ep = pf_rep["ETAT_POLICE"].astype(str) if "ETAT_POLICE" in pf_rep.columns else pd.Series([], dtype=str)
        nb_actif = int((ep=="ACTIF").sum())
        nb_resil = int((ep=="RESILIE").sum())
        nb_inact = int((ep=="INACTIF").sum())
        nb_echu  = int((ep=="ECHU").sum())
        nb_susp  = int((ep=="SUSPENDU").sum())
        ca_tot   = float(pf_rep["MONTENCA"].sum()) if "MONTENCA" in pf_rep.columns else 0.0
        ca_act   = float(pf_rep[ep=="ACTIF"]["MONTENCA"].sum()) if "MONTENCA" in pf_rep.columns else 0.0
        nb_comm  = int(pf_rep["NOM_APP"].nunique()) if "NOM_APP" in pf_rep.columns else 0
        nb_cli   = int(pf_rep["NOM_ASSU"].nunique()) if "NOM_ASSU" in pf_rep.columns else 0
        tx_actif = nb_actif/max(tot_p,1)*100
        tx_resil = nb_resil/max(tot_p,1)*100
        ticket   = ca_tot/max(tot_p,1)
        arpu     = ca_tot/max(nb_cli,1) if nb_cli else 0
    else:
        tot_p=nb_actif=nb_resil=nb_inact=nb_echu=nb_susp=nb_comm=nb_cli=0
        ca_tot=ca_act=ticket=arpu=tx_actif=tx_resil=0.0

    # KPIs internes (BD)
    nb_bia = len(df_bia_rep)
    cot_bia = float(df_bia_rep["cotisation_fcfa"].sum()) if (not df_bia_rep.empty and "cotisation_fcfa" in df_bia_rep.columns) else 0
    nb_ct_int = len(df_int_rep)

    # ── Affichage synthèse à l'écran ──────────────────────────────────────────
    sth(f"📊 Synthèse — {label_yr}", "INDICATEURS CLÉS")
    k1,k2,k3,k4,k5,k6 = st.columns(6)
    with k1: kpi("📋 Polices", f"{tot_p:,}", "portefeuille filtré","gold","")
    with k2: kpi("✅ Actives", f"{nb_actif:,}", f"{tx_actif:.1f}%","green","")
    with k3: kpi("📉 Résiliées", f"{nb_resil:,}", f"{tx_resil:.1f}%","red" if tx_resil>25 else "amber","")
    with k4: kpi("💰 CA total", fmt(ca_tot), "encaissements","gold","")
    with k5: kpi("👥 Commerciaux", f"{nb_comm:,}", "apporteurs","","")
    with k6: kpi("👤 Clients", f"{nb_cli:,}", "assurés distincts","teal","")

    k7,k8,k9,k10 = st.columns(4)
    with k7: kpi("🎫 Ticket moyen", fmt(ticket), "par police","gold","")
    with k8: kpi("📈 ARPU", fmt(arpu) if arpu else "—", "par client","teal","")
    with k9: kpi("📝 BIA saisis", f"{nb_bia:,}", "période sélectionnée","","")
    with k10: kpi("💳 Cotisations BIA", fmt(cot_bia), "total","gold","")

    st.markdown("---")
    sth("📥 Téléchargements", "RAPPORT PRÊT À DIFFUSER")

    cdl1, cdl2, cdl3 = st.columns(3)

    # ────────────────── 1. RAPPORT PDF EXÉCUTIF ──────────────────────────────
    with cdl1:
        st.subheader("📄 Rapport PDF exécutif")
        st.caption("Document professionnel prêt à diffuser à la Direction Générale.")
        if st.button("🎯 Générer le rapport PDF", use_container_width=True, type="primary"):
            try:
                from reportlab.lib.pagesizes import A4
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.units import cm
                from reportlab.lib import colors as rl_colors
                from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                    TableStyle, PageBreak)
                from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
            except ImportError:
                alert("⚠️ reportlab requis. Exécutez : pip install reportlab","danger"); st.stop()

            buf_pdf = io.BytesIO()
            doc = SimpleDocTemplate(buf_pdf, pagesize=A4,
                leftMargin=1.8*cm, rightMargin=1.8*cm,
                topMargin=2*cm, bottomMargin=2*cm,
                title=f"Rapport Exécutif AFG — {label_yr}",
                author="AFG Assurances Bénin Vie")

            ss = getSampleStyleSheet()
            NAVY_RL = rl_colors.HexColor("#003366")
            GOLD_RL = rl_colors.HexColor("#C9A227")
            GOLDL_RL = rl_colors.HexColor("#E8C84A")
            RED_RL = rl_colors.HexColor("#C0392B")
            LGRAY_RL = rl_colors.HexColor("#F4F6F9")

            st_title = ParagraphStyle("ti", parent=ss["Title"], fontName="Helvetica-Bold",
                fontSize=22, textColor=NAVY_RL, alignment=TA_CENTER, spaceAfter=8)
            st_sub = ParagraphStyle("su", parent=ss["Normal"], fontName="Helvetica",
                fontSize=11, textColor=rl_colors.HexColor("#5A6478"), alignment=TA_CENTER, spaceAfter=18)
            st_h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold",
                fontSize=14, textColor=NAVY_RL, spaceBefore=14, spaceAfter=8)
            st_body = ParagraphStyle("b", parent=ss["BodyText"], fontName="Helvetica",
                fontSize=10, leading=14, alignment=TA_JUSTIFY, textColor=rl_colors.HexColor("#1F2A40"))
            st_callout = ParagraphStyle("c", parent=ss["BodyText"], fontName="Helvetica-Oblique",
                fontSize=10, textColor=NAVY_RL, alignment=TA_CENTER, spaceAfter=6)
            st_small = ParagraphStyle("sm", parent=ss["Normal"], fontName="Helvetica",
                fontSize=8.5, textColor=rl_colors.HexColor("#5A6478"), alignment=TA_CENTER)

            story = []

            # ── PAGE DE GARDE ────────────────────────────────────────────────
            story.append(Spacer(1, 2.5*cm))
            logo_tbl = Table([["AFG\nVIE"]], colWidths=[3.2*cm], rowHeights=[3.2*cm])
            logo_tbl.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,-1),GOLD_RL),
                ("TEXTCOLOR",(0,0),(-1,-1),NAVY_RL),
                ("FONTNAME",(0,0),(-1,-1),"Helvetica-Bold"),
                ("FONTSIZE",(0,0),(-1,-1),22),
                ("ALIGN",(0,0),(-1,-1),"CENTER"),
                ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                ("BOX",(0,0),(-1,-1),1.5,NAVY_RL),
            ]))
            story.append(logo_tbl)
            story.append(Spacer(1, 0.6*cm))
            story.append(Paragraph("AFG ASSURANCES BÉNIN VIE", st_title))
            story.append(Paragraph("Rapport Exécutif — Direction Générale", st_sub))
            story.append(Spacer(1, 1.5*cm))

            cover_data = [
                ["Période couverte", label_yr],
                ["Source des données", src_lbl],
                ["Date d'édition", datetime.now().strftime("%d/%m/%Y à %H:%M")],
                ["Édité par", f"{user.get('nom','—')} ({role})"],
                ["Agence", agence_sel],
                ["Référence", f"AFG-RPT-{datetime.now().strftime('%Y%m%d-%H%M')}"],
            ]
            cover_tbl = Table(cover_data, colWidths=[6*cm, 9.5*cm])
            cover_tbl.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(0,-1),NAVY_RL),
                ("TEXTCOLOR",(0,0),(0,-1),GOLDL_RL),
                ("BACKGROUND",(1,0),(1,-1),LGRAY_RL),
                ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),
                ("FONTNAME",(1,0),(1,-1),"Helvetica"),
                ("FONTSIZE",(0,0),(-1,-1),10),
                ("LEFTPADDING",(0,0),(-1,-1),10),
                ("RIGHTPADDING",(0,0),(-1,-1),10),
                ("TOPPADDING",(0,0),(-1,-1),7),
                ("BOTTOMPADDING",(0,0),(-1,-1),7),
                ("BOX",(0,0),(-1,-1),0.5,NAVY_RL),
                ("INNERGRID",(0,0),(-1,-1),0.25,rl_colors.white),
            ]))
            story.append(cover_tbl)
            story.append(Spacer(1, 2*cm))
            story.append(Paragraph("« A AFG Assurances Benin Vie, nous avons pense a vous ! »", st_callout))
            story.append(Spacer(1, 0.4*cm))
            story.append(Paragraph("Document confidentiel — Usage interne — Direction Generale uniquement",
                ParagraphStyle("conf", parent=st_small, textColor=RED_RL, fontName="Helvetica-Bold")))
            story.append(PageBreak())

            # ── 1. RÉSUMÉ EXÉCUTIF ───────────────────────────────────────────
            story.append(Paragraph("1. Resume executif", st_h1))
            risk_qual = ("critique et exigeant un plan d'action immediat" if tx_resil>50
                        else ("eleve a surveiller" if tx_resil>25 else "maitrise"))
            résumé_txt = (
                f"Le present rapport synthetise les principaux indicateurs de performance "
                f"d'<b>AFG Assurances Benin Vie</b> pour la periode <b>{label_yr}</b>. "
                f"Le portefeuille analyse compte <b>{tot_p:,} polices</b>, dont "
                f"<b>{nb_actif:,} actives</b> ({tx_actif:.1f}%), pour un encaissement total de "
                f"<b>{fmt(ca_tot)}</b>. La compagnie compte <b>{nb_comm:,} apporteurs</b> actifs "
                f"servant <b>{nb_cli:,} assures distincts</b>. Le taux de resiliation s'etablit a "
                f"<b>{tx_resil:.1f}%</b> — niveau {risk_qual}."
            )
            story.append(Paragraph(résumé_txt, st_body))
            story.append(Spacer(1, 0.4*cm))

            # ── 2. INDICATEURS CLÉS ──────────────────────────────────────────
            story.append(Paragraph("2. Indicateurs cles de performance (KPI)", st_h1))
            kpi_data = [
                ["Indicateur","Valeur","Commentaire"],
                ["Polices totales", f"{tot_p:,}", f"Periode : {label_yr}"],
                ["Polices actives", f"{nb_actif:,}", f"{tx_actif:.1f}% du portefeuille"],
                ["Polices resiliees", f"{nb_resil:,}", f"{tx_resil:.1f}% — " + ("CRITIQUE" if tx_resil>50 else ("Eleve" if tx_resil>25 else "Maitrise"))],
                ["Polices inactives", f"{nb_inact:,}", f"{nb_inact/max(tot_p,1)*100:.1f}% — a relancer"],
                ["Polices echues", f"{nb_echu:,}", f"{nb_echu/max(tot_p,1)*100:.1f}%"],
                ["Polices suspendues", f"{nb_susp:,}", f"{nb_susp/max(tot_p,1)*100:.1f}%"],
                ["CA total (encaissements)", fmt(ca_tot), "Tous statuts confondus"],
                ["CA polices actives", fmt(ca_act), "Encaissements polices ACTIF"],
                ["Ticket moyen / police", fmt(ticket), "Encaissement moyen unitaire"],
                ["ARPU (revenu / client)", fmt(arpu) if arpu else "—", "Encaissement moyen par assure"],
                ["Nombre d'apporteurs", f"{nb_comm:,}", "Commerciaux actifs (NOM_APP distincts)"],
                ["Nombre de clients", f"{nb_cli:,}", "Assures distincts (NOM_ASSU)"],
                ["BIA saisis (BD interne)", f"{nb_bia:,}", "Bulletins d'Adhesion"],
                ["Cotisations BIA", fmt(cot_bia), "Total cumule periode"],
            ]
            kpi_tbl = Table(kpi_data, colWidths=[6.5*cm, 4*cm, 6.5*cm], repeatRows=1)
            kpi_tbl.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),NAVY_RL),
                ("TEXTCOLOR",(0,0),(-1,0),GOLDL_RL),
                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
                ("FONTSIZE",(0,0),(-1,0),9.5),
                ("FONTNAME",(0,1),(-1,-1),"Helvetica"),
                ("FONTSIZE",(0,1),(-1,-1),9),
                ("ALIGN",(1,1),(1,-1),"RIGHT"),
                ("ALIGN",(0,0),(-1,0),"CENTER"),
                ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[rl_colors.white, LGRAY_RL]),
                ("LINEBELOW",(0,0),(-1,0),1,GOLD_RL),
                ("BOX",(0,0),(-1,-1),0.5,rl_colors.HexColor("#CCCCCC")),
                ("LEFTPADDING",(0,0),(-1,-1),8),
                ("RIGHTPADDING",(0,0),(-1,-1),8),
                ("TOPPADDING",(0,0),(-1,-1),5),
                ("BOTTOMPADDING",(0,0),(-1,-1),5),
            ]))
            story.append(kpi_tbl)
            story.append(Spacer(1, 0.4*cm))

            # ── 3. RÉPARTITION PAR STATUT ────────────────────────────────────
            story.append(Paragraph("3. Repartition du portefeuille par statut", st_h1))
            stat_data = [
                ["Statut","Nombre","Part","CA estime (FCFA)"],
                ["Actif", f"{nb_actif:,}", f"{tx_actif:.1f}%", fmt(ca_act)],
                ["Resilie", f"{nb_resil:,}", f"{tx_resil:.1f}%", "—"],
                ["Inactif", f"{nb_inact:,}", f"{nb_inact/max(tot_p,1)*100:.1f}%", "—"],
                ["Echu", f"{nb_echu:,}", f"{nb_echu/max(tot_p,1)*100:.1f}%", "—"],
                ["Suspendu", f"{nb_susp:,}", f"{nb_susp/max(tot_p,1)*100:.1f}%", "—"],
                ["TOTAL", f"{tot_p:,}", "100%", fmt(ca_tot)],
            ]
            stat_tbl = Table(stat_data, colWidths=[4.5*cm, 3*cm, 3*cm, 6.5*cm], repeatRows=1)
            stat_tbl.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),NAVY_RL),
                ("TEXTCOLOR",(0,0),(-1,0),GOLDL_RL),
                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
                ("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
                ("BACKGROUND",(0,-1),(-1,-1),GOLD_RL),
                ("TEXTCOLOR",(0,-1),(-1,-1),NAVY_RL),
                ("FONTSIZE",(0,0),(-1,-1),9.5),
                ("ALIGN",(1,0),(-1,-1),"RIGHT"),
                ("ALIGN",(0,0),(-1,0),"CENTER"),
                ("ROWBACKGROUNDS",(0,1),(-1,-2),[rl_colors.white, LGRAY_RL]),
                ("BOX",(0,0),(-1,-1),0.5,rl_colors.HexColor("#CCCCCC")),
                ("INNERGRID",(0,0),(-1,-1),0.25,rl_colors.HexColor("#E0E0E0")),
                ("TOPPADDING",(0,0),(-1,-1),5),
                ("BOTTOMPADDING",(0,0),(-1,-1),5),
            ]))
            story.append(stat_tbl)
            story.append(PageBreak())

            def _make_top_table(rows, col_widths):
                t = Table(rows, colWidths=col_widths, repeatRows=1)
                t.setStyle(TableStyle([
                    ("BACKGROUND",(0,0),(-1,0),NAVY_RL),
                    ("TEXTCOLOR",(0,0),(-1,0),GOLDL_RL),
                    ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
                    ("FONTSIZE",(0,0),(-1,-1),9),
                    ("ALIGN",(0,0),(0,-1),"CENTER"),
                    ("ALIGN",(2,1),(-1,-1),"RIGHT"),
                    ("ROWBACKGROUNDS",(0,1),(-1,-1),[rl_colors.white, LGRAY_RL]),
                    ("BOX",(0,0),(-1,-1),0.5,rl_colors.HexColor("#CCCCCC")),
                    ("TOPPADDING",(0,0),(-1,-1),4),
                    ("BOTTOMPADDING",(0,0),(-1,-1),4),
                ]))
                return t

            # ── 4. TOP COMMERCIAUX ───────────────────────────────────────────
            story.append(Paragraph("4. Top 10 apporteurs (commerciaux)", st_h1))
            if pf_rep is not None and "NOM_APP" in pf_rep.columns:
                tcom = pf_rep.groupby("NOM_APP").agg(
                    nb=("NOM_APP","count"),
                    ca=("MONTENCA","sum") if "MONTENCA" in pf_rep.columns else ("NOM_APP","count"),
                ).reset_index().sort_values("ca",ascending=False).head(10)
                tcom["NOM_APP"] = tcom["NOM_APP"].astype(str).str.title()
                rows = [["Rang","Apporteur","Polices","CA (FCFA)"]]
                for i,(_,r) in enumerate(tcom.iterrows()):
                    rows.append([f"{i+1}", str(r["NOM_APP"])[:40], f"{int(r['nb']):,}", fmt(float(r['ca']))])
                story.append(_make_top_table(rows, [1.5*cm, 8*cm, 3*cm, 4.5*cm]))
            else:
                story.append(Paragraph("<i>Donnees apporteurs indisponibles (importez le portefeuille Excel).</i>", st_body))
            story.append(Spacer(1, 0.4*cm))

            # ── 5. TOP CLIENTS ───────────────────────────────────────────────
            story.append(Paragraph("5. Top 10 clients (par chiffre d'affaires)", st_h1))
            if pf_rep is not None and "NOM_ASSU" in pf_rep.columns:
                tcli = pf_rep.groupby("NOM_ASSU").agg(
                    nb=("NOM_ASSU","count"),
                    ca=("MONTENCA","sum") if "MONTENCA" in pf_rep.columns else ("NOM_ASSU","count"),
                ).reset_index().sort_values("ca",ascending=False).head(10)
                tcli["NOM_ASSU"] = tcli["NOM_ASSU"].astype(str).str.title()
                rows = [["Rang","Client","Contrats","CA (FCFA)"]]
                for i,(_,r) in enumerate(tcli.iterrows()):
                    rows.append([f"{i+1}", str(r["NOM_ASSU"])[:40], f"{int(r['nb']):,}", fmt(float(r['ca']))])
                story.append(_make_top_table(rows, [1.5*cm, 8*cm, 3*cm, 4.5*cm]))
            else:
                story.append(Paragraph("<i>Donnees clients indisponibles.</i>", st_body))
            story.append(PageBreak())

            # ── 6. RÉPARTITION PAR PRODUIT ───────────────────────────────────
            story.append(Paragraph("6. Performance par produit (top 10)", st_h1))
            if pf_rep is not None and "LIBECATE" in pf_rep.columns:
                tprod = pf_rep.groupby("LIBECATE").agg(
                    nb=("LIBECATE","count"),
                    ca=("MONTENCA","sum") if "MONTENCA" in pf_rep.columns else ("LIBECATE","count"),
                ).reset_index().sort_values("nb",ascending=False).head(10)
                rows = [["Rang","Produit","Polices","CA (FCFA)","Part"]]
                for i,(_,r) in enumerate(tprod.iterrows()):
                    rows.append([f"{i+1}", str(r["LIBECATE"])[:35], f"{int(r['nb']):,}",
                        fmt(float(r['ca'])), f"{int(r['nb'])/max(tot_p,1)*100:.1f}%"])
                story.append(_make_top_table(rows, [1.4*cm, 7*cm, 2.6*cm, 4*cm, 2*cm]))
            story.append(Spacer(1, 0.4*cm))

            # ── 7. RÉSEAU GÉOGRAPHIQUE (Top 10 villes) ──────────────────────
            story.append(Paragraph("7. Reseau geographique — Top 10 villes (LIBEVILL)", st_h1))
            if pf_rep is not None and "LIBEVILL" in pf_rep.columns:
                tvil = pf_rep.groupby("LIBEVILL").agg(
                    nb=("LIBEVILL","count"),
                    ca=("MONTENCA","sum") if "MONTENCA" in pf_rep.columns else ("LIBEVILL","count"),
                ).reset_index().sort_values("nb",ascending=False).head(10)
                rows = [["Rang","Ville","Polices","CA (FCFA)"]]
                for i,(_,r) in enumerate(tvil.iterrows()):
                    rows.append([f"{i+1}", str(r["LIBEVILL"])[:30], f"{int(r['nb']):,}", fmt(float(r['ca']))])
                story.append(_make_top_table(rows, [1.5*cm, 8*cm, 3*cm, 4.5*cm]))
            story.append(Spacer(1, 0.4*cm))

            # ── 8. DOMICILIATION BANCAIRE ────────────────────────────────────
            if pf_rep is not None and "LIBEBANQ" in pf_rep.columns:
                story.append(Paragraph("8. Top 10 banques de domiciliation", st_h1))
                tbnk = pf_rep["LIBEBANQ"].dropna().astype(str).value_counts().head(10).reset_index()
                tbnk.columns = ["Banque","Polices"]
                rows = [["Rang","Banque","Polices","Part"]]
                for i,(_,r) in enumerate(tbnk.iterrows()):
                    rows.append([f"{i+1}", str(r["Banque"])[:30], f"{int(r['Polices']):,}",
                        f"{int(r['Polices'])/max(tot_p,1)*100:.1f}%"])
                story.append(_make_top_table(rows, [1.5*cm, 8.5*cm, 3*cm, 3*cm]))
            story.append(PageBreak())

            # ── 9. ANALYSE DES RISQUES ───────────────────────────────────────
            story.append(Paragraph("9. Analyse des risques & recommandations", st_h1))
            risk_lvl = "CRITIQUE" if tx_resil>50 else ("ELEVE" if tx_resil>25 else "MAITRISE")
            risk_explain = ("(au-dessus du seuil critique CIMA de 50%). Une revision des produits Epargne Credit "
                            "et Horizon Retraite est recommandee." if tx_resil>50 else
                            ("(au-dessus du seuil d'alerte de 25%). Mettre en place une campagne de fidelisation."
                             if tx_resil>25 else "(en dessous du seuil d'alerte). Performance saine."))
            risk_txt = (
                f"<b>Niveau de risque global :</b> {risk_lvl}<br/><br/>"
                f"• <b>Taux de resiliation : {tx_resil:.1f}%</b> {risk_explain}<br/>"
                f"• <b>{nb_inact:,} polices inactives</b> representent un gisement de relance "
                f"({nb_inact/max(tot_p,1)*100:.1f}% du portefeuille).<br/>"
                f"• <b>{nb_echu:,} polices echues</b> a analyser pour reconduction tacite ou resiliation administrative.<br/>"
                f"• <b>Concentration geographique</b> : surveiller la dependance aux principales villes du reseau."
            )
            story.append(Paragraph(risk_txt, st_body))
            story.append(Spacer(1, 0.5*cm))

            recos = (
                "<b>Plan d'action recommande :</b><br/>"
                "1. Lancer une campagne de relance ciblee sur les polices inactives sous 30 jours.<br/>"
                "2. Programme d'incentive renforce pour le Top 10 des apporteurs.<br/>"
                "3. Audit des produits a fort taux de resiliation (revue tarifaire et contractuelle).<br/>"
                "4. Renforcement du maillage commercial dans les villes secondaires identifiees.<br/>"
                "5. Mise en place d'un suivi mensuel des KPIs avec ce tableau de bord."
            )
            story.append(Paragraph(recos, st_body))
            story.append(Spacer(1, 0.4*cm))

            # ── 10. CONCLUSION ───────────────────────────────────────────────
            story.append(Paragraph("10. Conclusion", st_h1))
            ccl = (
                f"Ce rapport offre a la Direction Generale d'AFG Assurances Benin Vie une vision "
                f"consolidee du portefeuille pour la periode <b>{label_yr}</b>. Les indicateurs presentes "
                f"permettent de prendre des decisions strategiques eclairees en matiere de pilotage "
                f"commercial, gestion des risques et developpement du reseau. Le tableau de bord PDG v19 "
                f"est conforme aux exigences CIMA et met a disposition des outils de prevision et de "
                f"surveillance temps reel pour piloter la performance avec precision."
            )
            story.append(Paragraph(ccl, st_body))
            story.append(Spacer(1, 0.6*cm))
            story.append(Paragraph("« A AFG Assurances Benin Vie, nous avons pense a vous ! »", st_callout))

            # ── PIED DE PAGE ─────────────────────────────────────────────────
            def _footer(canvas, doc_):
                canvas.saveState()
                canvas.setFont("Helvetica", 8)
                canvas.setFillColor(rl_colors.HexColor("#5A6478"))
                canvas.drawString(1.8*cm, 1*cm,
                    "AFG Assurances Benin Vie · Conforme CIMA · Groupe AFG Holding")
                canvas.drawRightString(A4[0]-1.8*cm, 1*cm,
                    f"Page {doc_.page} · {datetime.now().strftime('%d/%m/%Y')}")
                canvas.setStrokeColor(GOLD_RL)
                canvas.setLineWidth(0.6)
                canvas.line(1.8*cm, 1.3*cm, A4[0]-1.8*cm, 1.3*cm)
                canvas.restoreState()

            doc.build(story, onFirstPage=_footer, onLaterPages=_footer)

            pdf_bytes = buf_pdf.getvalue()
            st.session_state["last_pdf_report"] = pdf_bytes
            st.session_state["last_pdf_name"] = f"AFG_Rapport_Executif_{label_yr.replace(', ','-').replace(' ','_')}.pdf"
            st.success(f"✅ Rapport PDF généré ({len(pdf_bytes)//1024} Ko) — Cliquez ci-dessous pour télécharger.")

        if st.session_state.get("last_pdf_report"):
            st.download_button(
                "⬇️ Télécharger le rapport PDF",
                data=st.session_state["last_pdf_report"],
                file_name=st.session_state.get("last_pdf_name","AFG_Rapport.pdf"),
                mime="application/pdf",
                use_container_width=True, type="primary")

    # ────────────────── 2. EXCEL MULTI-ONGLETS ───────────────────────────────
    with cdl2:
        st.subheader("📊 Excel multi-onglets")
        st.caption("Fichier complet avec données brutes, KPIs, classements.")
        if st.button("📥 Générer Excel complet", use_container_width=True):
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as wr:
                kpis_df = pd.DataFrame({
                    'Indicateur': ['Période','Source','Polices totales','Polices actives',
                        'Polices résiliées','Polices inactives','Polices échues','Polices suspendues',
                        'CA total','CA actifs','Ticket moyen','ARPU','Taux actif','Taux résiliation',
                        'Apporteurs','Clients distincts','BIA saisis','Cotisations BIA'],
                    'Valeur': [label_yr, src_lbl, tot_p, nb_actif, nb_resil, nb_inact, nb_echu, nb_susp,
                        ca_tot, ca_act, ticket, arpu, f"{tx_actif:.2f}%", f"{tx_resil:.2f}%",
                        nb_comm, nb_cli, nb_bia, cot_bia]
                })
                kpis_df.to_excel(wr, sheet_name='KPIs', index=False)

                if pf_rep is not None and not pf_rep.empty:
                    pf_rep.head(10000).to_excel(wr, sheet_name='Portefeuille', index=False)
                    if "NOM_APP" in pf_rep.columns:
                        tcom = pf_rep.groupby("NOM_APP").agg(
                            polices=("NOM_APP","count"),
                            ca=("MONTENCA","sum") if "MONTENCA" in pf_rep.columns else ("NOM_APP","count"),
                        ).reset_index().sort_values("ca",ascending=False)
                        tcom.to_excel(wr, sheet_name='Top apporteurs', index=False)
                    if "NOM_ASSU" in pf_rep.columns:
                        tcli = pf_rep.groupby("NOM_ASSU").agg(
                            polices=("NOM_ASSU","count"),
                            ca=("MONTENCA","sum") if "MONTENCA" in pf_rep.columns else ("NOM_ASSU","count"),
                        ).reset_index().sort_values("ca",ascending=False).head(100)
                        tcli.to_excel(wr, sheet_name='Top 100 clients', index=False)
                    if "LIBECATE" in pf_rep.columns:
                        tprod = pf_rep.groupby("LIBECATE").agg(
                            polices=("LIBECATE","count"),
                            ca=("MONTENCA","sum") if "MONTENCA" in pf_rep.columns else ("LIBECATE","count"),
                        ).reset_index().sort_values("polices",ascending=False)
                        tprod.to_excel(wr, sheet_name='Produits', index=False)
                    if "LIBEVILL" in pf_rep.columns:
                        tvil = pf_rep.groupby("LIBEVILL").agg(
                            polices=("LIBEVILL","count"),
                            ca=("MONTENCA","sum") if "MONTENCA" in pf_rep.columns else ("LIBEVILL","count"),
                        ).reset_index().sort_values("polices",ascending=False)
                        tvil.to_excel(wr, sheet_name='Villes', index=False)

                if not df_bia_rep.empty:
                    bia_export = df_bia_rep.drop(
                        columns=['sig_souscripteur','sig_assure','sig_conseiller'], errors='ignore')
                    bia_export.to_excel(wr, sheet_name='BIA', index=False)

            st.download_button("⬇️ Télécharger Excel", data=buf.getvalue(),
                file_name=f"AFG_Rapport_Complet_{label_yr.replace(', ','-').replace(' ','_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True)

    # ────────────────── 3. CSV ───────────────────────────────────────────────
    with cdl3:
        st.subheader("📄 CSV portefeuille")
        st.caption("Export brut pour analyses externes.")
        if st.button("📥 Générer CSV", use_container_width=True):
            if pf_rep is not None and not pf_rep.empty:
                csv_data = pf_rep.to_csv(index=False).encode('utf-8-sig')
                st.download_button("⬇️ Télécharger CSV", data=csv_data,
                    file_name=f"AFG_Portefeuille_{label_yr.replace(', ','-').replace(' ','_')}.csv",
                    mime="text/csv", use_container_width=True)
            elif not df_int_rep.empty:
                csv_cols = [c for c in ['numero_contrat','date_souscription','nom','prenom',
                    'cln','pnom','categorie','groupe','prime_annuelle','prime_unique','eq',
                    'statut','region'] if c in df_int_rep.columns]
                csv_data = df_int_rep[csv_cols].to_csv(index=False).encode('utf-8-sig')
                st.download_button("⬇️ Télécharger CSV", data=csv_data,
                    file_name=f"AFG_Contrats_{label_yr.replace(', ','-').replace(' ','_')}.csv",
                    mime="text/csv", use_container_width=True)
            else:
                alert("Aucune donnée à exporter.","warn")


# ── FOOTER ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="afg-footer">
  <span style="font-weight:900;color:{GOLD};font-size:11.5px;">AFG VIE</span>
  <span class="fd">|</span>
  <strong>AFG Assurances Bénin Vie</strong> — Tableau de Bord PDG v17.0
  <span class="fd">|</span>
  À AFG Assurances Bénin Vie, nous avons pensé à vous !
  <span class="fd">|</span>
  18 produits · 3 groupes officiels · Conforme CIMA
  <span class="fd">|</span>
  Groupe AFG Holding · {datetime.now().strftime('%d/%m/%Y %H:%M')}
</div>""",unsafe_allow_html=True)
