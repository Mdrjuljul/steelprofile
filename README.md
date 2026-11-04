# SteelProfile

Générateur local de profilés métalliques normalisés européens.
Application de bureau, 100 % hors ligne, consacrée à la **géométrie exacte** des
sections : recherche, consultation, reconstruction, export CAO/3D.

> État : **Phase 4 terminée** — catalogue, moteur de géométrie exacte, exports
> CAO/3D (DXF, STEP exact, STL, OBJ, GLB) et interface de bureau PySide6.
> Le moteur et les exports restent utilisables sans Qt, et `verified` reste
> `false` partout.

## Démarrage rapide

```bash
git clone https://github.com/Mdrjuljul/steelprofile
cd steelprofile
python -m pip install -r requirements.txt
python -m app.gui
```

Au **premier lancement**, `data/profiles.db` est construit automatiquement à
partir des données MIT livrées dans `data/sources/` (1 792 références, environ
une seconde). La base n'est pas versionnée : une base de travail locale peut
contenir des séries commerciales non redistribuables.

Sous Windows, `Lancer SteelProfile.bat` fait la même chose en double-clic.
Sans interface :

```bash
python -m app.exports --profile "IPE/IPE 200" --out exports
```

Si le catalogue est absent ou vide, l'interface et la CLI le reconstruisent
avant de l'ouvrir ; en cas de source manquante, le message indique exactement
ce qui manque. Voir [`app/database/bootstrap.py`](app/database/bootstrap.py).

## Ce qui existe aujourd'hui

| Élément | État |
|---|---|
| Catalogue SQLite (base locale complète) | 2 238 références, 21 séries, 7 familles sur 7 |
| dont normalisé (MIT, livré et publié) | 1 792 références, 16 séries |
| dont commercial local | 446 références, 5 séries, jamais redistribuées |
| Catalogue d'un clone | 1 792 références normalisées, construit au premier lancement |
| Séparation normalisé / commercial | `series.category`, garantie à l'import (§3.7) |
| Analyse des sources | 11 pistes examinées, 1 source normalisée + 1 catalogue fabricant local |
| Licences | tranchées, redistribution encadrée |
| Moteur géométrique | 2 231 profilés complets reconstruits, 0 échec ; 7 T refusés (données manquantes) |
| Exports | DXF et STEP exacts, STL, OBJ, GLB — 5 formats, bibliothèque standard seule |
| Interface | PySide6 : catalogue, recherche, aperçu exact, propriétés, export |

Les rapports détaillés sont dans [`docs/catalogue.md`](docs/catalogue.md) (Phase 1),
[`docs/geometry.md`](docs/geometry.md) (Phase 2),
[`docs/exports.md`](docs/exports.md) (Phase 3) et
[`docs/gui.md`](docs/gui.md) (Phase 4).

## Contenu du catalogue

| Famille | Séries | Références | dont commerciales |
|---|---|---|---|
| I | IPE, IPN | 39 | 0 |
| H | HEA, HEB, HEM | 72 | 0 |
| U | UPN, UPE | 32 | 0 |
| L | cornières égales et inégales | 81 | 0 |
| T | Tés (gamme commerciale) | 7 | 7 |
| Creux | SHS, RHS, CHS (finis à chaud et formés à froid) | 1 506 | 0 |
| Pleins | plats, ronds, carrés | 501 | 439 |
| **Total** | **21 séries** | **2 238** | **446** |

Les 7 T sont importés mais **incomplets** : le catalogue ne publie ni la pente
des semelles ni la position de mesure de `tf`, donc aucune géométrie n'est
reconstructible. Les plats, ronds et carrés sont couverts par le programme
commercial, avec une géométrie exacte par désignation, mais hors du champ
normalisé. Voir `docs/sources.md` §11 et §12.

## Données locales (`data/staging/`)

Les séries dont la provenance n'autorise pas la redistribution (copie d'une norme
achetée, programme fabricant) s'importent depuis `data/staging/`, jamais livré
avec le projet :

```bash
python app/database/import_data.py
```

Ces séries sont marquées `local_only`, portent une anomalie `LOCAL_ONLY_DATA` et
sont **exclues** de `data/catalogue_inventory_redistributable.csv`. Une gamme
commerciale se déclare en outre `category = "commercial"` avec un
`commercial_ref` obligatoire : elle n'est jamais confondue avec une référence
normalisée (§3.7).

