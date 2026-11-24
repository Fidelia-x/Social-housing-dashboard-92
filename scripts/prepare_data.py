"""
Préparation des données RPLS (Répertoire des logements locatifs des bailleurs sociaux)
pour le dashboard Power BI.

Source : fichier SDES "Données nationales : régions, départements, EPCI et communes",
feuille des communes. On utilise uniquement le millésime le plus récent (2025) :
il contient déjà l'historique 2013-2024 des indicateurs principaux, avec les chiffres révisés.

Le script produit 4 fichiers dans data/processed/ :
  - dim_commune.csv         : une ligne par commune (code, nom)
  - fact_parc.csv           : une ligne par commune, photo du parc au 1er janvier de l'année de référence
  - fact_evolution.csv      : une ligne par commune et par année (2013 -> année de référence)
  - fact_repartition.csv    : répartitions du parc (pièces, âge, financement, DPE...) au format long

Usage :
  python scripts/prepare_data.py                         # fichier data/raw/rpls_2025.xlsx, département 92
  python scripts/prepare_data.py --file data/raw/rpls_2025.xlsx --dep 92 93 94
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "processed"
SCAN_ROWS = 15

# ---------------------------------------------------------------------------
# Choix des indicateurs (codes des colonnes du fichier SDES)
# ---------------------------------------------------------------------------

# Photo du parc pour l'année de référence : {code SDES: nom de colonne en sortie}
PARC_COLUMNS = {
    "nb_ls": "nb_logements_sociaux",
    "nb_lgt_tot": "nb_logements_bailleurs",
    "nb_loues": "nb_loues",
    "nb_vacants": "nb_vacants",
    "nb_vides": "nb_vides",
    "nb_asso": "nb_associations",
    "nb_occup_finan": "nb_occupes_autre",
    "nb_occup_temp": "nb_hebergement_temporaire",
    "densite": "densite_pour_100_residences",
    "nb_ls_en_qpv": "nb_logements_qpv",
    "age": "age_moyen_parc",
    "tx_vac": "taux_vacance_pct",
    "tx_vac3": "taux_vacance_3mois_pct",
    "tx_mob": "taux_mobilite_pct",
    "loymoy": "loyer_moyen_m2",
    "loymoy_r": "loyer_moyen_m2_parc_recent",
    "nv_mes": "nb_mises_en_service",
    "nb_ls_demolition": "nb_demolitions",
    "nb_ls_vendu_occupant": "nb_ventes_occupant",
    "nb_dpe_realise": "nb_dpe_realises",
    "perc_dpe_realise": "part_dpe_realises_pct",
}

# Historique : {nom en sortie: (code pour l'année de référence, préfixe pour les années passées)}
# ex. nb_ls -> année de référence, nb_ls2024 -> 2024 ; tx_vac -> référence, tx_vac_2024 -> 2024
EVOLUTION_COLUMNS = {
    "nb_logements_sociaux": ("nb_ls", "nb_ls{y}"),
    "taux_vacance_pct": ("tx_vac", "tx_vac_{y}"),
    "taux_mobilite_pct": ("tx_mob", "tx_mob_{y}"),
    "loyer_moyen_m2": ("loymoy", "loymoy_{y}"),
    "nb_mises_en_service": ("nv_mes", "nv_mes_{y}"),
}
FIRST_HISTORY_YEAR = 2013

# Répartitions : (thème, code SDES, catégorie affichée, ordre de tri)
REPARTITION_COLUMNS = [
    ("Nombre de pièces", "nb_ls_1piece", "1 pièce", 1),
    ("Nombre de pièces", "nb_ls_2piece", "2 pièces", 2),
    ("Nombre de pièces", "nb_ls_3piece", "3 pièces", 3),
    ("Nombre de pièces", "nb_ls_4piece", "4 pièces", 4),
    ("Nombre de pièces", "nb_ls_5piece_plus", "5 pièces et +", 5),
    ("Type de construction", "nb_ls_individuels", "Individuel", 1),
    ("Type de construction", "nb_ls_collectifs", "Collectif", 2),
    ("Financement d'origine", "nb_ls_plai", "PLAI", 1),
    ("Financement d'origine", "nb_ls_plus_av_77", "PLUS avant 1977", 2),
    ("Financement d'origine", "nb_ls_plus_ap_77", "PLUS après 1977", 3),
    ("Financement d'origine", "nb_ls_pls", "PLS", 4),
    ("Financement d'origine", "nb_ls_pli", "PLI", 5),
    ("Âge du parc", "age_inf_5", "Moins de 5 ans", 1),
    ("Âge du parc", "age_5_10", "5 à 10 ans", 2),
    ("Âge du parc", "age_10_20", "10 à 20 ans", 3),
    ("Âge du parc", "age_20_40", "20 à 40 ans", 4),
    ("Âge du parc", "age_40_60", "40 à 60 ans", 5),
    ("Âge du parc", "age_60_plus", "Plus de 60 ans", 6),
] + [
    ("DPE énergie (depuis 07/2021)", f"ener_{c}_new", c if c != "NR" else "Non renseigné", i)
    for i, c in enumerate(["A", "B", "C", "D", "E", "F", "G", "NR"], start=1)
] + [
    ("DPE énergie (avant 07/2021)", f"ener_{c}", c if c != "NR" else "Non renseigné", i)
    for i, c in enumerate(["A", "B", "C", "D", "E", "F", "G", "NR"], start=1)
]


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------

def clean(value: object) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).split())


def find_commune_sheet(path: Path) -> str:
    for name in pd.ExcelFile(path).sheet_names:
        if name.strip().lower().startswith("commune"):
            return name
    raise SystemExit(f"Pas de feuille 'communes' dans {path.name}")


def read_commune_table(path: Path) -> pd.DataFrame:
    """Lit la feuille communes et utilise la ligne des codes (REG, DEPCOM_ARM, nb_ls...) comme en-tête."""
    sheet = find_commune_sheet(path)
    raw = pd.read_excel(path, sheet_name=sheet, header=None, dtype=str)

    code_row = next(
        (i for i, row in raw.head(SCAN_ROWS).iterrows()
         if any(clean(v).lower().startswith("depcom") for v in row)),
        None,
    )
    if code_row is None:
        raise SystemExit(
            f"{path.name} : pas de ligne de codes (format ancien). "
            "Utilise le fichier 2024 ou plus récent."
        )

    df = raw.iloc[code_row + 1:].copy()
    df.columns = [clean(c) for c in raw.iloc[code_row]]
    df = df.loc[:, ~pd.Index(df.columns).duplicated()]  # garde la 1re colonne si un code est en double
    df = df.dropna(how="all")
    print(f"Feuille '{sheet}' : {len(df)} communes, {df.shape[1]} colonnes (codes en ligne {code_row})")
    return df


def to_number(series: pd.Series) -> pd.Series:
    """Convertit en nombre ; les valeurs non numériques (secret statistique, vide...) deviennent vides."""
    text = (series.astype(str)
            .str.replace(" ", "", regex=False)
            .str.replace(" ", "", regex=False)
            .str.replace(",", ".", regex=False))
    return pd.to_numeric(text, errors="coerce")


# ---------------------------------------------------------------------------
# Construction des tables
# ---------------------------------------------------------------------------

def build_tables(df: pd.DataFrame, ref_year: int, departements: list[str]) -> dict[str, pd.DataFrame]:
    df = df.copy()
    df["code_commune"] = df["DEPCOM_ARM"].map(clean).str.zfill(5)
    df = df[df["code_commune"].str[:2].isin(departements)].copy()
    if df.empty:
        raise SystemExit(f"Aucune commune trouvée pour {departements}")

    # --- Dimension commune
    dim = pd.DataFrame({
        "code_commune": df["code_commune"],
        "nom_commune": df["LIBCOM_DEP"].map(clean).str.replace(r"\s*\(\w+\)$", "", regex=True),
        "code_departement": df["code_commune"].str[:2],
    })

    missing: list[str] = []

    # --- Photo du parc
    parc = df[["code_commune"]].copy()
    parc.insert(1, "annee", ref_year)
    for code, name in PARC_COLUMNS.items():
        if code in df.columns:
            parc[name] = to_number(df[code])
        else:
            missing.append(code)

    # --- Évolution (format long : une ligne par commune et par année)
    frames = []
    for year in range(FIRST_HISTORY_YEAR, ref_year + 1):
        block = df[["code_commune"]].copy()
        block["annee"] = year
        for name, (current_code, past_pattern) in EVOLUTION_COLUMNS.items():
            code = current_code if year == ref_year else past_pattern.format(y=year)
            if code in df.columns:
                block[name] = to_number(df[code])
            else:
                block[name] = pd.NA
                missing.append(code)
        frames.append(block)
    evolution = pd.concat(frames, ignore_index=True)

    # --- Répartitions (format long)
    rows = []
    for theme, code, category, order in REPARTITION_COLUMNS:
        if code not in df.columns:
            missing.append(code)
            continue
        part = pd.DataFrame({
            "code_commune": df["code_commune"],
            "annee": ref_year,
            "theme": theme,
            "categorie": category,
            "ordre": order,
            "nb_logements": to_number(df[code]),
        })
        rows.append(part)
    repartition = pd.concat(rows, ignore_index=True)

    if missing:
        print(f"[!] Colonnes absentes du fichier (ignorées) : {sorted(set(missing))}")

    return {
        "dim_commune": dim.sort_values("code_commune"),
        "fact_parc": parc.sort_values("code_commune"),
        "fact_evolution": evolution.sort_values(["code_commune", "annee"]),
        "fact_repartition": repartition.sort_values(["code_commune", "theme", "ordre"]),
    }


def quality_report(tables: dict[str, pd.DataFrame]) -> None:
    parc = tables["fact_parc"]
    print("\n--- Contrôles qualité ---")
    print(f"Communes : {len(tables['dim_commune'])}")
    if "nb_logements_sociaux" in parc:
        print(f"Total logements sociaux : {parc['nb_logements_sociaux'].sum():,.0f}".replace(",", " "))

    # Les répartitions doivent retomber sur le nombre total de logements sociaux
    rep = tables["fact_repartition"]
    totals = rep.groupby("theme")["nb_logements"].sum()
    total_ls = parc.get("nb_logements_sociaux", pd.Series(dtype=float)).sum()
    for theme, value in totals.items():
        gap = (value - total_ls) / total_ls * 100 if total_ls else float("nan")
        print(f"  {theme:<32} somme = {value:>9,.0f}  (écart avec le total : {gap:+.1f} %)".replace(",", " "))

    print("\nValeurs manquantes dans fact_parc (part) :")
    na = parc.drop(columns=["code_commune", "annee"]).isna().mean()
    print(na[na > 0].round(2).to_string() if (na > 0).any() else "  aucune")


def save(tables: dict[str, pd.DataFrame], suffix: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        path = OUT_DIR / f"{name}_{suffix}.csv"
        # Séparateur ;, virgule décimale, utf-8-sig : format lu directement par Power BI / Excel en français
        table.to_csv(path, index=False, sep=";", decimal=",", encoding="utf-8-sig")
        print(f"Écrit : {path.relative_to(ROOT)} ({len(table)} lignes)")


def latest_raw_file() -> Path:
    files = sorted(RAW_DIR.glob("rpls_20*.xlsx"))
    if not files:
        raise SystemExit(f"Aucun fichier rpls_AAAA.xlsx dans {RAW_DIR}")
    return files[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Prépare les données RPLS pour Power BI.")
    parser.add_argument("--file", type=Path, help="Fichier RPLS à utiliser (défaut : le plus récent de data/raw/).")
    parser.add_argument("--dep", nargs="+", default=["92"], help="Codes départements à garder (défaut : 92).")
    args = parser.parse_args()

    path = args.file or latest_raw_file()
    year_match = re.search(r"(20\d{2})", path.name)
    if not year_match:
        raise SystemExit("L'année doit apparaître dans le nom du fichier, ex. rpls_2025.xlsx")
    ref_year = int(year_match.group(1))
    departements = [d.zfill(2) for d in args.dep]

    print(f"Fichier : {path.name} | année de référence : {ref_year} | départements : {departements}")
    df = read_commune_table(path)
    tables = build_tables(df, ref_year, departements)
    quality_report(tables)
    print()
    save(tables, "_".join(departements))


if __name__ == "__main__":
    main()