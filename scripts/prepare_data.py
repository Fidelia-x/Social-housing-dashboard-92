"""
Préparation des données RPLS (Répertoire du Parc Locatif Social) pour le dashboard Power BI.

Étapes :
  1. Lit les fichiers bruts déposés dans data/raw/ (ZIP, XLSX ou CSV, un par année).
  2. Repère la feuille "communes" et la ligne d'en-tête automatiquement.
  3. Garde uniquement les communes du département choisi (92 par défaut).
  4. Ajoute une colonne "annee" et empile toutes les années dans un seul fichier.

Usage :
  python scripts/prepare_data.py --explore          # affiche feuilles et colonnes, sans rien écrire
  python scripts/prepare_data.py                    # produit data/processed/rpls_communes_92.csv
  python scripts/prepare_data.py --dep 75 92 93 94  # plusieurs départements

Convention de nommage des fichiers bruts : l'année doit apparaître dans le nom,
par exemple rpls_2025.zip, rpls_2024.xlsx.
"""

from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
EXTRACT_DIR = RAW_DIR / "_extracted"
OUT_DIR = ROOT / "data" / "processed"

# Noms possibles de la colonne "code commune" selon les millésimes
COMMUNE_CODE_CANDIDATES = ["depcom", "codgeo", "code commune", "code_commune", "com", "codecom", "code insee"]
HEADER_SCAN_ROWS = 20


# ---------------------------------------------------------------------------
# Lecture des fichiers
# ---------------------------------------------------------------------------

def year_from_name(path: Path) -> int | None:
    match = re.search(r"(20\d{2})", path.name)
    return int(match.group(1)) if match else None


def unzip_if_needed(path: Path) -> list[Path]:
    """Renvoie la liste des fichiers tabulaires (xlsx/xls/csv) à lire pour ce fichier brut."""
    if path.suffix.lower() != ".zip":
        return [path]
    target = EXTRACT_DIR / path.stem
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as zf:
        zf.extractall(target)
    return sorted(
        p for p in target.rglob("*")
        if p.suffix.lower() in {".xlsx", ".xls", ".csv"} and not p.name.startswith("~$")
    )


def normalize(text: object) -> str:
    return str(text).strip().lower().replace("\n", " ")


def find_header_row(preview: pd.DataFrame) -> int | None:
    """Cherche la ligne qui contient un nom de colonne 'code commune'."""
    for i, row in preview.iterrows():
        values = [normalize(v) for v in row.tolist()]
        if any(v in COMMUNE_CODE_CANDIDATES for v in values):
            return int(i)
    return None


def find_commune_column(columns: list[str]) -> str | None:
    lowered = {normalize(c): c for c in columns}
    for candidate in COMMUNE_CODE_CANDIDATES:
        if candidate in lowered:
            return lowered[candidate]
    return None


def iter_tables(path: Path):
    """Produit (nom_feuille, DataFrame sans en-tête) pour chaque feuille/fichier."""
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path, header=None, sep=None, engine="python", dtype=str, encoding_errors="replace")
        yield path.name, df
    else:
        for sheet, df in pd.read_excel(path, sheet_name=None, header=None, dtype=str).items():
            yield sheet, df


def load_commune_table(path: Path) -> pd.DataFrame | None:
    """Trouve la table de niveau commune dans un fichier et la renvoie avec les bons en-têtes."""
    candidates = []
    for sheet, raw in iter_tables(path):
        header_row = find_header_row(raw.head(HEADER_SCAN_ROWS))
        if header_row is None:
            continue
        df = raw.iloc[header_row + 1:].copy()
        df.columns = [str(c).strip() for c in raw.iloc[header_row]]
        df = df.dropna(how="all")
        # Priorité aux feuilles dont le nom évoque les communes
        score = 1 if "com" in sheet.lower() else 0
        candidates.append((score, len(df), sheet, df))
    if not candidates:
        return None
    candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
    score, n, sheet, df = candidates[0]
    print(f"    -> feuille retenue : '{sheet}' ({n} lignes)")
    return df


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

