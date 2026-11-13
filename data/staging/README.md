# `data/staging/` — séries locales sous licence

Ce répertoire est le **point de dépôt local** pour les séries qui ne peuvent pas
être livrées avec le projet : tableaux d'une norme achetée, programme commercial
d'un fabricant autorisé, données fournies par l'utilisateur.

**Ce répertoire n'est jamais distribué avec le projet.** Les séries qui y sont
importées sont marquées `usage = 'local_only'`, `redistribution = 'restricted'`
(par défaut), tracées par une anomalie `LOCAL_ONLY_DATA`, et exclues de
`data/catalogue_inventory_redistributable.csv`.

Exemple réel : les douze séries `AM-*` (catalogue ArcelorMittal 2020 — ronds,
carrés, plats, larges plats, T, tôles trapézoïdales et tôle sinusoïdale) sont
déposées ici, avec leurs fichiers `generated/properties/`. Une base construite
avec ce dépôt peuplé n'est **pas** redistribuable ; voir la dernière section.

Les utilitaires qui régénèrent ce dépôt depuis le PDF sont dans
`data/staging/tools/` (voir son `README.md`) ; ils ne sont pas distribués non
plus. Le PDF source doit se trouver dans `data/sources/` avec l'empreinte
SHA-256 documentée dans `docs/sources.md` §12.

## Contrat de fichier

Une série = **deux fichiers de même nom** dans ce répertoire :

```
data/staging/T-EN10055.toml   métadonnées et provenance
data/staging/T-EN10055.csv    une ligne par référence
```

### Le TOML

```toml
id = "T-EN10055"                  # OBLIGATOIRE — identifiant unique de série
shape = "T_TAPERED"               # OBLIGATOIRE — voir tableaux ci-dessous
title = "Profilés T laminés EN 10055"
standard = "EN 10055:1995"        # doit correspondre à un standard_id connu
process = "hot_rolled"            # hot_rolled | cold_formed | welded | ...
category = "standard"             # standard | commercial (§3.7)
commercial_ref = ""               # OBLIGATOIRE si category = "commercial"

# --- provenance (OBLIGATOIRE) ---------------------------------------
source_id = "fr-boutique-normes-2026"   # OBLIGATOIRE, unique
source_name = "Copie licite EN 10055 (achat 2026-10)"
source_kind = "standard"          # repository | website | standard | manufacturer | dataset
source_license = "Copie personnelle, non redistribuable"
source_license_url = ""           # facultatif
source_version = "EN 10055:1995"  # facultatif
redistribution = "restricted"     # allowed | restricted | unknown | not_applicable
source_note = "Tableau 1, saisie manuelle contrôlée."

# --- blocage de forme (facultatif, avant toute table) --------------
# Motifs pour lesquels la forme réelle n'est PAS constructible même si
# toutes les cotes sont présentes : nervures non cotées, sommet arrondi,
# absence de coupe cotée, sinusoïde… Chaque motif force le statut
# `incomplete` de toutes les lignes de la série et une anomalie
# bloquante UNDIMENSIONED_FEATURE.
# blocking = [
#     "le plateau bas porte des nervures non cotées ; le trapèze simple ne les représente pas",
# ]

# --- désignations --------------------------------------------------
[designation]
pattern = "T {h}x{b}x{tf}"        # {…} remplacés par les nombres de la désignation, dans l'ordre
aliases = ["T{h}x{b}x{tf}"]

# --- manques déclarés (facultatif) ---------------------------------
# Paramètres que la source ne publie PAS. Leur absence devient un fait
# documenté : la référence est importée `incomplete` et bloquée par
# MISSING_PARAMETER. Un paramètre manquant non déclaré ici fait échouer
# tout l'import local.
[missing]
slope_pct = "non publiée par la source ; définie par la norme, non détenue"
x_tf = "position de mesure non publiée par la source"

# --- propriétés publiées par la source (facultatif) -----------------
# Recopiées telles quelles dans `derived_property`, jamais recalculées :
# elles ne valident pas la géométrie (independent = 0).
[conventions.mass]
method = "masse linéique publiée par le fabricant"
[conventions.A]
method = "section publiée par le fabricant"
```

`source_id` est **obligatoire** : sans lui, l'import s'arrête avec une erreur
explicite. Un même `source_id` peut couvrir plusieurs séries (le premier TOML
rencontré enregistre la source ; les suivants la réutilisent).

