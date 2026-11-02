# Exports CAO et 3D — Phase 3

Rapport d'état des exports. Chaque format est écrit par le projet lui-même,
avec la **bibliothèque standard uniquement** : aucun lecteur ni écrivain tiers
n'est embarqué. Le DXF et le STEP conservent la géométrie exacte (segments et
arcs de cercle) ; les trois formats de maillage (STL, OBJ, GLB) sont facettés à
une tolérance de corde déclarée dans le fichier et dans le manifeste.

> État : **Phase 3 terminée pour les cinq formats**. Les 2 231 profilés complets
> s'exportent sans erreur ; les 7 T restent refusés faute de pente de semelle et
> d'abscisse `x_tf` (EN 10055). Les fichiers produits ne changent rien au statut
> de licence : un profilé commercial reste `local_only`, et `verified` reste
> `false` partout.

## 1. Fichiers

| Fichier | Rôle |
|---|---|
| `app/exports/curve.py` | découpage des contours en tronçons ≤ 90°, tessellation, texte ASCII |
| `app/exports/dxf.py` | DXF R12 : polylignes fermées, arcs portés par les bulges |
| `app/exports/step.py` | STEP AP214 en B-REP exact : plans, cylindres, droites, cercles |
| `app/exports/mesh.py` | maillage fermé, STL binaire/ASCII, OBJ |
| `app/exports/glb.py` | glTF 2.0 binaire (GLB), un maillage non indexé |
| `app/exports/cli.py` | ligne de commande, nommage, manifeste et empreintes SHA-256 |
| `tests/test_exports.py` | 36 tests : découpage, étanchéité, structure des cinq formats, CLI |

Deux scripts de validation **optionnels** vivent dans `tools/` :
`validate_step.py` (OpenCASCADE) et `validate_dxf.py` (ezdxf). Ils ne sont ni
importés par l'outil ni requis à l'exécution ; voir §6.

Le module n'importe que `math`, `struct`, `json`, `hashlib`, `sqlite3` et la
géométrie du projet. Il peut être appelé depuis un script sans passer par la
ligne de commande. L'interface de bureau réutilise `export_selection`,
`build_manifest` et `write_manifest` : voir [`docs/gui.md`](gui.md).

## 2. Repère et unités

Tous les formats partagent la même convention, sans rotation ni mise à
l'échelle :

- la section est dans le plan `(X, Y)` avec `X = y` et `Y = z` du repère de
  section (voir [`docs/geometry.md`](geometry.md) §4) ;
- l'extrusion se fait selon `+Z`, de `Z = 0` à `Z = length` ;
- les longueurs sont en **millimètres**.

Le DXF déclare `$INSUNITS = 4` (millimètres) et `$MEASUREMENT = 1` (système
métrique). Le STEP déclare `SI_UNIT(.MILLI.,.METRE.)` et une incertitude de
`1.E-6` mm. Le GLB déclare `extras.units = "mm"`. Le STL et l'OBJ n'ont pas de
champ d'unité : l'en-tête et le commentaire le rappellent.

## 3. Découpage des arcs

Le noyau de géométrie peut produire un arc de n'importe quelle ouverture,
jusqu'au cercle complet. Les exports le découpent en tronçons d'au plus **90°**
(`MAX_SWEEP = π/2` dans `app/exports/curve.py`), pour deux raisons techniques :

- le DXF exprime un arc par un *bulge* `tan(θ/4)`, infini à 360° et
  numériquement fragile bien avant ;
- le STEP représenterait un cercle complet par une arête périodique dont les
  deux extrémités coïncident, topologie mal acceptée par certains noyaux.

Le découpage **ne change pas la géométrie** : chaque tronçon reste un arc du
même cercle, de même centre et de même rayon. Les extrémités des tronçons sont
chaînées : deux tronçons voisins partagent exactement le même point, condition
d'une topologie STEP étanche. Un arc de 90° a un bulge de `tan(π/8) ≈ 0,4142`,
valeur finie et bien conditionnée.

## 4. Exactitude par format

