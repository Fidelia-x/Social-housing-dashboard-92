# Le parc social des Hauts-de-Seine — Dashboard Power BI

> 🚧 Projet en cours

Dashboard Power BI sur le logement social dans les Hauts-de-Seine : loyers, vacance, performance
énergétique et évolution 2013–2025, avec une préparation des données en Python.

Analyse du parc de logements sociaux des Hauts-de-Seine (92) à partir des données publiques RPLS
(Répertoire des logements locatifs des bailleurs sociaux, SDES — ministère de la Transition écologique).

## Questions auxquelles le dashboard répond

- Combien de logements sociaux par commune, et comment le parc évolue-t-il depuis 2013 ?
- Où les loyers au m² sont-ils les plus élevés ?
- Quelles communes ont le plus de vacance ou de rotation des locataires ?
- Quelle part du parc est énergivore (DPE F ou G) ?

## Aperçu

_(captures d'écran à ajouter dans `docs/screenshots/`)_

## Architecture

```
Fichier RPLS 2025 (SDES)  →  Python (pandas)  →  4 CSV (modèle en étoile)  →  Power BI
   data/raw/                  scripts/              data/processed/              powerbi/
                              prepare_data.py
```

| Table | Grain | Contenu |
|---|---|---|
| `dim_commune` | 1 ligne par commune | code INSEE, nom, département |
| `fact_parc` | 1 ligne par commune | photo du parc au 1er janvier 2025 : effectifs, vacance, mobilité, loyers, mises en service |
| `fact_evolution` | 1 ligne par commune et par année | historique 2013–2025 : nb de logements, vacance, mobilité, loyer moyen, mises en service |
| `fact_repartition` | 1 ligne par commune, thème et catégorie | répartition du parc : pièces, type de construction, financement, âge, DPE |

## Données

Source : SDES (ministère de la Transition écologique), fichier
« Données nationales : régions, départements, EPCI et communes — RPLS au 1er janvier 2025 »,
feuille des communes.

- Téléchargement : https://www.statistiques.developpement-durable.gouv.fr/media/8938/download?inline
- À enregistrer sous `data/raw/rpls_2025.xlsx` (les fichiers bruts ne sont pas versionnés).

Le millésime 2025 contient déjà l'historique 2013–2024 des indicateurs principaux, avec les
chiffres révisés : un seul fichier suffit. Les millésimes précédents (2020–2023) n'ont pas de
ligne de codes de colonnes, seulement des titres sur plusieurs lignes ; ils ont été inspectés
avec `scripts/inspect_columns.py` mais ne sont pas utilisés.

<details>
<summary>Millésimes précédents</summary>

| Millésime | Lien |
|---|---|
| 2024 | https://www.statistiques.developpement-durable.gouv.fr/media/7970/download?inline |
| 2023 | https://www.statistiques.developpement-durable.gouv.fr/media/6897/download?inline |
| 2022 | https://www.statistiques.developpement-durable.gouv.fr/media/6006/download?inline |
| 2021 | https://www.statistiques.developpement-durable.gouv.fr/media/4997/download?inline |
| 2020 | https://www.statistiques.developpement-durable.gouv.fr/media/4096/download?inline |

</details>

## Lancer le projet

```bash
git clone https://github.com/Fidelia-x/social-housing-dashboard-92.git
cd social-housing-dashboard-92
pip install -r requirements.txt
python scripts/inspect_columns.py   # (optionnel) liste des colonnes de chaque fichier dans docs/columns/
python scripts/prepare_data.py      # produit les 4 CSV dans data/processed/
```

Puis ouvrir `powerbi/social_housing_92.pbix` dans Power BI Desktop.

## Stack

Python · pandas · Power BI (Power Query, modèle en étoile, DAX)

## Ce que j'ai appris

_(à compléter à la fin du projet)_