Le dépôt local actuel contient le **catalogue ArcelorMittal 2020** (5 séries,
446 références) : ronds, carrés, plats, larges plats et Tés. Le PDF source reste
dans `data/sources/` mais n'est pas redistribuable, et la base de travail
construite avec ce dépôt ne l'est pas non plus. Contrat de fichier :
[`data/staging/README.md`](data/staging/README.md).

## Base de données

`data/profiles.db` est générée, jamais éditée à la main.

```bash
python app/database/import_data.py
```

Elle est également construite automatiquement au premier lancement de
l'interface ou de la CLI, via `app/database/bootstrap.py`. La commande explicite
ci-dessus reste la voie de référence et la seule qui importe `data/staging/`.

Le script n'utilise que la bibliothèque standard (Python ≥ 3.11 pour `tomllib`).
Il lit les tables de `data/sources/Steel_Section_Database-main/` et, si présent,
le dépôt `data/staging/`, puis réécrit :

- `data/profiles.db` — la base de travail (2 238 références) ;
- `data/catalogue_inventory.csv` — le catalogue à plat ;
- `data/catalogue_stats.json` — comptages et anomalies ;
- `data/catalogue_inventory_redistributable.csv` — uniquement si des séries
  locales existent, sans elles (1 792 références).

Pour produire une base **publiable**, reconstruire avec un répertoire de staging
vide :

```bash
python app/database/import_data.py --staging <dir-vide> \
       --db <tmp>/profiles.db --stats <tmp>/catalogue_stats.json
python app/database/check_catalogue.py --publish --db <tmp>/profiles.db
```

Schéma commenté : [`app/database/schema.sql`](app/database/schema.sql).

## Moteur géométrique (`app/geometry/`)

Chaque section est reconstruite depuis ses dimensions primaires comme un
ensemble de contours fermés de **segments et d'arcs de cercle exacts** : aucun
congé n'est remplacé par une corde ou un chanfrein. Les aires, centres de
gravité, moments quadratiques et modules élastiques sont obtenus par intégration
de Green en forme close (voir [`docs/geometry.md`](docs/geometry.md)).

Le moteur ne dépend que de la bibliothèque standard et n'a besoin d'aucune
interface. Les dimensions manquantes ne sont jamais comblées : un profilé dont
un paramètre requis est `NULL` est refusé.

```bash
# Tests unitaires et d'intégration
python -m unittest discover -s tests

# Reconstruction et comparaison aux valeurs publiées
python -m app.geometry.verify

# Une série, une catégorie, ou les anomalies de masse en échec
python -m app.geometry.verify --series IPE
python -m app.geometry.verify --category standard --verbose
python -m app.geometry.verify --strict
```

Utilisation comme bibliothèque :

```python
from app.geometry.build import connect, build_profile
from app.geometry.properties import section_properties

con = connect()
properties = section_properties(build_profile(con, "IPE/IPE 200"))
print(properties.catalogue_values()["Iy"], "cm4")
```

Résultat : 2 231 profilés reconstruits (1 792 normalisés + 439 commerciaux),
aucun échec géométrique ; l'erreur relative maximale sur les séries normalisées
est de `4,87 × 10⁻⁶`. Les 7 T restent non constructibles faute de pente de
semelle et d'abscisse `x_tf` (EN 10055).

## Exports (`app/exports/`)

Cinq formats sont écrits par le projet lui-même, sans aucune dépendance
externe. Le **DXF** et le **STEP** conservent la géométrie exacte (segments et
arcs de cercle) ; le **STL**, l'**OBJ** et le **GLB** sont des maillages fermés,
facettés à une tolérance de corde déclarée. Détail, validation et limites :
[`docs/exports.md`](docs/exports.md).

```bash
# Tous les formats pour un profilé (longueur 1 000 mm par défaut)
python -m app.exports --profile "IPE/IPE 200" --out exports

# Toute une série, en DXF et STEP
python -m app.exports --series IPE --format dxf step --out exports/IPE

# Maillages fins
python -m app.exports --profile "CHS-CF/CHS 168.3x6" --format stl glb --tolerance 0.01
```

