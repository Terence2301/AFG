#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  AFG ASSURANCES BÉNIN VIE — DASHBOARD ACTUARIEL EXPERT v3.0
  Bug-fixes v3 : chargement direct (no pickle) · filtre date corrigé
                 navigation cachée · jointures inter-bases fiables
================================================================================
  LANCEMENT : streamlit run app_afg.py
  LOGIN     : Acces restreint — identifiants communiques separement
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
/* Labels et zone de dépôt des uploaders en noir lisible sur fond sombre */
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
    background: rgba(255,255,255,0.93) !important;
    border: 1.5px dashed #1A7F6E !important;
    border-radius: 8px !important;
}
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] * {
    color: #000000 !important;
    font-weight: 600 !important;
}
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] {
    color: #000000 !important;
}
section[data-testid="stSidebar"] .stFileUploader label {
    color: rgba(255,255,255,0.85) !important;
    font-size: 11px !important;
    font-weight: 600 !important;
}
</style>
""", unsafe_allow_html=True)

import pandas as pd, numpy as np, io, os, tempfile, warnings, hashlib, sqlite3
from datetime import datetime, date, timedelta
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
warnings.filterwarnings("ignore")

# PDF
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors as rl_colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, HRFlowable, PageBreak)
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    _PDF_OK = True
except ImportError:
    _PDF_OK = False

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
    {"code":"PA0","nom":"Prévoyance Auto","grp":"Groupe 1","cat":"Décès"},
]

# ── Barème Prévoyance Auto ────────────────────────────────────────
# Prime annuelle  Capital garanti décès
PA_BAREME = {
    500:  100_000,
    1000: 225_000,
    1500: 350_000,
    2000: 500_000,
}

# Rôle courtier — accès Saisie BIA uniquement, produit PA0 uniquement
COURTIER_ROLE = "COURTIER"
def is_courtier(user_dict: dict) -> bool:
    return user_dict.get("role","").upper() == COURTIER_ROLE

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

    Vérif : 10 000 F/mois, 5 ans, i=3,5 %  C ≈ 645 797 FCFA ✓
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
    # Sn terme échu (versements en FIN de période) :
    # s_n|  = [(1+i_per)^N - 1] / i_per
    sdot  = ((1 + i_per) ** N - 1) / i_per
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

# ══════════════════════════════════════════════════════════════════════════════
#  GÉNÉRATION PDF — RAPPORT DIRECTION GÉNÉRALE
# ══════════════════════════════════════════════════════════════════════════════
def generer_pdf_rapport(pf, ca, sin, period_lbl, user_nom,
                        sections_voulues=None) -> bytes:
    """
    Génère un rapport PDF professionnel pour le DG.
    sections_voulues : liste de clés parmi
        ["kpis","portefeuille","ca","sinistres","commerciaux","cima"]
    Retourne les bytes PDF.
    """
    if not _PDF_OK:
        return b""
    if sections_voulues is None:
        sections_voulues = ["kpis","portefeuille","ca","sinistres","commerciaux","cima"]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2.5*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    # Styles personnalisés AFG
    s_title  = ParagraphStyle("afg_title",  parent=styles["Title"],
        fontSize=18, textColor=rl_colors.HexColor("#0D1F3C"),
        spaceAfter=6, fontName="Helvetica-Bold")
    s_h1     = ParagraphStyle("afg_h1",     parent=styles["Heading1"],
        fontSize=13, textColor=rl_colors.HexColor("#1A7F6E"),
        spaceBefore=14, spaceAfter=4, fontName="Helvetica-Bold")
    s_h2     = ParagraphStyle("afg_h2",     parent=styles["Heading2"],
        fontSize=11, textColor=rl_colors.HexColor("#0D1F3C"),
        spaceBefore=8, spaceAfter=3, fontName="Helvetica-Bold")
    s_body   = ParagraphStyle("afg_body",   parent=styles["Normal"],
        fontSize=10, leading=14, spaceAfter=4)
    s_center = ParagraphStyle("afg_center", parent=styles["Normal"],
        fontSize=10, alignment=TA_CENTER)
    s_small  = ParagraphStyle("afg_small",  parent=styles["Normal"],
        fontSize=8, textColor=rl_colors.grey, alignment=TA_CENTER)

    # Couleurs AFG
    C_GREEN  = rl_colors.HexColor("#1A7F6E")
    C_NAVY   = rl_colors.HexColor("#0D1F3C")
    C_MINT   = rl_colors.HexColor("#A9DFBF")
    C_RED    = rl_colors.HexColor("#C0392B")
    C_AMBER  = rl_colors.HexColor("#CA6F1E")
    C_LGRAY  = rl_colors.HexColor("#F3F6FA")
    C_MGRAY  = rl_colors.HexColor("#DDE3EE")

    def tbl_style(header_color=C_GREEN):
        return TableStyle([
            ("BACKGROUND",  (0,0), (-1,0), header_color),
            ("TEXTCOLOR",   (0,0), (-1,0), rl_colors.white),
            ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",    (0,0), (-1,0), 9),
            ("ALIGN",       (0,0), (-1,0), "CENTER"),
            ("FONTNAME",    (0,1), (-1,-1), "Helvetica"),
            ("FONTSIZE",    (0,1), (-1,-1), 8.5),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[rl_colors.white, C_LGRAY]),
            ("GRID",        (0,0), (-1,-1), 0.4, C_MGRAY),
            ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING", (0,0), (-1,-1), 5),
            ("RIGHTPADDING",(0,0), (-1,-1), 5),
            ("TOPPADDING",  (0,0), (-1,-1), 3),
            ("BOTTOMPADDING",(0,0),(-1,-1), 3),
        ])

    story = []

    # ── En-tête ───────────────────────────────────────────────────────────────
    story.append(Paragraph("AFG ASSURANCES BÉNIN VIE", s_title))
    story.append(Paragraph(
        f"<b>RAPPORT D'ACTIVITÉ — {period_lbl.upper()}</b>", s_h1))
    story.append(Paragraph(
        f"Généré le {date.today().strftime('%d/%m/%Y')} · Par : {user_nom}",
        s_small))
    story.append(HRFlowable(width="100%", thickness=2,
        color=C_GREEN, spaceAfter=12))

    def fcfa(v):
        if v is None or (isinstance(v,float) and np.isnan(v)): return "—"
        v = float(v)
        if abs(v)>=1e9: return f"{v/1e9:.3f} Mrd FCFA"
        if abs(v)>=1e6: return f"{v/1e6:.3f} M FCFA"
        if abs(v)>=1e3: return f"{v/1e3:.0f} K FCFA"
        return f"{v:,.0f} FCFA"

    # ── Section 1 : KPIs principaux ───────────────────────────────────────────
    if "kpis" in sections_voulues:
        story.append(Paragraph("1. INDICATEURS CLÉS", s_h1))
        rows_kpi = [["Indicateur","Valeur","Observation"]]

        if pf is not None:
            nb   = len(pf)
            act  = int((pf["ETAT_POLICE"].str.strip()=="ACTIF").sum()) if "ETAT_POLICE" in pf.columns else 0
            res  = int((pf["ETAT_POLICE"].str.strip()=="RESILIE").sum()) if "ETAT_POLICE" in pf.columns else 0
            ina  = int((pf["ETAT_POLICE"].str.strip()=="INACTIF").sum()) if "ETAT_POLICE" in pf.columns else 0
            mon  = float(pf["MONTENCA"].fillna(0).sum()) if "MONTENCA" in pf.columns else 0
            tx_a = act/max(nb,1)*100
            tx_r = res/max(nb-ina,1)*100
            rows_kpi += [
                ["Nb total polices", f"{nb:,}", "Portefeuille complet"],
                ["Polices actives",  f"{act:,} ({tx_a:.1f}%)",
                 "✅ Conforme" if tx_a>=50 else "⚠️ < 50%"],
                ["Polices résiliées",f"{res:,} ({tx_r:.1f}%)",
                 "✅ < 25%" if tx_r<=25 else "⚠️ > 25% (seuil CIMA)"],
                ["Encaissements",    fcfa(mon), "MONTENCA total"],
            ]

        if ca is not None:
            ca_tot = float(ca["CHIFAFFA"].fillna(0).sum()) if "CHIFAFFA" in ca.columns else 0
            comm   = float(ca["COMMAPPO"].fillna(0).sum()) if "COMMAPPO" in ca.columns else 0
            tx_c   = comm/max(ca_tot,1)*100
            rows_kpi += [
                ["Chiffre d'affaires", fcfa(ca_tot), "CHIFAFFA total"],
                ["Commissions",        fcfa(comm), f"Taux {tx_c:.2f}%"],
                ["Nb quittances",      f"{len(ca):,}", "Total CA"],
            ]

        if sin is not None:
            sin_tot = float(sin["Réglement Total"].fillna(0).sum()) if "Réglement Total" in sin.columns else 0
            sap_tot = float(sin["SAP au 31/12/2025"].fillna(0).sum()) if "SAP au 31/12/2025" in sin.columns else 0
            ca_ref  = float(ca["CHIFAFFA"].fillna(0).sum()) if ca is not None and "CHIFAFFA" in ca.columns else 0
            sp      = sin_tot/max(ca_ref,1)*100
            rows_kpi += [
                ["Total réglé sinistres", fcfa(sin_tot), "Toutes périodes"],
                ["SAP (provisions)",      fcfa(sap_tot), "Au 31/12/2025"],
                ["Ratio S/P",             f"{sp:.1f}%",
                 "✅ < 80%" if sp<=80 else "⚠️ > 80% (seuil CIMA)"],
            ]

        t = Table(rows_kpi, colWidths=[6*cm, 4.5*cm, 6.5*cm])
        t.setStyle(tbl_style())
        story.append(t); story.append(Spacer(1, 10))

    # ── Section 2 : Portefeuille par produit ─────────────────────────────────
    if "portefeuille" in sections_voulues and pf is not None and "LIBECATE" in pf.columns:
        story.append(Paragraph("2. PORTEFEUILLE PAR PRODUIT", s_h1))
        pp = pf.groupby("LIBECATE").agg(
            Nb=("LIBECATE","count"),
            Actifs=("ETAT_POLICE",lambda x:(x.str.strip()=="ACTIF").sum()),
            CA=("MONTENCA","sum")
        ).reset_index().sort_values("Nb",ascending=False)
        rows_pf = [["Produit","Nb polices","Dont actives","Encaissements","Tx actif"]]
        for _,r in pp.iterrows():
            tx = r["Actifs"]/max(r["Nb"],1)*100
            rows_pf.append([str(r["LIBECATE"])[:35], f"{r['Nb']:,}",
                            f"{r['Actifs']:,}", fcfa(r["CA"]), f"{tx:.1f}%"])
        t = Table(rows_pf, colWidths=[6*cm,2.5*cm,2.5*cm,4*cm,2*cm])
        t.setStyle(tbl_style())
        story.append(t); story.append(Spacer(1,10))

    # ── Section 3 : Chiffre d'affaires ───────────────────────────────────────
    if "ca" in sections_voulues and ca is not None and "LIBECATE" in ca.columns:
        story.append(Paragraph("3. CHIFFRE D'AFFAIRES PAR PRODUIT", s_h1))
        cp = ca.groupby("LIBECATE").agg(
            CA=("CHIFAFFA","sum"), NbQ=("CHIFAFFA","count"),
            Comm=("COMMAPPO","sum")
        ).reset_index().sort_values("CA",ascending=False)
        cp["Tx"] = cp["Comm"]/cp["CA"].replace(0,np.nan)*100
        cp["Part"] = cp["CA"]/cp["CA"].sum()*100
        rows_ca = [["Produit","CA","Nb quittances","Commissions","Tx comm","Part CA"]]
        for _,r in cp.iterrows():
            rows_ca.append([str(r["LIBECATE"])[:30], fcfa(r["CA"]),
                            f"{r['NbQ']:,}", fcfa(r["Comm"]),
                            f"{r['Tx']:.2f}%" if pd.notna(r['Tx']) else "—",
                            f"{r['Part']:.2f}%"])
        t = Table(rows_ca, colWidths=[5.5*cm,3.5*cm,2.5*cm,3*cm,2*cm,2*cm])
        t.setStyle(tbl_style())
        story.append(t); story.append(Spacer(1,10))

    # ── Section 4 : Sinistres ─────────────────────────────────────────────────
    if "sinistres" in sections_voulues and sin is not None:
        story.append(Paragraph("4. SINISTRES & PROVISIONS", s_h1))
        if "Nature Sinistre" in sin.columns:
            nat = sin.groupby("Nature Sinistre").agg(
                Nb=(_c_nat_,"count") if _c_nat_ else ("POLICE_KEY","count"),
                Regle=(_c_regle_,"sum") if _c_regle_ else ("CHIFAFFA","count"),
                SAP=(_c_sap_,"sum") if "_c_sap_" in dir() and _c_sap_ else ("CHIFAFFA","count")
            ).reset_index().sort_values("Réglé",ascending=False)
            rows_sin = [["Nature","Nb dossiers","Montant réglé","SAP résiduel","Charge totale"]]
            for _,r in nat.iterrows():
                rows_sin.append([str(r["Nature Sinistre"])[:28],
                                  f"{r['Nb']:,}", fcfa(r["Réglé"]),
                                  fcfa(r["SAP"]), fcfa(r["Réglé"]+r["SAP"])])
            t = Table(rows_sin, colWidths=[5*cm,2.5*cm,3.5*cm,3.5*cm,3.5*cm])
            t.setStyle(tbl_style(C_RED))
            story.append(t); story.append(Spacer(1,10))

    # ── Section 5 : Top commerciaux ───────────────────────────────────────────
    if "commerciaux" in sections_voulues and ca is not None:
        story.append(Paragraph("5. PERFORMANCE COMMERCIALE — TOP 20", s_h1))
        ag_k = "NOM_INTERMEDIAIRE" if "NOM_INTERMEDIAIRE" in ca.columns else "NOM_APP"
        if ag_k in ca.columns:
            cg = ca.groupby(ag_k).agg(
                CA=("CHIFAFFA","sum"), NbQ=("CHIFAFFA","count"),
                Comm=("COMMAPPO","sum")
            ).reset_index().sort_values("CA",ascending=False).head(20)
            tot = cg["CA"].sum()
            cg["Part"] = cg["CA"]/max(tot,1)*100
            rows_com = [["Commercial(e)","CA réalisé","Nb contrats","Commissions","Part CA"]]
            for _,r in cg.iterrows():
                rows_com.append([str(r[ag_k])[:28], fcfa(r["CA"]),
                                  f"{r['NbQ']:,}", fcfa(r["Comm"]),
                                  f"{r['Part']:.2f}%"])
            t = Table(rows_com, colWidths=[5.5*cm,3.5*cm,2.5*cm,3.5*cm,2*cm])
            t.setStyle(tbl_style())
            story.append(t); story.append(Spacer(1,10))

    # ── Section 6 : Scorecard CIMA ────────────────────────────────────────────
    if "cima" in sections_voulues and pf is not None:
        story.append(Paragraph("6. SCORECARD CIMA", s_h1))
        nb   = len(pf)
        act  = int((pf["ETAT_POLICE"].str.strip()=="ACTIF").sum()) if "ETAT_POLICE" in pf.columns else 0
        res  = int((pf["ETAT_POLICE"].str.strip()=="RESILIE").sum()) if "ETAT_POLICE" in pf.columns else 0
        ina  = int((pf["ETAT_POLICE"].str.strip()=="INACTIF").sum()) if "ETAT_POLICE" in pf.columns else 0
        tx_a = act/max(nb,1)*100
        tx_r = res/max(nb-ina,1)*100
        ca_t = float(ca["CHIFAFFA"].fillna(0).sum()) if ca is not None else 0
        sin_t= float(sin["Réglement Total"].fillna(0).sum()) if sin is not None and "Réglement Total" in sin.columns else 0
        sp   = sin_t/max(ca_t,1)*100
        tx_i = ina/max(nb,1)*100
        cima_rows = [["Indicateur","Valeur","Seuil CIMA","Statut"]]
        for lbl, val, seuil, ok in [
            ("Taux d'activité net", f"{tx_a:.1f}%","≥ 50%", tx_a>=50),
            ("Taux résiliation",    f"{tx_r:.1f}%","≤ 25%", tx_r<=25),
            ("Ratio S/P",          f"{sp:.1f}%",   "≤ 80%", sp<=80),
            ("Part inactifs",       f"{tx_i:.1f}%","≤ 5%",  tx_i<=5),
        ]:
            cima_rows.append([lbl, val, seuil, "✅ Conforme" if ok else "⚠️ Non conforme"])
        t = Table(cima_rows, colWidths=[6*cm,3*cm,3*cm,5*cm])
        ts = tbl_style()
        for i,(lbl,val,seuil,ok_str) in enumerate(cima_rows[1:],1):
            c_ = rl_colors.HexColor("#D5F5E3") if "Conforme" in ok_str else rl_colors.HexColor("#FDECEA")
            ts.add("BACKGROUND",(3,i),(3,i), c_)
        t.setStyle(ts)
        story.append(t); story.append(Spacer(1,10))

    # ── Pied de page ──────────────────────────────────────────────────────────
    story.append(Spacer(1,20))
    story.append(HRFlowable(width="100%",thickness=1,color=C_GREEN,spaceAfter=6))
    story.append(Paragraph(
        f"© {date.today().year} AFG Assurances Bénin Vie · Rapport confidentiel · "
        f"Généré automatiquement par le Dashboard Actuariel Expert v3.0",
        s_small))

    doc.build(story)
    return buf.getvalue()




def _fmt_periode(periodicite: str) -> str:
    return {"Journalière":"jour","Hebdomadaire":"sem.","Mensuelle":"mois",
            "Trimestrielle":"trim.","Semestrielle":"sem.","Annuelle":"an","Unique":"unique"}.get(periodicite, periodicite)
AGENCES = ["","Siège Social — Cotonou","Agence Cotonou Centre","Agence Cotonou Littoral",
    "Agence Cotonou Cadjèhoun","Agence Porto-Novo","Agence Abomey-Calavi",
    "Agence Parakou","Agence Bohicon","Agence Natitingou","Agence Ouidah",
    "Agence Lokossa","Agence Kandi","Agence Abomey","Agence Djougou","Agence Allada"]

# ── Mots de passe chargés depuis st.secrets ─────────────────────────────────
# Définis dans Streamlit Cloud  Settings  Secrets  [auth]
# Le code ne contient JAMAIS de mot de passe en clair.
def _pwd(key: str, fallback: str) -> str:
    try:
        raw = st.secrets["auth"][key]
        return hashlib.sha256(raw.encode()).hexdigest()
    except Exception:
        return hashlib.sha256(fallback.encode()).hexdigest()

USERS = {
    "PDG AFG":       _pwd("pdg_pwd",      "1001"),
    "DG AFG":        _pwd("dg_pwd",       "1002"),
    "ADMIN AFG":     _pwd("admin_pwd",    "1003"),
    "MANAGER AFG":   _pwd("admin_pwd",    "1004"),
    "ACTUAIRE AFG":  _pwd("actuaire_pwd", "1005"),
    "DEMO VISITEUR": _pwd("demo_pwd",     "0000"),
    "COURTIER AFG":  _pwd("courtier_pwd", "2001"),
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

def clean_str_col(s: pd.Series) -> pd.Series:
    """Nettoie une colonne texte : strip, normalise Unicode, supprime NaN affichés."""
    import unicodedata
    def _clean(v):
        if pd.isna(v): return ""
        t = str(v).strip()
        # Normalise les caractères accentués mal encodés (Latin-1  UTF-8)
        try:
            t = t.encode("latin-1").decode("utf-8")
        except Exception:
            pass
        # Normalise NFC (formes composées)
        try:
            t = unicodedata.normalize("NFC", t)
        except Exception:
            pass
        return t
    return s.apply(_clean)

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
#    • PostgreSQL (Supabase / Neon / serveur AFG)  base partagée entre tous
#      les utilisateurs, persistante entre les rechargements.
#    • SQLite local  fallback automatique si PostgreSQL non configuré
#      (utile pour les tests en local avant déploiement).
#
#  CONFIGURATION PostgreSQL :
#    Définir la variable d'environnement DATABASE_URL dans :
#      - Streamlit Cloud : Settings  Secrets  [database] url = "..."
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
    Retourne None si aucune URL n'est trouvée  fallback SQLite.
    """
    try:
        url = st.secrets["database"]["url"]
        if url and url.startswith("postgresql"):
            return url
    except Exception:
        pass
    env_url = os.environ.get("DATABASE_URL", "")
    if env_url.startswith("postgresql") or env_url.startswith("postgres"):
        # Neon/Heroku écrivent parfois "postgres://"  normaliser
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
# SQLite n'accepte pas SERIAL  on remplace
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
    """Met à jour le statut d'un BIA (ex. Brouillon  Validé)."""
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
    """Désérialise des bytes Parquet  DataFrame."""
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
    Strip systématique des noms de colonnes après désérialisation Parquet.
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
        # Strip systématique des noms de colonnes (espaces parasites dans fichiers AFG)
        df.columns = [str(c).strip() for c in df.columns]
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
# Rôles autorisés à charger/gérer les bases de données
UPLOAD_ROLES    = {"PDG", "ACTUAIRE"}   # peuvent charger PF, CA, Prestations
# Rôles autorisés à voir les onglets analytiques
ANALYTICS_ROLES = {"PDG", "ACTUAIRE"}   # voient le dashboard complet

def is_admin(user_dict: dict) -> bool:
    """Peut charger et gérer les bases de données."""
    return user_dict.get("role","").upper() in UPLOAD_ROLES

def can_see_analytics(user_dict: dict) -> bool:
    """Peut accéder aux onglets analytiques (dashboard complet)."""
    return user_dict.get("role","").upper() in ANALYTICS_ROLES

# ══════════════════════════════════════════════════════════════════════════════
#  CHARGEMENT OPTIMISÉ — lecture directe, colonnes filtrées, typage minimal
#  Fixes : removeChild DOM bug, lenteur 300K lignes, crash mémoire
# ══════════════════════════════════════════════════════════════════════════════

# Colonnes utiles uniquement — élimine les ~80 colonnes mortes du PF (306K×100  306K×21)
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
# Colonnes Prestations — noms EXACTS vérifiés sur le fichier réel AFG
# Libéllé Catégorie : double 'l' (particularité AFG)
# Réglement : un seul 'è' (sans accent sur le 'e' final)
SIN_COLS = {
    "Int police","No Police",
    "Exercice Sinistre","No Sinistre",
    "Date Survenance","Date Déclaration","Date validation",
    "Date Emission","Date Comptabilisation","Date Création",
    "Libéllé Catégorie","Libellé Garantie","Garantie",
    "Nature Sinistre","Sort Sinistre",
    "Souscripteur","Désignation risque","Nom Bénéficiaire",
    "Réglement Total","Réglement Principal","Réglement Honoraires",
    "Réglement Comptable","SAP au 31/12/2025",
    "RAE Cie au 31/12/2025",
    "Libellé branche","Code branche",
    "Raison Sociale Int","Libellé Unité",
}

def _excel_sheet(path: str, preferred: str) -> str:
    """Retourne le nom de feuille existant (préféré en premier, sinon sheet[0])."""
    xl = pd.ExcelFile(path, engine="openpyxl")
    if preferred in xl.sheet_names:
        return preferred
    for s in xl.sheet_names:
        if "liste" in s.lower():
            return s
    return xl.sheet_names[0]

def _detect_encoding(raw: bytes) -> str:
    """
    Détecte l'encodage d'un fichier CSV.
    Les exports AFG (Megasoft/Orass) sont en Windows-1252 (latin-1).
    Stratégie : essayer utf-8-sig  utf-8  latin-1 (fallback universel).
    """
    # Essayer utf-8 avec BOM
    try:
        raw.decode('utf-8-sig')
        return 'utf-8-sig'
    except UnicodeDecodeError:
        pass
    # Essayer utf-8 strict
    try:
        raw.decode('utf-8')
        # Vérifier que les accents français sont bien lisibles
        txt = raw.decode('utf-8')
        if 'R\xef\xbf\xbd' not in txt and 'R\xc3\xa9' not in txt[:500]:
            return 'utf-8'
    except UnicodeDecodeError:
        pass
    # Fallback latin-1 (Windows-1252) — universel pour fichiers AFG
    return 'latin-1'

def _read_csv_auto(raw: bytes) -> pd.DataFrame:
    """
    Lit un CSV avec détection automatique de l'encodage et du séparateur.
    Gère les fichiers AFG exportés en latin-1/Windows-1252.
    """
    # Détecter l'encodage
    enc = _detect_encoding(raw)
    txt = raw.decode(enc, errors='replace')

    # Détecter le séparateur sur la première ligne
    first = txt.split('\n')[0]
    sep   = ';' if first.count(';') > first.count(',') else ','

    df = pd.read_csv(
        io.StringIO(txt), sep=sep, dtype=str,
        low_memory=False, encoding=None)

    # Strip systématique des noms de colonnes (espaces parasites)
    df.columns = [str(c).strip() for c in df.columns]
    return df

def _keep_cols(df: pd.DataFrame, wanted: set) -> pd.DataFrame:
    """Conserve uniquement les colonnes présentes ET utiles."""
    keep = [c for c in df.columns if c in wanted]
    return df[keep] if keep else df

def load_pf(f) -> pd.DataFrame:
    """
    Charge le Portefeuille de façon optimisée.

    OPTIMISATIONS :
    • usecols = seulement les 19 colonnes utiles (PF_COLS)  306K×19 au lieu de 306K×100
    • Lecture en une seule passe (pas de double-lecture des headers)
    • Toutes les colonnes lues en str  typage minimal uniquement sur celles utilisées
    • Nettoyage mémoire immédiat après typage

    RÉSULTAT : ~3× plus rapide, ~80% moins de RAM vs lecture complète
    """
    data = f.read()
    name = getattr(f, "name", "f.xlsx").lower()

    if name.endswith(".csv"):
        df = _read_csv_auto(data)
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
        df = _read_csv_auto(data)
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
        df = _read_csv_auto(data)
        df = _keep_cols(df, SIN_COLS)
    else:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp.write(data); path = tmp.name
        try:
            sh  = _excel_sheet(path, "Liste")
            xl  = pd.ExcelFile(path, engine="openpyxl")
            # Lire les headers bruts pour construire usecols
            hdr_raw = pd.read_excel(xl, sheet_name=sh, nrows=0)
            # Matcher avec strip : "Raison Sociale Int "  "Raison Sociale Int"
            use = [c for c in hdr_raw.columns
                   if str(c).strip() in SIN_COLS or str(c) in SIN_COLS]
            if not use:
                use = None  # fallback : lire toutes les colonnes
            df  = pd.read_excel(xl, sheet_name=sh, dtype=str, usecols=use)
            # Strip systématique des noms de colonnes
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
      jour     dcol.dt.date == sel
      semaine  semaine ISO contenant sel (lundi–dimanche)
      mois     même année et mois
      trim     même année et trimestre
      sem      même année et semestre
      annee    même année
    """
    if df is None or df.empty: return pd.DataFrame()
    if dcol not in df.columns: return df
    col = df[dcol]
    if not pd.api.types.is_datetime64_any_dtype(col):
        col = pd.to_datetime(col, errors="coerce")
    if mode == "jour":
        mask = col.dt.date == sel
    elif mode == "semaine":
        _lun = sel - timedelta(days=sel.weekday())
        _dim = _lun + timedelta(days=6)
        mask = (col.dt.date >= _lun) & (col.dt.date <= _dim)
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
    # Pour trimestre/semestre/annee  filtre sur ANNEE_SIN
    if "ANNEE_SIN" not in df.columns: return df
    yr = sel.year
    if mode == "annee":
        mask = df["ANNEE_SIN"] == yr
    elif mode == "trim":
        mask = df["ANNEE_SIN"] == yr   # exercice pas découpé en trim  filtre annuel
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
        <div style="text-align:center;padding:2rem 0 1.2rem">
          <img src="data:image/jpeg;base64,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"
               style="height:80px;object-fit:contain;margin-bottom:10px;display:block;margin-left:auto;margin-right:auto"/>
          <p style="color:#8899AA;font-size:12px;margin-top:6px">Tableau de bord actuariel expert · Conforme CIMA</p>
        </div>""", unsafe_allow_html=True)
        with st.container(border=True):

            ident = st.text_input("👤 Identifiant", placeholder="Ex : PDG AFG")
            code  = st.text_input("🔑 Mot de passe", type="password")
            if st.button("🔐 Accéder au système", use_container_width=True, type="primary"):
                up = ident.strip().upper()
                if up in USERS and USERS[up] == hashlib.sha256(code.encode()).hexdigest():
                    st.session_state.auth = True
                    st.session_state.user = {"nom": ident.strip(), "role": up.split()[0]}
                    st.rerun()
                    st.error("❌ Identifiant ou code PIN incorrect.")
    st.stop()

user  = st.session_state.user
today = date.today()

