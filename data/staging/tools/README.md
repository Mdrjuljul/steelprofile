# `data/staging/tools/` — utilitaires d'extraction ArcelorMittal 2020

Ces scripts rejouent l'extraction du catalogue ArcelorMittal 2020 vers le dépôt
local `data/staging/AM-*`. Ils font partie du répertoire `data/staging/`, donc
**ils ne sont jamais distribués** avec le projet.

| Fichier | Rôle |
|---|---|
| `extract_pdf.py` | décompresse les flux PDF et en extrait le texte positionné (bibliothèque standard seule : `re`, `zlib`) |
| `am_parse.py` | socle commun : `PDF`, `DATA`, `STREAMS`, `row_runs()`, `num()` |
| `am_extract.py` | lecture des tableaux et recoupement par les colonnes masse / surface ; affiche le rapport de contrôle |
| `am_staging.py` | écrit `data/staging/AM-*.csv`, `AM-*.toml` et `generated/properties/AM-*.csv` |

## Prérequis

Le PDF n'est pas versionné. Le placer ici :

```
data/sources/Arcelor-Catalogue-Web-2020-avec-liens-bouton-light.pdf
```

Empreinte attendue (SHA-256) :

```
3c23ac7d2b0af6c420343e23aa857326eaade571cd7e6b16b43d2e4fdbae0d82
```

`am_staging.py` recalcule et affiche cette empreinte au démarrage ; toute
différence signifie que le document n'est pas l'édition 2020 utilisée pour le
dépôt, et l'extraction ne doit pas être considérée comme reproductible.

## Exécution

Depuis la racine du projet :

```bash
python data/staging/tools/am_extract.py    # rapport de contrôle, n'écrit rien
python data/staging/tools/am_staging.py    # régénère le dépôt AM-*
```

## Reproductibilité vérifiée

Régénérer le dépôt avec ces scripts produit des fichiers **identiques octet pour
octet** aux 15 fichiers déjà présents (5 CSV de séries, 5 TOML, 5 CSV de
propriétés publiées) : mêmes empreintes SHA-256 avant et après exécution.

Les compteurs attendus sont : ronds 69, carrés 28, plats 288, larges plats 54,
tés 7 retenus sur 9 lus (T 25\* et T 45\* écartés, jamais corrigés).

## Règles appliquées

- aucune valeur inventée, interpolée ou arrondie au-delà du tableau ;
- une ligne dont les deux colonnes dérivées contredisent les dimensions est
  **écartée**, jamais corrigée ;
- une coquille d'une seule colonne dérivée est consignée en note, la valeur
  fautive n'est pas recopiée dans `derived_property` ;
- le troisième rayon `r3` n'est pas mappé (signification non documentée).

Après régénération, reconstruire la base et contrôler :

```bash
python app/database/import_data.py
python app/database/check_catalogue.py
```