def explore(raw_files: list[Path]) -> None:
    for raw in raw_files:
        print(f"\n=== {raw.name} (année {year_from_name(raw)}) ===")
        for table_file in unzip_if_needed(raw):
            print(f"  Fichier : {table_file.name}")
            for sheet, df in iter_tables(table_file):
                header_row = find_header_row(df.head(HEADER_SCAN_ROWS))
                print(f"    Feuille '{sheet}' : {df.shape[0]} lignes x {df.shape[1]} colonnes, "
                      f"en-tête détecté ligne {header_row}")
                if header_row is not None:
                    cols = [str(c).strip() for c in df.iloc[header_row].tolist()]
                    print(f"      Colonnes : {cols}")


def prepare(raw_files: list[Path], departements: list[str]) -> Path:
    frames = []
    for raw in raw_files:
        year = year_from_name(raw)
        if year is None:
            print(f"[!] Année introuvable dans le nom '{raw.name}' : fichier ignoré.")
            continue
        print(f"\n=== {raw.name} (année {year}) ===")
        table = None
        for table_file in unzip_if_needed(raw):
            table = load_commune_table(table_file)
            if table is not None:
                break
        if table is None:
            print("[!] Aucune table communale trouvée : lance --explore pour voir la structure.")
            continue

        code_col = find_commune_column(list(table.columns))
        table[code_col] = table[code_col].astype(str).str.strip().str.zfill(5)
        table = table[table[code_col].str[:2].isin(departements)].copy()
        table = table.rename(columns={code_col: "code_commune"})
        table.insert(0, "annee", year)
        print(f"    -> {len(table)} communes gardées pour {departements}")
        frames.append(table)

    if not frames:
        raise SystemExit("Aucune donnée produite.")

    result = pd.concat(frames, ignore_index=True, sort=False)

    # Conversion en nombres des colonnes qui le sont (virgule décimale française gérée)
    for col in result.columns:
        if col in {"annee", "code_commune"}:
            continue
        converted = pd.to_numeric(
            result[col].astype(str).str.replace(" ", "", regex=False)
                                   .str.replace(" ", "", regex=False)
                                   .str.replace(",", ".", regex=False),
            errors="coerce",
        )
        # On ne convertit que si la grande majorité des valeurs sont numériques
        if converted.notna().mean() > 0.8:
            result[col] = converted

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "_".join(departements)
    out_path = OUT_DIR / f"rpls_communes_{suffix}.csv"
    # Séparateur ;, virgule décimale et encodage utf-8-sig : s'ouvre proprement dans Excel et Power BI en français
    result.to_csv(out_path, index=False, sep=";", decimal=",", encoding="utf-8-sig")

    print(f"\nFichier écrit : {out_path}")
    print(f"{len(result)} lignes, années : {sorted(int(a) for a in result['annee'].unique())}")
    print("\nColonnes et part de valeurs manquantes :")
    print(result.isna().mean().round(2).to_string())
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Prépare les données RPLS pour Power BI.")
    parser.add_argument("--explore", action="store_true", help="Affiche la structure des fichiers bruts.")
    parser.add_argument("--dep", nargs="+", default=["92"], help="Codes départements à garder (défaut : 92).")
    args = parser.parse_args()

    raw_files = sorted(
        p for p in RAW_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in {".zip", ".xlsx", ".xls", ".csv"}
    ) if RAW_DIR.exists() else []
    if not raw_files:
        raise SystemExit(f"Aucun fichier dans {RAW_DIR}. Voir le README pour les liens de téléchargement.")

    if args.explore:
        explore(raw_files)
    else:
        prepare(raw_files, [d.zfill(2) for d in args.dep])


if __name__ == "__main__":
    main()