Un BOM UTF-8 en tête de fichier (réenregistrement par un éditeur Windows) est
toléré. Les nombres des colonnes CSV utilisent le **point décimal** ; les notes
en prose peuvent utiliser la virgule. Une **désignation** qui contient une
virgule décimale (par exemple `TRAPEZA 3.333.39T e0,63`) doit être **quotée**,
sinon la virgule coupe la ligne en deux champs.

### Catégorie commerciale (§3.7)

Le cahier des charges autorise des dimensions commerciales « dans une catégorie
distincte, sans les confondre avec les références normalisées ». Cette séparation
est imposée par le schéma :

```toml
category = "commercial"
commercial_ref = "Programme fabricant X, édition 2026"
```

Règles appliquées à l'import :

- une série `commercial` **ne peut pas** déclarer `standard` (erreur explicite) ;
- `commercial_ref` est **obligatoire** (programme, fabricant, édition) ;
- `commercial_ref` sans `category = "commercial"` est refusé ;
- la série reçoit une anomalie `COMMERCIAL_DATA` et apparaît dans
  `v_series_stats` avec `category = 'commercial'` ;
- elle reste exclue de l'export redistribuable tant que `redistribution`
  n'est pas `allowed`.

Une dimension commerciale n'est **jamais** présentée comme une référence
normalisée, même si sa géométrie est exacte (c'est le cas des plats, carrés et
ronds, entièrement définis par `b×t`, `a×a`, `ØD`).

`redistribution = "allowed"` n'est à utiliser que si vous disposez d'une
autorisation écrite ; la série sera alors incluse dans l'export redistribuable,
sous votre responsabilité.

### Le CSV

Première colonne `designation`, puis les paramètres de la forme, dans n'importe
quel ordre. Une colonne facultative `note` peut suivre : elle est recopiée dans
`profile.notes` et sert à consigner une réserve de la source (coquille d'une
colonne dérivée, taille hors norme, valeur écartée).

Les valeurs sont décimales, **point décimal**, en millimètres. **Aucune valeur
inventée ou interpolée** : une valeur inconnue reste vide *et* doit être déclarée
dans `[missing]`, sinon l'import local est refusé.

```
designation,b,t,note
Plat 80x35,80,35,"masse et surface imprimées incohérentes ; dimensions seules retenues"
```

### Tôles profilées

```
designation,pitch,depth,crest,trough,t,r,note
"TRAPEZA 6.175.25B e0,63",175,25,75,35,0.63,,
```

La désignation porte une virgule décimale : elle est quotée. `r` (rayon de
pliage extérieur) reste vide et doit être déclaré dans `[missing]` tant que la
source ne le publie pas.

## Colonnes par forme

| `shape` | Paramètres | Remarques |
|---|---|---|
| `FLAT` | `b, t` | plat : largeur × épaisseur |
| `ROUND` | `D` | rond plein : diamètre |
| `SQUARE` | `a` | carré plein : côté |
| `T_TAPERED` | `h, b, tw, tf, r1, r2, slope_pct, x_tf` | **modèle provisoire**, voir ci-dessous |
| `TRAPEZOIDAL` | `pitch, depth, crest, trough, t, r` | tôle trapézoïdale, **un module = un pas**, voir ci-dessous |
| `SINUSOIDAL` | `pitch, depth, t` | tôle ondulée sinusoïdale : importable, **jamais constructible** |

Une colonne `note` facultative est acceptée pour toutes les formes.

Les trois formes pleines (`FLAT`, `ROUND`, `SQUARE`) n'ont **ni rayon ni
raccordement** : leur géométrie est entièrement définie par la désignation. Il n'y
a donc aucune valeur à approximer.

### Manques déclarés (`[missing]`)

Un paramètre absent du tableau n'est acceptable que si le TOML le déclare :

```toml
[missing]
slope_pct = "non publiée par le catalogue ; la pente est définie par EN 10055"
```

À l'import :

- la valeur reste `NULL` dans `profile_param`, avec le motif en `note` ;
- la référence passe en `geometry_status = 'incomplete'` ;
- une anomalie **bloquante** `MISSING_PARAMETER` cite le paramètre et son motif ;
- un paramètre absent **non déclaré** fait échouer tout l'import local
  (politique de sévérité ci-dessous) ;
- une clé `[missing]` inconnue pour la forme est refusée (faute de frappe
  probable).

Un manque déclaré n'est donc pas une donnée manquante par accident : c'est une
propriété documentée de la source.

### Formes non constructibles (`blocking`)