| Format | Géométrie | Facettage |
|---|---|---|
| DXF R12 | **exacte** : segments et arcs de cercle | aucun |
| STEP AP214 | **exacte** : plans et cylindres, arêtes droites et circulaires | aucun |
| STL | maillage triangulaire | tolérance de corde déclarée |
| OBJ | maillage triangulaire | tolérance de corde déclarée |
| GLB | maillage triangulaire | tolérance de corde déclarée |

### 4.1 DXF R12 (AC1009)

Chaque contour devient une `POLYLINE` fermée 2D. Un arc n'est jamais une
corde : il est porté par le code de groupe `42` (bulge) du sommet de départ,
avec `θ` l'ouverture signée du tronçon. Le contour extérieur est sur le calque
`PROFILE`, les trous sur `HOLES`.

Le fichier contient un en-tête minimal (`$ACADVER`, `$INSBASE`, `$EXTMIN`,
`$EXTMAX`, `$INSUNITS`, `$MEASUREMENT`), la table des deux calques et la section
`ENTITIES`. Tout est ASCII : les accents des désignations sont retirés
(`Carré` → `Carre`), jamais remplacés par des séquences dépendantes d'une page
de code.

Le format R12 est choisi pour sa compatibilité : pas de poignées, pas de table
obligatoire au-delà des calques, et support natif du bulge. Le fichier ne
contient ni cotation, ni texte, ni bloc : uniquement la section.

### 4.2 STEP AP214

Le solide est un `MANIFOLD_SOLID_BREP` unique, refermé par un `CLOSED_SHELL`.
La géométrie est **exacte** :

- une arête de contour droite est une `LINE` portée par un `VECTOR` de longueur
  exacte ;
- une arête de contour courbe est un `CIRCLE` de rayon exact ;
- une face latérale issue d'un segment est un `PLANE` ; issue d'un arc, un
  `CYLINDRICAL_SURFACE` de rayon exact ;
- les deux chapeaux sont des `PLANE` dont les boucles réutilisent les mêmes
  arêtes.

Pour un contour de `n` tronçons, la topologie est :

- arête basse `Eb_i` (`J_i → J_{i+1}`, `Z = 0`) et haute `Et_i` (`Z = length`) ;
- arête verticale `Ev_i` (`J_i` bas → `J_i` haut) ;
- face latérale `Eb_i` + `Ev_{i+1}` + `Et_i` inversée + `Ev_i` inversée ;
- chapeau bas : boucles inversées (normale `−Z`) ; chapeau haut : boucles
  directes.

Chaque `EDGE_CURVE` est référencée par exactement deux `ORIENTED_EDGE`, une fois
`.T.` et une fois `.F.` : c'est la condition de coque fermée, vérifiée par les
tests. Le fichier ne contient **aucune** `B_SPLINE` ni `POLY_LOOP` : la section
n'est jamais facettée.

