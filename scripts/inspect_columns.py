"""
Inspecte la feuille "communes" de chaque fichier RPLS et écrit la liste des colonnes
dans docs/columns/<annee>.txt.

Deux formats existent selon les années :
  - format "codes" : une ligne contient des codes de colonnes (REG, DEPCOM_ARM, nb_loues...)
  - format "titres" : seulement des titres en français sur plusieurs lignes, sans codes

Usage :
  python scripts/inspect_columns.py
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "docs" / "columns"
SCAN_ROWS = 15
COMMUNE_CODE = re.compile(r"^(\d{4,5}|2[ABab]\d{3})$")


def commune_sheet(path: Path) -> str | None:
    sheets = pd.ExcelFile(path).sheet_names
    for name in sheets:
        if name.strip().lower().startswith("commune"):
            return name
    return None


def clean(value: object) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).split())


def fill_merged_titles(titles: pd.DataFrame) -> list[list[str]]:
    """Complète les titres de cellules fusionnées vers la droite, mais seulement
    à l'intérieur du même groupe parent (la ligne du dessus doit être identique)."""
    grid = [[clean(v) for v in row] for _, row in titles.iterrows()]
    for r, row in enumerate(grid):
        for j in range(1, len(row)):
            same_parent = r == 0 or grid[r - 1][j] == grid[r - 1][j - 1]
            if not row[j] and row[j - 1] and same_parent:
                row[j] = row[j - 1]
    return grid


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in RAW_DIR.glob("*.xlsx") if re.search(r"20\d{2}", p.name))
    if not files:
        raise SystemExit(f"Aucun fichier .xlsx dans {RAW_DIR}")

    for path in files:
        year = re.search(r"(20\d{2})", path.name).group(1)
        sheet = commune_sheet(path)
        if sheet is None:
            print(f"{year} : pas de feuille communes trouvée")
            continue

        top = pd.read_excel(path, sheet_name=sheet, header=None, nrows=SCAN_ROWS, dtype=str)

        # 1) Ligne de codes ? (une cellule qui commence par "depcom")
        code_row = next(
            (i for i, row in top.iterrows()
             if any(clean(v).lower().startswith("depcom") for v in row)),
            None,
        )

        # 2) Première ligne de données : une cellule qui ressemble à un code commune
        data_row = next(
            (i for i, row in top.iterrows()
             if any(COMMUNE_CODE.match(clean(v)) for v in row.iloc[:4])
             and (code_row is None or i > code_row)),
            None,
        )

        # 3) Titres en français, lignes au-dessus des données (ou des codes),
        #    complétés vers la droite (cellules fusionnées dans Excel)
        title_end = code_row if code_row is not None else data_row
        grid = fill_merged_titles(top.iloc[:title_end] if title_end else top.iloc[:0])

        lines = []
        for col in top.columns:
            label = " | ".join(t for t in (row[col] for row in grid) if t)
            code = clean(top.iloc[code_row][col]) if code_row is not None else ""
            lines.append(f"{col:>3} | {code:<25} | {label}")

        fmt = "codes" if code_row is not None else "titres"
        header = (f"Année {year} | feuille '{sheet}' | format : {fmt} | "
                  f"ligne des codes : {code_row} | première ligne de données : {data_row}\n")
        out = OUT_DIR / f"{year}.txt"
        out.write_text(header + "\n".join(lines), encoding="utf-8")
        print(header.strip(), f"-> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()