Repère commun : la section est dans le plan `(X, Y) = (y, z)`, l'extrusion va
de `Z = 0` à `Z = length`, en millimètres. Chaque arc est découpé en tronçons
d'au plus 90° **sans changer sa géométrie** (bulge DXF fini, arêtes STEP non
périodiques). Un `manifest.json` accompagne l'export avec l'aire, la longueur,
la tolérance et l'empreinte SHA-256 de chaque fichier ; `verified` y reste
`false`.

Les 2 231 profilés complets produisent des maillages étanches (chaque arête
partagée par exactement deux triangles), et les STEP relus par OpenCASCADE en
validation de développement sont des solides valides, au volume exact.

## Interface de bureau (`app/gui/`)

L'interface est un client du moteur et des exports : elle ne contient aucune
formule de géométrie et aucune règle d'écriture de fichier. PySide6 n'est requis
que pour cette couche, et il est importé paresseusement : `app.geometry` et
`app.exports` fonctionnent sans Qt.

```bash
# Une seule fois
python -m pip install -r requirements-gui.txt

# Lancement
python -m app.gui
python -m app.gui --profile "IPE/IPE 200"
```

La fenêtre présente le catalogue en trois panneaux : arbre famille → série →
profilé avec recherche (`ipé 200`, `HEA`, `168.3x6`) et filtre
normalisé/commercial ; aperçu 2D **exact** (arcs réels, trous compris, zoom et
déplacement) ; dimensions avec leur provenance, propriétés calculées face aux
valeurs publiées avec l'écart rapporté à la tolérance de `verify`, et réserves.
Les profilés incomplets restent visibles mais sont refusés à l'export : l'aperçu
affiche un refus explicite et les propriétés restent vides, avec la liste exacte
des paramètres manquants.

L'export reprend `app.exports.cli` (mêmes formats, nommage, manifeste et
empreintes) et s'exécute dans un fil de fond avec sa propre connexion SQLite.
Détail de l'architecture, des tests hors écran et des limites :
[`docs/gui.md`](docs/gui.md).

## Principes non négociables

1. **Aucune valeur inventée.** Une dimension absente reste `NULL` et la référence
   est marquée incomplète.
2. **Aucune approximation géométrique.** Les congés sont des arcs, pas des
   chanfreins ; les rayons non documentés ne sont pas ajoutés.
3. **La provenance est une donnée.** Chaque valeur porte son origine (table ou
   règle normative) et sa série source.
4. **Un profilé non vérifié n'est pas déclaré exact.** `verified = 0` tant que la
   géométrie n'a pas été contrôlée contre une source normative licite.
5. **Le procédé fait partie de l'identité.** Un SHS fini à chaud et un SHS formé
   à froid ne sont pas le même profilé.

## Documentation

| Fichier | Contenu |
|---|---|
| [`docs/catalogue.md`](docs/catalogue.md) | rapport Phase 1 : inventaire, manques, schéma, limites |
| [`docs/geometry.md`](docs/geometry.md) | rapport Phase 2 : moteur exact, conventions, validation, limites |
| [`docs/exports.md`](docs/exports.md) | rapport Phase 3 : formats, exactitude, tessellation, CLI, validation |
| [`docs/gui.md`](docs/gui.md) | rapport Phase 4 : architecture, aperçu exact, export, tests, limites |
| [`docs/sources.md`](docs/sources.md) | analyse détaillée des 11 pistes examinées |
| [`docs/licenses.md`](docs/licenses.md) | licences et droits de redistribution |
| [`data/staging/README.md`](data/staging/README.md) | contrat d'import des séries locales |
| [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md) | licences MIT (données), LGPLv3 (PySide6), données commerciales |

## Feuille de route

- **Phase 2** — ~~moteur géométrique : IPE → HEA/HEB → UPN/UPE → cornières → creux~~ **terminée**.
- **Phase 3** — ~~exports STEP, DXF, OBJ, STL, GLB~~ **terminée**.
- **Phase 4** — ~~interface PySide6 : catalogue, aperçu, propriétés, export~~ **terminée**.
- **Phase 5** — extension : géométrie des T (EN 10055), séries IPE A/AA/O/V, HE C.

## Licence

Code sous **MIT** (voir [`LICENSE`](LICENSE)). Données normalisées : Steel
Section Database (MIT, avec notice). Données commerciales : usage local
seulement, non redistribuées. PySide6/Qt : LGPLv3, installé séparément. Détail :
[`docs/licenses.md`](docs/licenses.md) et
[`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md).