Le module produit aussi la structure produit minimale attendue par les
lecteurs : `APPLICATION_CONTEXT`, `PRODUCT`, `PRODUCT_DEFINITION`,
`ADVANCED_BREP_SHAPE_REPRESENTATION`, `SHAPE_DEFINITION_REPRESENTATION`, unités
et contexte géométrique. Les noms non ASCII sont échappés en `\X2\…\X0\`.

**Limite assumée** : l'écriture STEP suppose **un seul contour extérieur**
(garanti par toutes les formes actuelles) ; une section à plusieurs extérieurs
serait refusée par `GeometryError` plutôt que mal exportée.

### 4.3 Maillages (STL, OBJ, GLB)

Les trois formats partagent le même maillage, construit par `build_mesh` :

1. les contours sont tessellés à la tolérance demandée (flèche maximale entre
   l'arc et la corde) ;
2. les chapeaux sont triangulés par **tranches horizontales** : entre deux cotes
   de sommets consécutives, les intersections sont des segments droits appariés
   par la règle pair-impair, ce qui traite les trous sans pont ni découpe
   d'oreille ;
3. les arêtes horizontales mitoyennes de deux tranches sont découpées aux
   **mêmes** abscisses, et les cotes séparées de moins de `1e-7` mm sont
   regroupées : la triangulation est conforme, sans fissure en T ;
4. chaque arête de contour devient une paroi (deux triangles), découpée aux
   mêmes cotes que les chapeaux.

Conséquence structurelle : **chaque arête du maillage est partagée par
exactement deux triangles**. Ce n'est pas seulement visuel — le volume signé
est celui d'un solide fermé. Le maillage est réorienté globalement si le volume
calculé est négatif.

Les tests vérifient l'étanchéité sur une section de chaque famille et le volume
comparé à `A × length`. Pour une frontière circulaire de rayon `R`, l'erreur
relative de volume d'un polygone inscrit vaut environ

```text
(4/3) · tolérance / R
```

car la tolérance est **absolue**, en millimètres. C'est négligeable pour les
profilés structuraux, mais pas pour les petits ronds : `Rond 5` (`R = 2,5 mm`)
atteint `2,6 × 10⁻²` à la tolérance par défaut de `0,05 mm`. Pour un petit
profilé rond, utiliser `--tolerance 0.005` ou moins.

Deux points de forme :

- **STL** : binaire par défaut (en-tête 80 octets, `uint32` de comptage, 50
  octets par facette) ; `--ascii-stl` pour le texte. Les coordonnées sont
  stockées en `float32`, comme le format l'impose.
- **OBJ** : sommets partagés, une normale par facette. Les numéros de sommets
  et de normales sont vérifiés par les tests.
- **GLB** : glTF 2.0 binaire, un seul maillage **non indexé** (chaque triangle
  porte ses trois sommets et sa normale), pour un rendu à facettes net sans
  couture de lissage. Les bornes `accessor.min/max` sont calculées sur les
  valeurs réellement stockées en `float32`.

## 5. Ligne de commande

```bash
# Un profilé, tous les formats, longueur 1 000 mm
python -m app.exports --profile "IPE/IPE 200" --out exports

# Toute une série, DXF et STEP seulement
python -m app.exports --series IPE --format dxf step --out exports/IPE

# Une catégorie, maillages fins
python -m app.exports --category commercial --format stl glb --tolerance 0.01