Certaines sources publient toutes les cotes utiles et, malgré cela, la forme
réelle n'est pas représentable exactement : nervures non cotées dans un plateau,
sommet arrondi, absence totale de coupe cotée, onde sinusoïdale. Le TOML le
déclare une fois pour la série :

```toml
blocking = [
    "le plateau bas porte trois nervures par onde qui ne sont pas cotées",
]
```

À l'import :

- toutes les lignes de la série passent en `geometry_status = 'incomplete'`,
  **même si aucun paramètre ne manque** ;
- une anomalie bloquante `UNDIMENSIONED_FEATURE` cite les motifs, au niveau de
  la série ;
- la géométrie n'est jamais approximée : aucun générateur de remplacement n'est
  appelé, et l'export reste refusé ;
- `blocking` doit être une liste de textes non vides, placée **avant la première
  table** du TOML (sinon elle appartiendrait à cette table).

Un produit simplement dépourvu de rayon n'a pas besoin de `blocking` : le
`[missing]` sur `r` suffit. Le blocage est réservé aux cas où **même avec toutes
les cotes** le modèle ne décrit pas la tôle réelle.

### Propriétés publiées (`generated/properties/`)

Un fichier facultatif par série, au même nom que la série, dans
`data/staging/generated/properties/<SÉRIE>.csv` :

```
designation,mass_kg_m,A_cm2,surf_m2_m
Rond 20,2.47,3.14,
```

Pour une tôle, la propriété publiée est une masse **surfacique**, et la colonne
s'appelle `mass_area_kg_m2` :

```
designation,mass_area_kg_m2
"TRAPEZA 6.175.25B e0,63",5.58
```

- la première colonne est la désignation exacte du CSV de la série ;
- les autres colonnes sont des propriétés **publiées par la source** (`mass_kg_m`,
  `A_cm2`, `surf_m2_m`, etc.), pas des valeurs recalculées ;
- elles sont stockées dans `derived_property` avec `independent = 0` ; elles
  documentent la source mais **ne valident jamais** la géométrie ;
- une cellule vide ou `unsupported` donne `status = 'unsupported'` ;
- une valeur publiée fausse (masse incohérente, par exemple) ne doit pas être
  recopiée : laisser la cellule vide et l'expliquer dans la colonne `note` du
  CSV de série.

### `T_TAPERED` — provisoire

Le modèle de forme des T de EN 10055 (semelles inclinées, âme inclinée) est
**déduit des paramètres publiés par Dlubal**, pas validé contre la norme :

- `h` hauteur totale, `b` largeur de semelle ;
- `tw` épaisseur d'âme, `tf` épaisseur de semelle (**`tw ≠ tf`**) ;
- `r1`, `r2` rayons de raccordement (âme/semelle et extrémité de semelle) ;
- `slope_pct` pente des faces, en % ;
- `x_tf` position de la mesure de `tf` sur la semelle.

Tant que ce modèle n'a pas été confronté à une copie licite de EN 10055, une
série `T_TAPERED` importée ne doit pas servir à reconstruire une section : elle
documente des dimensions, pas une géométrie validée.

### `TRAPEZOIDAL` — tôle trapézoïdale

Un module couvre **un pas** ; la largeur utile commerciale (1 000, 1 050 mm…) est
une donnée de catalogue, pas une cote de la section.

- `pitch` pas de l'onde, `depth` profondeur, `t` épaisseur de tôle ;
- `crest` plateau haut, `trough` plateau bas, mesurés entre les **intersections
  théoriques** avant congés ;
- `r` rayon de pliage **extérieur** ;
- l'angle des âmes n'est pas un paramètre : il découle de `pitch`, `depth`,
  `crest` et `trough`.

Le module est centré sur `y = 0` (plateau haut au milieu, deux demi-creux aux
bords) ; la face extérieure du creux est en `z = 0`, la matière en dessous. Les
plis sont des arcs de cercle vrais, et la face intérieure est l'offset exact à
`t` (arcs concentriques `r + t` aux creux, `r − t` aux sommets). Le générateur
refuse `r ≤ t`, un pas trop court pour les plateaux, ou un congé qui consomme
tout le plateau ou toute l'âme.

**Aucun rayon n'est déduit d'une masse.** Le catalogue ArcelorMittal ne publie
aucun rayon de pliage : `r` reste vide et déclaré dans `[missing]`. Les produits
dont la forme réelle n'est pas un trapèze (nervures, sommet arrondi, aucune
coupe) portent en plus `blocking`.

