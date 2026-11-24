# Le parc social des Hauts-de-Seine — Dashboard Power BI

> 🚧 Projet en cours

Analyse du parc de logements sociaux des Hauts-de-Seine (92) à partir des données publiques RPLS
(Répertoire des logements locatifs des bailleurs sociaux, SDES — ministère de la Transition écologique).

## Questions auxquelles le dashboard répond

- Combien de logements sociaux par commune, et comment le parc évolue-t-il depuis 2020 ?
- Où les loyers au m² sont-ils les plus élevés ?
- Quelles communes ont le plus de vacance ou de rotation des locataires ?
- Quelle part du parc est énergivore (DPE F ou G) ?

## Aperçu

_(captures d'écran à ajouter dans `docs/screenshots/`)_

## Architecture

```
Fichiers RPLS (SDES)  →  Python (pandas)  →  CSV nettoyé  →  Power BI
   data/raw/              scripts/            data/processed/    powerbi/
                          prepare_data.py                        (modèle en étoile + DAX)
```

## Données

| Millésime | Format | Lien |
|---|---|---|
| RPLS au 1er janvier 2025 | ZIP | https://www.statistiques.developpement-durable.gouv.fr/media/8938/download?inline |
| RPLS au 1er janvier 2024 | XLSX | https://www.statistiques.developpement-durable.gouv.fr/media/7970/download?inline |
| Années précédentes | — | https://www.statistiques.developpement-durable.gouv.fr/recherche?text=RPLS |

Les fichiers bruts ne sont pas versionnés (trop lourds). Les télécharger dans `data/raw/`
en gardant l'année dans le nom : `rpls_2025.zip`, `rpls_2024.xlsx`, etc.

## Lancer le projet

```bash
pip install -r requirements.txt
python scripts/prepare_data.py --explore   # voir la structure des fichiers
python scripts/prepare_data.py             # produit data/processed/rpls_communes_92.csv
```

Puis ouvrir `powerbi/rpls_92.pbix` dans Power BI Desktop.

## Stack

Python · pandas · Power BI (Power Query, modèle en étoile, DAX)

## Ce que j'ai appris

_(à compléter à la fin du projet)_