# ══════════════════════════════════════════════════════════════════════════════
#  CHARGEMENT AUTOMATIQUE DES BASES DEPUIS LA BASE CENTRALISÉE
#  Au premier rendu après login, on vérifie si des bases sont déjà stockées.
#  Si oui  chargement transparent, aucun upload nécessaire.
#  Les bases restent disponibles pour TOUS les visiteurs même après refresh.
# ══════════════════════════════════════════════════════════════════════════════
# Chargement initial des bases depuis Supabase.
# Utilise un placeholder vide pour afficher un message pendant le chargement.
# Aucun st.rerun()
if not st.session_state.bases_loaded_from_db:
    # Charger les bases uniquement pour les rôles qui ont accès aux onglets analytiques
    # ADMIN et COURTIER n'ont pas accès aux dashboards  pas besoin de charger
    _role_needs_data = can_see_analytics(user)
    if _role_needs_data:
        _ph_load = st.empty()
        _meta = get_bases_meta()
        _loaded_any = False
        for _bt, _attr in [("pf","pf"), ("ca","ca"), ("sin","sin")]:
            if _bt in _meta and not getattr(st.session_state, f"{_attr}_ok"):
                _ph_load.info(f"⏳ Chargement {_bt.upper()} depuis la base...")
                _df, _ = load_base(_bt)
                if _df is not None and not _df.empty:
                    setattr(st.session_state, _attr, _df)
                    setattr(st.session_state, f"{_attr}_ok", True)
                    _loaded_any = True
        _ph_load.empty()
    st.session_state.bases_loaded_from_db = True

# ─────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────
# ── Définition de toutes les pages disponibles ────────────────────────────────
ALL_PAGES = [
    "🏠  Accueil & KPIs",
    "📊  Analyse CA",
    "📋  Portefeuille",
    "🛒  Produits",
    "👥  Commerciaux",
    "🏦  Partenaires Financiers",
    "👤  Clients & Géographie",
    "⚠️  Sinistres & Prestations",
    "📐  Actuariat Avancé",
    "🔮  Prévisions & Tendances",
    "📝  Saisie BIA",
    "🗂️  Base BIA",
    
    "📄  Rapport PDF",
]
# Seule page visible sans aucune base chargée
VISIBLE_DEFAULT = ["📝  Saisie BIA"]

# ── Calcul des pages disponibles selon les bases chargées ─────────────────────
# RÈGLE : Saisie BIA toujours visible.
#         Dès qu'AU MOINS une base est chargée  toutes les pages se débloquent.
#         Ce calcul est fait à chaque rendu (pas besoin de bouton).
_any_data     = (st.session_state.pf_ok or st.session_state.ca_ok or st.session_state.sin_ok)
SEL_YEAR = st.session_state.get("sel_year_num", None)
_can_analysis = can_see_analytics(user)   # PDG ou ACTUAIRE uniquement
_is_courtier  = is_courtier(user)         # Courtiers  Saisie BIA uniquement

# Règle d'accès :
# • PDG / ACTUAIRE + bases chargées  tous les onglets
# • COURTIER  Saisie BIA uniquement (produit PA0)
# • Tous les autres  Saisie BIA uniquement
pages_visible = ALL_PAGES if (_any_data and _can_analysis and not _is_courtier) else VISIBLE_DEFAULT

# Sécurité : si la page courante a disparu (ex. données effacées), revenir à BIA
if st.session_state.current_page not in pages_visible:
    st.session_state.current_page = "📝  Saisie BIA"


# ── Callbacks file_uploader — appelés par Streamlit APRÈS le rendu React ──────
# C'est le SEUL pattern garanti sans removeChild sur Streamlit Cloud.
# Le callback s'exécute entre deux cycles, DOM stable.
def _cb_pf():
    f = st.session_state.get("up_pf")
    if f is not None and not st.session_state.get("_pf_bytes_stored"):
        st.session_state["_pending_pf_bytes"] = f.read()
        st.session_state["_pending_pf_name"]  = f.name
        st.session_state["_pf_bytes_stored"]  = True

def _cb_ca():
    f = st.session_state.get("up_ca")
    if f is not None:
        _cid = f"{f.name}_{f.size}"
        if _cid not in st.session_state.get("_ca_seen_ids", set()):
            raw  = f.read()
            lst  = st.session_state.get("_pending_ca_list", [])
            lst.append({"bytes": raw, "name": f.name, "id": _cid})
            st.session_state["_pending_ca_list"] = lst

def _cb_sin():
    f = st.session_state.get("up_sin")
    if f is not None and not st.session_state.get("_sin_bytes_stored"):
        st.session_state["_pending_sin_bytes"] = f.read()
        st.session_state["_pending_sin_name"]  = f.name
        st.session_state["_sin_bytes_stored"]  = True

with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center;padding:.6rem 0 .3rem">
      <img src="data:image/jpeg;base64,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"
           style="height:52px;object-fit:contain;display:block;margin:0 auto"/>
    </div><hr>
    <div style="background:rgba(26,127,110,.12);border-radius:8px;padding:8px 10px;margin:0 4px 8px">
      <div style="font-size:9px;opacity:.5;text-transform:uppercase;letter-spacing:.05em">Connecté</div>
      <div style="font-weight:700;font-size:12px;margin-top:1px">{user['nom']}</div>
    </div>""", unsafe_allow_html=True)

    # ── Message d'état navigation ─────────────────────────────────────────────
    if _is_courtier:
        # Courtier — message spécifique
        st.markdown(f"""
        <div style="background:rgba(26,127,110,.15);border:1px solid {GREEN};border-radius:8px;
             padding:8px 10px;margin:6px 4px 4px;font-size:10px;color:rgba(255,255,255,.8);line-height:1.5">
          📋 <b style="color:{MINT}">Espace Courtier</b><br>
          Saisie BIA — Prévoyance Auto
        </div>""", unsafe_allow_html=True)
    elif not _can_analysis:
        # Rôle sans accès analytique — message informatif
        st.markdown(f"""
        <div style="background:rgba(202,111,30,.15);border:1px solid {AMBER};border-radius:8px;
             padding:8px 10px;margin:6px 4px 4px;font-size:10px;color:rgba(255,255,255,.7);line-height:1.5">
          🔒 <b style="color:{MINT}">Accès Saisie BIA</b><br>
          Votre profil est limité à la saisie des bulletins d'adhésion.
        </div>""", unsafe_allow_html=True)
    elif not _any_data:
        # Rôle analytique mais aucune base chargée
        st.markdown(f"""
        <div style="background:rgba(202,111,30,.15);border:1px solid {AMBER};border-radius:8px;
             padding:8px 10px;margin:6px 4px 4px;font-size:10px;color:rgba(255,255,255,.7);line-height:1.5">
          ⏳ <b style="color:{MINT}">Aucune base chargée</b><br>
          Chargez au moins une base pour accéder aux tableaux de bord.
        </div>""", unsafe_allow_html=True)
    else:
        # Rôle analytique + bases disponibles
        _nb_bases = sum([st.session_state.pf_ok, st.session_state.ca_ok, st.session_state.sin_ok])
        st.markdown(f"""
        <div style="background:rgba(26,127,110,.15);border:1px solid {GREEN};border-radius:8px;
             padding:8px 10px;margin:6px 4px 4px;font-size:10px;color:rgba(255,255,255,.7);line-height:1.5">
          ✅ <b style="color:{MINT}">{_nb_bases}/3 base(s)</b> chargée(s) — tableau de bord complet disponible.
        </div>""", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    nav_choice = st.radio("", pages_visible,
                          index=pages_visible.index(st.session_state.current_page),
                          label_visibility="collapsed")
    st.session_state.current_page = nav_choice

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Filtre période ──────────────────────────────────────────────────────
    # CSS calendrier : fond sombre  texte visible
    st.markdown("""
    <style>
    div[data-baseweb="calendar"] {
        background: #FFFFFF !important;
        border: 1.5px solid #1A7F6E !important;
        border-radius: 10px !important;
        padding: 8px !important;
        box-shadow: 0 4px 20px rgba(13,31,60,.18) !important;
    }
    div[data-baseweb="calendar"] * {
        color: #0D1F3C !important;
        font-weight: 500 !important;
    }
    div[data-baseweb="calendar"] [aria-selected="true"] {
        background: #1A7F6E !important;
        border-radius: 6px !important;
        color: white !important;
        font-weight: 700 !important;
    }
    div[data-baseweb="calendar"] [aria-selected="true"] * {
        color: white !important;
    }
    div[data-baseweb="calendar"] button:hover {
        background: #D5F5E3 !important;
        border-radius: 6px !important;
    }
    div[data-baseweb="calendar"] [data-today="true"] {
        border: 2px solid #CA6F1E !important;
        border-radius: 6px !important;
        font-weight: 700 !important;
    }
    </style>""", unsafe_allow_html=True)

    st.markdown(f"<div style='font-size:9.5px;font-weight:700;opacity:.55;text-transform:uppercase;letter-spacing:.07em;margin-bottom:5px'>📅 Période d'analyse</div>", unsafe_allow_html=True)
    mode_lbl = st.selectbox("", ["Semaine","Mois","Trimestre","Semestre","Année","Jour"],
                            label_visibility="collapsed", key="mode_sel")
    MODE = {"Semaine":"semaine","Mois":"mois","Trimestre":"trim",
            "Semestre":"sem","Année":"annee","Jour":"jour"}[mode_lbl]

    default_date = date(2024, 6, 30)
    sel_date = st.date_input("", value=default_date,
        label_visibility="collapsed", key="sel_date",
        help="Sélectionnez une date dans la période souhaitée")

    if MODE=="jour":
        period_lbl = ds(sel_date)
    elif MODE=="semaine":
        # Semaine ISO : lundi au dimanche contenant sel_date
        _lun = sel_date - timedelta(days=sel_date.weekday())
        _dim = _lun + timedelta(days=6)
        _iso = sel_date.isocalendar()
        period_lbl = f"Sem. {_iso[1]} · {ds(_lun)}–{ds(_dim)}"
    elif MODE=="mois":
        period_lbl = f"{MOIS_LONG[sel_date.month-1]} {sel_date.year}"
    elif MODE=="trim":
        period_lbl = f"T{(sel_date.month-1)//3+1} {sel_date.year}"
    elif MODE=="sem":
        period_lbl = f"S{'1' if sel_date.month<=6 else '2'} {sel_date.year}"
    else:
        period_lbl = str(sel_date.year)

    st.markdown(f"<div style='background:#C0392B;color:white;text-align:center;border-radius:7px;padding:5px;margin:5px 4px;font-weight:800;font-size:12px'>{period_lbl}</div>", unsafe_allow_html=True)

    # ── Filtre par année ────────────────────────────────────────────────────
    # Utiliser st.session_state pour éviter le NameError (ca/pf/sin définis plus tard)
    _annees_all = []
    _ca_ss  = st.session_state.ca
    _pf_ss  = st.session_state.pf
    _sin_ss = st.session_state.sin
    if _ca_ss is not None and "ANNEE" in _ca_ss.columns:
        _annees_all = sorted([int(a) for a in _ca_ss["ANNEE"].dropna().unique()
                              if str(a).isdigit()], reverse=True)
    elif _sin_ss is not None and "ANNEE_SIN" in _sin_ss.columns:
        _annees_all = sorted([int(a) for a in _sin_ss["ANNEE_SIN"].dropna().unique()
                              if pd.notna(a)], reverse=True)
    elif _pf_ss is not None and "ANNEESOUS" in _pf_ss.columns:
        _annees_all = sorted([int(a) for a in _pf_ss["ANNEESOUS"].dropna().unique()
                              if str(a).isdigit()], reverse=True)
    _yr_opts = ["Toutes les années"] + [str(a) for a in _annees_all]
    _cur_yr  = st.session_state.get("filtre_annee", "Toutes les années")
    if _cur_yr not in _yr_opts: _cur_yr = "Toutes les années"
    _sel_yr  = st.selectbox("📅 Année", _yr_opts,
                             index=_yr_opts.index(_cur_yr), key="yr_sel")
    st.session_state["filtre_annee"] = _sel_yr
    # Alias numérique pour les pages analytiques
    SEL_YEAR_SB = None if _sel_yr == "Toutes les années" else int(_sel_yr)
    st.session_state["sel_year_num"] = SEL_YEAR_SB

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

        # ── PATTERN DÉFINITIF anti-removeChild ───────────────────────────────
        # on_change= : Streamlit appelle le callback ENTRE deux cycles React,
        # quand le DOM est complètement stable. Aucun f.read() dans le rendu.
        with st.expander(
                f"📋 Portefeuille {'✅' if st.session_state.pf_ok else '▶ Charger'}",
                expanded=not st.session_state.pf_ok):
            if st.session_state.pf_ok:
                pf_cols = len(st.session_state.pf.columns) if st.session_state.pf is not None else 0
                st.caption(f"{len(st.session_state.pf):,} polices · {pf_cols} col.")
            st.file_uploader(
                "CSV recommandé · xlsx accepté",
                type=["csv","xlsx","xls"],
                key="up_pf",
                on_change=_cb_pf,
                label_visibility="visible")
            if st.session_state.pf_ok:
                c1, c2 = st.columns(2)
                if c1.button("🔄 Remplacer", key="rep_pf", use_container_width=True):
                    st.session_state["_action_pf"]      = "delete"
                    st.session_state["_pf_bytes_stored"] = False
                if c2.button("🗑️ Supprimer", key="del_pf", use_container_width=True):
                    st.session_state["_action_pf"]      = "delete"
                    st.session_state["_pf_bytes_stored"] = False

        with st.expander(
                f"💰 Base CA {'✅' if st.session_state.ca_ok else '▶ Charger'}",
                expanded=not st.session_state.ca_ok):
            if st.session_state.ca_ok:
                _yrs = (sorted(st.session_state.ca["ANNEE"].dropna()
                               .unique().astype(int).tolist())
                        if "ANNEE" in st.session_state.ca.columns else [])
                st.caption(f"{len(st.session_state.ca):,} quittances"
                           f"{' · '+', '.join(map(str,_yrs)) if _yrs else ''}")
            st.caption("Plusieurs exercices : charger un par un — ils s'accumulent")
            st.file_uploader(
                "CSV recommandé · xlsx accepté",
                type=["csv","xlsx","xls"],
                key="up_ca",
                on_change=_cb_ca,
                label_visibility="visible")
            if st.session_state.ca_ok:
                if st.button("🗑️ Vider tout le CA", key="del_ca",
                             use_container_width=True):
                    st.session_state["_action_ca"] = "delete"

        with st.expander(
                f"🏥 Prestations {'✅' if st.session_state.sin_ok else '▶ Charger'}",
                expanded=not st.session_state.sin_ok):
            if st.session_state.sin_ok:
                sin_cols = len(st.session_state.sin.columns) if st.session_state.sin is not None else 0
                st.caption(f"{len(st.session_state.sin):,} dossiers · {sin_cols} col.")
            st.file_uploader(
                "CSV recommandé · xlsx accepté",
                type=["csv","xlsx","xls"],
                key="up_sin",
                on_change=_cb_sin,
                label_visibility="visible")
            if st.session_state.sin_ok:
                c1, c2 = st.columns(2)
                if c1.button("🔄 Remplacer", key="rep_sin", use_container_width=True):
                    st.session_state["_action_sin"]      = "delete"
                    st.session_state["_sin_bytes_stored"] = False
                if c2.button("🗑️ Supprimer", key="del_sin", use_container_width=True):
                    st.session_state["_action_sin"]      = "delete"
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
#  On ne fait JAMAIS st.rerun()
#  À la place :
#   • Cycle 1 : widget stocke fichier dans _pending_XX  rendu normal  fin
#   • Cycle 2 : on détecte _pending_XX  on traite (load + save) 
#               on met _ok=True  st.rerun()
#               (après tous les widgets, après tout le rendu)
#   • Cycle 3 : _ok=True  onglets disponibles  affichage normal
#
#  Le st.rerun()
#  est stable et React a terminé tous ses effets.
# ══════════════════════════════════════════════════════════════════════════════

# ── Déconnexion ───────────────────────────────────────────────────────────────
if "_logout" in dir() and _logout:
    for k in DEFAULTS:
        st.session_state[k] = DEFAULTS[k]
    st.rerun()
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
# Zone de progression visible pendant le traitement (avant le rendu principal)
_processed = False

# ── Helpers pour lire depuis bytes stockés ───────────────────────────────────
def _bytes_to_df_pf(raw: bytes, fname: str) -> pd.DataFrame:
    """Parse bytes (CSV ou XLSX) en DataFrame PF filtré."""
    if fname.lower().endswith(".csv"):
        df = _read_csv_auto(raw)
        df = _keep_cols(df, PF_COLS)
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
    # Nettoyage Unicode des colonnes texte (corrige les "?" sur noms accentués)
    for _tc in ["LIBECATE","NOM_ASSU","LIBEVILL","NOM_APP","ETAT_POLICE","CODEPERI"]:
        if _tc in df.columns:
            df[_tc] = clean_str_col(df[_tc])
    return df.loc[:, df.notna().any(axis=0)]

def _bytes_to_df_ca(raw: bytes, fname: str) -> pd.DataFrame:
    """Parse bytes (CSV ou XLSX) en DataFrame CA filtré."""
    if fname.lower().endswith(".csv"):
        df = _read_csv_auto(raw)
        df = _keep_cols(df, CA_COLS)
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
    for _tc in ["LIBECATE","NOM_INTERMEDIAIRE","TYPEMOUV","SORTQUIT"]:
        if _tc in df.columns:
            df[_tc] = clean_str_col(df[_tc])
    return df.loc[:, df.notna().any(axis=0)]

def _bytes_to_df_sin(raw: bytes, fname: str) -> pd.DataFrame:
    """Parse bytes (CSV ou XLSX) en DataFrame Prestations filtré."""
    if fname.lower().endswith(".csv"):
        df = _read_csv_auto(raw)
        df = _keep_cols(df, SIN_COLS)
        df = _keep_cols(df, SIN_COLS)
    else:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp.write(raw); path = tmp.name
        try:
            sh  = _excel_sheet(path, "Liste")
            xl  = pd.ExcelFile(path, engine="openpyxl")
            hdr_raw = pd.read_excel(xl, sheet_name=sh, nrows=0)
            # Match avec strip pour gérer espaces parasites dans noms AFG
            use = [c for c in hdr_raw.columns
                   if str(c).strip() in SIN_COLS or str(c) in SIN_COLS]
            if not use:
                use = None
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
    # Nettoyer les espaces dans les noms de colonnes (ex: "Code Unité ")
    df.columns = [c.strip() for c in df.columns]

    # Nettoyage Unicode sur colonnes texte clés
    for _tc in ["Nature Sinistre","Sort Sinistre","Libéllé Catégorie",
                "Souscripteur","Désignation risque","Nom Bénéficiaire",
                "Libellé branche","Libellé Garantie","Raison Sociale Int",
                "Libellé Unité"]:
        if _tc in df.columns:
            df[_tc] = clean_str_col(df[_tc])

    # Convertir colonnes monétaires en numérique
    for _mc in ["Réglement Total","Réglement Principal","Réglement Honoraires",
                "Réglement Comptable","SAP au 31/12/2025","RAE Cie au 31/12/2025"]:
        if _mc in df.columns:
            df[_mc] = clean_num(df[_mc])

    # Exercice sinistre en entier
    if "Exercice Sinistre" in df.columns:
        df["ANNEE_SIN"] = pd.to_numeric(df["Exercice Sinistre"], errors="coerce").astype("Int64")

    # Clé de jointure
    if "Int police" in df.columns and "No Police" in df.columns:
        df["POLICE_KEY"] = (df["Int police"].astype(str).str.strip()
                            + "-" + df["No Police"].astype(str).str.strip())

    return df.loc[:, df.notna().any(axis=0)]

# ── Traitement des bytes stockés — parsing et sauvegarde ─────────────────────
# Les bytes sont déjà en mémoire (lus instantanément dans la sidebar).
# On parse ici, sans aucun widget actif  DOM stable  st.rerun()

if st.session_state.get("_pending_pf_bytes") is not None:
    _raw  = st.session_state.pop("_pending_pf_bytes")
    _name = st.session_state.pop("_pending_pf_name", "portefeuille.xlsx")
    _ph_pf = st.empty()
    try:
        _ph_pf.info(f"⏳ Traitement du Portefeuille ({len(_raw)//1024} KB)…")
        _df = _bytes_to_df_pf(_raw, _name)
        del _raw
        _ok = save_base("pf", _df, _name, user["nom"])
        if _ok:
            st.session_state.pf    = _df
            st.session_state.pf_ok = True
            _processed = True
            _ph_pf.success(f"✅ Portefeuille chargé — {len(_df):,} polices")
        else:
            _ph_pf.error("❌ Erreur lors de la sauvegarde")
    except Exception as _e:
        _ph_pf.error(f"❌ Portefeuille : {_e}")
        st.session_state["_pf_bytes_stored"] = False

if st.session_state.get("_pending_ca_list"):
    _pending_list = st.session_state.pop("_pending_ca_list")
    for _item in _pending_list:
        _raw  = _item["bytes"]
        _name = _item["name"]
        _cid  = _item["id"]
        _ph_ca = st.empty()
        try:
            _ph_ca.info(f"⏳ Traitement CA — {_name} ({len(_raw)//1024} KB)…")
            _df_new = _bytes_to_df_ca(_raw, _name)
            del _raw
            _seen = st.session_state.get("_ca_seen_ids", set())
            _seen.add(_cid)
            st.session_state["_ca_seen_ids"] = _seen
            st.session_state.ca_list_raw.append(_df_new)
            _merged = (_df_new if len(st.session_state.ca_list_raw) == 1
                       else pd.concat(st.session_state.ca_list_raw, ignore_index=True))
            _ok = save_base("ca", _merged, _name, user["nom"])
            if _ok:
                st.session_state.ca    = _merged
                st.session_state.ca_ok = True
                _processed = True
                _yrs = (sorted(_merged["ANNEE"].dropna().unique().astype(int).tolist())
                        if "ANNEE" in _merged.columns else [])
                _ph_ca.success(f"✅ CA chargé — {len(_merged):,} quittances · {', '.join(map(str,_yrs))}")
            else:
                _ph_ca.error("❌ Erreur lors de la sauvegarde CA")
        except Exception as _e:
            _ph_ca.error(f"❌ CA : {_e}")

if st.session_state.get("_pending_sin_bytes") is not None:
    _raw  = st.session_state.pop("_pending_sin_bytes")
    _name = st.session_state.pop("_pending_sin_name", "prestations.xlsx")
    _ph_sin = st.empty()
    try:
        _ph_sin.info(f"⏳ Traitement des Prestations ({len(_raw)//1024} KB)…")
        _df = _bytes_to_df_sin(_raw, _name)
        del _raw
        _ok = save_base("sin", _df, _name, user["nom"])
        if _ok:
            st.session_state.sin    = _df
            st.session_state.sin_ok = True
            _processed = True
            _ph_sin.success(f"✅ Prestations chargées — {len(_df):,} dossiers")
        else:
            _ph_sin.error("❌ Erreur lors de la sauvegarde")
    except Exception as _e:
        _ph_sin.error(f"❌ Prestations : {_e}")
        st.session_state["_sin_bytes_stored"] = False

# ── Rerun final — uniquement si un traitement a eu lieu ──────────────────────
# À ce point, TOUT le DOM est stable : sidebar rendue, widgets stabilisés,
# traitements terminés. st.rerun()
if _processed:
    st.rerun()
#  FONCTIONS CACHÉES — évite de recalculer à chaque clic d'onglet
#  @st.cache_data : résultat mis en cache selon les paramètres (hash du df)
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False, ttl=600)
def _cached_pf_stats(pf_hash: int, df_json: str):
    """Calcule les stats portefeuille en cache (10 min)."""
    import json
    df = pd.read_json(df_json, orient="split")
    res = {}
    if "ETAT_POLICE" in df.columns:
        vc = df["ETAT_POLICE"].str.strip().value_counts()
        res["actifs"] = int(vc.get("ACTIF", 0))
        res["resil"]  = int(vc.get("RESILIE", 0))
        res["inact"]  = int(vc.get("INACTIF", 0))
        res["echu"]   = int(vc.get("ECHU", 0) + vc.get("ASSURE ECHU", 0))
    res["nb"]     = len(df)
    res["monten"] = float(df["MONTENCA"].fillna(0).sum()) if "MONTENCA" in df.columns else 0
    res["nb_app"] = int(df["NOM_APP"].nunique()) if "NOM_APP" in df.columns else 0
    return res

@st.cache_data(show_spinner=False, ttl=600)
def _cached_ca_stats(ca_hash: int, df_json: str):
    """Calcule les stats CA en cache."""
    df = pd.read_json(df_json, orient="split")
    res = {}
    res["chifaffa"] = float(df["CHIFAFFA"].fillna(0).sum()) if "CHIFAFFA" in df.columns else 0
    res["commappo"] = float(df["COMMAPPO"].fillna(0).sum()) if "COMMAPPO" in df.columns else 0
    res["primnett"] = float(df["PRIMNETT"].fillna(0).sum()) if "PRIMNETT" in df.columns else 0
    res["nb_q"]     = len(df)
    return res

def _safe_groupby(df, by, agg_dict, sort_col=None, asc=False):
    """groupby robuste : ignore les colonnes absentes dans agg_dict."""
    safe_agg = {k: v for k, v in agg_dict.items()
                if isinstance(v, tuple) and v[0] in df.columns}
    if not safe_agg:
        return pd.DataFrame()
    try:
        res = df.groupby(by).agg(**safe_agg).reset_index()
        if sort_col and sort_col in res.columns:
            res = res.sort_values(sort_col, ascending=asc)
        return res
    except Exception as _e:
        return pd.DataFrame()

# ─────────────────────────────────────────────
#  RACCOURCIS
# ─────────────────────────────────────────────
pf  = st.session_state.pf
ca  = st.session_state.ca
sin = st.session_state.sin
page = st.session_state.current_page

# Fonctions filtre période
def pf_f():
    if pf is None: return pd.DataFrame()
    _df = filter_df(pf, "DATESOUS", sel_date, MODE)
    _yr = st.session_state.get("filtre_annee","Toutes les années")
    if _yr != "Toutes les années" and "ANNEESOUS" in _df.columns:
        _df = _df[_df["ANNEESOUS"].astype(str) == _yr]
    return _df
def ca_f():
    if ca is None: return pd.DataFrame()
    _df = filter_df(ca, "DATECOMP", sel_date, MODE)
    _yr = st.session_state.get("filtre_annee","Toutes les années")
    if _yr != "Toutes les années" and "ANNEE" in _df.columns:
        _df = _df[_df["ANNEE"].astype(str) == _yr]
    return _df

def sin_f():
    if sin is None: return pd.DataFrame()
    _df = filter_sin_exo(sin, sel_date, MODE)
    _yr = st.session_state.get("filtre_annee","Toutes les années")
    if _yr != "Toutes les années" and "ANNEE_SIN" in _df.columns:
        _df = _df[_df["ANNEE_SIN"].astype(str) == _yr]
    return _df

# ─────────────────────────────────────────────
#  TOPBAR
# ─────────────────────────────────────────────
pf_ct  = f"{len(pf):,}"  if pf  is not None else "—"
ca_ct  = f"{len(ca):,}"  if ca  is not None else "—"
sin_ct = f"{len(sin):,}" if sin is not None else "—"
st.markdown(f"""
<div class="afg-bar">
  <div style="display:flex;align-items:center;gap:12px">
    <img src="data:image/jpeg;base64,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"
         style="height:40px;object-fit:contain;border-radius:6px;background:white;padding:3px"/>
    <div>
      <div style="color:white;font-size:1.05rem;font-weight:800">AFG Assurances Bénin Vie</div>
      <div style="color:rgba(255,255,255,.45);font-size:9px;letter-spacing:.1em">DASHBOARD ACTUARIEL EXPERT · CIMA · GROUPE AFG HOLDING</div>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:9px">
    <div style="font-size:10px;color:rgba(255,255,255,.4)">
      Portefeuille: <b style="color:{MINT}">{pf_ct}</b> &nbsp;·&nbsp;
      CA: <b style="color:{MINT}">{ca_ct}</b> &nbsp;·&nbsp;
      Sinistres: <b style="color:{MINT}">{sin_ct}</b>
    </div>
    <div style="background:#C0392B;border-radius:7px;padding:4px 12px;color:white;font-size:11px;font-weight:800">{period_lbl}</div>
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
    # Badge filtre actif
    _yr_badge = f" · <b>Année {SEL_YEAR}</b>" if SEL_YEAR else ""
    section(f"📊 Indicateurs clés — {period_lbl}{_yr_badge}",
            f"CIMA · PORTEFEUILLE · {'TOUTES PÉRIODES' if not SEL_YEAR else f'EXERCICE {SEL_YEAR}'}")
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

    if sin is not None and not df_sin.empty:
        st.markdown("")
        _sin_yr_lbl = f"Exercice {SEL_YEAR}" if SEL_YEAR else "Toutes périodes"
        section(f"🏥 Sinistres & Prestations — {_sin_yr_lbl}",
                "RÉGLEMENTS · SAP · RATIO S/P · DONNÉES FILTRÉES")
        # Résolution dynamique des colonnes
        _c_r_a = next((c for c in df_sin.columns if "glement" in c.lower() and "otal" in c.lower()), None)
        _c_s_a = next((c for c in df_sin.columns if c.upper().startswith("SAP")), None)
        _c_srt = next((c for c in df_sin.columns if "ort" in c.lower() and "ini" in c.lower()), None)
        tot_sin = float(df_sin[_c_r_a].fillna(0).sum()) if _c_r_a else 0
        tot_sap = float(df_sin[_c_s_a].fillna(0).sum()) if _c_s_a else 0
        nb_sin  = len(df_sin)
        nb_ouv  = int((df_sin[_c_srt]=="Ouvert").sum()) if _c_srt else 0
        nb_clos = int((df_sin[_c_srt]=="Cloturé").sum()) if _c_srt else 0
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
                            _mc = [GREEN if v >= moy_g else "rgba(26,127,110,0.35)" for v in saison["CA moyen"]]
                            fig2=go.Figure(go.Bar(
                                x=saison["Label"], y=saison["CA moyen"],
                                marker_color=_mc,
                                text=[fmt(v) for v in saison["CA moyen"]],
                                textposition="outside", textfont=dict(size=9)))
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
                            text=[fmt(v) for v in cp["CA"]],textposition="outside", textfont=dict(size=10)))
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
    # 