# Longueur et répertoire explicites
python -m app.exports --profile "CHS-CF/CHS 168.3x6" --length 2500 --out exports/chs
```

| Option | Effet |
|---|---|
| `--profile` | identifiant exact, répétable |
| `--series` | limite à une série (ex. `IPE`) |
| `--category` | `standard` ou `commercial` |
| `--limit` | nombre maximal de profilés |
| `--format` | `dxf step stl obj glb` ou `all` (défaut) |
| `--length` | longueur d'extrusion en mm (défaut `1000`) |
| `--tolerance` | flèche de corde maximale en mm (défaut `0.05`) |
| `--ascii-stl` | STL texte au lieu du binaire |
| `--out` | répertoire de sortie (défaut `exports`) |
| `--no-manifest` | ne pas écrire `manifest.json` |

Le nom de fichier est dérivé de l'identifiant : `/` devient `-`, les accents
sont retirés, tout le reste est conservé (`IPE/IPE 200` →
`IPE-IPE-200.step`, `AM-TES/Té 20x20x3` → `AM-TES-Te-20x20x3.step`).

Codes de sortie : `0` si tous les profilés demandés ont été exportés, `1` si au
moins un a été refusé (profilé inconnu ou incomplet), `2` si la sélection est
vide ou si un argument est invalide. Un refus n'interrompt pas les autres
exports : il est consigné dans le manifeste.

### Manifeste

`manifest.json` accompagne chaque export :

```json
{
  "tool": "SteelProfile",
  "formats": ["dxf", "step", "stl", "obj", "glb"],
  "length_mm": 1000.0,
  "tolerance_mm": 0.05,
  "profiles": [
    {
      "profile_id": "IPE/IPE 200",
      "category": "standard",
      "verified": false,
      "area_mm2": 2848.410657905736,
      "files": {"dxf": "IPE-IPE-200.dxf", "step": "IPE-IPE-200.step"},
      "sha256": {"dxf": "…", "step": "…"}
    }
  ],
  "failures": []
}
```

Chaque fichier est accompagné de son empreinte SHA-256, ce qui permet de
vérifier un export sans le régénérer. `verified` est toujours `false` : aucun
profilé n'est déclaré vérifié sans copie licite de la norme. Le manifeste ne
contient **ni dimension primaire ni valeur commerciale** au-delà de l'aire, et
ne constitue pas une redistribution du catalogue.

## 6. Validation

### 6.1 Tests

`tests/test_exports.py` (36 tests) vérifie, entre autres :

- le découpage (≤ 90°, chaînage exact, bulge fini, cercle complet découpé) ;
- la tessellation (points sur les cercles, flèche sous la tolérance) ;
- l'étanchéité du maillage sur une section de chaque famille, à deux
  tolérances, et l'absence de triangle dégénéré ;
- le volume comparé à `A × length`, et son amélioration quand la tolérance
  diminue ;
- la structure du DXF (entités, calques, bulges, ASCII) ;
- la taille binaire du STL, le comptage des facettes ASCII, les indices OBJ ;
- l'en-tête et les chunks du GLB, les bornes `accessor` ;
- l'audit des références STEP : chaque `EDGE_CURVE` référencée deux fois, une
  fois `.T.` et une fois `.F.`, aucune `B_SPLINE`, nombre de faces exact ;
- la ligne de commande : manifeste, empreintes, formats choisis, refus d'un
  profilé incomplet et d'un identifiant inconnu.

### 6.2 Maillages sur tout le catalogue

À la tolérance par défaut de `0,05 mm` et sur 1 000 mm de longueur :

| Contrôle | Résultat |
|---|---|
| profilés complets maillés | 2 231 (1 792 normalisés + 439 commerciaux) |
| maillages non étanches | **0** |
| pire erreur relative de volume | `2,55 × 10⁻²` (`AM-RONDS/Rond 5`, `R = 2,5 mm`) |

Pire écart relatif de volume par forme :

| Forme | Écart | Profilé |
|---|---|---|
| `FLAT` | `0` (exact) | — |
| `SQUARE` | `0` (exact) | — |
| `L` | `1,02 × 10⁻⁴` | `L 100x50x6` |
| `L_EQ` | `1,41 × 10⁻⁴` | `L 55x55x6` |
| `I_TAPERED` | `3,58 × 10⁻⁴` | `IPN 80` |
| `U_TAPERED` | `3,96 × 10⁻⁴` | `UPN 50` |
| `U` | `1,00 × 10⁻³` | `UPE 80` |
| `I` | `1,25 × 10⁻³` | `IPE 100` |
| `CHS` | `3,17 × 10⁻³` | `CHS 21.3x2.5` |
| `RHS` | `5,36 × 10⁻³` | `RHS 20x10x2` |
| `SHS` | `5,36 × 10⁻³` | `SHS 15x15x2` |
| `ROUND` | `2,55 × 10⁻²` | `Rond 5` |

L'écart suit la loi `(4/3) · tolérance / R` : il est nul sur les sections à
arêtes vives et ne devient sensible que lorsque le plus petit rayon de courbure
est petit. Il ne mesure pas la qualité du maillage — la flèche de corde est
respectée partout — mais la conséquence inévitable d'une tolérance **absolue**
sur une petite courbure. Réduire `--tolerance` réduit l'écart
proportionnellement.

### 6.3 STEP relu par un noyau indépendant

Les fichiers STEP ont été relus par **OpenCASCADE** via `cadquery-ocp`
(`8.0.1.1.0`, roue `cp313` Windows), installé dans un environnement virtuel
temporaire. Cet outil **n'est pas une dépendance du projet** : il ne sert qu'à
la validation de développement. Le script reproductible est
[`tools/validate_step.py`](../tools/validate_step.py).

```bash
python -m venv %TEMP%\stepcheck
%TEMP%\stepcheck\Scripts\python -m pip install cadquery-ocp
%TEMP%\stepcheck\Scripts\python tools\validate_step.py exports\step
```

| Contrôle | Résultat |
|---|---|
| fichiers relus | **1 792** (toute la catégorie normalisée) |
| `BRepCheck_Analyzer.IsValid()` | **1 792 / 1 792 valides** |
| solides par fichier | **1** partout |
| volume OCC vs `A × length` | écart maximal `1,61 × 10⁻¹¹` (`IPN`), aucun au-delà de `10⁻⁹` |
| faces par fichier | 6 à 22, conformes au découpage (`IPE 200` : 18 = 16 tronçons + 2 chapeaux) |

Un second contrôle a porté sur **20 profilés (un par série) exportés dans les
cinq formats** : les 20 STEP sont valides (1 solide, volume exact) et les 20 DXF
sont fermés, sans erreur d'audit, avec l'aire exacte. L'écart résiduel vient de
l'intégration numérique du noyau, pas de la géométrie : les faces sont des plans
et des cylindres exacts, sans aucun facettage.

### 6.4 DXF relu par ezdxf

Les 1 792 DXF de la catégorie normalisée ont été relus par **ezdxf**
(`1.4.5`), lui aussi installé dans un environnement virtuel jetable. Le script
[`tools/validate_dxf.py`](../tools/validate_dxf.py) vérifie la structure, le
caractère fermé des polylignes et reconstruit l'aire **exacte** à partir des
bulges (aire du triangle + aire du segment circulaire `(r²/2)(θ − sin θ)`),
puis la compare à l'aire du manifeste.

| Contrôle | Résultat |
|---|---|
| fichiers relus | **1 792** |
| polylignes fermées | **1 792 / 1 792** |
| `doc.audit()` sans erreur | **1 792 / 1 792** |
| aire reconstruite vs aire exacte | écart maximal `1,07 × 10⁻¹¹` (`UPN 300`) |
| entités par fichier | 1 (section pleine) ou 2 (extérieur + trou) |

L'aire lue depuis les bulges retrouve l'aire du moteur à la précision de la
machine : le DXF contient bien des arcs, pas des cordes.

## 7. Limites

- **Pas d'interface** : la Phase 3 est un moteur et une ligne de commande ; la
  Phase 4 apportera l'interface.
- **Pas de couleurs, matières, calques métier, cotations, assemblages** : un
  export = une section extrudée.
- **STEP** : un seul contour extérieur, pas de `B_SPLINE`, pas d'AP242, pas
  d'épaisseur de paroi.
- **Maillages** : facettés par construction ; la précision est une flèche de
  corde absolue, pas une erreur relative. Les très petites tolérances
  (`< 10⁻³ mm`) augmentent fortement le nombre de triangles.
- **STL** : coordonnées en `float32` ; pas de normales par sommet.
- **GLB** : non indexé, donc plus volumineux qu'un maillage indexé.
- **DXF** : R12 uniquement, deux calques, pas de spline (inutile ici).
- **Licence** : un export ne change pas le statut d'un profilé. Les profilés
  commerciaux restent `local_only` ; le catalogue normalisé reste soumis à sa
  licence (MIT pour SSDB, voir [`docs/licenses.md`](licenses.md)).
- **`verified`** : toujours `false` ; aucun export ne prétend à une conformité
  normative non vérifiée.

## 8. Provenance et licence

Le code des exports est original et peut être distribué avec le projet (MIT
recommandée). Aucune bibliothèque tierce n'est nécessaire à l'exécution :

- DXF, STL, OBJ, GLB et STEP sont écrits par le projet ;
- OpenCASCADE et ezdxf n'interviennent qu'en validation de développement, dans
  un environnement virtuel jetable, via `tools/` ; ils ne sont ni livrés ni
  requis ;
- les fichiers produits ne contiennent que la géométrie dérivée de la base
  locale ; ils n'emportent aucune donnée commerciale supplémentaire.

## 9. Commandes

```bash
# Tests unitaires et d'intégration complets
python -m unittest discover -s tests

# Un export rapide de contrôle
python -m app.exports --profile "IPE/IPE 200" --out exports

# Export STEP de toute la catégorie normalisée
python -m app.exports --category standard --format step --out exports/step

# Export de maillages fins pour une série
python -m app.exports --series CHS-HF --format stl glb --tolerance 0.01 --out exports/chs
```