La masse surfacique se recoupe par `kg/m² = 7,85 × A_module / pitch`, mais elle
n'est **pas** recalculée dans la base : la valeur publiée reste la seule
propriété stockée.

### `SINUSOIDAL` — onde non représentable

Une sinusoïde n'est pas une suite de segments et d'arcs de cercle : le
générateur `sinusoidal_sheet` refuse explicitement la construction au lieu de
l'approximer. La série reste importable (`pitch`, `depth`, `t`), avec
`blocking`, pour documenter le produit et sa provenance ; elle ne produira
jamais de section ni d'export.

## Import

```bash
python app/database/import_data.py                 # base principale + data/staging
python app/database/import_data.py --staging <dir> # autre dépôt
```

Contrôles automatiques à l'import :

| Contrôle | Comportement |
|---|---|
| `source_id` absent | arrêt : champ obligatoire |
| `redistribution` / `source_kind` invalides | arrêt avec la valeur refusée |
| `shape` inconnue | arrêt, liste des formes gérées affichée |
| `category` hors `standard` / `commercial` | arrêt |
| `commercial` + `standard` | arrêt : catégories confondues (§3.7) |
| `commercial` sans `commercial_ref` | arrêt |
| `id` de série déjà utilisé | arrêt : série en double |
| `[missing]` : clé inconnue pour la forme | arrêt : faute de frappe probable |
| paramètre requis vide **non déclaré** dans `[missing]` | **arrêt** : une série locale est refusée plutôt qu'incomplète |
| paramètre requis vide **déclaré** dans `[missing]` | import `incomplete` + anomalie bloquante `MISSING_PARAMETER` |
| `blocking` non-liste ou texte vide | arrêt : le blocage doit être explicite |
| `blocking` non vide | série entière `incomplete` + anomalie bloquante `UNDIMENSIONED_FEATURE`, même si toutes les cotes sont présentes |
| géométrie infaisable (ex. `D = 0`) | **arrêt** : idem |
| colonne `note` | recopiée dans `profile.notes`, sans contrôle de contenu |

En cas d'arrêt, **aucune base n'est écrite** : la base partiellement construite et
les inventaires CSV sont supprimés, ce qui évite de laisser un catalogue tronqué
derrière un import refusé. Le message indique la référence et la ligne CSV
(`A/R 10 (ligne 2) — faisabilité : D doit être > 0`).

Cette sévérité est propre aux séries locales : les tables du dépôt MIT, elles,
conservent la politique d'origine (une ligne infaisable y est enregistrée avec le
statut `infeasible` et une anomalie bloquante, comme le font les deux RHS-HF
exclues).

## Vérification après import

```bash
python app/database/check_catalogue.py            # base de travail (avec ce dépôt)
python app/database/check_catalogue.py --publish --db <chemin>  # base publiable
```

Puis, dans la base :

```sql
SELECT * FROM source WHERE usage = 'local_only';
SELECT * FROM catalog_issue WHERE code = 'LOCAL_ONLY_DATA';
SELECT * FROM catalog_issue WHERE code = 'MISSING_PARAMETER';
SELECT COUNT(*) FROM profile p JOIN series s USING (series_id)
  JOIN source sr USING (source_id) WHERE sr.redistribution <> 'allowed';
```

Le second inventaire `data/catalogue_inventory_redistributable.csv` n'est écrit
que si des séries locales existent ; il ne contient aucune d'entre elles.

Avec le dépôt `AM-*` actuel, les compteurs attendus sont : 2 259 profils
(1 792 normalisés + 467 commerciaux), 12 séries commerciales, 467 lignes absentes
de l'export redistribuable, 28 profils `incomplete` (7 T + 21 tôles), 26 anomalies
bloquantes `MISSING_PARAMETER` et 5 anomalies `UNDIMENSIONED_FEATURE` (nervures,
sommet arrondi, absence de coupe, sinusoïde). Aucune tôle n'est `complete`.

## Avant de publier

1. Vider ce répertoire (ou l'exclure explicitement de l'archive livrée), y compris
   `generated/`.
2. Reconstruire la base sans `data/staging/` et vérifier avec
   `check_catalogue.py --publish` : 1 792 profils, 0 série commerciale, 0 série
   locale, aucune entrée `source` en `local_only`.
3. Ne pas joindre le PDF du catalogue fabricant à la publication.
4. Ne jamais présenter une série locale comme une référence normalisée vérifiée :
   `verified` reste à 0.