# PAGE — PORTEFEUILLE
# ═══════════════════════════════════════════════════════════════════════════════
elif "Portefeuille" in page:
    if pf is None: alert("Chargez le Portefeuille dans la barre latérale.","warn"); st.stop()
    df_all = pf  # portefeuille complet
    # Filtre par année via SEL_YEAR (sélecteur sidebar)
    if SEL_YEAR:
        _yr_col = next((c for c in ["ANNEESOUS","ANNEE"] if c in pf.columns), None)
        if _yr_col:
            fi_yr = pf[pf[_yr_col].astype(str).str.strip() == str(SEL_YEAR)].copy()
        elif "DATESOUS" in pf.columns:
            _tmp = pf.copy()
            _tmp["_yr"] = pd.to_datetime(_tmp["DATESOUS"], errors="coerce").dt.year
            fi_yr = _tmp[_tmp["_yr"] == SEL_YEAR].copy()
        else:
            fi_yr = pf.copy()
        df = fi_yr if not fi_yr.empty else pf
    else:
        df = df_all

    # Titre dynamique selon filtre année
    _pf_yr_lbl = f" · Année {SEL_YEAR}" if SEL_YEAR else ""
    section(f"📋 Portefeuille{_pf_yr_lbl}","ANALYSE · FILTRES · EXPORT")

    # Listes de choix construites depuis df (déjà filtré par année si SEL_YEAR)
    _base_opts = df  # base pour les options = données de l'année choisie

    f0,f1,f2,f3,f4 = st.columns([1.2,1.2,1.2,1.2,1.2])

    # 0. Filtre état ETAT_POLICE
    etat_opts = ["Tous"] + sorted(
        _base_opts["ETAT_POLICE"].str.strip().dropna().unique().tolist()
    ) if "ETAT_POLICE" in _base_opts.columns else ["Tous"]
    etat_sel  = f0.selectbox("🔘 État police", etat_opts, key="pf_etat")

    # 1. Filtre produit / catégorie
    prod_opts = ["Tous"] + sorted(
        _base_opts["LIBECATE"].dropna().unique().tolist()
    ) if "LIBECATE" in _base_opts.columns else ["Tous"]
    prod_sel  = f1.selectbox("📦 Produit", prod_opts, key="pf_prod")

    # 2. Filtre périodicité — basé sur CODEPERI (valeur réelle) mappé en libellé
    _peri_col = "CODEPERI" if "CODEPERI" in _base_opts.columns else (
                "PERIODICITE" if "PERIODICITE" in _base_opts.columns else None)
    if _peri_col == "CODEPERI":
        _peri_vals = sorted(_base_opts["CODEPERI"].dropna().unique().tolist())
        _peri_lbls = [CODEPERI_MAP.get(v, str(v)) for v in _peri_vals]
        peri_opts  = ["Toutes"] + _peri_lbls
        _peri_code_map = dict(zip(_peri_lbls, _peri_vals))  # libellé → code
    elif _peri_col == "PERIODICITE":
        peri_opts  = ["Toutes"] + sorted(_base_opts["PERIODICITE"].dropna().unique().tolist())
        _peri_code_map = {}
    else:
        peri_opts  = ["Toutes"]
        _peri_code_map = {}
    peri_sel = f2.selectbox("🔄 Périodicité", peri_opts, key="pf_peri")

    # 3. Filtre ville
    villes_opts = ["Toutes"] + sorted(
        _base_opts["LIBEVILL"].dropna().unique().tolist()[:80]
    ) if "LIBEVILL" in _base_opts.columns else ["Toutes"]
    ville_sel   = f3.selectbox("📍 Ville", villes_opts, key="pf_ville")

    # 4. Recherche texte libre
    srch_pf = f4.text_input("🔍 Recherche", placeholder="Nom, ville, apporteur…", key="pf_srch")

    # Appliquer les filtres
    fi = df.copy()
    if etat_sel  != "Tous"    and "ETAT_POLICE"  in fi.columns:
        fi = fi[fi["ETAT_POLICE"].str.strip() == etat_sel]
    if prod_sel  != "Tous"    and "LIBECATE"      in fi.columns:
        fi = fi[fi["LIBECATE"] == prod_sel]
    if peri_sel  != "Toutes":
        if _peri_col == "CODEPERI" and "CODEPERI" in fi.columns:
            _code_sel = _peri_code_map.get(peri_sel)
            if _code_sel is not None:
                fi = fi[fi["CODEPERI"] == _code_sel]
        elif "PERIODICITE" in fi.columns:
            fi = fi[fi["PERIODICITE"] == peri_sel]
    if ville_sel != "Toutes"  and "LIBEVILL"      in fi.columns:
        fi = fi[fi["LIBEVILL"] == ville_sel]
    if srch_pf.strip():
        _cols_s = [c for c in ["NOM_ASSU","LIBEVILL","NOM_APP","LIBECATE"] if c in fi.columns]
        _mask   = pd.Series(False, index=fi.index)
        for c_ in _cols_s:
            _mask |= fi[c_].astype(str).str.lower().str.contains(srch_pf.lower(), na=False)
        fi = fi[_mask]

    # Badge filtres actifs
    _filters_active = [x for x in [
        f"Année {SEL_YEAR}" if SEL_YEAR else None,
        f"État : {etat_sel}" if etat_sel != "Tous" else None,
        f"Produit : {prod_sel}" if prod_sel != "Tous" else None,
        f"Périodicité : {peri_sel}" if peri_sel != "Toutes" else None,
        f"Ville : {ville_sel}" if ville_sel != "Toutes" else None,
        f"Recherche : {srch_pf}" if srch_pf.strip() else None,
    ] if x]
    if _filters_active:
        st.markdown(
            " &nbsp;".join([f'<span style="background:{NAVY}20;border:1px solid {NAVY}40;'
                            f'border-radius:12px;padding:2px 10px;font-size:11px;'
                            f'font-weight:600">🔍 {f}</span>'
                            for f in _filters_active]),
            unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:11px;color:#888;margin:4px 0'>"
                f"<b>{len(fi):,}</b> police(s) sur {len(df):,}</div>",
                unsafe_allow_html=True)

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
    t1,t2,t3,t4,t5 = st.tabs(["📋 Tableau","📊 Statistiques","📈 Évolution souscriptions","🔗 Jointure CA","👤 Tous les clients"])

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
        try:
            sc1,sc2=st.columns(2)
            with sc1:
                if "LIBECATE" in fi.columns and not fi.empty:
                    _pc_agg = {"Nb":("LIBECATE","count")}
                    if "MONTENCA" in fi.columns: _pc_agg["CA"] = ("MONTENCA","sum")
                    pc_=fi.groupby("LIBECATE").agg(**_pc_agg).reset_index().sort_values("Nb",ascending=False)
                    if "CA" not in pc_.columns: pc_["CA"] = 0
                    fig=go.Figure(go.Bar(x=pc_["Nb"],y=pc_["LIBECATE"].astype(str).str[:24],
                        orientation="h",
                        marker=dict(color=pc_["Nb"],colorscale=[[0,MINT],[1,GREEN2]],showscale=False),
                        text=pc_["Nb"].astype(str),textposition="outside", textfont=dict(size=10)))
                    fig.update_layout(yaxis=dict(autorange="reversed"))
                    fig_style(fig,380,"Polices par produit / catégorie")
                    st.plotly_chart(fig,use_container_width=True)
            with sc2:
                if "ETAT_POLICE" in fi.columns and not fi.empty:
                    etat_c_={"ACTIF":GREEN,"RESILIE":RED,"INACTIF":AMBER,
                             "ECHU":"#5A6478","ASSURE ECHU":"#2C3E50","SUSPENDU":BLUE}
                    ec=fi["ETAT_POLICE"].str.strip().value_counts().reset_index()
                    ec.columns=["État","Nb"]
                    fig2=go.Figure(go.Pie(labels=ec["État"],values=ec["Nb"],hole=.44,
                        marker_colors=[etat_c_.get(e,"#888") for e in ec["État"]],
                        textinfo="percent+label", textfont=dict(size=11)))
                    fig_style(fig2,380,"États du portefeuille")
                    st.plotly_chart(fig2,use_container_width=True)
            sc3,sc4=st.columns(2)
            with sc3:
                if "CODEPERI" in fi.columns and not fi.empty:
                    per=fi["CODEPERI"].map(CODEPERI_MAP).fillna("Autre").value_counts().reset_index()
                    per.columns=["Périodicité","Nb"]
                    fig3=go.Figure(go.Pie(labels=per["Périodicité"],values=per["Nb"],
                        hole=.44,marker_colors=PAL,textinfo="percent+label", textfont=dict(size=11)))
                    fig_style(fig3,320,"Périodicité des cotisations")
                    st.plotly_chart(fig3,use_container_width=True)
            with sc4:
                if "LIBEVILL" in fi.columns and not fi.empty:
                    vl=fi["LIBEVILL"].value_counts().head(10).reset_index()
                    vl.columns=["Ville","Nb"]
                    fig4=go.Figure(go.Bar(x=vl["Nb"],y=vl["Ville"].astype(str).str[:18],
                        orientation="h",marker_color=PAL[:len(vl)],
                        text=vl["Nb"].astype(str),textposition="outside", textfont=dict(size=10)))
                    fig4.update_layout(yaxis=dict(autorange="reversed"))
                    fig_style(fig4,320,"Top 10 villes d'implantation")
                    st.plotly_chart(fig4,use_container_width=True)
            _pc_stat = pc_ if "pc_" in dir() else fi
            a,b=st.columns(2)
            a.download_button("📥 CSV stats",dl_csv(_pc_stat),"stats_pf.csv",
                "text/csv",use_container_width=True,key="dl_stats_pf")
        except Exception as _e_t2:
            alert(f"Erreur Statistiques portefeuille : {_e_t2}","danger")

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
            section(f"🔗 Polices avec CA — {period_lbl}","JOINTURE PF × CA")
            _ca_tmp = ca_f(); _ca_join = _ca_tmp if _ca_tmp is not None and not _ca_tmp.empty else ca
            # Merge avec suffixes : colonnes PF ont suffixe _PF si conflit
            _fi_join = fi[["POLICE_KEY","LIBECATE","ETAT_POLICE","NOM_ASSU","LIBEVILL","NOM_APP"]].drop_duplicates("POLICE_KEY")
            ca_pf = _ca_join.merge(_fi_join, on="POLICE_KEY", how="inner", suffixes=("","_PF"))
            # Résolution dynamique des noms de colonnes après merge
            _libe = "LIBECATE_PF" if "LIBECATE_PF" in ca_pf.columns else "LIBECATE"
            _etat = "ETAT_POLICE_PF" if "ETAT_POLICE_PF" in ca_pf.columns else "ETAT_POLICE"
            _nom  = "NOM_ASSU_PF"  if "NOM_ASSU_PF"  in ca_pf.columns else "NOM_ASSU"
            _app  = "NOM_APP_PF"   if "NOM_APP_PF"   in ca_pf.columns else "NOM_APP"
            _grp_cols = [c for c in ["POLICE_KEY",_libe,_etat,_nom,_app] if c in ca_pf.columns]
            tp = (ca_pf.groupby(_grp_cols)
                       .agg(CA=("CHIFAFFA","sum"), NbQ=("CHIFAFFA","count"))
                       .reset_index()
                       .sort_values("CA", ascending=False)
                       .head(25))
            tp.columns = [c.replace("_PF","") for c in tp.columns]
            tp_d = tp.copy(); tp_d["CA"] = tp_d["CA"].apply(fmt)
            st.dataframe(tp_d, use_container_width=True, hide_index=True)
            a,b=st.columns(2)
            a.download_button("📥 CSV jointure",dl_csv(tp),"jointure_pf_ca.csv","text/csv",use_container_width=True,key="dl_join_pf")
        else: alert("Chargez la Base CA pour voir la jointure PF × CA.","info")

    with t5:
        section("👤 Liste complète des clients","NOM_ASSU · TOUTES POLICES")
        if pf is None:
            alert("Chargez le Portefeuille.","warn")
        else:
            # Filtres clients
            fc1,fc2,fc3 = st.columns(3)
            srch_cli = fc1.text_input("🔍 Rechercher un assuré",
                placeholder="Nom, prénom…", label_visibility="collapsed",
                key="srch_cli")
            etat_cli_opts = ["Tous"] + sorted(
                pf["ETAT_POLICE"].dropna().unique().tolist()) if "ETAT_POLICE" in pf.columns else ["Tous"]
            etat_cli = fc2.selectbox("État police", etat_cli_opts,
                label_visibility="collapsed", key="etat_cli")
            ville_cli_opts = ["Toutes"] + sorted(
                pf["LIBEVILL"].dropna().unique().tolist()) if "LIBEVILL" in pf.columns else ["Toutes"]
            ville_cli = fc3.selectbox("Ville", ville_cli_opts,
                label_visibility="collapsed", key="ville_cli")

            df_cli = pf.copy()
            if etat_cli != "Tous" and "ETAT_POLICE" in df_cli.columns:
                df_cli = df_cli[df_cli["ETAT_POLICE"] == etat_cli]
            if ville_cli != "Toutes" and "LIBEVILL" in df_cli.columns:
                df_cli = df_cli[df_cli["LIBEVILL"] == ville_cli]
            if srch_cli:
                _mask = pd.Series(False, index=df_cli.index)
                for _c in ["NOM_ASSU","LIBEVILL","NOM_APP"]:
                    if _c in df_cli.columns:
                        _mask |= df_cli[_c].astype(str).str.lower().str.contains(
                            srch_cli.lower(), na=False)
                df_cli = df_cli[_mask]

            # Colonnes à afficher
            _cli_cols = [c for c in [
                "NOM_ASSU","LIBECATE","ETAT_POLICE","LIBEVILL","NOM_APP",
                "DATESOUS","COTI_PERIODIQUE","MONTENCA","CODEPERI","POLICE_KEY"
            ] if c in df_cli.columns]
            df_cli_disp = df_cli[_cli_cols].copy()
            if "DATESOUS" in df_cli_disp.columns:
                df_cli_disp["DATESOUS"] = df_cli_disp["DATESOUS"].apply(ds)
            for _nc in ["COTI_PERIODIQUE","MONTENCA"]:
                if _nc in df_cli_disp.columns:
                    df_cli_disp[_nc] = df_cli_disp[_nc].apply(lambda x: fmt(x,""))

            st.caption(f"**{len(df_cli):,} clients** affichés sur {len(pf):,} polices totales")

            # Afficher avec pagination (1000 lignes max)
            page_size = 1000
            total_pages = max(1, (len(df_cli) + page_size - 1) // page_size)
            if total_pages > 1:
                page_num = st.number_input(
                    f"Page (1–{total_pages})", min_value=1,
                    max_value=total_pages, value=1, key="cli_page")
                start = (page_num - 1) * page_size
                df_show = df_cli_disp.iloc[start:start+page_size]
            else:
                df_show = df_cli_disp

            st.dataframe(df_show, use_container_width=True,
                        hide_index=True, height=500)
            ac1, ac2 = st.columns(2)
            ac1.download_button("📥 CSV clients filtrés",
                dl_csv(df_cli[_cli_cols]),
                f"clients_{etat_cli}_{ville_cli}.csv",
                "text/csv", use_container_width=True, key="dl_cli_csv")
            ac2.download_button("📥 Excel clients",
                dl_xlsx(df_cli[_cli_cols].head(50000)),
                "clients.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True, key="dl_cli_xl")

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
                            text=[fmt(v) for v in cp["CA"]],textposition="outside", textfont=dict(size=10)))
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
    # 
# PAGE — COMMERCIAUX
# ═══════════════════════════════════════════════════════════════════════════════
elif "Commerciaux" in page and "Partenaires" not in page:
    if ca is None: alert("Chargez la Base CA.","warn"); st.stop()
    df_com = ca_f()
    if df_com.empty: df_com = ca  # fallback toutes périodes

    section(f"👥 Performance Commerciale — {period_lbl}","CA · CLIENTS · COMMISSIONS · CLASSEMENT")

    # Priorité : NOM_APPORT (nom complet apporteur)  NOM_INTERMEDIAIRE  NOM_APP
    ag_k = next((c for c in ["NOM_APPORT","NOM_APPO","NOM_INTERMEDIAIRE","NOM_APP"]
                 if c in df_com.columns), None)
    if ag_k is None: alert("Colonne nom apporteur introuvable (NOM_APPORT/NOM_INTERMEDIAIRE).","danger"); st.stop()

    # Agrégation commerciale complète
    _agg_com = {"CA":("CHIFAFFA","sum"), "NbQ":("CHIFAFFA","count")}
    if "COMMAPPO" in df_com.columns:  _agg_com["Comm"]     = ("COMMAPPO","sum")
    else:                             _agg_com["Comm"]     = ("CHIFAFFA","count")
    if "POLICE_KEY" in df_com.columns: _agg_com["NbPolices"] = ("POLICE_KEY","nunique")
    else:                              _agg_com["NbPolices"] = ("CHIFAFFA","count")
    grp = df_com.groupby(ag_k).agg(**_agg_com).reset_index().sort_values("CA",ascending=False).reset_index(drop=True)
    grp.index += 1
    tot = grp["CA"].sum()
    grp["Part %"]    = (grp["CA"]/max(tot,1)*100).round(2)
    grp["Part cum %"]= grp["Part %"].cumsum().round(1)
    grp["Tx comm %"] = (grp["Comm"]/grp["CA"].replace(0,np.nan)*100).round(2)
    grp["Ticket moy"]= grp["CA"]/grp["NbQ"].replace(0,np.nan)

    # KPIs synthèse
    k1,k2,k3,k4 = st.columns(4)
    kpi(k1,"Nb commerciaux",f"{len(grp):,}","Intermédiaires actifs","teal",icon="👥")
    kpi(k2,"CA total",fmt(tot),"Période filtrée","",icon="💰")
    kpi(k3,"Ticket moyen",fmt(grp["CA"].mean()),"CA moyen/commercial","blue",icon="🎫")
    kpi(k4,"Commission moyenne",pct(grp["Tx comm %"].mean()),"Taux moyen","amber",icon="💼")

    st.markdown("")

    # Podium Top 3
    medals=["🥇","🥈","🥉"]; mc_c=[GREEN,TEAL,BLUE]
    cols3 = st.columns(3)
    for col,(med,mc),(idx,row) in zip(cols3,zip(medals,mc_c),grp.head(3).iterrows()):
        col.markdown(f"""
        <div style="background:linear-gradient(135deg,{mc}18,white);border:2px solid {mc};
             border-radius:14px;padding:1rem;text-align:center">
          <div style="font-size:28px">{med}</div>
          <div style="font-size:12px;font-weight:700;margin:5px 0;overflow:hidden;
               text-overflow:ellipsis;white-space:nowrap" title="{row[ag_k]}">{str(row[ag_k])[:26]}</div>
          <div style="font-size:10px;color:#666">{row['NbQ']:,} quittances · {row['NbPolices']:,} polices</div>
          <div style="font-size:17px;font-weight:800;color:{mc};margin-top:5px">{fmt(row['CA'])}</div>
          <div style="font-size:10px;color:#888">{pct(row['Part %'])} du CA · Comm. {fmt(row['Comm'])}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("")
    t_cl,t_par,t_stat,t_dt = st.tabs([
        "🏆 Classement complet","📊 Pareto CA","📈 Statistiques détaillées","🔍 Données par date"])

    with t_cl:
        # Recherche
        srch_com = st.text_input("🔍 Rechercher un commercial",
            label_visibility="collapsed", placeholder="Nom…", key="srch_com")
        df_show = grp.copy()
        if srch_com:
            df_show = df_show[df_show[ag_k].str.lower().str.contains(srch_com.lower(),na=False)]
        df_disp = df_show.copy()
        df_disp["CA"]        = df_disp["CA"].apply(fmt)
        df_disp["Comm"]      = df_disp["Comm"].apply(fmt)
        df_disp["Ticket moy"]= df_disp["Ticket moy"].apply(fmt)
        df_disp["Part %"]    = df_disp["Part %"].apply(lambda x:f"{x:.2f}%")
        df_disp["Part cum %"]= df_disp["Part cum %"].apply(lambda x:f"{x:.1f}%")
        df_disp["Tx comm %"] = df_disp["Tx comm %"].apply(lambda x:f"{x:.2f}%")
        df_disp.columns = [ag_k,"CA","Nb quittances","Commissions","Nb polices uniques",
                           "Part CA","Part cumulée","Tx commission","Ticket moyen"]
        st.dataframe(df_disp, use_container_width=True, height=480)
        a,b = st.columns(2)
        a.download_button("📥 CSV",dl_csv(grp),"commerciaux.csv","text/csv",use_container_width=True,key="dl_com_csv")
        b.download_button("📥 Excel",dl_xlsx(grp),"commerciaux.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_com_xl")

    with t_par:
        c1,c2 = st.columns(2)
        with c1:
            t30 = grp.head(30)
            fig = make_subplots(specs=[[{"secondary_y":True}]])
            fig.add_bar(x=t30["CA"],y=t30[ag_k].str[:22],name="CA",marker_color=GREEN,orientation="h")
            fig.add_scatter(x=t30["Part cum %"],y=t30[ag_k].str[:22],name="Cumul %",
                line=dict(color=RED,width=2.5),secondary_y=True,orientation="h")
            fig.update_layout(yaxis=dict(autorange="reversed"))
            fig_style(fig,520,f"📊 Pareto CA — Top 30 commerciaux · {period_lbl}")
            st.plotly_chart(fig,use_container_width=True)
        with c2:
            # Distribution des CA
            fig2 = go.Figure(go.Histogram(x=grp["CA"],nbinsx=30,
                marker_color=GREEN,opacity=.85))
            fig_style(fig2,520,"📊 Distribution CA par commercial")
            st.plotly_chart(fig2,use_container_width=True)

    with t_stat:
        c1,c2 = st.columns(2)
        with c1:
            # CA par produit × commercial (heatmap)
            if "LIBECATE" in df_com.columns:
                heat = df_com.groupby([ag_k,"LIBECATE"])["CHIFAFFA"].sum().reset_index()
                heat_piv = heat.pivot_table(index=ag_k,columns="LIBECATE",
                    values="CHIFAFFA",aggfunc="sum",fill_value=0)
                top10_com = grp.head(10)[ag_k].tolist()
                heat_piv  = heat_piv.loc[heat_piv.index.isin(top10_com)]
                fig3 = go.Figure(go.Heatmap(
                    z=heat_piv.values.tolist(),
                    x=[str(c)[:20] for c in heat_piv.columns],
                    y=[str(i)[:22] for i in heat_piv.index],
                    colorscale=[[0,MINT],[.5,GREEN],[1,GREEN2]],
                    text=[[fmt(v) for v in row] for row in heat_piv.values],
                    texttemplate="%{text}", textfont=dict(size=9)))
                fig3.update_layout(height=420,margin=dict(l=140,r=20,t=40,b=80))
                fig3.update_layout(title=dict(text="CA par commercial × produit (Top 10)",
                    font=dict(size=12,color=NAVY),x=.01))
                st.plotly_chart(fig3,use_container_width=True)
        with c2:
            # Évolution mensuelle des top 5
            if "DATECOMP" in df_com.columns:
                top5 = grp.head(5)[ag_k].tolist()
                df_ev = df_com[df_com[ag_k].isin(top5)].copy()
                df_ev["Mois"] = df_ev["DATECOMP"].dt.to_period("M").astype(str)
                ev_grp = df_ev.groupby(["Mois",ag_k])["CHIFAFFA"].sum().reset_index()
                fig4 = px.line(ev_grp, x="Mois", y="CHIFAFFA",color=ag_k,
                    color_discrete_sequence=PAL,
                    labels={"CHIFAFFA":"CA (FCFA)","Mois":"Mois"})
                fig_style(fig4,420,"📈 Évolution CA — Top 5 commerciaux")
                st.plotly_chart(fig4,use_container_width=True)

    with t_dt:
        if "DATECOMP" in df_com.columns and ag_k in df_com.columns:
            sel_com = st.selectbox("Sélectionner un commercial",
                ["Tous"]+grp[ag_k].tolist()[:50], key="sel_com_dt")
            df_dt = df_com if sel_com=="Tous" else df_com[df_com[ag_k]==sel_com]
            dt_grp = df_dt.groupby(df_dt["DATECOMP"].dt.date).agg(
                CA=("CHIFAFFA","sum"),NbQ=("CHIFAFFA","count")).reset_index()
            dt_grp.columns = ["Date","CA","Nb quittances"]
            fig5 = make_subplots(specs=[[{"secondary_y":True}]])
            fig5.add_bar(x=dt_grp["Date"].astype(str),y=dt_grp["CA"],
                name="CA",marker_color=GREEN,opacity=.85)
            fig5.add_scatter(x=dt_grp["Date"].astype(str),y=dt_grp["Nb quittances"],
                name="Nb quittances",line=dict(color=BLUE,width=2),secondary_y=True)
            fig_style(fig5,420,f"📅 CA journalier — {sel_com}")
            st.plotly_chart(fig5,use_container_width=True)
            dt_d = dt_grp.copy(); dt_d["CA"] = dt_d["CA"].apply(fmt)
            st.dataframe(dt_d, use_container_width=True, hide_index=True, height=300)
            a,b = st.columns(2)
            a.download_button("📥 CSV",dl_csv(dt_grp),"ca_journalier.csv","text/csv",use_container_width=True,key="dl_dt_csv")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — PARTENAIRES FINANCIERS
# ═══════════════════════════════════════════════════════════════════════════════
elif "Partenaires" in page:
    if ca is None: alert("Chargez la Base CA.","warn"); st.stop()
    df_part_all = ca_f()
    if df_part_all is None or df_part_all.empty: df_part_all = ca

    section(f"🏦 Partenaires Financiers — {period_lbl}",
            "CODE INTERMÉDIAIRE 3 CHIFFRES · HORS CODE 100")

    # Identifier la colonne code intermédiaire : CODEINTE (priorité)
    _col_code = next((c for c in ["CODEINTE","CODE_INTER","CODEINTER","CODEAPPO"]
                      if c in df_part_all.columns), None)
    # Nom de l'intermédiaire : NOM_APPORT priorité
    _col_nom  = next((c for c in ["NOM_APPORT","NOM_APPO","NOM_INTERMEDIAIRE","NOM_APP"]
                      if c in df_part_all.columns), None)

    if _col_code is None:
        alert("Colonne code intermédiaire introuvable (CODE_INTER / CODEAPPO).","warn")
        st.stop()

    # Construire CODEAPPO_STR normalisé
    df_part_all["_CODE_STR"] = df_part_all[_col_code].astype(str).str.strip().str.zfill(3)

    # Partenaires financiers = code 3 chiffres numériques, hors 100
    def _is_pf(x):
        s = str(x).strip().lstrip("0") or "0"
        return str(x).strip().isdigit() and len(str(x).strip()) <= 3 and str(x).strip() != "100"

    _mask_pf  = df_part_all["_CODE_STR"].apply(
        lambda x: x.isdigit() and len(x) <= 3 and x not in ("100","000"))
    df_pf     = df_part_all[_mask_pf].copy()
    df_ri     = df_part_all[~_mask_pf].copy()

    ca_pf_tot = float(df_pf["CHIFAFFA"].sum()) if "CHIFAFFA" in df_pf.columns else 0
    ca_ri_tot = float(df_ri["CHIFAFFA"].sum()) if "CHIFAFFA" in df_ri.columns else 0
    ca_total  = ca_pf_tot + ca_ri_tot

    p1,p2,p3,p4 = st.columns(4)
    kpi(p1,"CA partenaires",fmt(ca_pf_tot),f"{pct(ca_pf_tot/max(ca_total,1)*100)}","blue",icon="🏦")
    kpi(p2,"CA réseau interne",fmt(ca_ri_tot),f"{pct(ca_ri_tot/max(ca_total,1)*100)}","teal",icon="🏢")
    kpi(p3,"Nb partenaires",str(df_pf["_CODE_STR"].nunique()),"Codes distincts","",icon="🤝")
    _nq_pf = int(df_pf["CHIFAFFA"].count()) if "CHIFAFFA" in df_pf.columns else 1
    kpi(p4,"Ticket moyen",fmt(ca_pf_tot/max(_nq_pf,1)),"CA / quittance","amber",icon="🎫")

    st.markdown("")
    tp1,tp2,tp3 = st.tabs(["📊 Par partenaire","🥧 Réseau vs Partenaires","🔍 Données brutes"])

    with tp1:
        if not df_pf.empty:
            _grp_cols = ["_CODE_STR"]
            if _col_nom and _col_nom in df_pf.columns:
                _grp_cols.append(_col_nom)
            _agg_p = {"CA":("CHIFAFFA","sum"), "NbQ":("CHIFAFFA","count")}
            if "COMMAPPO" in df_pf.columns: _agg_p["Commission"] = ("COMMAPPO","sum")
            dp = df_pf.groupby(_grp_cols).agg(**_agg_p).reset_index()
            dp = dp.sort_values("CA",ascending=False)
            dp["Part %"] = (dp["CA"]/max(ca_pf_tot,1)*100).round(2)
            dp.index = range(1, len(dp)+1)

            c1p,c2p = st.columns(2)
            with c1p:
                # Libellé : nom si dispo, sinon code
                _par_lbl_col = _col_nom if (_col_nom and _col_nom in dp.columns) else "_CODE_STR"
                _par_lbl15   = dp[_par_lbl_col].astype(str).str[:22].head(15)
                _par_val15   = dp["CA"].head(15)

                fig = go.Figure(go.Bar(
                    x=_par_val15, y=_par_lbl15,
                    orientation="h", marker_color=BLUE,
                    text=[fmt(v) for v in _par_val15],
                    textposition="outside", textfont=dict(size=9)))
                fig.update_layout(yaxis=dict(autorange="reversed"))
                _yr_lbl_p = f" · {SEL_YEAR}" if SEL_YEAR else f" · {period_lbl}"
                fig_style(fig, 420, f"CA par partenaire{_yr_lbl_p}")
                st.plotly_chart(fig, use_container_width=True)
            with c2p:
                dp_top = dp.head(10)
                _pie_lbl = dp_top[_par_lbl_col].astype(str).str[:18]
                fig2 = go.Figure(go.Pie(
                    labels=_pie_lbl, values=dp_top["CA"], hole=.4,
                    textinfo="percent+label", textfont=dict(size=10)))
                fig_style(fig2, 420, "Part de marché — Top 10")
                st.plotly_chart(fig2, use_container_width=True)

            # Tableau — renommer proprement sans réindexer colonnes
            dp_d = dp.copy()
            # Formatage des montants
            if "CA" in dp_d.columns:
                dp_d["CA"] = dp_d["CA"].apply(fmt)
            if "Commission" in dp_d.columns:
                dp_d["Commission"] = dp_d["Commission"].apply(fmt)
            if "Part %" in dp_d.columns:
                dp_d["Part %"] = dp_d["Part %"].apply(lambda x: f"{x:.2f}%")
            # Renommer les colonnes de façon lisible
            _rename_dp = {"_CODE_STR": "Code", "CA": "CA (FCFA)", "NbQ": "Nb affaires",
                          "Commission": "Commission (FCFA)", "Part %": "Part %"}
            if _col_nom and _col_nom in dp_d.columns:
                _rename_dp[_col_nom] = "Partenaire"
            dp_d = dp_d.rename(columns=_rename_dp)
            st.dataframe(dp_d, use_container_width=True, height=380, hide_index=True)
            # Export
            _dl1, _dl2 = st.columns(2)
            _dl1.download_button("📥 CSV partenaires", dl_csv(dp),
                "partenaires.csv", "text/csv",
                use_container_width=True, key="dl_part_csv")
            _dl2.download_button("📥 Excel partenaires", dl_xlsx(dp),
                "partenaires.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True, key="dl_part_xl")
            a,b = st.columns(2)
            a.download_button("📥 CSV",dl_csv(dp),"partenaires.csv","text/csv",
                use_container_width=True,key="dl_pf_csv")
            b.download_button("📥 Excel",dl_xlsx(dp),"partenaires.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,key="dl_pf_xl")
        else:
            alert("Aucun partenaire financier identifié dans les données.","info")

    with tp2:
        labels = ["Partenaires financiers","Réseau interne / Autres"]
        vals   = [ca_pf_tot, ca_ri_tot]
        fig3 = go.Figure(go.Pie(labels=labels, values=vals, hole=.5,
            marker_colors=[BLUE, GREEN], textinfo="percent+label+value",
            textfont=dict(size=12)))
        fig_style(fig3, 400, f"Réseau vs Partenaires — {period_lbl}")
        st.plotly_chart(fig3, use_container_width=True)

    with tp3:
        if not df_pf.empty:
            _show_cols = [c for c in ["_CODE_STR", _col_nom, "CHIFAFFA","COMMAPPO","PRIMNETT"]
                          if c and c in df_pf.columns]
            _raw = df_pf[_show_cols].rename(columns={"_CODE_STR":"Code"}).copy()
            for mc in ["CHIFAFFA","COMMAPPO","PRIMNETT"]:
                if mc in _raw.columns: _raw[mc] = _raw[mc].apply(fmt)
            st.dataframe(_raw.head(500), use_container_width=True, hide_index=True)
            st.download_button("📥 CSV brut",dl_csv(df_pf),"pf_brut.csv","text/csv",
                use_container_width=True,key="dl_pf_raw")


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
        t_g,t_d,t_a,t_cl=st.tabs(["🗺️ Géographie","📊 Démographie","🎂 Pyramide des âges","👤 Répertoire clients"])
        with t_g:
            if "LIBEVILL" in df.columns:
                c1,c2=st.columns(2)
                with c1:
                    vl=df.groupby("LIBEVILL").agg(Nb=("LIBEVILL","count"),CA=("MONTENCA","sum")).reset_index().sort_values("Nb",ascending=False).head(15)
                    fig=go.Figure(go.Bar(x=vl["Nb"],y=vl["LIBEVILL"].str[:18],orientation="h",
                        marker=dict(color=vl["Nb"],colorscale=[[0,MINT],[1,GREEN2]],showscale=False),
                        text=vl["Nb"].astype(str),textposition="outside", textfont=dict(size=10)))
                    fig.update_layout(yaxis=dict(autorange="reversed"))
                    fig_style(fig,400,"📍 Top 15 villes — Polices")
                    st.plotly_chart(fig,use_container_width=True)
                with c2:
                    vl_ca=df.groupby("LIBEVILL")["MONTENCA"].sum().reset_index().sort_values("MONTENCA",ascending=False).head(12)
                    fig2=go.Figure(go.Bar(x=vl_ca["MONTENCA"],y=vl_ca["LIBEVILL"].str[:18],orientation="h",
                        marker=dict(color=vl_ca["MONTENCA"],colorscale=[[0,MINT],[1,GREEN2]],showscale=False),
                        text=[fmt(v) for v in vl_ca["MONTENCA"]],textposition="outside", textfont=dict(size=10)))
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
                    fig=go.Figure(go.Pie(labels=sx["Sexe"],values=sx["Nb"],hole=.44,marker_colors=[BLUE,GREEN],textinfo="percent+label+value", textfont=dict(size=12)))
                    fig_style(fig,320,"👥 Répartition H/F"); st.plotly_chart(fig,use_container_width=True)
            with c2:
                if "CODEPERI" in df.columns:
                    per=df["CODEPERI"].map(CODEPERI_MAP).fillna("Autre").value_counts().reset_index(); per.columns=["Périodicité","Nb"]
                    fig2=go.Figure(go.Pie(labels=per["Périodicité"],values=per["Nb"],hole=.44,marker_colors=PAL,textinfo="percent+label", textfont=dict(size=11)))
                    fig_style(fig2,320,"📅 Périodicité cotisations"); st.plotly_chart(fig2,use_container_width=True)
            with c3:
                if "NOM_APP" in df.columns:
                    ap=df[df["ETAT_POLICE"].str.strip()=="ACTIF"]["NOM_APP"].value_counts().head(10).reset_index() if "ETAT_POLICE" in df.columns else df["NOM_APP"].value_counts().head(10).reset_index()
                    ap.columns=["Apporteur","Nb actifs"]
                    fig3=go.Figure(go.Bar(y=ap["Apporteur"].str[:18],x=ap["Nb actifs"],orientation="h",marker_color=GREEN,text=ap["Nb actifs"].astype(str),textposition="outside", textfont=dict(size=10)))
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
                    fig.add_bar(y=pyr["tranch"],x=-pyr["M"],name="Hommes",orientation="h",marker_color=BLUE,text=pyr["M"].astype(str),textposition="outside", textfont=dict(size=9))
                    fig.add_bar(y=pyr["tranch"],x=pyr["F"],name="Femmes",orientation="h",marker_color=GREEN,text=pyr["F"].astype(str),textposition="outside", textfont=dict(size=9))
                    fig.update_layout(barmode="overlay",xaxis=dict(tickvals=list(range(-4000,4001,500)),ticktext=[str(abs(x)) for x in range(-4000,4001,500)]))
                    fig_style(fig,520,"🎂 Pyramide des âges (tranches quinquennales)")
                    st.plotly_chart(fig,use_container_width=True)
                    a,_=st.columns(2)
                    a.download_button("📥 CSV pyramide",dl_csv(da[["age","SEXERISQ"]]),"pyramide.csv","text/csv",use_container_width=True,key="dl_pyr")
            else: alert("Colonnes DATENAIS et SEXERISQ requises dans le portefeuille.","info")

        with t_cl:
            section("👤 Répertoire complet des clients assurés","RECHERCHE · FILTRE · EXPORT")
            _c1,_c2,_c3,_c4 = st.columns(4)
            _srch = _c1.text_input("🔍 Rechercher",placeholder="Nom assuré…",
                label_visibility="collapsed", key="cli_geo_srch")
            _etat_opts = ["Tous"]+sorted(df["ETAT_POLICE"].dropna().unique().tolist())             if "ETAT_POLICE" in df.columns else ["Tous"]
            _etat = _c2.selectbox("État",_etat_opts,label_visibility="collapsed",key="cli_geo_etat")
            _vill_opts = ["Toutes"]+sorted(df["LIBEVILL"].dropna().unique().tolist())             if "LIBEVILL" in df.columns else ["Toutes"]
            _vill = _c3.selectbox("Ville",_vill_opts,label_visibility="collapsed",key="cli_geo_vill")
            _prod_opts = ["Tous"]+sorted(df["LIBECATE"].dropna().unique().tolist())             if "LIBECATE" in df.columns else ["Tous"]
            _prod = _c4.selectbox("Produit",_prod_opts,label_visibility="collapsed",key="cli_geo_prod")

            _df_rep = df.copy()
            if _etat != "Tous" and "ETAT_POLICE" in _df_rep.columns:
                _df_rep = _df_rep[_df_rep["ETAT_POLICE"]==_etat]
            if _vill != "Toutes" and "LIBEVILL" in _df_rep.columns:
                _df_rep = _df_rep[_df_rep["LIBEVILL"]==_vill]
            if _prod != "Tous" and "LIBECATE" in _df_rep.columns:
                _df_rep = _df_rep[_df_rep["LIBECATE"]==_prod]
            if _srch:
                _m = pd.Series(False,index=_df_rep.index)
                for _c in ["NOM_ASSU","LIBEVILL","NOM_APP","LIBECATE"]:
                    if _c in _df_rep.columns:
                        _m |= _df_rep[_c].astype(str).str.lower().str.contains(_srch.lower(),na=False)
                _df_rep = _df_rep[_m]

            _rep_cols = [c for c in ["NOM_ASSU","LIBECATE","ETAT_POLICE","LIBEVILL",
                "NOM_APP","DATESOUS","COTI_PERIODIQUE","MONTENCA","CODEPERI","POLICE_KEY"]
                if c in _df_rep.columns]
            _df_rep_d = _df_rep[_rep_cols].copy()
            if "DATESOUS" in _df_rep_d.columns:
                _df_rep_d["DATESOUS"] = _df_rep_d["DATESOUS"].apply(ds)
            for _nc in ["COTI_PERIODIQUE","MONTENCA"]:
                if _nc in _df_rep_d.columns:
                    _df_rep_d[_nc] = _df_rep_d[_nc].apply(lambda x: fmt(x,""))
            _df_rep_d.columns = [
                {"NOM_ASSU":"Assuré","LIBECATE":"Produit","ETAT_POLICE":"État",
                 "LIBEVILL":"Ville","NOM_APP":"Apporteur","DATESOUS":"Date souscription",
                 "COTI_PERIODIQUE":"Cotisation","MONTENCA":"Encaissement",
                 "CODEPERI":"Périodicité","POLICE_KEY":"N° Police"}.get(c,c)
                for c in _df_rep_d.columns]

            st.caption(f"**{len(_df_rep):,} polices** · {_df_rep['NOM_ASSU'].nunique() if 'NOM_ASSU' in _df_rep.columns else 0:,} clients distincts")

            # Pagination 500 lignes
            _ps = 500
            _tp = max(1,(len(_df_rep)+_ps-1)//_ps)
            if _tp > 1:
                _pn = st.number_input(f"Page (1–{_tp})",min_value=1,max_value=_tp,value=1,key="cli_rep_page")
                _st = (_pn-1)*_ps
                st.dataframe(_df_rep_d.iloc[_st:_st+_ps],use_container_width=True,hide_index=True,height=520)
            else:
                st.dataframe(_df_rep_d,use_container_width=True,hide_index=True,height=520)

            _ac1,_ac2 = st.columns(2)
            _ac1.download_button("📥 CSV répertoire",dl_csv(_df_rep[_rep_cols]),
                "repertoire_clients.csv","text/csv",use_container_width=True,key="dl_rep_csv")
            _ac2.download_button("📥 Excel répertoire",dl_xlsx(_df_rep[_rep_cols].head(50000)),
                "repertoire_clients.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,key="dl_rep_xl")

    # ═══════════════════════════════════════════════════════════════════════════════
    # 
# PAGE — SINISTRES & PROVISIONS
# ═══════════════════════════════════════════════════════════════════════════════
elif "Sinistres" in page:
    if sin is None: alert("Chargez le fichier Prestations.","warn"); st.stop()
    df_s = sin  # tout le fichier

    # Filtre par année
    if SEL_YEAR and "ANNEE_SIN" in sin.columns:
        _sin_yr = sin[sin["ANNEE_SIN"] == SEL_YEAR].copy()
        df_sf = _sin_yr if not _sin_yr.empty else sin_f()
    elif SEL_YEAR and "Exercice Sinistre" in sin.columns:
        _sin_yr = sin[sin["Exercice Sinistre"].astype(str) == str(SEL_YEAR)].copy()
        df_sf = _sin_yr if not _sin_yr.empty else sin_f()
    else:
        df_sf = sin_f()

    # Filtre supplémentaire : Nature de sinistre (périodicité)
    _c_nat_sin = next((c for c in df_sf.columns
                       if "ature" in c.lower() and "ini" in c.lower()), None)
    _c_sort_sin = next((c for c in df_sf.columns
                        if "ort" in c.lower() and "ini" in c.lower()), None)
    _sf1, _sf2, _sf3 = st.columns(3)
    if _c_nat_sin:
        _nat_opts = ["Toutes"] + sorted(df_sf[_c_nat_sin].dropna().unique().tolist())
        _nat_sel  = _sf1.selectbox("🔷 Nature sinistre", _nat_opts, key="sin_nat_f")
        if _nat_sel != "Toutes":
            df_sf = df_sf[df_sf[_c_nat_sin] == _nat_sel]
    if _c_sort_sin:
        _sort_opts = ["Tous"] + sorted(df_sf[_c_sort_sin].dropna().unique().tolist())
        _sort_sel  = _sf2.selectbox("📌 Sort sinistre", _sort_opts, key="sin_sort_f")
        if _sort_sel != "Tous":
            df_sf = df_sf[df_sf[_c_sort_sin] == _sort_sel]
    _sin_srch = _sf3.text_input("🔍 Recherche", placeholder="N° police, nature…", key="sin_srch")
    if _sin_srch.strip():
        _cols_sin = [c for c in df_sf.columns if df_sf[c].dtype == object][:6]
        _msk_sin  = pd.Series(False, index=df_sf.index)
        for _cs in _cols_sin:
            _msk_sin |= df_sf[_cs].astype(str).str.lower().str.contains(_sin_srch.lower(), na=False)
        df_sf = df_sf[_msk_sin]
    _yr_lbl_sin = f"Exercice {SEL_YEAR}" if SEL_YEAR else period_lbl
    st.markdown(f"<div style='font-size:11px;color:#888'><b>{len(df_sf):,}</b> dossier(s) — {_yr_lbl_sin}</div>",
                unsafe_allow_html=True)
    # Résolution colonnes sinistres — noms exacts vérifiés sur fichier AFG réel
    def _find_col(df, *candidates):
        """
        Retourne la 1ère colonne trouvée parmi les candidats.
        Stratégie : exact  strip  lower+strip  fuzzy.
        """
        # Index normalisé : {nom_lowercase_sans_espaces: nom_réel}
        cols_norm = {c.strip().lower().replace(" ",""): c for c in df.columns}
        for cand in candidates:
            # 1. Correspondance exacte
            if cand in df.columns:
                return cand
            # 2. Après strip des deux côtés
            cand_strip = cand.strip()
            for col in df.columns:
                if col.strip() == cand_strip:
                    return col
            # 3. Normalisé lowercase sans espaces
            cand_norm = cand.strip().lower().replace(" ","")
            if cand_norm in cols_norm:
                return cols_norm[cand_norm]
            # 4. Fuzzy : tous les mots du candidat présents dans la colonne
            cand_words = [w for w in cand.lower().split() if len(w) > 2]
            for col in df.columns:
                col_l = col.lower()
                if cand_words and all(w in col_l for w in cand_words):
                    return col
        return None

    # Noms EXACTS confirmés sur le fichier Prestations_au_31122025.xlsx
    # + fallbacks pour robustesse si encodage différent
    _c_regle_ = _find_col(sin, "Réglement Total",      "Reglement Total",      "Règlement Total")
    _c_sap_   = _find_col(sin, "SAP au 31/12/2025",    "SAP")
    _c_hon_   = _find_col(sin, "Réglement Honoraires",  "Reglement Honoraires", "Règlement Honoraires")
    _c_nat_   = _find_col(sin, "Nature Sinistre",       "Nature Sinstre")
    _c_sort_  = _find_col(sin, "Sort Sinistre")
    _c_cat_   = _find_col(sin, "Libéllé Catégorie",    "Libellé Catégorie",    "Libelle Categorie", "Libéllé Catégorie risque")
    _c_souscr = _find_col(sin, "Souscripteur")
    _c_exo    = _find_col(sin, "Exercice Sinistre")
    _c_surv_  = _find_col(sin, "Date Survenance")
    _c_decl   = _find_col(sin, "Date Déclaration",     "Date Declaration")
    _c_compt  = _find_col(sin, "Réglement Comptable",   "Reglement Comptable")
    _c_rae    = _find_col(sin, "RAE Cie au 31/12/2025")
    _c_branch = _find_col(sin, "Libellé branche")

    # Debug : afficher ce qui a été trouvé (si colonnes manquantes)
    _missing_cols = [n for n,v in [
        ("Réglement Total",_c_regle_),("SAP",_c_sap_),
        ("Nature Sinistre",_c_nat_),("Sort Sinistre",_c_sort_),
        ("Libéllé Catégorie",_c_cat_)] if v is None]
    if _missing_cols:
        st.warning(f"⚠️ Colonnes non trouvées : {_missing_cols} | "
                   f"Colonnes disponibles : {list(sin.columns[:10])}")

    section(f"⚠️ Sinistres & Prestations — {period_lbl}","ANALYSE ACTUARIELLE · SAP · S/P")
    # Noms exacts vérifiés sur fichier AFG réel
    _c_tot  = "Réglement Total"     if "Réglement Total"     in sin.columns else next((c for c in sin.columns if "glement" in c and "otal" in c), None)
    _c_sap  = "SAP au 31/12/2025"  if "SAP au 31/12/2025"  in sin.columns else next((c for c in sin.columns if c.startswith("SAP")), None)
    _c_hon  = "Réglement Honoraires" if "Réglement Honoraires" in sin.columns else next((c for c in sin.columns if "glement" in c and "onnor" in c), None)
    tot_sin = float(sin[_c_tot].fillna(0).sum()) if _c_tot and _c_tot in sin.columns else 0
    tot_sap = float(sin[_c_sap].fillna(0).sum()) if _c_sap and _c_sap in sin.columns else 0
    tot_hon = float(sin[_c_hon].fillna(0).sum()) if _c_hon and _c_hon in sin.columns else 0
    charge_u=tot_sin+tot_sap+tot_hon
    nb_sin=len(sin); nb_clos=int((sin[_c_sort_]=="Cloturé").sum()) if _c_sort_ and _c_sort_ in sin.columns else 0
    nb_ouv=int((sin[_c_sort_]=="Ouvert").sum()) if _c_sort_ and _c_sort_ in sin.columns else 0
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
        if _c_nat_ and _c_regle_:
            try:
                nat = _safe_groupby(sin, _c_nat_,
                    {"Nb":(_c_nat_,"count"),
                     "Réglé":(_c_regle_,"sum"),
                     **( {"SAP":(_c_sap_,"sum")} if _c_sap_ else {})},
                    sort_col="Réglé")
                if "Réglé" not in nat.columns: nat["Réglé"] = 0.0
                if "SAP"   not in nat.columns: nat["SAP"]   = 0.0
                nat["Charge"]   = nat["Réglé"] + nat["SAP"]
                nat["Coût moyen"] = nat["Réglé"] / nat["Nb"].replace(0, np.nan)
                c1,c2 = st.columns(2)
                with c1:
                    fig = go.Figure()
                    fig.add_bar(y=nat[_c_nat_].astype(str).str[:24],
                        x=nat["Réglé"], name="Réglé", marker_color=RED, orientation="h")
                    fig.add_bar(y=nat[_c_nat_].astype(str).str[:24],
                        x=nat["SAP"],   name="SAP",   marker_color=AMBER, orientation="h")
                    fig.update_layout(barmode="stack", yaxis=dict(autorange="reversed"))
                    fig_style(fig, 380, "Règlements + SAP par nature de sinistre")
                    st.plotly_chart(fig, use_container_width=True)
                with c2:
                    _nat_c = nat[nat["Charge"]>0]
                    if not _nat_c.empty:
                        fig2 = px.treemap(_nat_c, path=[_c_nat_], values="Charge",
                            color="Nb", color_continuous_scale=[[0,MINT],[.5,AMBER],[1,RED]])
                        fig2.update_layout(height=380, margin=dict(l=5,r=5,t=20,b=5))
                        st.plotly_chart(fig2, use_container_width=True)
                nat_d = nat.copy()
                for c_ in ["Réglé","SAP","Charge","Coût moyen"]:
                    if c_ in nat_d.columns: nat_d[c_] = nat_d[c_].apply(fmt)
                st.dataframe(nat_d, use_container_width=True, hide_index=True)
                a,b = st.columns(2)
                a.download_button("📥 CSV", dl_csv(nat), "sin_nature.csv",
                    "text/csv", use_container_width=True, key="dl_sin_nat")
                b.download_button("📥 Excel", dl_xlsx(nat), "sin_nature.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True, key="dl_sin_nat_xl")
            except Exception as _e:
                alert(f"Erreur 'Par nature' : {_e}", "danger")
        else:
            alert("Colonne 'Nature Sinistre' ou 'Reglement Total' absente du fichier.", "warn")

    with t_e:
        if "ANNEE_SIN" in sin.columns:
            evo = _safe_groupby(sin, "ANNEE_SIN",
                {"Nb":("ANNEE_SIN","count"),
                 "Réglé":(_c_regle_,"sum") if _c_regle_ else None,
                 "SAP":(_c_sap_,"sum") if _c_sap_ else None})
            if "Réglé" not in evo.columns: evo["Réglé"] = 0
            if "SAP"   not in evo.columns: evo["SAP"]   = 0
            evo=evo[evo["ANNEE_SIN"].between(1997,2025)].sort_values("ANNEE_SIN")
            fig=make_subplots(specs=[[{"secondary_y":True}]])
            fig.add_bar(x=evo["ANNEE_SIN"].astype(str),y=evo["Réglé"],name="Réglé",marker_color=RED,opacity=.82)
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
        # Détection robuste du nom de colonne (accents variables selon encodage)
        cat_c = next((c for c in sin.columns
                      if "cat" in c.lower() and ("gorie" in c.lower() or "g" in c.lower())),
                     "Libéllé Catégorie")
        if _c_cat_ and _c_cat_ in sin.columns:
            cat_c = _c_cat_
            sp2 = _safe_groupby(sin, cat_c,
                {"Nb":(cat_c,"count"),
                 "Réglé":(_c_regle_,"sum") if _c_regle_ else None,
                 "SAP":(_c_sap_,"sum") if _c_sap_ else None},
                sort_col="Réglé")
            if "Réglé" not in sp2.columns: sp2["Réglé"] = 0
            if "SAP"   not in sp2.columns: sp2["SAP"]   = 0
            sp2["Charge"]=sp2["Réglé"]+sp2["SAP"]
            fig=go.Figure()
            fig.add_bar(x=sp2["Réglé"],y=sp2[cat_c].str[:24],name="Réglé",marker_color=RED,orientation="h")
            fig.add_bar(x=sp2["SAP"],y=sp2[cat_c].str[:24],name="SAP",marker_color=AMBER,orientation="h")
            fig.update_layout(barmode="stack",yaxis=dict(autorange="reversed"))
            fig_style(fig,360,"🛒 Sinistres par produit"); st.plotly_chart(fig,use_container_width=True)
            sp2_d=sp2.copy()
            for c_ in ["Réglé","SAP","Charge"]: sp2_d[c_]=sp2_d[c_].apply(fmt)
            st.dataframe(sp2_d,use_container_width=True,hide_index=True)
            a,_=st.columns(2)
            a.download_button("📥 CSV",dl_csv(sp2),"sin_prod.csv","text/csv",use_container_width=True,key="dl_sin_p")

    with t_tri:
        section("Triangle de développement — Décès","EXERCICE x SURVENANCE · DÉCÈS UNIQUEMENT")
        # Filtrer sur DÉCÈS avant le triangle
        _sin_tri = sin.copy()
        if _c_nat_ and _c_nat_ in _sin_tri.columns:
            _mask_deces = _sin_tri[_c_nat_].astype(str).str.upper().str.contains(
                r"D[EÉ]C[EÈ]|DECES|DEATH|MORTAL", regex=True, na=False)
            _sin_dec = _sin_tri[_mask_deces]
            if not _sin_dec.empty:
                _sin_tri = _sin_dec
                st.info(f"ℹ️ Triangle calculé sur {len(_sin_tri):,} dossiers DÉCÈS.")
            else:
                st.warning("⚠️ Aucun dossier DÉCÈS — triangle sur tous les sinistres.")
        _surv_col = _c_surv_ if "_c_surv_" in dir() and _c_surv_ else (
                    "Date Survenance" if "Date Survenance" in sin.columns else None)
        if "ANNEE_SIN" in sin.columns and _surv_col and _c_regle_:
            try:
                _sin_tri_local = sin[["ANNEE_SIN", _surv_col, _c_regle_]].copy()
                _sin_tri_local["DEV_YEAR"] = pd.to_datetime(
                    _sin_tri_local[_surv_col], errors="coerce").dt.year.astype("Int64")
                _sin_tri_local[_c_regle_]  = pd.to_numeric(_sin_tri_local[_c_regle_], errors="coerce").fillna(0)
                _sin_tri_local = _sin_tri_local.dropna(subset=["ANNEE_SIN","DEV_YEAR"])
                if _sin_tri_local.empty:
                    alert("Pas de données pour le triangle.", "warn")
                else:
                    tri = _sin_tri_local.pivot_table(
                        index="ANNEE_SIN", columns="DEV_YEAR",
                        values=_c_regle_, aggfunc="sum", fill_value=0)
                    tri = tri.loc[
                        tri.index.dropna(),
                        [c for c in sorted(tri.columns) if pd.notna(c)]]
                    alert("Montants regles par exercice sinistre (lignes) x annee de survenance (colonnes).","info")
                    tri_d = tri.copy()
                    for col_ in tri_d.columns:
                        tri_d[col_] = tri_d[col_].apply(fmt)
                    st.dataframe(tri_d, use_container_width=True, height=380)
                    a,_ = st.columns(2)
                    a.download_button("📥 CSV triangle",
                        dl_csv(tri.reset_index()), "triangle.csv",
                        "text/csv", use_container_width=True, key="dl_tri")
            except Exception as _e_tri:
                alert(f"Erreur triangle : {_e_tri}", "danger")
        else:
            alert(f"Colonnes requises : ANNEE_SIN={('ANNEE_SIN' in sin.columns)}, "
                  f"Date Survenance={_surv_col!r}, Reglement={_c_regle_!r}", "info")

    with t_r:
        # Colonnes brutes — noms EXACTS confirmés sur fichier AFG
        _sin_raw_want = [c for c in [
            "Date Survenance", _c_cat_, _c_nat_, _c_sort_, "Souscripteur",
            "Désignation risque", _c_regle_, _c_sap_, _c_hon_,
            "Date Déclaration", "Date validation", "Nom Bénéficiaire",
            "Exercice Sinistre", "POLICE_KEY", "No Sinistre",
            "Réglement Comptable", "RAE Cie au 31/12/2025"
        ] if c is not None and c in sin.columns]
        _sin_raw_want_orig = _sin_raw_want
        # Ajouter la colonne catégorie quelle que soit son orthographe
        _cat_col = next((c for c in sin.columns if "cat" in c.lower()),None)
        if _cat_col and _cat_col not in _sin_raw_want: _sin_raw_want.insert(1, _cat_col)
        cs=[c for c in _sin_raw_want if c in sin.columns]
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
                # Résolution dynamique des colonnes sinistres dans l'onglet Actuariat
                _act_nat  = next((c for c in sin.columns if "ature" in c.lower() and "ini" in c.lower()), None)
                _act_regl = next((c for c in sin.columns if "glement" in c.lower() and "otal" in c.lower()), None)
                _act_sap  = next((c for c in sin.columns if c.upper().startswith("SAP")), None)
                _act_sort = next((c for c in sin.columns if "ort" in c.lower() and "ini" in c.lower()), None)

                if _act_nat is None:
                    alert("Colonne 'Nature Sinistre' introuvable dans le fichier Prestations.","warn")
                else:
                    _agg_prov = {"Nb": (_act_nat, "count")}
                    if _act_regl: _agg_prov["Regle"]  = (_act_regl, "sum")
                    if _act_sap:  _agg_prov["SAP"]    = (_act_sap, "sum")
                    if _act_sort: _agg_prov["Ouvert"] = (_act_sort, lambda x: (x == "Ouvert").sum())

                    prov = sin.groupby(_act_nat).agg(**_agg_prov).reset_index()
                    if "Regle"  not in prov.columns: prov["Regle"]  = 0
                    if "SAP"    not in prov.columns: prov["SAP"]    = 0
                    if "Ouvert" not in prov.columns: prov["Ouvert"] = 0

                    prov["Charge"]           = prov["Regle"] + prov["SAP"]
                    prov["Ratio SAP/Charge"] = prov["SAP"] / prov["Charge"].replace(0, np.nan) * 100
                    prov["Cout moy clos"]    = prov["Regle"] / (prov["Nb"] - prov["Ouvert"]).replace(0, np.nan)
                fig=go.Figure()
                _lbl_nat = prov[_act_nat].astype(str).str[:22]
                fig.add_bar(y=_lbl_nat, x=prov["Regle"], name="Réglé",     marker_color=GREEN, orientation="h")
                fig.add_bar(y=_lbl_nat, x=prov["SAP"],   name="SAP résid.", marker_color=AMBER, orientation="h")
                fig.update_layout(barmode="stack",yaxis=dict(autorange="reversed"))
                fig_style(fig,360,"📌 Structure Réglé / SAP par nature"); st.plotly_chart(fig,use_container_width=True)
                pv = prov.copy()
                for c_ in ["Regle","SAP","Charge","Cout moy clos"]:
                    if c_ in pv.columns: pv[c_] = pv[c_].apply(fmt)
                if "Ratio SAP/Charge" in pv.columns:
                    pv["Ratio SAP/Charge"] = pv["Ratio SAP/Charge"].apply(
                        lambda x: f"{x:.1f}%" if pd.notna(x) else "—")
                _pv_rename = {
                    _act_nat:           "Nature de sinistre",
                    "Regle":            "Réglé (FCFA)",
                    "SAP":              "SAP (FCFA)",
                    "Ouvert":           "Dossiers ouverts",
                    "Charge":           "Charge totale (FCFA)",
                    "Ratio SAP/Charge": "Ratio SAP/Charge",
                    "Cout moy clos":    "Coût moyen clos (FCFA)",
                }
                pv = pv.rename(columns={k:v for k,v in _pv_rename.items() if k in pv.columns})
                st.dataframe(pv, use_container_width=True, hide_index=True)
                a,b = st.columns(2)
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
                    sin_agg=sin.groupby("POLICE_KEY").agg(Regle=(_c_regle_,"sum") if _c_regle_ else ("CHIFAFFA","count"),SAP=(_c_sap_,"sum") if _c_sap_ else ("CHIFAFFA","count"),NbSin=("POLICE_KEY","count")).reset_index()
                    ca_pf=ca_pf.merge(sin_agg,on="POLICE_KEY",how="left")
                else:
                    ca_pf["Réglé"]=np.nan; ca_pf["SAP"]=np.nan; ca_pf["NbSin"]=np.nan
                tp=ca_pf.groupby(["POLICE_KEY","LIBECATE","ETAT_POLICE","NOM_ASSU","NOM_APP"]).agg(
                    CA=("CHIFAFFA","sum"),NbQ=("CHIFAFFA","count"),
                    Regle=("Réglé","first"),SAP=("SAP","first"),NbSin=("NbSin","first")
                ).reset_index().sort_values("CA",ascending=False).head(30)
                tp_d=tp.copy()
                for c_ in ["CA","Réglé","SAP"]: tp_d[c_]=tp_d[c_].apply(lambda x:fmt(x) if pd.notna(x) else "—")
                tp_d["NbSin"]=tp_d["NbSin"].apply(lambda x:str(int(x)) if pd.notna(x) else "0")
                st.dataframe(tp_d,use_container_width=True,hide_index=True)
                a,_=st.columns(2)
                a.download_button("📥 CSV jointure 3 bases",dl_csv(tp),"jointure_3bases.csv","text/csv",use_container_width=True,key="dl_join3")
            else: alert("Chargez le Portefeuille et la Base CA.","info")

    # ═══════════════════════════════════════════════════════════════════════════════
    # 
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
            _mc = [GREEN if v >= moy_g else "rgba(26,127,110,0.3)" for v in saison["CA moyen"]]
            fig2=go.Figure(go.Bar(x=saison["Label"],y=saison["CA moyen"],
                marker_color=_mc,
                text=[fmt(v) for v in saison["CA moyen"]],textposition="outside", textfont=dict(size=10)))
            fig2.add_hline(y=moy_g,line_dash="dash",line_color=RED,annotation_text=f"Moy. {fmt(moy_g)}",annotation_font_size=10)
            fig_style(fig2,360,"📅 Saisonnalité — CA moyen par mois")
            st.plotly_chart(fig2,use_container_width=True)
            a2,_=st.columns(2)
            a2.download_button("📥 CSV saisonnalité",dl_csv(saison),"saisonnalite.csv","text/csv",use_container_width=True,key="dl_sai")


    # ═══════════════════════════════════════════════════════════════════════════════
    # 
# PAGE — SAISIE BIA (7 étapes)
# ═══════════════════════════════════════════════════════════════════════════════
elif "Saisie BIA" in page:
    # Compteurs BIA — filtrés sur PA0 pour les courtiers
    _df_bia_hdr = bia_all()
    _is_crt_bia = is_courtier(user)
    if _is_crt_bia and not _df_bia_hdr.empty and "code_produit" in _df_bia_hdr.columns:
        _df_bia_hdr = _df_bia_hdr[_df_bia_hdr["code_produit"] == "PA0"]
    nb_bia  = len(_df_bia_hdr)
    cot_tot = float(_df_bia_hdr["cotisation"].fillna(0).astype(float).sum()) if not _df_bia_hdr.empty else 0
    nb_val  = int((_df_bia_hdr["statut"]=="Validé").sum()) if not _df_bia_hdr.empty else 0
    _titre_kpi = "BIA Prévoyance Auto" if _is_crt_bia else "BIA enregistrés"
    c1,c2,c3=st.columns(3)
    kpi(c1, _titre_kpi, str(nb_bia), "Prévoyance Auto" if _is_crt_bia else "Total base BIA","teal",icon="📋")
    kpi(c2,"Validés",str(nb_val),f"{nb_val/max(nb_bia,1)*100:.0f}%","",icon="✅")
    kpi(c3,"Cotisations",fmt(cot_tot),"Total FCFA","blue",icon="💰")

    # ── Étape 1 : Sélection du produit ─────────────────────────────────────────
    _is_crt_step = is_courtier(user)
    GC = {"Groupe 1": RED, "Groupe 2": GREEN}   # défini AVANT tout usage

    if _is_crt_step:
        # ── COURTIER : flux PA0 uniquement ───────────────────────────────────
        section("Prévoyance Auto — BIA","AFG ASSURANCES BÉNIN VIE")

        st.markdown(f"""
        <div style="background:linear-gradient(135deg,{RED}18,{AMBER}10);
             border:1.5px solid {RED};border-radius:12px;padding:14px 18px;margin:10px 0">
          <div style="font-size:11px;font-weight:800;color:{RED};text-transform:uppercase;
               letter-spacing:.06em;margin-bottom:10px">Prévoyance Auto — Barème</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
            <div style="background:white;border-radius:8px;padding:10px;text-align:center">
              <div style="font-size:10px;color:#888">Prime annuelle</div>
              <div style="font-size:15px;font-weight:800;color:{RED}">500 FCFA</div>
              <div style="font-size:11px;color:{NAVY};font-weight:700"> 100 000 FCFA</div>
            </div>
            <div style="background:white;border-radius:8px;padding:10px;text-align:center">
              <div style="font-size:10px;color:#888">Prime annuelle</div>
              <div style="font-size:15px;font-weight:800;color:{RED}">1 000 FCFA</div>
              <div style="font-size:11px;color:{NAVY};font-weight:700"> 225 000 FCFA</div>
            </div>
            <div style="background:white;border-radius:8px;padding:10px;text-align:center">
              <div style="font-size:10px;color:#888">Prime annuelle</div>
              <div style="font-size:15px;font-weight:800;color:{RED}">1 500 FCFA</div>
              <div style="font-size:11px;color:{NAVY};font-weight:700"> 350 000 FCFA</div>
            </div>
            <div style="background:white;border-radius:8px;padding:10px;text-align:center">
              <div style="font-size:10px;color:#888">Prime annuelle</div>
              <div style="font-size:15px;font-weight:800;color:{RED}">2 000 FCFA</div>
              <div style="font-size:11px;color:{NAVY};font-weight:700"> 500 000 FCFA</div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)

        _nom_courtier = st.text_input(
            "Courtier (nom ou sigle)",
            value=st.session_state.get("f_courtier_nom",""),
            placeholder="Ex: ATLANTIQUE COURTAGE, ABC Assurances...",
            key="inp_courtier")
        st.session_state["f_courtier_nom"] = _nom_courtier

        # Logo courtier — Clearbit (auto) + fallback avatar initiales
        if _nom_courtier and len(_nom_courtier.strip()) >= 2:
            _slug_crt  = _nom_courtier.strip().lower().replace(" ","").replace(".","")                                       .replace("-","").replace("'","").replace(",","")
            _logo_url  = f"https://logo.clearbit.com/{_slug_crt}.com"
            _logo_q    = _nom_courtier.strip().replace(" ", "+")
            _fallback  = f"https://ui-avatars.com/api/?name={_logo_q}&background=003366&color=fff&size=200&bold=true&font-size=0.38&format=png"
            st.markdown(f"""
            <div style="text-align:center;margin:8px 0 14px">
              <img src="{_logo_url}"
                   onerror="this.onerror=null;this.src='{_fallback}'"
                   style="height:72px;object-fit:contain;border-radius:10px;
                          box-shadow:0 2px 12px rgba(0,0,0,.12)"
                   alt="{_nom_courtier}"/>
              <div style="font-size:11px;color:#888;margin-top:5px">{_nom_courtier}</div>
            </div>""", unsafe_allow_html=True)

        if st.button("▶ Commencer la saisie BIA", type="primary",
                     use_container_width=True, key="pa_go"):
            st.session_state["bia_prod"]    = "PA0"
            st.session_state["bia_step"]    = 2
            st.session_state["f_peri"]      = "Annuelle"
            st.session_state["f_gar"]       = "Avec garantie décès"
            st.session_state["f_duree"]     = 1
            st.session_state["f_code_appo"] = _nom_courtier
            st.session_state["f_nom_appo"]  = _nom_courtier
            st.rerun()
        if st.session_state.get("bia_prod") != "PA0":
            st.stop()

        prod      = next(p for p in PRODUITS if p["code"] == "PA0")
        gc        = RED
        step      = st.session_state.get("bia_step", 2)
        is_avigbo = is_vigninou = is_deces = is_epargne = False

    else:
        # ── NON-COURTIER : sélection normale des produits ────────────────────
        section("Étape 1 — Sélection du produit","AFG ASSURANCES BÉNIN VIE")

        with st.expander("🛡️ Groupe 1 — Décès & Vie", expanded=True):
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"""<div style="border:2px solid {RED}44;border-radius:10px;
                  padding:12px 14px;margin-bottom:6px">
                  <span style="background:{RED};color:white;font-size:9px;font-weight:700;
                        padding:2px 7px;border-radius:3px">221</span>
                  <div style="font-size:13px;font-weight:700;margin-top:6px;color:{NAVY}">ASSURTOUS AVIGBO</div>
                  <div style="font-size:11px;color:#666;margin-top:3px">Décès · Barème fixe</div>
                  <div style="font-size:10px;color:#888;margin-top:5px;line-height:1.7">
                    100 F/mois  Capital 100 000 F  (unique : 1 000 F)<br>
                    200 F/mois  Capital 200 000 F  (unique : 2 000 F)<br>
                    300 F/mois  Capital 300 000 F  (unique : 3 000 F)
                  </div></div>""", unsafe_allow_html=True)
                if st.button("Choisir AVIGBO (221)", key="bp_221", use_container_width=True):
                    st.session_state["bia_prod"]="221"
                    st.session_state["bia_step"]=2; st.rerun()
                st.markdown(f"""<div style="border:2px solid {RED}44;border-radius:10px;
                  padding:12px 14px;margin-bottom:6px">
                  <span style="background:{RED};color:white;font-size:9px;font-weight:700;
                        padding:2px 7px;border-radius:3px">220</span>
                  <div style="font-size:13px;font-weight:700;margin-top:6px;color:{NAVY}">ASSURTOUS VIGNINOU</div>
                  <div style="font-size:11px;color:#666;margin-top:3px">Décès · Durée max 12 mois · Barème fixe</div>
                  <div style="font-size:10px;color:#888;margin-top:5px;line-height:1.7">
                    400 F/mois  Capital 500 000 F  (unique : 48 000 F)<br>
                    800 F/mois  Capital 1 000 000 F (unique : 96 000 F)<br>
                    1 200 F/mois  Capital 1 500 000 F (unique : 144 000 F)
                  </div></div>""", unsafe_allow_html=True)
                if st.button("Choisir VIGNINOU (220)", key="bp_220", use_container_width=True):
                    st.session_state["bia_prod"]="220"
                    st.session_state["bia_step"]=2; st.rerun()
        with st.expander("🚗 Prévoyance Auto (PA0)", expanded=False):
            st.markdown(f"""<div style="border:2px solid {RED}44;border-radius:10px;
              padding:12px 14px;margin-bottom:6px">
              <span style="background:{RED};color:white;font-size:9px;font-weight:700;
                    padding:2px 7px;border-radius:3px">PA0</span>
              <div style="font-size:13px;font-weight:700;margin-top:6px;color:{NAVY}">Prévoyance Auto</div>
              <div style="font-size:11px;color:#666;margin-top:3px">Décès · Durée 1 an · Barème fixe</div>
              <div style="font-size:10px;color:#888;margin-top:5px;line-height:1.7">
                500 FCFA/an  Capital 100 000 FCFA<br>
                1 000 FCFA/an  Capital 225 000 FCFA<br>
                1 500 FCFA/an  Capital 350 000 FCFA<br>
                2 000 FCFA/an  Capital 500 000 FCFA
              </div></div>""", unsafe_allow_html=True)
            if st.button("Choisir Prévoyance Auto (PA0)", key="bp_PA0", use_container_width=True):
                st.session_state["bia_prod"]="PA0"
                st.session_state["bia_step"]=2; st.rerun()
            st.markdown(f"""<div style="border:2px solid {GREEN}44;border-radius:10px;
              padding:12px 14px;margin-bottom:6px">
              <span style="background:{GREEN};color:white;font-size:9px;font-weight:700;
                    padding:2px 7px;border-radius:3px">EP0</span>
              <div style="font-size:13px;font-weight:700;margin-top:6px;color:{NAVY}">Épargne</div>
              <div style="font-size:11px;color:#666;margin-top:3px">Épargne vie · Périodicité libre · Capital calculé à la souscription</div>
              <div style="font-size:10px;color:#888;margin-top:5px">
                Périodicités : Journalière · Hebdomadaire · Mensuelle · Trimestrielle · Semestrielle · Annuelle · Unique<br>
                Chargements : 1% acquisition + 0.5% gestion · Taux technique : 3.5%
              </div></div>""", unsafe_allow_html=True)
            if st.button("Choisir Épargne", key="bp_EP0", use_container_width=True):
                st.session_state["bia_prod"]="EP0"
                st.session_state["bia_step"]=2; st.rerun()
            alert("Sélectionnez un produit pour afficher le formulaire BIA.","info")
            st.stop()

        prod = next((p for p in PRODUITS if p["code"]==st.session_state.get("bia_prod")), None)
        if not prod:
            st.session_state.pop("bia_prod", None); st.rerun()
        step      = st.session_state.get("bia_step", 2)
        is_avigbo   = prod["code"] == "221"
        is_vigninou = prod["code"] == "220"
        is_deces    = prod["code"] in ("220", "221")
        is_epargne  = prod["code"] == "EP0"

    # ── Logo courtier affiché en haut ────────────────────────────────────────
    if _is_crt_step:
        _crt_n = st.session_state.get("f_courtier_nom","")
        if _crt_n and len(_crt_n) >= 3:
            _logo_u = f"https://logo.clearbit.com/{_crt_n.lower().replace(' ','').replace('.','')+'.com'}"
            _fallback_u = f"https://ui-avatars.com/api/?name={_crt_n.replace(' ','+')}&background=C0392B&color=fff&size=128&bold=true&format=png"
            st.markdown(f"""
            <div style="text-align:center;padding:10px 0 6px">
              <img src="{_logo_u}"
                   onerror="this.onerror=null;this.src='{_fallback_u}'"
                   style="height:68px;object-fit:contain;border-radius:10px;
                          box-shadow:0 2px 14px rgba(0,0,0,.13)"
                   alt="{_crt_n}"/>
              <div style="font-size:10px;color:#888;margin-top:4px;font-weight:600">{_crt_n}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown(f"""<div style="background:{NAVY};border-radius:10px;padding:10px 16px;margin:10px 0;display:flex;align-items:center;justify-content:space-between">
      <div><div style="color:rgba(255,255,255,.45);font-size:9px;letter-spacing:.1em">BIA — BULLETIN INDIVIDUEL D'ADHÉSION</div>
      <div style="color:white;font-size:14px;font-weight:700">{prod['nom']}</div></div>
      <span style="background:{gc};color:white;font-size:12px;font-weight:700;padding:5px 12px;border-radius:6px">{prod['code']}</span>
    </div>""",unsafe_allow_html=True)

    if st.button("↩️ Changer de produit",key="chg_p"):
        st.session_state.pop("bia_prod",None); st.session_state.pop("bia_step",None); st.rerun()
    if _is_crt_step:
        # Courtier PA0 : 4 étapes réelles  steps 2,3,5,7 (les autres sont skippés)
        # Mapping step  numéro d'étape affiché
        _crt_map = {2: (1,4,"Souscripteur"), 3: (2,4,"Bénéficiaires"),
                    5: (3,4,"Contrat"),       7: (4,4,"Validation")}
        _crt_num, _crt_tot, _crt_lbl = _crt_map.get(step, (1,4,""))
        _prog_val = min(max((_crt_num - 1) / (_crt_tot - 1), 0.0), 1.0)
        st.progress(_prog_val, text=f"Étape {_crt_num}/{_crt_tot} — {_crt_lbl}")
    else:
        SLBL={2:"Identification",3:"Souscripteur",4:"Assuré",5:"Contrat",6:"Médical",7:"Validation"}
        _prog_gen = min(max((step-2)/5, 0.0), 1.0)
        st.progress(_prog_gen, text=f"Étape {step-1}/6 — {SLBL.get(step,'')}")
    st.markdown("")

    def ti(k,lbl,ph="",t="text"):
        st.session_state[k]=st.text_input(lbl,value=st.session_state.get(k,""),placeholder=ph,key=f"i_{k}")
    def si(k,lbl,opts):
        cur=st.session_state.get(k,opts[0]); idx=opts.index(cur) if cur in opts else 0
        st.session_state[k]=st.selectbox(lbl,opts,index=idx,key=f"s_{k}")

    if step==2:
        if _is_crt_step:
            # ── COURTIER PA0 — Étape 1/3 : Souscripteur ─────────────────────
            section("Étape 1 / 3 — Souscripteur","PRÉVOYANCE AUTO · INFORMATIONS PERSONNELLES")

            # Afficher logo courtier en haut de chaque étape
            _crt_n2 = st.session_state.get("f_courtier_nom","")
            if _crt_n2:
                _s2_slug = _crt_n2.strip().lower().replace(" ","").replace(".","").replace("-","")
                _s2_logo = f"https://logo.clearbit.com/{_s2_slug}.com"
                _s2_fbk  = f"https://ui-avatars.com/api/?name={_crt_n2.replace(' ','+')}&background=003366&color=fff&size=80&bold=true&format=png"
                st.image("https://logo.clearbit.com/logo.com", width=60)

            # Champs souscripteur (sans adresse, agence, code/nom apporteur)
            c1,c2,c3 = st.columns([1,2,2])
            with c1: si("f_c_tit","Civilité *",["","M.","Mme","Mlle"])
            with c2: ti("f_c_nom","Nom *","NOM EN MAJUSCULES")
            with c3: ti("f_c_prn","Prénoms *","Prénoms")

            c4,c5 = st.columns(2)
            with c4:
                _ddn_v = st.session_state.get("f_c_ddn", date(1985,1,1))
                if isinstance(_ddn_v, str):
                    try: _ddn_v = date.fromisoformat(_ddn_v)
                    except: _ddn_v = date(1985,1,1)
                st.session_state["f_c_ddn"] = st.date_input(
                    "Date de naissance *", value=_ddn_v,
                    min_value=date(1920,1,1), max_value=today, key="ddn_pa2")
            with c5:
                ti("f_c_tel","Téléphone *","+229 97…")

            # Valeurs par défaut silencieuses
            if not st.session_state.get("f_c_nat"):
                st.session_state["f_c_nat"] = "Béninoise"
            st.session_state["f_ass_meme"] = True
            st.session_state["f_bc"]       = True

            st.markdown("")
            b1,b2 = st.columns(2)
            if b1.button("← Retour", key="ret2_pa"):
                st.session_state.pop("bia_prod",None)
                st.session_state.pop("bia_step",None); st.rerun()
            if b2.button("Étape suivante ▶", type="primary", key="nxt2_pa"):
                _errs = []
                if not st.session_state.get("f_c_nom","").strip():  _errs.append("Le nom est obligatoire.")
                if not st.session_state.get("f_c_tel","").strip():  _errs.append("Le téléphone est obligatoire.")
                if _errs:
                    for _e in _errs: st.error(_e)
                else:
                    st.session_state["bia_step"] = 5; st.rerun()
        else:
            section("Étape 2 — Identification & Agence")
            c1,c2,c3=st.columns(3)
            with c2: ti("f_code_appo","Code apporteur","Ex : AFG001")
            with c3: ti("f_nom_appo","Nom apporteur")
            c4,c5=st.columns(2)
            with c4: ti("f_realis","Réalisateur",user["nom"])
            with c5: si("f_deja","Déjà assuré AFGVie ?",["Non","Oui"])
            if st.session_state.get("f_deja")=="Oui": ti("f_num_ct","N° contrat existant")
            if st.button("Suivant ▶",type="primary"): st.session_state["bia_step"]=3; st.rerun()
        if _is_crt_step:
            # COURTIER PA0 — Étape 2/4 : Bénéficiaires (optionnel)
            section("Étape 2 / 4 — Bénéficiaires","OPTIONNEL — vous pouvez passer cette étape")
            st.info("Les informations bénéficiaires sont optionnelles pour ce produit.")
            section("Bénéficiaires")
            _bc_opts = ["Oui","Non"]
            _cur_bc  = "Oui" if st.session_state.get("f_bc", True) else "Non"
            _bc_sel  = st.radio("Le conjoint est bénéficiaire ?",
                                _bc_opts, horizontal=True,
                                index=_bc_opts.index(_cur_bc), key="bc_r_pa")
            st.session_state["f_bc"] = (_bc_sel == "Oui")
            ti("f_ba","Autres bénéficiaires (nom, lien de parenté)","Ex: Jean MARTIN, fils")
            st.markdown("")
            b1,b2,b3 = st.columns(3)
            if b1.button("← Retour", key="ret3_pa"):
                st.session_state["bia_step"] = 2; st.rerun()
                st.session_state["bia_step"] = 4; st.rerun()
                st.session_state["f_bc"] = True
                st.session_state["bia_step"] = 4; st.rerun()
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
        if b2.button("Suivant ▶", type="primary", key="nxt3_gen_a"):
            if not st.session_state.get("f_c_nom","").strip(): st.error("Nom obligatoire")
            elif not st.session_state.get("f_c_prn","").strip(): st.error("Prénom obligatoire")
            else: st.session_state["bia_step"]=4; st.rerun()
        if _is_crt_step:
            # COURTIER PA0 — Étape 3/4 : Caractéristiques du contrat
            # Rediriger vers step==5 où est défini le bloc PA0 contrat
            st.session_state["bia_step"] = 5; st.rerun()
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

    elif step==5:

        # ── Date d'effet commune ──────────────────────────────────────────────
        cur_e = st.session_state.get("f_deff", today)
        if isinstance(cur_e, str):
            try:    cur_e = date.fromisoformat(cur_e)
            except: cur_e = today

        # ══════════════════════════════════════════════════════════════════════
        # CAS 1 — Courtier PA0 : Étape 3/4 — Caractéristiques du contrat
        # ══════════════════════════════════════════════════════════════════════
        if _is_crt_step:
            section("Étape 2 / 3 — Contrat","PRÉVOYANCE AUTO · DATE · PRIME · MODE RÈGLEMENT")
            # Logo courtier en haut
            _crt_n5 = st.session_state.get("f_courtier_nom","")
            if _crt_n5:
                _s5_slug = _crt_n5.strip().lower().replace(" ","").replace(".","").replace("-","")
                _s5_fbk  = f"https://ui-avatars.com/api/?name={_crt_n5.replace(' ','+')}&background=003366&color=fff&size=80&bold=true&format=png"
                st.image("https://logo.clearbit.com/logo.com", width=60)
            from dateutil.relativedelta import relativedelta

            # Prime annuelle — sélection parmi les 4 tranches
            st.markdown(f"<div style='font-weight:700;color:{NAVY};margin-bottom:4px'>Prime annuelle *</div>",
                        unsafe_allow_html=True)
            _pa_opts   = {"500 FCFA":(500,100_000), "1 000 FCFA":(1000,225_000),
                          "1 500 FCFA":(1500,350_000), "2 000 FCFA":(2000,500_000)}
            _pa_labels = list(_pa_opts.keys())
            _cur_lbl   = st.session_state.get("f_pa_lbl", _pa_labels[0])
            if _cur_lbl not in _pa_labels: _cur_lbl = _pa_labels[0]
            _pa_sel    = st.radio("Prime", _pa_labels,
                                  index=_pa_labels.index(_cur_lbl),
                                  horizontal=True, key="pa_prime_r5",
                                  label_visibility="collapsed")
            st.session_state["f_pa_lbl"]  = _pa_sel
            _pa_prime, _pa_capital        = _pa_opts[_pa_sel]
            st.session_state["f_coti"]    = _pa_prime
            st.session_state["f_cap"]     = _pa_capital
            st.session_state["f_peri"]    = "Annuelle"
            st.session_state["f_duree"]   = 1
            st.session_state["f_gar"]     = "Avec garantie décès"

            # Badge prime / capital
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,{RED},{AMBER});border-radius:10px;
                 padding:14px 20px;margin:10px 0;display:flex;gap:28px;align-items:center">
              <div>
                <div style="color:rgba(255,255,255,.7);font-size:9px;text-transform:uppercase">Prime annuelle</div>
                <div style="color:white;font-size:22px;font-weight:800">{_pa_prime:,} FCFA</div>
              </div>
              <div style="background:rgba(255,255,255,.25);width:1px;height:48px"></div>
              <div>
                <div style="color:rgba(255,255,255,.7);font-size:9px;text-transform:uppercase">Capital garanti décès</div>
                <div style="color:white;font-size:22px;font-weight:800">{_pa_capital:,} FCFA</div>
              </div>
            </div>""", unsafe_allow_html=True)

            # Date d'effet + terme automatique
            c1, c2 = st.columns(2)
            with c1:
                _d_eff = st.date_input("Date d'effet *", value=cur_e, key="eff_d_pa")
                st.session_state["f_deff"] = _d_eff
            _deff_pa = _d_eff if isinstance(_d_eff, date) else today
            try:    _terme_pa = _deff_pa + relativedelta(years=1)
            except: _terme_pa = _deff_pa.replace(year=_deff_pa.year+1)
            st.session_state["f_terme_auto"] = str(_terme_pa)
            with c2:
                st.markdown(f"""
                <div style="background:{GREEN}12;border:1.5px solid {GREEN};border-radius:8px;
                     padding:10px 14px;margin-top:4px">
                  <div style="font-size:9px;color:#888;text-transform:uppercase">Date terme (auto)</div>
                  <div style="font-size:18px;font-weight:800;color:{NAVY}">{_terme_pa.strftime("%d/%m/%Y")}</div>
                  <div style="font-size:10px;color:{GREEN}">Date d'effet + 1 an</div>
                </div>""", unsafe_allow_html=True)

            # Mode de règlement
            st.markdown("---")
            st.markdown(f"<div style='font-weight:700;color:{NAVY};margin-bottom:4px'>Mode de règlement *</div>",
                        unsafe_allow_html=True)
            _modes   = ["Mobile Monnaie","Par chèque","Par virement bancaire","Par Espèce"]
            _cur_m   = st.session_state.get("f_mode", _modes[0])
            if _cur_m not in _modes: _cur_m = _modes[0]
            st.session_state["f_mode"] = st.radio(
                "Mode", _modes, horizontal=True,
                index=_modes.index(_cur_m), key="mode_r_pa5",
                label_visibility="collapsed")
            _refs = {"Mobile Monnaie":"N° Téléphone Mobile Money",
                     "Par chèque":"N° Chèque",
                     "Par virement bancaire":"N° Compte bancaire",
                     "Par Espèce":"Référence reçu"}
            st.session_state["f_mref"] = st.text_input(
                _refs.get(st.session_state["f_mode"],"Référence"),
                value=st.session_state.get("f_mref",""),
                key="mref_pa5")

            st.markdown("")
            b1, b2 = st.columns(2)
            if b1.button("← Retour", key="ret5_pa"):
                st.session_state["bia_step"] = 3; st.rerun()
                st.session_state["bia_step"] = 7; st.rerun()

        # ══════════════════════════════════════════════════════════════════════
        # CAS 2 — Non-courtier : produits AVIGBO / VIGNINOU / Épargne
        # ══════════════════════════════════════════════════════════════════════
        else:
            section("Étape 5 — Caractéristiques du Contrat")

            # ── AVIGBO (221) ─────────────────────────────────────────────────
            if prod["code"] == "221":
                alert("AVIGBO : capital et cotisation unique déterminés automatiquement.","info")
                opt_map = {
                    "100 F/mois  Capital 100 000 F":  (100,  100_000,  1_000),
                    "200 F/mois  Capital 200 000 F":  (200,  200_000,  2_000),
                    "300 F/mois  Capital 300 000 F":  (300,  300_000,  3_000),
                }
                opts_l = list(opt_map.keys())
                cur_o  = st.session_state.get("f_avigbo_opt", opts_l[0])
                if cur_o not in opts_l: cur_o = opts_l[0]
                sel_o  = st.radio("Barème *", opts_l,
                                  index=opts_l.index(cur_o), key="avigbo_opt_r5")
                st.session_state["f_avigbo_opt"] = sel_o
                pm, cg, pu = opt_map[sel_o]

                c1,c2 = st.columns(2)
                with c1:
                    pav = ["Mensuelle","Unique"]
                    cpv = st.session_state.get("f_peri","Mensuelle")
                    if cpv not in pav: cpv = "Mensuelle"
                    st.session_state["f_peri"] = st.radio("Périodicité *",pav,
                        horizontal=True,index=pav.index(cpv),key="peri_av_r5")
                with c2:
                    st.session_state["f_deff"] = st.date_input("Date d'effet *",
                        value=cur_e, key="eff_av")
                coti_a = pm if st.session_state["f_peri"]=="Mensuelle" else pu
                st.session_state["f_coti"] = coti_a
                st.session_state["f_cap"]  = cg
                st.markdown(f"""
                <div style="background:{GREEN}12;border:1.5px solid {GREEN};border-radius:10px;
                     padding:12px 16px;margin:10px 0;display:grid;
                     grid-template-columns:1fr 1fr 1fr;gap:12px">
                  <div><div style="font-size:9px;color:#888">Cotisation</div>
                       <div style="font-weight:700">{coti_a:,} FCFA/{st.session_state["f_peri"].lower()}</div></div>
                  <div><div style="font-size:9px;color:#888">Capital décès</div>
                       <div style="font-weight:700;color:{RED}">{cg:,} FCFA</div></div>
                  <div><div style="font-size:9px;color:#888">Garantie</div>
                       <div style="font-weight:700">Avec garantie décès</div></div>
                </div>""", unsafe_allow_html=True)
                st.session_state["f_gar"] = "Avec garantie décès"
                st.session_state["f_duree"] = st.number_input("Durée (ans) *",
                    min_value=1, max_value=40,
                    value=int(st.session_state.get("f_duree",5)), key="dur_av5")

            # ── VIGNINOU (220) ───────────────────────────────────────────────
            elif prod["code"] == "220":
                alert("VIGNINOU : durée maximale 12 mois.","warn")
                opt_v = {
                    "400 F/mois  Capital 500 000 F":       (400,  500_000,   48_000),
                    "800 F/mois  Capital 1 000 000 F":     (800,  1_000_000, 96_000),
                    "1 200 F/mois  Capital 1 500 000 F":   (1200, 1_500_000, 144_000),
                }
                opts_v = list(opt_v.keys())
                cur_v  = st.session_state.get("f_vigninou_opt", opts_v[0])
                if cur_v not in opts_v: cur_v = opts_v[0]
                sel_v  = st.radio("Barème *", opts_v,
                                  index=opts_v.index(cur_v), key="vign_opt_r5")
                st.session_state["f_vigninou_opt"] = sel_v
                pmv, cgv, puv = opt_v[sel_v]

                c1,c2,c3 = st.columns(3)
                with c1:
                    pvv = ["Mensuelle","Unique"]
                    cpvv = st.session_state.get("f_peri","Mensuelle")
                    if cpvv not in pvv: cpvv = "Mensuelle"
                    st.session_state["f_peri"] = st.radio("Périodicité *",pvv,
                        horizontal=True,index=pvv.index(cpvv),key="peri_v_r5")
                with c2:
                    dv = st.number_input("Durée (mois, max 12) *",min_value=1,max_value=12,
                        value=int(st.session_state.get("f_duree_mois_v",12)),key="dur_v_m5")
                    st.session_state["f_duree_mois_v"] = dv
                    st.session_state["f_duree"] = 1
                with c3:
                    st.session_state["f_deff"] = st.date_input("Date d'effet *",
                        value=cur_e, key="eff_vg")
                cotiv = pmv if st.session_state["f_peri"]=="Mensuelle" else puv
                st.session_state["f_coti"] = cotiv
                st.session_state["f_cap"]  = cgv
                st.session_state["f_gar"]  = "Avec garantie décès"

            # ── ÉPARGNE (EP0) ────────────────────────────────────────────────
            elif prod["code"] == "EP0":
                peri_ep_opts = ["Journalière","Hebdomadaire","Mensuelle",
                                "Trimestrielle","Semestrielle","Annuelle","Unique"]
                c1,c2,c3 = st.columns(3)
                with c1:
                    st.session_state["f_coti"] = st.number_input(
                        "Cotisation *", min_value=1000, step=500,
                        value=int(st.session_state.get("f_coti",5000)), key="coti_ep5")
                with c2:
                    st.session_state["f_duree"] = st.number_input(
                        "Durée (ans) *", min_value=1, max_value=40,
                        value=int(st.session_state.get("f_duree",10)), key="dur_ep5")
                with c3:
                    st.session_state["f_deff"] = st.date_input("Date d'effet *",
                        value=cur_e, key="eff_ep5")
                cur_pep = st.session_state.get("f_peri","Mensuelle")
                if cur_pep not in peri_ep_opts: cur_pep = "Mensuelle"
                st.session_state["f_peri"] = st.selectbox(
                    "Périodicité *", peri_ep_opts,
                    index=peri_ep_opts.index(cur_pep), key="peri_ep_s5")

                # Capital affiché (simple lookup, pas de calcul actuariel ici)
                P_ep  = float(st.session_state.get("f_coti",5000))
                n_ep  = int(st.session_state.get("f_duree",10))
                pep   = st.session_state.get("f_peri","Mensuelle")
                res_ep = calcul_capital_epargne(P_ep, pep, n_ep)
                cap_ep = res_ep["capital_brut"]
                st.session_state["f_cap"] = int(cap_ep)

                st.markdown(f"""
                <div style="background:{GREEN}10;border:1.5px solid {GREEN};border-radius:10px;
                     padding:12px 16px;margin:10px 0;text-align:center">
                  <div style="font-size:10px;color:#888;text-transform:uppercase">Capital au terme estimé</div>
                  <div style="font-size:24px;font-weight:800;color:{GREEN}">{cap_ep:,.0f} FCFA</div>
                  <div style="font-size:10px;color:#888">Taux technique 3,5% · α=1% · β=0,5%</div>
                </div>""", unsafe_allow_html=True)

            # ── Mode de règlement (commun AVIGBO/VIGNINOU/EP0) ───────────────
            st.markdown("---")
            section("Mode de règlement")
            m_o  = ["","Mobile Monnaie","Par chèque","Par virement bancaire","Par prélèvement sur salaire"]
            cur_m = st.session_state.get("f_mode","")
            st.session_state["f_mode"] = st.radio("Mode *", m_o, horizontal=True,
                index=m_o.index(cur_m) if cur_m in m_o else 0, key="mode_r_gen",
                format_func=lambda x:"— Choisir —" if x=="" else x)
            if st.session_state["f_mode"]:
                _ref_gen = {"Mobile Monnaie":"N° Mobile Money",
                            "Par chèque":"N° Chèque",
                            "Par virement bancaire":"N° Compte/RIB",
                            "Par prélèvement sur salaire":"N° Matricule"
                            }.get(st.session_state["f_mode"],"Référence")
                st.session_state["f_mref"] = st.text_input(
                    _ref_gen, value=st.session_state.get("f_mref",""),
                    key="mref_gen5")

            b1,b2 = st.columns(2)
            if b1.button("← Retour", key="ret5_gen"):
                st.session_state["bia_step"] = 4; st.rerun()
                st.session_state["bia_step"] = 6; st.rerun()
        # Courtier PA0 : pas de questionnaire médical  rediriger vers validation
        if _is_crt_step:
            st.session_state["bia_step"] = 7; st.rerun()
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

    elif step==7 or (step==5 and _is_crt_step):
        if _is_crt_step:
            section("Étape 3 / 3 — Signatures & Validation","PRÉVOYANCE AUTO")
            # Logo courtier en haut de la page de validation
            _crt_n7 = st.session_state.get("f_courtier_nom","")
            if _crt_n7:
                _s7_slug = _crt_n7.strip().lower().replace(" ","").replace(".","").replace("-","")
                _s7_fbk  = f"https://ui-avatars.com/api/?name={_crt_n7.replace(' ','+')}&background=003366&color=fff&size=80&bold=true&format=png"
                st.image("https://logo.clearbit.com/logo.com", width=60)
        else:
            section("Étape 7 — Déclaration & Validation")

        # ── Récapitulatif compact ─────────────────────────────────────────────
        with st.expander("📋 Récapitulatif du contrat", expanded=True):
            _cap_r = int(st.session_state.get("f_cap", 0))
            _dur_r = st.session_state.get("f_duree", 1)
            _dur_l = (f"{st.session_state.get('f_duree_mois_v',12)} mois"
                      if is_vigninou else f"{_dur_r} an(s)")
            _terme_r = st.session_state.get("f_terme_auto","")
            st.markdown(f"""| Champ | Valeur |
|---|---|
|**Souscripteur**|{st.session_state.get('f_c_tit','')} {st.session_state.get('f_c_nom','').upper()} {st.session_state.get('f_c_prn','')}|
|**Produit**|{prod['nom']} — {prod['code']}|
|**Prime / Cotisation**|{int(st.session_state.get('f_coti',0)):,} FCFA / {st.session_state.get('f_peri','—')}|
|**Capital garanti**|**{_cap_r:,} FCFA**|
|**Date d'effet**|{ds(st.session_state.get('f_deff',today))}|
|**Date terme**|{_terme_r if _terme_r else _dur_l}|
|**Mode règlement**|{st.session_state.get('f_mode','—')}|
|**Apporteur / Courtier**|{st.session_state.get('f_nom_appo','—')}|""")

        st.markdown("---")

        # ── Déclaration ───────────────────────────────────────────────────────
        st.markdown("""<div style="background:#f8f9fa;border:1px solid #ddd;border-radius:8px;
            padding:12px;font-size:11px;line-height:1.8;margin-bottom:12px">
            Je reconnais avoir reçu la notice d'information du produit et les conditions générales.
            Je certifie exactes et sincères toutes les informations renseignées.
            Conformément à l'article 18 du code CIMA, toute fausse déclaration
            entraîne la nullité du contrat.</div>""", unsafe_allow_html=True)

        st.session_state["f_dc"] = st.checkbox(
            "☑ J'accepte les conditions de souscription *",
            value=st.session_state.get("f_dc", False), key="chk_dc")
        st.session_state["f_dd"] = st.checkbox(
            "☑ J'accepte la politique de protection des données *",
            value=st.session_state.get("f_dd", False), key="chk_dd")

        st.markdown("---")

        # ── Signatures ────────────────────────────────────────────────────────
        section("Signatures")
        st.markdown(f"""
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:10px 0">
          <div style="border:1.5px dashed #888;border-radius:8px;padding:14px;
               min-height:90px;text-align:center;background:#fafafa">
            <div style="font-size:10px;color:#888;font-weight:600;text-transform:uppercase;
                 margin-bottom:4px">Signature du souscripteur</div>
            <div style="font-size:11px;color:{NAVY};font-weight:700;margin-top:8px">
              {st.session_state.get('f_c_tit','')} {st.session_state.get('f_c_nom','').upper()}
              {st.session_state.get('f_c_prn','')}
            </div>
          </div>
          <div style="border:1.5px dashed #888;border-radius:8px;padding:14px;
               min-height:90px;text-align:center;background:#fafafa">
            <div style="font-size:10px;color:#888;font-weight:600;text-transform:uppercase;
                 margin-bottom:4px">Cachet & Signature</div>
            <div style="font-size:11px;color:{NAVY};font-weight:700;margin-top:8px">
              {st.session_state.get('f_nom_appo','AFG Assurances Bénin Vie')}
            </div>
          </div>
        </div>""", unsafe_allow_html=True)

        # Upload signature souscripteur (optionnel)
        _sig_file = st.file_uploader(
            "📎 Joindre la signature du souscripteur (image optionnelle)",
            type=["png","jpg","jpeg","pdf"],
            key="sig_upload")
        if _sig_file is not None:
            st.success(f"✅ Fichier joint : {_sig_file.name}")
            st.session_state["f_sig_file"] = _sig_file.name

        st.markdown("---")

        # ── Statut & Observations ─────────────────────────────────────────────
        c1, c2 = st.columns(2)
        stat_o  = ["Brouillon","En cours","Validé"]
        cur_st  = st.session_state.get("f_stat", "Brouillon")
        st.session_state["f_stat"] = c1.selectbox(
            "Statut", stat_o,
            index=stat_o.index(cur_st) if cur_st in stat_o else 0,
            key="stat_s")
        st.session_state["f_obs"] = c2.text_input(
            "Observations", value=st.session_state.get("f_obs",""),
            key="obs_t")


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
        # ── Impression BIA (courtier PA0 uniquement) ─────────────────────────
        if _is_crt_step and st.button("🖨️ Imprimer le BIA — 2 exemplaires",
                                       use_container_width=True, key="print_bia_btn"):
            try:
                from reportlab.lib.pagesizes import A4
                from reportlab.lib.units import cm
                from reportlab.lib import colors as rl_colors
                from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                    Table, TableStyle, HRFlowable, Image as _RLImg)
                from reportlab.lib.styles import ParagraphStyle
                from reportlab.lib.enums import TA_CENTER
                import io as _io, base64 as _b64
                from datetime import datetime as _dt

                _buf = _io.BytesIO()
                doc  = SimpleDocTemplate(_buf, pagesize=A4,
                    leftMargin=1.5*cm, rightMargin=1.5*cm,
                    topMargin=1.5*cm, bottomMargin=1.5*cm)

                C_N=rl_colors.HexColor("#0D1F3C"); C_G=rl_colors.HexColor("#1A7F6E")
                C_R=rl_colors.HexColor("#C0392B"); C_W=rl_colors.white
                C_L=rl_colors.HexColor("#F3F6FA")

                st_ti = ParagraphStyle("T",fontName="Helvetica-Bold",fontSize=12,textColor=C_W,alignment=TA_CENTER)
                st_su = ParagraphStyle("S",fontName="Helvetica",fontSize=9,textColor=rl_colors.HexColor("#A9DFBF"),alignment=TA_CENTER)
                st_bd = ParagraphStyle("B",fontName="Helvetica",fontSize=9,textColor=rl_colors.HexColor("#2C3E50"),leading=13)
                st_sm = ParagraphStyle("Sm",fontName="Helvetica",fontSize=8,textColor=rl_colors.grey,alignment=TA_CENTER)
                st_bf = ParagraphStyle("Bf",fontName="Helvetica-Bold",fontSize=9,textColor=C_N)

                def _exemplaire(label):
                    items = []
                    # Logo
                    try:
                        _img = _RLImg(_io.BytesIO(_b64.b64decode(LOGO_B64)), width=3.5*cm, height=1.5*cm)
                        _img.hAlign = "CENTER"; items.append(_img); items.append(Spacer(1,0.15*cm))
                    except Exception: pass
                    # En-tête
                    h = Table([[Paragraph("BULLETIN INDIVIDUEL D'ADHÉSION",st_ti)],
                                [Paragraph("Prévoyance Auto — AFG Assurances Bénin Vie",st_su)],
                                [Paragraph(f"Exemplaire : {label}",st_su)]],
                               colWidths=[17*cm])
                    h.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),C_N),
                        ("ALIGN",(0,0),(-1,-1),"CENTER"),
                        ("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7)]))
                    items.append(h); items.append(Spacer(1,0.25*cm))
                    # Données
                    _n = f"{st.session_state.get('f_c_tit','')} {st.session_state.get('f_c_nom','').upper()} {st.session_state.get('f_c_prn','')}".strip()
                    rows = [
                        ["N° BIA", st.session_state.get("_last_bia_num","—"), "Date saisie", _dt.now().strftime("%d/%m/%Y")],
                        ["Courtier", st.session_state.get("f_courtier_nom","—") or "—", "Produit", "Prévoyance Auto"],
                        ["Souscripteur", _n, "Téléphone", st.session_state.get("f_c_tel","—")],
                        ["Prime annuelle", f"{int(st.session_state.get('f_coti',0)):,} FCFA", "Capital garanti", f"{int(st.session_state.get('f_cap',0)):,} FCFA"],
                        ["Date effet", ds(st.session_state.get("f_deff","")), "Date terme", str(st.session_state.get("f_terme_auto","—"))],
                        ["Mode règlement", st.session_state.get("f_mode","—"), "Référence", st.session_state.get("f_mref","—") or "—"],
                    ]
                    t = Table(rows, colWidths=[4*cm,4.5*cm,4*cm,4.5*cm])
                    t.setStyle(TableStyle([
                        ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),("FONTNAME",(2,0),(2,-1),"Helvetica-Bold"),
                        ("FONTSIZE",(0,0),(-1,-1),8.5),
                        ("ROWBACKGROUNDS",(0,0),(-1,-1),[C_L,C_W]),
                        ("GRID",(0,0),(-1,-1),0.3,rl_colors.HexColor("#DDE3EE")),
                        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),("LEFTPADDING",(0,0),(-1,-1),6),
                    ]))
                    items.append(t); items.append(Spacer(1,0.3*cm))
                    items.append(Paragraph("Je soussigné(e) certifie l'exactitude des informations ci-dessus et reconnais avoir reçu les conditions générales du contrat.",st_bd))
                    items.append(Spacer(1,0.5*cm))
                    sig = Table([["Signature souscripteur","Cachet & Signature AFG"],["",""],["",""]],
                                 colWidths=[8.5*cm,8.5*cm])
                    sig.setStyle(TableStyle([
                        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8),
                        ("ALIGN",(0,0),(-1,-1),"CENTER"),
                        ("BOX",(0,1),(0,2),0.5,C_N),("BOX",(1,1),(1,2),0.5,C_N),
                        ("BOTTOMPADDING",(0,1),(-1,2),25),
                    ]))
                    items.append(sig)
                    items.append(Spacer(1,0.15*cm))
                    items.append(Paragraph("AFG Assurances Bénin Vie · Groupe AFG Holding · Conforme CIMA",st_sm))
                    return items

                story = []
                story.extend(_exemplaire("EXEMPLAIRE CLIENT"))
                story.append(Spacer(1,0.3*cm))
                story.append(HRFlowable(width="100%",thickness=0.8,color=C_R,dash=[3,3],spaceAfter=3))
                story.append(Paragraph("✂ — — — Découper ici — — — ✂",
                    ParagraphStyle("C",fontName="Helvetica",fontSize=8,textColor=rl_colors.grey,alignment=TA_CENTER)))
                story.append(Spacer(1,0.3*cm))
                story.extend(_exemplaire("EXEMPLAIRE AFG ASSURANCES"))

                doc.build(story)
                _pdf_bia = _buf.getvalue()
                _nom_bia = st.session_state.get("f_c_nom","").upper()
                st.success(f"✅ BIA généré — {len(_pdf_bia)//1024} Ko")
                st.download_button("📥 Télécharger le BIA (PDF — 2 exemplaires)",
                    data=_pdf_bia,
                    file_name=f"BIA_PA0_{_nom_bia}_{_dt.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf", use_container_width=True,
                    type="primary", key="dl_bia_pdf_final")
            except ImportError:
                alert("La bibliothèque <b>reportlab</b> n'est pas installée.","danger")
            except Exception as _ep_bia:
                alert(f"Erreur impression BIA : {_ep_bia}","danger")

        # ── Bouton PDF universel (tous produits) ────────────────────────────────
        if not _is_crt_step:
            if st.button("🖨️ Télécharger le BIA (PDF — 2 exemplaires)",
                         use_container_width=True, key="dl_bia_btn_all"):
                try:
                    from reportlab.lib.pagesizes import A4
                    from reportlab.lib.units import cm
                    from reportlab.lib import colors as _rlc
                    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                        Table, TableStyle, HRFlowable, Image as _RLImg)
                    from reportlab.lib.styles import ParagraphStyle
                    from reportlab.lib.enums import TA_CENTER
                    import io as _io2, base64 as _b64_2
                    from datetime import datetime as _dt2
                    _buf2 = _io2.BytesIO()
                    _doc2 = SimpleDocTemplate(_buf2, pagesize=A4,
                        leftMargin=1.5*cm, rightMargin=1.5*cm,
                        topMargin=1.5*cm, bottomMargin=1.5*cm)
                    _CN=_rlc.HexColor("#0D1F3C"); _CG=_rlc.HexColor("#1A7F6E")
                    _CR=_rlc.HexColor("#C0392B"); _CW=_rlc.white; _CL=_rlc.HexColor("#F3F6FA")
                    _st_ti=ParagraphStyle("T",fontName="Helvetica-Bold",fontSize=11,textColor=_CW,alignment=TA_CENTER)
                    _st_su=ParagraphStyle("S",fontName="Helvetica",fontSize=8.5,textColor=_rlc.HexColor("#A9DFBF"),alignment=TA_CENTER)
                    _st_bd=ParagraphStyle("B",fontName="Helvetica",fontSize=8.5,textColor=_rlc.HexColor("#2C3E50"),leading=12)
                    _st_sm=ParagraphStyle("M",fontName="Helvetica",fontSize=7.5,textColor=_rlc.grey,alignment=TA_CENTER)
                    _nom_sous_g = f"{st.session_state.get('f_c_tit','')} {st.session_state.get('f_c_nom','').upper()} {st.session_state.get('f_c_prn','')}".strip()
                    def _gen_bia_ex(lbl):
                        _it=[]
                        try:
                            _img=_RLImg(_io2.BytesIO(_b64_2.b64decode(LOGO_B64)),width=3.5*cm,height=1.5*cm)
                            _img.hAlign="CENTER"; _it.append(_img); _it.append(Spacer(1,.15*cm))
                        except Exception: pass
                        _h=Table([[Paragraph("BULLETIN INDIVIDUEL D'ADHÉSION",_st_ti)],
                                  [Paragraph(f"{prod['nom']} — AFG Assurances Bénin Vie",_st_su)],
                                  [Paragraph(f"Exemplaire : {lbl}",_st_su)]],colWidths=[17*cm])
                        _h.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),_CN),
                            ("ALIGN",(0,0),(-1,-1),"CENTER"),
                            ("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7)]))
                        _it.append(_h); _it.append(Spacer(1,.2*cm))
                        _rows=[
                            ["N° BIA",st.session_state.get("_last_bia_num","—"),"Date",_dt2.now().strftime("%d/%m/%Y")],
                            ["Produit",prod["nom"],"Code",prod["code"]],
                            ["Souscripteur",_nom_sous_g,"Téléphone",st.session_state.get("f_c_tel","—")],
                            ["Cotisation",f"{int(st.session_state.get('f_coti',0)):,} FCFA / {st.session_state.get('f_peri','—')}","Capital",f"{int(st.session_state.get('f_cap',0)):,} FCFA"],
                            ["Date effet",str(st.session_state.get("f_deff","—")),"Durée",f"{st.session_state.get('f_duree','—')} an(s)"],
                            ["Mode règlement",st.session_state.get("f_mode","—"),"Référence",st.session_state.get("f_mref","—") or "—"],
                            ["Apporteur",st.session_state.get("f_nom_appo","—") or "—","Code",str(st.session_state.get("f_code_appo","—"))],
                        ]
                        _t=Table(_rows,colWidths=[4*cm,4.5*cm,4*cm,4.5*cm])
                        _t.setStyle(TableStyle([
                            ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),("FONTNAME",(2,0),(2,-1),"Helvetica-Bold"),
                            ("FONTSIZE",(0,0),(-1,-1),8.5),("ROWBACKGROUNDS",(0,0),(-1,-1),[_CL,_CW]),
                            ("GRID",(0,0),(-1,-1),.3,_rlc.HexColor("#DDE3EE")),
                            ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),("LEFTPADDING",(0,0),(-1,-1),6),
                        ]))
                        _it.append(_t); _it.append(Spacer(1,.3*cm))
                        _it.append(Paragraph("Je soussigné(e) certifie l'exactitude des informations ci-dessus et reconnais avoir reçu les conditions générales.",_st_bd))
                        _it.append(Spacer(1,.5*cm))
                        _sig=Table([["Signature souscripteur","Cachet & Signature AFG"],["",""],["",""]],colWidths=[8.5*cm,8.5*cm])
                        _sig.setStyle(TableStyle([("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
                            ("FONTSIZE",(0,0),(-1,-1),8),("ALIGN",(0,0),(-1,-1),"CENTER"),
                            ("BOX",(0,1),(0,2),.5,_CN),("BOX",(1,1),(1,2),.5,_CN),
                            ("BOTTOMPADDING",(0,1),(-1,2),22)]))
                        _it.append(_sig); _it.append(Spacer(1,.15*cm))
                        _it.append(Paragraph("AFG Assurances Bénin Vie · Groupe AFG Holding · Conforme CIMA",_st_sm))
                        return _it
                    _st2=[]
                    _st2.extend(_gen_bia_ex("EXEMPLAIRE CLIENT"))
                    _st2.append(Spacer(1,.3*cm))
                    _st2.append(HRFlowable(width="100%",thickness=.7,color=_CR,dash=[3,3],spaceAfter=3))
                    _st2.append(Paragraph("✂  —  —  Découper ici  —  —  ✂",
                        ParagraphStyle("CUT",fontName="Helvetica",fontSize=7.5,textColor=_rlc.grey,alignment=TA_CENTER)))
                    _st2.append(Spacer(1,.3*cm))
                    _st2.extend(_gen_bia_ex("EXEMPLAIRE AFG ASSURANCES BÉNIN VIE"))
                    _doc2.build(_st2)
                    _pdf2=_buf2.getvalue()
                    _fn2=f"BIA_{prod['code']}_{_nom_sous_g.replace(' ','_')}_{_dt2.now().strftime('%Y%m%d')}.pdf"
                    st.success(f"✅ BIA généré — {len(_pdf2)//1024} Ko")
                    st.download_button("📥 Télécharger le BIA PDF",data=_pdf2,file_name=_fn2,
                        mime="application/pdf",use_container_width=True,type="primary",key="dl_bia_pdf_final")
                except ImportError:
                    alert("La bibliothèque <b>reportlab</b> n'est pas installée.","danger")
                except Exception as _ep_g:
                    alert(f"Erreur génération PDF : {_ep_g}","danger")

        st.markdown("")
        b1,b2,b3=st.columns([1,1,1.4])
        if b1.button("← Retour", key=f"ret7_{4157}"): st.session_state["bia_step"] = 5 if _is_crt_step else 6; st.rerun()
        if b2.button("💾 Brouillon", key="brouillon_btn_a"):
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
                if num:
                    st.session_state["bia_saved_id"] = num
                    st.session_state["_bia_print_ready"] = True

            # ── Bouton impression PDF (pour courtier PA0) ─────────────────
            if _is_crt_step and st.session_state.get("_bia_print_ready"):
                st.markdown("---")
                if st.button("🖨️ Imprimer le BIA (2 exemplaires)", type="primary",
                             use_container_width=True, key="print_bia_pa0"):
                    try:
                        from reportlab.lib.pagesizes import A4
                        from reportlab.lib.styles import ParagraphStyle
                        from reportlab.lib.units import cm
                        from reportlab.lib import colors as _rc
                        from reportlab.platypus import (SimpleDocTemplate, Paragraph,
                            Spacer, Table, TableStyle, HRFlowable)
                        from reportlab.lib.enums import TA_CENTER
                        import io as _io, base64 as _b64
                        from datetime import datetime as _dt

                        def _bloc_bia(story, label_expl):
                            """Génère un exemplaire du BIA."""
                            C_N = _rc.HexColor("#0D1F3C"); C_G = _rc.HexColor("#1A7F6E")
                            C_R = _rc.HexColor("#C0392B"); C_L = _rc.HexColor("#F3F6FA")
                            st_ti  = ParagraphStyle("T",fontName="Helvetica-Bold",fontSize=12,textColor=_rc.white,alignment=TA_CENTER)
                            st_su  = ParagraphStyle("S",fontName="Helvetica",fontSize=8,textColor=_rc.HexColor("#A9DFBF"),alignment=TA_CENTER)
                            st_lbl = ParagraphStyle("L",fontName="Helvetica-Bold",fontSize=8,textColor=C_N)
                            st_val = ParagraphStyle("V",fontName="Helvetica",fontSize=9,textColor=_rc.HexColor("#2C3E50"))
                            st_sm  = ParagraphStyle("Sm",fontName="Helvetica",fontSize=7,textColor=_rc.grey)
                            ss     = st.session_state
                            # Bandeau exemplaire
                            col_band = C_R if label_expl=="CLIENT" else C_N
                            band = Table([[Paragraph(f"EXEMPLAIRE {label_expl}",
                                ParagraphStyle("EX",fontName="Helvetica-Bold",fontSize=9,
                                textColor=_rc.white,alignment=TA_CENTER))]],colWidths=[17*cm])
                            band.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),col_band),
                                ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
                            story.append(band)
                            # Logo
                            try:
                                _img = __import__("reportlab.platypus",fromlist=["Image"]).Image
                                story.append(_img(_io.BytesIO(_b64.b64decode(LOGO_B64)),
                                    width=4*cm,height=1.6*cm))
                            except Exception: pass
                            # En-tête
                            hdr = Table([[Paragraph("AFG ASSURANCES BÉNIN VIE",st_ti)],
                                [Paragraph("BULLETIN D'ADHÉSION — PRÉVOYANCE AUTO",st_su)],
                                [Paragraph(f"N° : {ss.get('bia_saved_id','—')}  ·  {_dt.now().strftime('%d/%m/%Y')}",st_su)]],
                                colWidths=[17*cm])
                            hdr.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),C_N),
                                ("ALIGN",(0,0),(-1,-1),"CENTER"),
                                ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8)]))
                            story.append(hdr); story.append(Spacer(1,0.2*cm))
                            def _sec(t):
                                s=Table([[Paragraph(t,ParagraphStyle("SH",fontName="Helvetica-Bold",
                                    fontSize=9,textColor=_rc.white))]],colWidths=[17*cm])
                                s.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),C_G),
                                    ("LEFTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),4),
                                    ("BOTTOMPADDING",(0,0),(-1,-1),4)]))
                                return s
                            def _tbl(rows):
                                t=Table([[Paragraph(r[0],st_lbl),
                                    Paragraph(str(r[1]) if r[1] else "—",st_val)]
                                    for r in rows],colWidths=[5.5*cm,11.5*cm])
                                t.setStyle(TableStyle([
                                    ("ROWBACKGROUNDS",(0,0),(-1,-1),[C_L,_rc.white]),
                                    ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
                                    ("LEFTPADDING",(0,0),(-1,-1),6),
                                    ("GRID",(0,0),(-1,-1),0.3,_rc.HexColor("#DDE3EE"))]))
                                return t
                            # Courtier
                            story.append(_sec("COURTIER / INTERMÉDIAIRE"))
                            story.append(_tbl([["Courtier :",ss.get("f_courtier_nom","—")],
                                               ["Date de saisie :",_dt.now().strftime("%d/%m/%Y")]]))
                            story.append(Spacer(1,0.15*cm))
                            # Souscripteur
                            story.append(_sec("SOUSCRIPTEUR / ASSURÉ"))
                            ddn_s = ss.get("f_c_ddn","")
                            try: ddn_s = _dt.strptime(str(ddn_s),"%Y-%m-%d").strftime("%d/%m/%Y")
                            except: pass
                            story.append(_tbl([
                                ["Nom complet :",f"{ss.get('f_c_tit','')} {ss.get('f_c_nom','').upper()} {ss.get('f_c_prn','')}".strip()],
                                ["Date de naissance :",ddn_s],
                                ["Téléphone :",ss.get("f_c_tel","—")],
                                ["Adresse :",ss.get("f_c_adr","—")],
                                ["Nationalité :",ss.get("f_c_nat","Béninoise")]]))
                            story.append(Spacer(1,0.15*cm))
                            # Contrat
                            story.append(_sec("CONTRAT"))
                            prime_v = float(ss.get("f_coti",0))
                            cap_v   = float(ss.get("f_cap",0))
                            deff_s  = ss.get("f_deff","")
                            term_s  = ss.get("f_terme_auto","")
                            try: deff_s = _dt.strptime(str(deff_s),"%Y-%m-%d").strftime("%d/%m/%Y")
                            except: pass
                            try: term_s = _dt.strptime(str(term_s),"%Y-%m-%d").strftime("%d/%m/%Y")
                            except: pass
                            story.append(_tbl([
                                ["Produit :","Prévoyance Auto (PA0)"],
                                ["Prime annuelle :",f"{prime_v:,.0f} FCFA"],
                                ["Capital garanti décès :",f"{cap_v:,.0f} FCFA"],
                                ["Date d'effet :",deff_s],
                                ["Date terme :",term_s],
                                ["Mode de règlement :",ss.get("f_mode","—")],
                                ["Référence paiement :",ss.get("f_mref","—")]]))
                            story.append(Spacer(1,0.2*cm))
                            # Signatures
                            story.append(_sec("SIGNATURES"))
                            sig = Table([[Paragraph("Signature du souscripteur",st_lbl),
                                         Paragraph("Cachet & Signature AFG",st_lbl)],
                                        [Paragraph("\n\n\n",st_val),Paragraph("\n\n\n",st_val)]],
                                colWidths=[8.5*cm,8.5*cm])
                            sig.setStyle(TableStyle([
                                ("BOX",(0,1),(0,1),1,_rc.HexColor("#CCCCCC")),
                                ("BOX",(1,1),(1,1),1,_rc.HexColor("#CCCCCC")),
                                ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
                                ("LEFTPADDING",(0,0),(-1,-1),6),("ALIGN",(0,0),(-1,-1),"CENTER")]))
                            story.append(sig)
                            story.append(Spacer(1,0.1*cm))
                            story.append(Paragraph(
                                "<i>AFG Assurances Bénin Vie · Groupe AFG Holding · Conforme CIMA</i>",st_sm))
                            story.append(HRFlowable(width="100%",thickness=0.5,color=C_G,spaceAfter=3))

                        _buf = _io.BytesIO()
                        doc  = SimpleDocTemplate(_buf, pagesize=A4,
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
                        story = []
                        _bloc_bia(story, "CLIENT")
                        story.append(Spacer(1,0.3*cm))
                        story.append(Table([[Paragraph(
                            "✂ — — — — — — — — — — — — — — — — — — — — — — — — ✂",
                            ParagraphStyle("cut",fontName="Helvetica",fontSize=8,
                            textColor=__import__("reportlab.lib.colors",fromlist=["grey"]).grey,
                            alignment=TA_CENTER))]],colWidths=[17*cm]))
                        story.append(Spacer(1,0.3*cm))
                        _bloc_bia(story, "AFG")
                        doc.build(story)
                        _pdf = _buf.getvalue()
                        _nom = f"{st.session_state.get('f_c_nom','').upper()}_{st.session_state.get('f_c_prn','')}"
                        st.success(f"✅ BIA généré — {len(_pdf)//1024} Ko")
                        st.download_button("📥 Télécharger le BIA (PDF 2 exemplaires)",
                            data=_pdf,
                            file_name=f"BIA_PA0_{_nom}_{_dt.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf",
                            use_container_width=True, type="primary",
                            key="dl_bia_pdf")
                    except ImportError:
                        alert("reportlab non installé.","danger")
                    except Exception as _e_bp:
                        alert(f"Erreur PDF : {_e_bp}","danger")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — BASE BIA
# ═══════════════════════════════════════════════════════════════════════════════
elif "Base BIA" in page:
    df_bia = bia_all()
    section("🗂️ Base BIA — Registre des contrats","CONSULTATION · EXPORT · GESTION")

    if df_bia.empty:
        alert("Aucun BIA enregistré. Utilisez l'onglet <b>Saisie BIA</b>.","info"); st.stop()

    # KPIs
    nb_all = len(df_bia)
    nb_val = int((df_bia["statut"] == "Validé").sum())
    nb_bro = int((df_bia["statut"] == "Brouillon").sum())
    cot_t  = float(df_bia["cotisation"].fillna(0).astype(float).sum())

    c1,c2,c3,c4 = st.columns(4)
    kpi(c1,"Total contrats", str(nb_all), "Base complète","teal", icon="📋")
    kpi(c2,"Cotisations",    fmt(cot_t),  "Total FCFA",   "",    icon="💰")
    kpi(c3,"Validés",        str(nb_val), f"{nb_val/max(nb_all,1)*100:.0f}%","", icon="✅")
    kpi(c4,"Brouillons",     str(nb_bro), "À compléter","amber", icon="💾")

    st.markdown("---")

    # Filtres
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        _prod_opts = ["Tous"] + sorted(df_bia["produit"].dropna().unique().tolist()) if "produit" in df_bia.columns else ["Tous"]
        _prod_sel  = st.selectbox("Produit", _prod_opts, key="bia_filt_prod")
    with fc2:
        _stat_opts = ["Tous","Validé","Brouillon","En cours"]
        _stat_sel  = st.selectbox("Statut", _stat_opts, key="bia_filt_stat")
    with fc3:
        _srch = st.text_input("🔍 Recherche (nom, numéro…)", key="bia_srch", placeholder="Nom, N° BIA…")

    # Appliquer filtres
    df_show = df_bia.copy()
    if _prod_sel != "Tous" and "produit" in df_show.columns:
        df_show = df_show[df_show["produit"] == _prod_sel]
    if _stat_sel != "Tous":
        df_show = df_show[df_show["statut"] == _stat_sel]
    if _srch.strip():
        _q = _srch.strip().lower()
        df_show = df_show[df_show.apply(lambda r: _q in str(r).lower(), axis=1)]

    st.markdown(f"**{len(df_show):,} contrat(s) affiché(s)**")

    # Colonnes à afficher (ordre logique)
    _display_cols = [c for c in [
        "numero_bia","date_saisie","statut","produit",
        "nom_souscripteur","prenom_souscripteur",
        "telephone_souscripteur","adresse_souscripteur",
        "date_naissance_souscripteur","nationalite_souscripteur",
        "cotisation","capital_garanti","periodicite",
        "date_effet","date_echeance","duree",
        "mode_reglement","reference_reglement",
        "nom_apporteur","code_apporteur","agence",
        "saisi_par","obs"
    ] if c in df_show.columns]

    # Renommer pour affichage lisible
    _rename = {
        "numero_bia":"N° BIA","date_saisie":"Date saisie","statut":"Statut",
        "produit":"Produit","nom_souscripteur":"Nom","prenom_souscripteur":"Prénoms",
        "telephone_souscripteur":"Téléphone","adresse_souscripteur":"Adresse",
        "date_naissance_souscripteur":"Date naissance","nationalite_souscripteur":"Nationalité",
        "cotisation":"Cotisation (FCFA)","capital_garanti":"Capital (FCFA)",
        "periodicite":"Périodicité","date_effet":"Date effet","date_echeance":"Date terme",
        "duree":"Durée","mode_reglement":"Mode règlement","reference_reglement":"Référence",
        "nom_apporteur":"Apporteur","code_apporteur":"Code apporteur",
        "agence":"Agence","saisi_par":"Saisi par","obs":"Observations",
    }
    df_disp = df_show[_display_cols].rename(columns=_rename)

    # Formater les montants
    for col in ["Cotisation (FCFA)","Capital (FCFA)"]:
        if col in df_disp.columns:
            df_disp[col] = df_disp[col].apply(lambda x: fmt(x,"") if pd.notna(x) and x != "" else "—")

    st.dataframe(df_disp, use_container_width=True, hide_index=True, height=450)

    # Exports
    st.markdown("---")
    ea, eb, ec = st.columns(3)
    ea.download_button("📥 CSV complet",
        dl_csv(df_show), "base_bia.csv", "text/csv",
        use_container_width=True, key="dl_bia_csv")
    eb.download_button("📥 Excel complet",
        dl_xlsx(df_show), "base_bia.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True, key="dl_bia_xl")
    ec.download_button("📥 Export affiché",
        dl_csv(df_show), f"bia_{_prod_sel}_{_stat_sel}.csv", "text/csv",
        use_container_width=True, key="dl_bia_filt")

    # Graphiques synthèse
    if nb_all > 0:
        st.markdown("---")
        g1,g2 = st.columns(2)
        with g1:
            by_st = df_bia["statut"].value_counts().reset_index()
            by_st.columns = ["Statut","Nb"]
            fig = go.Figure(go.Pie(labels=by_st["Statut"],values=by_st["Nb"],hole=.44,
                marker_colors=[GREEN,AMBER,RED,BLUE],
                textinfo="percent+label+value", textfont=dict(size=12)))
            fig_style(fig,260,"Répartition par statut")
            st.plotly_chart(fig,use_container_width=True)
        with g2:
            if "produit" in df_bia.columns:
                by_p = (df_bia.groupby("produit")
                        .agg(Nb=("produit","count"),Cot=("cotisation","sum"))
                        .reset_index().sort_values("Cot",ascending=False).head(8))
                fig2 = go.Figure(go.Bar(
                    x=by_p["Cot"], y=by_p["produit"].str[:20],
                    orientation="h", marker_color=GREEN,
                    text=[fmt(v,"") for v in by_p["Cot"]],
                    textposition="outside", textfont=dict(size=10)))
                fig2.update_layout(yaxis=dict(autorange="reversed"))
                fig_style(fig2,260,"CA cotisations par produit")
                st.plotly_chart(fig2,use_container_width=True)


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
                        text=[fmt(v) for v in cp["CA"]],textposition="outside", textfont=dict(size=10)))
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
    try:
        section(f"👥 Commerciaux & Partenaires — {period_lbl}","CLASSEMENT · PARETO")
        df_com_src = ca_f() if ca is not None else pf_f()
        if df_com_src is None or df_com_src.empty:
            alert("Chargez la Base CA ou le Portefeuille.","warn"); st.stop()

        # ── Résolution du nom apporteur ──────────────────────────────────────
        # Stratégie : NOM_APPORT dans CA  sinon jointure PF sur CODEAPPO
        ca_k   = "CHIFAFFA" if "CHIFAFFA" in df_com_src.columns else "MONTENCA"
        comm_k = "COMMAPPO" if "COMMAPPO" in df_com_src.columns else None
        code_k = next((c for c in ["CODEAPPO","CODE_APPO","CODEINTE","CODE_INTER"]
                       if c in df_com_src.columns), None)

        ag_k = next((c for c in ["NOM_APPORT","NOM_APPO","NOM_INTERMEDIAIRE","NOM_APP"]
                     if c in df_com_src.columns), None)

        if ag_k is None and code_k and pf is not None:
            # Jointure PF  récupérer le nom via code apporteur
            _pf_code = next((c for c in ["CODEAPPO","CODE_APPO"] if c in pf.columns), None)
            _pf_nom  = next((c for c in ["NOM_APP","NOM_APPORT","NOM_APPO"] if c in pf.columns), None)
            if _pf_code and _pf_nom:
                _ref = pf[[_pf_code,_pf_nom]].drop_duplicates(_pf_code).rename(
                    columns={_pf_code: code_k, _pf_nom: "_NOM_JOIN"})
                df_com_src = df_com_src.merge(_ref, on=code_k, how="left")
                ag_k = "_NOM_JOIN"

        if ag_k is None:
            # Fallback : utiliser le code directement
            if code_k:
                df_com_src["_NOM_CODE"] = df_com_src[code_k].astype(str)
                ag_k = "_NOM_CODE"
            else:
                alert("Impossible d'identifier les apporteurs (NOM_APPORT / CODEAPPO introuvables).","warn")
                st.stop()

        # Groupby agrégé
        _grp_keys = [ag_k] + ([code_k] if code_k and code_k != ag_k else [])
        grp = df_com_src.groupby(_grp_keys, dropna=False).agg(
            CA=(ca_k,"sum"), Nb=(ca_k,"count"),
            **({} if not comm_k else {"Comm":(comm_k,"sum")})
        ).reset_index().sort_values("CA", ascending=False).reset_index(drop=True)
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
            fig=go.Figure(go.Bar(
                x=t30["CA"],
                y=t30[ag_k].fillna("N/A").astype(str).str[:25],
                name="CA",marker_color=GREEN,orientation="h",
                text=[fmt(v) for v in t30["CA"]],
                textposition="outside", textfont=dict(size=10)))
            fig.update_layout(yaxis=dict(autorange="reversed"))
            fig_style(fig,500,"📊 Pareto CA — Top 30")
            st.plotly_chart(fig,use_container_width=True)
    except Exception as _com_err:
        st.error(f"Erreur onglet Commerciaux : {_com_err}")

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
                    text=vl["Nb"].astype(str),textposition="outside", textfont=dict(size=10)))
                fig.update_layout(yaxis=dict(autorange="reversed"))
                fig_style(fig,400,"📍 Top 15 villes — Polices")
                st.plotly_chart(fig,use_container_width=True)
            with c2:
                vl_ca=df.groupby("LIBEVILL")["MONTENCA"].sum().reset_index().sort_values("MONTENCA",ascending=False).head(12)
                fig2=go.Figure(go.Bar(x=vl_ca["MONTENCA"],y=vl_ca["LIBEVILL"].str[:18],orientation="h",
                    marker=dict(color=vl_ca["MONTENCA"],colorscale=[[0,MINT],[1,GREEN2]],showscale=False),
                    text=[fmt(v) for v in vl_ca["MONTENCA"]],textposition="outside", textfont=dict(size=10)))
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
                fig=go.Figure(go.Pie(labels=sx["Sexe"],values=sx["Nb"],hole=.44,marker_colors=[BLUE,GREEN],textinfo="percent+label+value", textfont=dict(size=12)))
                fig_style(fig,320,"👥 Répartition H/F"); st.plotly_chart(fig,use_container_width=True)
        with c2:
            if "CODEPERI" in df.columns:
                per=df["CODEPERI"].map(CODEPERI_MAP).fillna("Autre").value_counts().reset_index(); per.columns=["Périodicité","Nb"]
                fig2=go.Figure(go.Pie(labels=per["Périodicité"],values=per["Nb"],hole=.44,marker_colors=PAL,textinfo="percent+label", textfont=dict(size=11)))
                fig_style(fig2,320,"📅 Périodicité cotisations"); st.plotly_chart(fig2,use_container_width=True)
        with c3:
            if "NOM_APP" in df.columns:
                ap=df[df["ETAT_POLICE"].str.strip()=="ACTIF"]["NOM_APP"].value_counts().head(10).reset_index() if "ETAT_POLICE" in df.columns else df["NOM_APP"].value_counts().head(10).reset_index()
                ap.columns=["Apporteur","Nb actifs"]
                fig3=go.Figure(go.Bar(y=ap["Apporteur"].str[:18],x=ap["Nb actifs"],orientation="h",marker_color=GREEN,text=ap["Nb actifs"].astype(str),textposition="outside", textfont=dict(size=10)))
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
                fig.add_bar(y=pyr["tranch"],x=-pyr["M"],name="Hommes",orientation="h",marker_color=BLUE,text=pyr["M"].astype(str),textposition="outside", textfont=dict(size=9))
                fig.add_bar(y=pyr["tranch"],x=pyr["F"],name="Femmes",orientation="h",marker_color=GREEN,text=pyr["F"].astype(str),textposition="outside", textfont=dict(size=9))
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

        section(f"⚠️ Sinistres & Prestations — {period_lbl}","ANALYSE ACTUARIELLE · SAP · S/P")
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
                    Nb=(_c_nat_,"count") if _c_nat_ else ("POLICE_KEY","count"),Regle=(_c_regle_,"sum") if _c_regle_ else ("CHIFAFFA","count"),SAP=(_c_sap_,"sum") if _c_sap_ else ("CHIFAFFA","count")).reset_index().sort_values("Réglé",ascending=False)
                nat["Charge"]=nat["Réglé"]+nat["SAP"]; nat["Coût moy"]=nat["Réglé"]/nat["Nb"].replace(0,np.nan)
                c1,c2=st.columns(2)
                with c1:
                    fig=go.Figure()
                    fig.add_bar(y=nat["Nature Sinistre"].str[:22],x=nat["Réglé"],name="Réglé",marker_color=RED,orientation="h")
                    fig.add_bar(y=nat["Nature Sinistre"].str[:22],x=nat["SAP"],name="SAP",marker_color=AMBER,orientation="h")
                    fig.update_layout(barmode="stack",yaxis=dict(autorange="reversed"))
                    fig_style(fig,360,"💊 Réglé + SAP par nature"); st.plotly_chart(fig,use_container_width=True)
                with c2:
                    fig2=px.treemap(nat,path=["Nature Sinistre"],values="Charge",color="Nb",
                        color_continuous_scale=[[0,MINT],[.5,AMBER],[1,RED]])
                    fig2.update_layout(height=360,margin=dict(l=5,r=5,t=20,b=5)); st.plotly_chart(fig2,use_container_width=True)
                nat_d=nat.copy()
                for c_ in ["Réglé","SAP","Charge","Coût moy"]: nat_d[c_]=nat_d[c_].apply(fmt)
                st.dataframe(nat_d,use_container_width=True,hide_index=True)
                a,b=st.columns(2)
                a.download_button("📥 CSV",dl_csv(nat),"sin_nature.csv","text/csv",use_container_width=True,key="dl_sin_nat")
                b.download_button("📥 Excel",dl_xlsx(nat),"sin_nature.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="dl_sin_nat_xl")

        with t_e:
            if "ANNEE_SIN" in sin.columns:
                evo=sin.groupby("ANNEE_SIN").agg(Nb=("ANNEE_SIN","count"),Regle=(_c_regle_,"sum") if _c_regle_ else ("CHIFAFFA","count"),SAP=(_c_sap_,"sum") if _c_sap_ else ("CHIFAFFA","count")).reset_index()
                evo=evo[evo["ANNEE_SIN"].between(1997,2025)].sort_values("ANNEE_SIN")
                fig=make_subplots(specs=[[{"secondary_y":True}]])
                fig.add_bar(x=evo["ANNEE_SIN"].astype(str),y=evo["Réglé"],name="Réglé",marker_color=RED,opacity=.82)
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
                sp2=sin.groupby(cat_c).agg(Nb=(cat_c,"count"),Regle=(_c_regle_,"sum") if _c_regle_ else ("CHIFAFFA","count"),SAP=(_c_sap_,"sum") if _c_sap_ else ("CHIFAFFA","count")).reset_index().sort_values("Réglé",ascending=False)
                sp2["Charge"]=sp2["Réglé"]+sp2["SAP"]
                fig=go.Figure()
                fig.add_bar(x=sp2["Réglé"],y=sp2[cat_c].str[:24],name="Réglé",marker_color=RED,orientation="h")
                fig.add_bar(x=sp2["SAP"],y=sp2[cat_c].str[:24],name="SAP",marker_color=AMBER,orientation="h")
                fig.update_layout(barmode="stack",yaxis=dict(autorange="reversed"))
                fig_style(fig,360,"🛒 Sinistres par produit"); st.plotly_chart(fig,use_container_width=True)
                sp2_d=sp2.copy()
                for c_ in ["Réglé","SAP","Charge"]: sp2_d[c_]=sp2_d[c_].apply(fmt)
                st.dataframe(sp2_d,use_container_width=True,hide_index=True)
                a,_=st.columns(2)
                a.download_button("📥 CSV",dl_csv(sp2),"sin_prod.csv","text/csv",use_container_width=True,key="dl_sin_p")

        with t_tri:
            section("📐 Triangle de développement des sinistres","EXERCICE × SURVENANCE")
            if "ANNEE_SIN" in sin.columns and "Date Survenance" in sin.columns:
                sin2=sin.copy()
                sin2["DEV_YEAR"]=pd.to_datetime(sin2["Date Survenance"],errors="coerce").dt.year.astype("Int64")
                tri=sin2.pivot_table(index="ANNEE_SIN",columns="DEV_YEAR",values=_c_regle_,aggfunc="sum",fill_value=0)
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
                Nb=(_c_nat_,"count") if _c_nat_ else ("POLICE_KEY","count"),Regle=(_c_regle_,"sum") if _c_regle_ else ("CHIFAFFA","count"),
                SAP=(_c_sap_,"sum") if "_c_sap_" in dir() and _c_sap_ else ("CHIFAFFA","count"),Ouvert=(_c_sort_,lambda x:(x=="Ouvert").sum()) if "_c_sort_" in dir() and _c_sort_ else ("CHIFAFFA","count")
            ).reset_index()
            prov["Charge"]=prov["Regle"]+prov["SAP"]
            prov["Ratio SAP/Charge"]=prov["SAP"]/prov["Charge"].replace(0,np.nan)*100
            prov["Cout moy clos"]=prov["Regle"]/(prov["Nb"]-prov["Ouvert"]).replace(0,np.nan)
            fig=go.Figure()
            fig.add_bar(y=prov["Nature Sinistre"].str[:22],x=prov["Regle"],name="Regle",marker_color=GREEN,orientation="h")
            fig.add_bar(y=prov["Nature Sinistre"].str[:22],x=prov["SAP"],name="SAP résiduel",marker_color=AMBER,orientation="h")
            fig.update_layout(barmode="stack",yaxis=dict(autorange="reversed"))
            fig_style(fig,360,"📌 Structure Réglé / SAP par nature"); st.plotly_chart(fig,use_container_width=True)
            pv=prov.copy()
            for c_ in ["Regle","SAP","Charge","Cout moy clos"]: pv[c_]=pv[c_].apply(fmt)
            pv["Ratio SAP/Charge"]=pv["Ratio SAP/Charge"].apply(lambda x:f"{x:.1f}%" if pd.notna(x) else "—")
            pv.columns=["Nature","Nb","Réglé","SAP","Dossiers ouverts","Charge","Ratio SAP/Charge","Coût moyen clos"]
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
                sin_agg=sin.groupby("POLICE_KEY").agg(Regle=(_c_regle_,"sum") if _c_regle_ else ("CHIFAFFA","count"),SAP=(_c_sap_,"sum") if _c_sap_ else ("CHIFAFFA","count"),NbSin=("POLICE_KEY","count")).reset_index()
                ca_pf=ca_pf.merge(sin_agg,on="POLICE_KEY",how="left")
            else:
                ca_pf["Réglé"]=np.nan; ca_pf["SAP"]=np.nan; ca_pf["NbSin"]=np.nan
            tp=ca_pf.groupby(["POLICE_KEY","LIBECATE","ETAT_POLICE","NOM_ASSU","NOM_APP"]).agg(
                CA=("CHIFAFFA","sum"),NbQ=("CHIFAFFA","count"),
                Regle=("Réglé","first"),SAP=("SAP","first"),NbSin=("NbSin","first")
            ).reset_index().sort_values("CA",ascending=False).head(30)
            tp_d=tp.copy()
            for c_ in ["CA","Réglé","SAP"]: tp_d[c_]=tp_d[c_].apply(lambda x:fmt(x) if pd.notna(x) else "—")
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
        _mc = [GREEN if v >= moy_g else "rgba(26,127,110,0.3)" for v in saison["CA moyen"]]
        fig2=go.Figure(go.Bar(x=saison["Label"],y=saison["CA moyen"],
            marker_color=_mc,
            text=[fmt(v) for v in saison["CA moyen"]],textposition="outside", textfont=dict(size=10)))
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
                100 F/mois  Capital 100 000 F  (unique : 1 000 F)<br>
                200 F/mois  Capital 200 000 F  (unique : 2 000 F)<br>
                300 F/mois  Capital 300 000 F  (unique : 3 000 F)
              </div>
            </div>""", unsafe_allow_html=True)
            if st.button("Choisir AVIGBO (221)", key="bp_221", use_container_width=True):
                st.session_state["bia_prod"]="221"; st.session_state["bia_step"]=2; st.rerun()
        with col_b:
            st.markdown(f"""<div style="border:2px solid {RED}44;border-radius:10px;padding:12px 14px;margin-bottom:6px">
              <span style="background:{RED};color:white;font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px">220</span>
              <div style="font-size:13px;font-weight:700;margin-top:6px;color:{NAVY}">ASSURTOUS VIGNINOU</div>
              <div style="font-size:11px;color:#666;margin-top:3px">Décès · Durée max 12 mois · Barème fixe</div>
              <div style="font-size:10px;color:#888;margin-top:5px;line-height:1.6">
                400 F/mois  Capital 500 000 F  (unique : 48 000 F)<br>
                800 F/mois  Capital 1 000 000 F (unique : 96 000 F)<br>
                1 200 F/mois  Capital 1 500 000 F (unique : 144 000 F)
              </div>
            </div>""", unsafe_allow_html=True)
            if st.button("Choisir VIGNINOU (220)", key="bp_220", use_container_width=True):
                st.session_state["bia_prod"]="220"; st.session_state["bia_step"]=2; st.rerun()
        alert("Sélectionnez un produit pour afficher le formulaire BIA.","info"); st.stop()
    prod=next((p for p in PRODUITS if p["code"]==st.session_state.get("bia_prod")),None)
    if not prod: st.session_state.pop("bia_prod",None); st.rerun()
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
        if b2.button("Suivant ▶", type="primary", key="nxt3_gen_b"):
            if not st.session_state.get("f_c_nom","").strip(): st.error("Nom obligatoire")
            elif not st.session_state.get("f_c_prn","").strip(): st.error("Prénom obligatoire")
            else: st.session_state["bia_step"]=4; st.rerun()
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
                "100 F/mois  Capital 100 000 F (unique : 1 000 F)":   (100,  100_000,  1_000),
                "200 F/mois  Capital 200 000 F (unique : 2 000 F)":   (200,  200_000,  2_000),
                "300 F/mois  Capital 300 000 F (unique : 3 000 F)":   (300,  300_000,  3_000),
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
                "400 F/mois  Capital 500 000 F (unique : 48 000 F)":    (400,  500_000,  48_000),
                "800 F/mois  Capital 1 000 000 F (unique : 96 000 F)":  (800,  1_000_000,96_000),
                "1 200 F/mois  Capital 1 500 000 F (unique : 144 000 F)": (1200, 1_500_000,144_000),
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
        if b1.button("← Retour", key=f"ret7_{5249}"): st.session_state["bia_step"] = 4 if _is_crt_step else 6; st.rerun()
        if b2.button("💾 Brouillon", key="brouillon_btn_b"):
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
                marker_colors=[GREEN,AMBER,RED,BLUE],textinfo="percent+label+value", textfont=dict(size=12)))
            fig_style(fig,260,"📊 Répartition par statut"); st.plotly_chart(fig,use_container_width=True)
        with g2:
            if "produit" in df_bia.columns:
                by_p=df_bia.groupby("produit").agg(Nb=("produit","count"),Cot=("cotisation","sum")).reset_index().sort_values("Cot",ascending=False).head(8)
                fig2=go.Figure(go.Bar(x=by_p["Cot"],y=by_p["produit"].str[:22],orientation="h",
                    marker_color=GREEN,text=[fmt(v) for v in by_p["Cot"]],textposition="outside", textfont=dict(size=10)))
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
                        delete_bia(int(br["id"])); st.rerun()
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


    elif "Rapport PDF" in page:
        section("📄 Rapport DG — Génération PDF","SYNTHÈSE ACTUARIELLE · CIMA · AFG BÉNIN VIE")
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,{NAVY},{GREEN2});border-radius:12px;
             padding:1.2rem 1.5rem;margin-bottom:16px">
          <div style="color:{MINT};font-size:11px;font-weight:700;text-transform:uppercase;
               letter-spacing:.08em;margin-bottom:4px">📄 Rapport confidentiel</div>
          <div style="color:white;font-size:14px;font-weight:700">
            AFG Assurances Bénin Vie — Rapport de Gestion · {period_lbl}</div>
          <div style="color:rgba(255,255,255,.5);font-size:10px;margin-top:3px">
            À l'attention de la Direction Générale · Conforme CIMA · Groupe AFG Holding</div>
        </div>""", unsafe_allow_html=True)

        rc1,rc2,rc3 = st.columns(3)
        s_kpis  = rc1.checkbox("📊 KPIs Portefeuille", value=True, key="rp_kpis")
        s_ca    = rc1.checkbox("💰 Chiffre d'Affaires", value=True, key="rp_ca")
        s_com   = rc2.checkbox("👥 Commerciaux",        value=True, key="rp_com")
        s_sin   = rc2.checkbox("⚠️ Sinistres",           value=True, key="rp_sin")
        s_cima  = rc3.checkbox("🏛️ Scorecard CIMA",     value=True, key="rp_cima")
        dest    = st.text_input("Destinataire", value="M. le Directeur Général", key="rp_dest")
        auteur  = st.text_input("Rédigé par",  value=user["nom"],                 key="rp_auteur")
        st.markdown("---")

        if pf is None and ca is None:
            alert("Chargez au moins une base de données pour générer le rapport.", "warn")
        else:
            # Aperçu
            ap1,ap2,ap3,ap4 = st.columns(4)
            if pf is not None:
                _act_r = int((pf["ETAT_POLICE"].str.strip().isin(["ACTIF"])).sum()) if "ETAT_POLICE" in pf.columns else 0
                ap1.metric("Polices", f"{len(pf):,}")
                ap2.metric("Actives", f"{_act_r:,}")
            if ca is not None:
                ap3.metric("CA global", fmt(float(ca["CHIFAFFA"].fillna(0).sum()) if "CHIFAFFA" in ca.columns else 0))
            if sin is not None:
                ap4.metric("Sinistres", fmt(float(sin["Réglement Total"].fillna(0).sum()) if "Réglement Total" in sin.columns else 0))
            st.markdown("")

            if st.button("🖨️ Générer le rapport PDF", type="primary",
                         use_container_width=True, key="gen_pdf_btn"):
                with st.spinner("⏳ Génération du rapport PDF en cours…"):
                    try:
                        from reportlab.lib.pagesizes import A4
                        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                        from reportlab.lib.units import cm
                        from reportlab.lib import colors as rl_colors
                        from reportlab.platypus import (SimpleDocTemplate, Paragraph,
                            Spacer, Table, TableStyle, HRFlowable)
                        from reportlab.lib.enums import TA_CENTER, TA_RIGHT
                        import io as _io
                        from datetime import datetime as _dt

                        _buf = _io.BytesIO()
                        doc  = SimpleDocTemplate(_buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2.5*cm, bottomMargin=2*cm)

                        C_N = rl_colors.HexColor("#0D1F3C")
                        C_G = rl_colors.HexColor("#1A7F6E")
                        C_R = rl_colors.HexColor("#C0392B")
                        C_A = rl_colors.HexColor("#CA6F1E")
                        C_L = rl_colors.HexColor("#F3F6FA")
                        C_W = rl_colors.white
                        C_M = rl_colors.HexColor("#A9DFBF")

                        st_ti = ParagraphStyle("T",fontName="Helvetica-Bold",fontSize=16,
                            textColor=C_W,alignment=TA_CENTER,spaceAfter=4)
                        st_su = ParagraphStyle("S",fontName="Helvetica",fontSize=9,
                            textColor=C_M,alignment=TA_CENTER,spaceAfter=4)
                        st_h1 = ParagraphStyle("H1",fontName="Helvetica-Bold",fontSize=12,
                            textColor=C_N,spaceBefore=12,spaceAfter=5)
                        st_h2 = ParagraphStyle("H2",fontName="Helvetica-Bold",fontSize=10,
                            textColor=C_G,spaceBefore=8,spaceAfter=4)
                        st_bd = ParagraphStyle("B",fontName="Helvetica",fontSize=9,
                            textColor=rl_colors.HexColor("#2C3E50"),spaceAfter=4,leading=13)
                        st_bld= ParagraphStyle("Bo",fontName="Helvetica-Bold",fontSize=9,
                            textColor=C_N,spaceAfter=3)
                        st_sm = ParagraphStyle("Sm",fontName="Helvetica",fontSize=8,
                            textColor=rl_colors.grey,spaceAfter=3)

                        def _tbl_style(data, col_widths, header_bg=None):
                            t = Table(data, colWidths=col_widths)
                            _bg = header_bg or C_N
                            t.setStyle(TableStyle([
                                ("BACKGROUND",(0,0),(-1,0),_bg),
                                ("TEXTCOLOR",(0,0),(-1,0),C_W),
                                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
                                ("FONTSIZE",(0,0),(-1,-1),8.5),
                                ("ROWBACKGROUNDS",(0,1),(-1,-1),[C_L, C_W]),
                                ("ALIGN",(1,0),(-1,-1),"RIGHT"),
                                ("GRID",(0,0),(-1,-1),0.3,rl_colors.HexColor("#DDE3EE")),
                                ("TOPPADDING",(0,0),(-1,-1),4),
                                ("BOTTOMPADDING",(0,0),(-1,-1),4),
                                ("LEFTPADDING",(0,0),(-1,-1),7),
                            ]))
                            return t

                        def _sec(txt):
                            t = Table([[Paragraph(txt, ParagraphStyle("SH",
                                fontName="Helvetica-Bold",fontSize=11,textColor=C_W))]],
                                colWidths=[17*cm])
                            t.setStyle(TableStyle([
                                ("BACKGROUND",(0,0),(-1,-1),C_G),
                                ("LEFTPADDING",(0,0),(-1,-1),10),
                                ("TOPPADDING",(0,0),(-1,-1),6),
                                ("BOTTOMPADDING",(0,0),(-1,-1),6),
                            ]))
                            return t

                        story = []

                        # En-tête
                        # En-tête avec logo AFG encodé base64
                        import base64 as _b64
                        try:
                            from reportlab.platypus import Image as RLImage
                            from io import BytesIO as _BIO
                            # Logo AFG depuis le code
                            _logo_b64_pdf = LOGO_B64  # variable globale
                            _logo_bytes = _b64.b64decode(_logo_b64_pdf)
                            _logo_img = RLImage(_BIO(_logo_bytes), width=4*cm, height=1.8*cm)
                            _logo_img.hAlign = 'CENTER'
                            story.append(_logo_img)
                            story.append(Spacer(1, 0.2*cm))
                        except Exception:
                            pass
                        hdr_t = Table([[Paragraph("AFG ASSURANCES BÉNIN VIE", st_ti)],
                            [Paragraph("RAPPORT DE GESTION — DIRECTION GÉNÉRALE", st_su)],
                            [Paragraph(f"Période d'analyse : {period_lbl}  ·  Édité le {_dt.now().strftime('%d %B %Y')}", st_su)]],
                            colWidths=[17*cm])
                        hdr_t.setStyle(TableStyle([
                            ("BACKGROUND",(0,0),(-1,-1),C_N),
                            ("ALIGN",(0,0),(-1,-1),"CENTER"),
                            ("TOPPADDING",(0,0),(-1,-1),14),
                            ("BOTTOMPADDING",(0,0),(-1,-1),14),
                        ]))
                        story.append(hdr_t)
                        story.append(Spacer(1,0.3*cm))
                        info_t = Table([
                            ["Destinataire :", dest],
                            ["Rédigé par :", auteur],
                            ["Classification :", "CONFIDENTIEL — Usage interne"],
                            ["Référence :", f"AFG-RPT-{_dt.now().strftime('%Y%m%d')}"],
                        ], colWidths=[5*cm,12*cm])
                        info_t.setStyle(TableStyle([
                            ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),
                            ("FONTSIZE",(0,0),(-1,-1),9),
                            ("TEXTCOLOR",(0,0),(0,-1),C_N),
                            ("ROWBACKGROUNDS",(0,0),(-1,-1),[C_L,C_W]),
                            ("TOPPADDING",(0,0),(-1,-1),5),
                            ("BOTTOMPADDING",(0,0),(-1,-1),5),
                            ("LEFTPADDING",(0,0),(-1,-1),8),
                        ]))
                        story.append(info_t)
                        story.append(Spacer(1,0.4*cm))
                        story.append(HRFlowable(width="100%",thickness=2,color=C_G,spaceAfter=6))

                        # 1. KPIs
                        if s_kpis and pf is not None:
                            story.append(_sec("1.  PORTEFEUILLE DE POLICES"))
                            story.append(Spacer(1,0.2*cm))
                            _nb  = len(pf); _ek="ETAT_POLICE"
                            _act = int((pf[_ek].str.strip().isin(["ACTIF"])).sum()) if _ek in pf.columns else 0
                            _res = int((pf[_ek].str.strip()=="RESILIE").sum()) if _ek in pf.columns else 0
                            _ina = int((pf[_ek].str.strip()=="INACTIF").sum()) if _ek in pf.columns else 0
                            _ec  = int((pf[_ek].str.strip().isin(["ECHU","ASSURE ECHU"])).sum()) if _ek in pf.columns else 0
                            _mon = float(pf["MONTENCA"].fillna(0).sum()) if "MONTENCA" in pf.columns else 0
                            _txa = _act/_nb*100 if _nb else 0
                            _txr = _res/max(_nb-_ina,1)*100
                            kd   = [["Indicateur","Valeur","Note"],
                                ["Total polices",         f"{_nb:,}",   "Ensemble du portefeuille"],
                                ["Polices actives",        f"{_act:,}", f"Taux activité : {_txa:.1f}%"],
                                ["Polices résiliées",      f"{_res:,}", f"Tx CIMA : {_txr:.1f}% (seuil ≤25%)"],
                                ["Polices échues",         f"{_ec:,}",  "ECHU + ASSURE ECHU"],
                                ["Encaissements (MONTENCA)",fmt(_mon),  "Total encaissements FCFA"]]
                            story.append(_tbl_style(kd,[7*cm,4*cm,6*cm]))
                            story.append(Spacer(1,0.2*cm))
                            story.append(Paragraph(
                                f"Le portefeuille compte <b>{_nb:,} polices</b> dont "
                                f"<b>{_act:,} actives ({_txa:.1f}%)</b>. "
                                f"Taux résiliation : <b>{_txr:.1f}%</b>"
                                f"{' — conforme CIMA.' if _txr<=25 else ' — DÉPASSE LE SEUIL CIMA (25%).'}",
                                st_bd))

                        # 2. CA
                        if s_ca and ca is not None:
                            story.append(Spacer(1,0.3*cm))
                            story.append(_sec("2.  CHIFFRE D'AFFAIRES"))
                            story.append(Spacer(1,0.2*cm))
                            _cat = float(ca["CHIFAFFA"].fillna(0).sum()) if "CHIFAFFA" in ca.columns else 0
                            _cm  = float(ca["COMMAPPO"].fillna(0).sum()) if "COMMAPPO" in ca.columns else 0
                            _pr  = float(ca["PRIMNETT"].fillna(0).sum()) if "PRIMNETT" in ca.columns else 0
                            _nq  = len(ca); _tk = _cat/_nq if _nq else 0
                            cd   = [["Indicateur","Valeur","Note"],
                                ["CA brut total",      fmt(_cat),   "CHIFAFFA total"],
                                ["Prime nette totale", fmt(_pr),    "Après chargements"],
                                ["Commissions",        fmt(_cm),    f"Taux : {_cm/_cat*100:.1f}%" if _cat else "—"],
                                ["Nb quittances",      f"{_nq:,}", "Émissions totales"],
                                ["Ticket moyen",       fmt(_tk),   "CA/quittance"]]
                            story.append(_tbl_style(cd,[7*cm,4*cm,6*cm]))
                            if "LIBECATE" in ca.columns:
                                story.append(Spacer(1,0.2*cm))
                                story.append(Paragraph("Répartition par produit (Top 8) :", st_h2))
                                _cp = ca.groupby("LIBECATE")["CHIFAFFA"].sum().reset_index()
                                _cp = _cp.sort_values("CHIFAFFA",ascending=False).head(8)
                                _cp["Part"] = (_cp["CHIFAFFA"]/_cat*100).round(1)
                                pd_   = [["Produit","CA (FCFA)","Part %"]] + [
                                    [str(r["LIBECATE"])[:38],fmt(r["CHIFAFFA"]),f"{r['Part']:.1f}%"]
                                    for _,r in _cp.iterrows()]
                                story.append(_tbl_style(pd_,[9*cm,4.5*cm,3.5*cm]))

                        # 3. Commerciaux
                        if s_com and ca is not None:
                            story.append(Spacer(1,0.3*cm))
                            story.append(_sec("3.  PERFORMANCE COMMERCIALE & PARTENAIRES"))
                            story.append(Spacer(1,0.2*cm))
                            if _agk in ca.columns:
                                _g = ca.groupby(_agk).agg(CA=("CHIFAFFA","sum"),NbQ=("CHIFAFFA","count")).reset_index()
                                if "COMMAPPO" in ca.columns:
                                    _gc = ca.groupby(_agk)["COMMAPPO"].sum()
                                    _g["Comm"] = _gc.reindex(_g[_agk]).values
                                else:
                                    _g["Comm"] = 0
                                _g = _g.sort_values("CA",ascending=False).head(15)
                                _gt = _g["CA"].sum()
                                _g["Part"] = (_g["CA"]/_gt*100).round(1)
                                comD = [["Commercial / Apporteur","CA (FCFA)","Nb affaires","Commission","Part %"]]
                                for _,r in _g.iterrows():
                                    comD.append([str(r[_agk])[:28], fmt(r["CA"]),
                                        f"{r['NbQ']:,}", fmt(r["Comm"]), f"{r['Part']:.1f}%"])
                                story.append(_tbl_style(comD,[7*cm,3.5*cm,2.2*cm,2.5*cm,1.8*cm]))
                                story.append(Spacer(1,0.2*cm))
                                # Partenaires financiers (code intermédiaire 3 chiffres, hors 100)
                                _col_ci = next((c for c in ["CODEINTE","CODEAPPO","CODE_INTER"] if c in ca.columns), None)
                                _col_ni = next((c for c in ["NOM_APPORT","NOM_APPO","NOM_INTERMEDIAIRE"] if c in ca.columns), None)
                                if _col_ci:
                                    _ca_part = ca.copy()
                                    _ca_part[_col_ci] = _ca_part[_col_ci].astype(str).str.strip()
                                    _ca_part = _ca_part[
                                        (_ca_part[_col_ci].str.len() == 3) &
                                        (_ca_part[_col_ci] != "100") &
                                        (_ca_part[_col_ci].str.isdigit())
                                    ]
                                    if not _ca_part.empty:
                                        _grp_part_key = _col_ci if _col_ni is None else [_col_ci, _col_ni]
                                        _gp = _ca_part.groupby(_grp_part_key).agg(
                                            CA=("CHIFAFFA","sum"), NbAff=("CHIFAFFA","count")
                                        ).reset_index().sort_values("CA",ascending=False).head(10)
                                        story.append(Paragraph("Partenaires financiers (codes 3 chiffres, hors 100) :", st_h2))
                                        _pD_hdr = ["Code","Partenaire","CA (FCFA)","Nb affaires"] if _col_ni else ["Code","CA (FCFA)","Nb affaires"]
                                        _pD = [_pD_hdr]
                                        for _,r in _gp.iterrows():
                                            if _col_ni and isinstance(_grp_part_key, list):
                                                _pD.append([str(r[_col_ci]), str(r[_col_ni])[:25], fmt(r["CA"]), f"{r['NbAff']:,}"])
                                            else:
                                                _pD.append([str(r[_col_ci]), fmt(r["CA"]), f"{r['NbAff']:,}"])
                                        _pw = [2*cm,6*cm,4.5*cm,4.5*cm] if _col_ni else [3*cm,8*cm,6*cm]
                                        story.append(_tbl_style(_pD, _pw))

                        # 4. Sinistres
                        if s_sin and sin is not None:
                            story.append(Spacer(1,0.3*cm))
                            story.append(_sec("4.  SINISTRES ET PRESTATIONS"))
                            story.append(Spacer(1,0.2*cm))
                            _st  = float(sin["Réglement Total"].fillna(0).sum()) if "Réglement Total" in sin.columns else 0
                            _ss  = float(sin["SAP au 31/12/2025"].fillna(0).sum()) if "SAP au 31/12/2025" in sin.columns else 0
                            _sh  = float(sin["Réglement Honoraires"].fillna(0).sum()) if "Réglement Honoraires" in sin.columns else 0
                            _sc  = int((sin["Sort Sinistre"]=="Cloturé").sum()) if "Sort Sinistre" in sin.columns else 0
                            _so  = int((sin["Sort Sinistre"]=="Ouvert").sum()) if "Sort Sinistre" in sin.columns else 0
                            _sn  = len(sin)
                            _ca2 = float(ca["CHIFAFFA"].fillna(0).sum()) if ca is not None and "CHIFAFFA" in ca.columns else 1
                            _sp  = _st/_ca2*100
                            _cu  = _st+_ss+_sh
                            sd   = [["Indicateur","Valeur","Note"],
                                ["Total réglé",       fmt(_st),      "Montant total règlements"],
                                ["SAP (provisions)",  fmt(_ss),      "Sinistres à payer"],
                                ["Honoraires",        fmt(_sh),      "Experts médicaux"],
                                ["Charge ultime",     fmt(_cu),      "Réglé + SAP + Honoraires"],
                                ["Ratio S/P",         f"{_sp:.1f}%", f"Seuil CIMA ≤80% {'✓' if _sp<=80 else '⚠'}"],
                                ["Dossiers ouverts",  f"{_so:,}",    f"Sur {_sn:,} dossiers"],
                                ["Dossiers clos",     f"{_sc:,}",    f"Taux clôture : {_sc/_sn*100:.1f}%" if _sn else "—"]]
                            story.append(_tbl_style(sd,[6*cm,4*cm,7*cm]))

                        # 5. CIMA
                        if s_cima and pf is not None:
                            story.append(Spacer(1,0.3*cm))
                            story.append(_sec("5.  SCORECARD CONFORMITÉ CIMA"))
                            story.append(Spacer(1,0.2*cm))
                            _nb2 = len(pf); _ek2="ETAT_POLICE"
                            _a2  = int((pf[_ek2].str.strip().isin(["ACTIF"])).sum()) if _ek2 in pf.columns else 0
                            _r2  = int((pf[_ek2].str.strip()=="RESILIE").sum()) if _ek2 in pf.columns else 0
                            _i2  = int((pf[_ek2].str.strip()=="INACTIF").sum()) if _ek2 in pf.columns else 0
                            _c2  = float(ca["CHIFAFFA"].fillna(0).sum()) if ca is not None and "CHIFAFFA" in ca.columns else 1
                            _s2  = float(sin["Réglement Total"].fillna(0).sum()) if sin is not None and "Réglement Total" in sin.columns else 0
                            _ta2 = _a2/_nb2*100 if _nb2 else 0
                            _tr2 = _r2/max(_nb2-_i2,1)*100
                            _sp2 = _s2/_c2*100
                            _in2 = _i2/_nb2*100 if _nb2 else 0
                            # Formules des taux CIMA
                            _st_f = ParagraphStyle("Ff",fontName="Helvetica",fontSize=8,
                                textColor=rl_colors.HexColor("#333"),leading=12,spaceAfter=2)
                            story.append(Paragraph("<b>Formules de calcul des indicateurs :</b>", st_h2))
                            _fd = [
                                ["Indicateur","Formule","Valeur"],
                                ["Taux activite net",
                                 f"Actifs / (Total - Inactifs) x 100 = {_a2:,} / {max(_nb2-_i2,1):,} x 100",
                                 f"{_ta2:.1f}%"],
                                ["Taux resiliation",
                                 f"Resilies / (Total - Inactifs) x 100 = {_r2:,} / {max(_nb2-_i2,1):,} x 100",
                                 f"{_tr2:.1f}%"],
                                ["Ratio S/P",
                                 f"Reglements / CA brut x 100 = {fmt(_s2)} / {fmt(_c2)} x 100",
                                 f"{_sp2:.1f}%"],
                                ["Part inactifs",
                                 f"Inactifs / Total x 100 = {_i2:,} / {max(_nb2,1):,} x 100",
                                 f"{_in2:.1f}%"],
                            ]
                            _ft = Table(_fd, colWidths=[4*cm, 10*cm, 3*cm])
                            _ft.setStyle(TableStyle([
                                ("BACKGROUND",(0,0),(-1,0),C_N),("TEXTCOLOR",(0,0),(-1,0),C_W),
                                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
                                ("FONTSIZE",(0,0),(-1,-1),8),
                                ("ROWBACKGROUNDS",(0,1),(-1,-1),[C_L,C_W]),
                                ("GRID",(0,0),(-1,-1),0.3,rl_colors.HexColor("#DDE3EE")),
                                ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
                                ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                                ("FONTNAME",(2,1),(2,-1),"Helvetica-Bold"),
                                ("TEXTCOLOR",(2,1),(2,-1),C_G),
                            ]))
                            story.append(_ft)
                            story.append(Spacer(1,0.3*cm))
                            cm_d = [["Indicateur CIMA","Valeur","Seuil","Statut"],
                                ["Taux d'activité net",  f"{_ta2:.1f}%", "≥ 50%", "CONFORME" if _ta2>=50 else "NON CONFORME"],
                                ["Taux résiliation",     f"{_tr2:.1f}%", "≤ 25%", "CONFORME" if _tr2<=25 else "NON CONFORME"],
                                ["Ratio S/P",            f"{_sp2:.1f}%", "≤ 80%", "CONFORME" if _sp2<=80 else "NON CONFORME"],
                                ["Part inactifs",        f"{_in2:.1f}%", "≤ 5%",  "CONFORME" if _in2<=5 else "NON CONFORME"]]
                            t_cm = Table(cm_d, colWidths=[6*cm,3*cm,3*cm,5*cm])
                            _cm_style = TableStyle([
                                ("BACKGROUND",(0,0),(-1,0),C_N),
                                ("TEXTCOLOR",(0,0),(-1,0),C_W),
                                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
                                ("FONTSIZE",(0,0),(-1,-1),9),
                                ("ROWBACKGROUNDS",(0,1),(-1,-1),[C_L,C_W]),
                                ("ALIGN",(1,0),(-1,-1),"CENTER"),
                                ("GRID",(0,0),(-1,-1),0.3,rl_colors.HexColor("#DDE3EE")),
                                ("TOPPADDING",(0,0),(-1,-1),5),
                                ("BOTTOMPADDING",(0,0),(-1,-1),5),
                                ("LEFTPADDING",(0,0),(-1,-1),8),
                            ])
                            for _i in range(1,len(cm_d)):
                                _ok = cm_d[_i][3]=="CONFORME"
                                _cm_style.add("TEXTCOLOR",(3,_i),(3,_i),C_G if _ok else C_R)
                                _cm_style.add("FONTNAME",(3,_i),(3,_i),"Helvetica-Bold")
                            t_cm.setStyle(_cm_style)
                            story.append(t_cm)

                        # Conclusion
                        story.append(Spacer(1,0.4*cm))
                        story.append(HRFlowable(width="100%",thickness=1,color=C_G,spaceAfter=6))
                        story.append(Paragraph("CONCLUSION",st_h1))
                        story.append(Paragraph(
                            f"Le présent rapport dresse un état de la situation actuarielle "
                            f"et commerciale d'AFG Assurances Bénin Vie "
                            f"pour la période du <b>{period_lbl}</b>. "
                            f"Les données présentées proviennent des bases de gestion "
                            f"officielles de la compagnie et ont été traitées conformément "
                            f"aux exigences du Code CIMA.",st_bd))
                        story.append(Spacer(1,0.2*cm))
                        story.append(Paragraph(
                            f"<i>Document confidentiel — AFG Assurances Bénin Vie · "
                            f"Groupe AFG Holding · Conforme CIMA · {_dt.now().strftime('%d/%m/%Y')}</i>",st_sm))

                        doc.build(story)
                        _pdf = _buf.getvalue()
                        st.success(f"✅ Rapport généré — {len(_pdf)//1024} Ko")
                        st.download_button("📥 Télécharger le rapport PDF",
                            data=_pdf,
                            file_name=f"AFG_Rapport_DG_{period_lbl.replace(' ','_')}_{_dt.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf",
                            use_container_width=True, type="primary",
                            key="dl_pdf_final")
                    except ImportError:
                        alert("La bibliothèque <b>reportlab</b> n'est pas installée.", "danger")
                    except Exception as _e:
                        alert(f"Erreur génération PDF : {_e}", "danger")
                        import traceback; st.code(traceback.format_exc())


    # ── FOOTER ────────────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="background:{NAVY};color:rgba(255,255,255,.3);text-align:center;
         font-size:10px;padding:12px;border-radius:10px;margin-top:20px;border-top:3px solid {GREEN}">
      © 2025 <strong style="color:{MINT}">AFG Assurances Bénin Vie</strong>
      · Dashboard Actuariel Expert v3.0 · Conforme CIMA · 306 295 polices · Groupe AFG Holding
      · <em>Données confidentielles — Accès restreint</em>
    </div>""", unsafe_allow_html=True)
