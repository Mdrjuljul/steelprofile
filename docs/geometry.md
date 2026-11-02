# Moteur géométrique — Phase 2

Rapport d'état du moteur de géométrie exacte. Il reconstruit la section d'un
profilé à partir de ses dimensions primaires, sans interface et sans export :
la Phase 2 se limite à la géométrie et aux propriétés élastiques qui la
vérifient.

> État : **Phase 2 terminée pour les 2 231 profilés complets** (1 792 normalisés
> + 439 commerciaux). Les 7 profilés T restent non constructibles faute de pente
> de semelle et d'abscisse `x_tf` (EN 10055). Aucune géométrie n'est déclarée
> « vérifiée » au sens normative : la validation porte sur la cohérence interne
> et sur les valeurs publiées de la base.

## 1. Fichiers

| Fichier | Rôle |
|---|---|
| `app/geometry/contour.py` | segments et arcs exacts, contours fermés, intégrales de Green en forme close |
| `app/geometry/shapes.py` | générateurs par forme (I, U, L, tubes, pleins), validation des paramètres |
| `app/geometry/properties.py` | aire, centre de gravité, moments, modules élastiques, rayons de giration, masse, surface |
| `app/geometry/build.py` | lecture SQLite, contrôle des paramètres requis, construction |
| `app/geometry/verify.py` | comparaison aux valeurs publiées, rapport et code de sortie |
| `tests/` | formes closes, arcs, convention de repère, intégration à la base |

Le moteur ne dépend que de la bibliothèque standard. Il n'importe ni CadQuery,
ni Open CASCADE, ni le moteur SSDB : celui-ci sert uniquement d'oracle de
compréhension et de référence documentaire.

## 2. Exactitude

Une section est un ensemble de contours fermés :

- contour extérieur orienté dans le sens trigonométrique (aire positive) ;
- trous orientés dans le sens horaire (aire négative).

Les primitives sont des **segments** et des **arcs de cercle exacts**. Un congé
n'est jamais remplacé par une corde, un chanfrein ou un polygone. Les rayons
inconnus ne sont pas inventés : ils restent absents et la construction échoue.

Les moments sont obtenus par intégration de Green le long de la frontière, en
forme close :

```text
A   = ½ ∮ (y dz − z dy)
Qy  = ∫ z dA = −½ ∮ z² dy
Qz  = ∫ y dA =  ½ ∮ y² dz
Iy  = ∫ z² dA = ∮ y z² dz
Iz  = ∫ y² dA = −∮ y² z dy
Iyz = ∫ y z dA = ¼ (∮ y² z dz − ∮ y z² dy)
```

Pour un segment, les intégrandes sont des polynômes en `t` et s'intègrent
exactement. Pour un arc `(y, z) = (a + R cos t, b + R sin t)`, les intégrandes
deviennent des monômes `sin^p t · cos^q t`, intégrés par la récurrence exacte de
`_int_sin_cos` ; aucune quadrature numérique n'intervient. Les bornes en `y` et
`z` incluent les extrema des arcs (`cos t = 0`, `sin t = 0`), ce qui donne des
modules élastiques exacts même quand l'extrémité de l'arc est un point courant.

Les seules erreurs sont donc les arrondis flottants de la bibliothèque standard,
de l'ordre de `1e-15` en relatif.

## 3. Conventions de repère

Les conventions sont celles de `docs/CONVENTIONS.md` du dépôt SSDB, reprises
pour que les valeurs publiées soient comparables sans transformation :

| Forme | Origine | Orientation |
|---|---|---|
| `I`, `I_TAPERED` | centre de la section | y horizontal vers +y, z vers le haut |
| `U`, `U_TAPERED` | dos de l'âme en `y = 0`, mi-hauteur en `z = 0` | ailes vers +y |
| `L`, `L_EQ` | talon à l'origine | aile `h` selon +z, aile `b` selon +y |
| `RHS`, `SHS`, `CHS` | centre de la section | y vers +y, z vers le haut |
| `FLAT` | centre | largeur `b` selon z, épaisseur `t` selon y (« sur chant ») |
| `ROUND`, `SQUARE` | centre | — |

Conséquences vérifiées :

- `Iy = ∫ (z − z_c)² dA`, `Iz = ∫ (y − y_c)² dA`, `Iyz = ∫ (y − y_c)(z − z_c) dA` ;
- `Wel_y = Iy / max(z_max − z_c, z_c − z_min)` et
  `Wel_z = Iz / max(y_max − y_c, y_c − y_min)` ;
- `ys` et `zs` sont les coordonnées du centre de gravité mesurées depuis les
  bords du rectangle englobant (`y_c − y_min`, `z_c − z_min`), comme dans les
  catalogues et la base ;
- `surface [m²/m] = périmètre extérieur / 1000` (les trous ne comptent pas) ;
- `masse [kg/m] = A [mm²] × 10⁻⁶ × 7 850`.

## 4. Formes et paramètres

| `shape_id` | Générateur | Paramètres requis |
|---|---|---|
| `I` | `i_section` | `h, b, tw, tf, r` |
| `I_TAPERED` | `i_tapered` | `h, b, tw, tf, r1, r2, slope_pct, x_tf` |
| `U` | `channel` avec `slope_pct = 0`, `r2 = 0` | `h, b, tw, tf, r` |
| `U_TAPERED` | `channel` | `h, b, tw, tf, r1, r2, slope_pct, x_tf` |
| `L` | `angle` | `h, b, t, r1, r2` |
| `L_EQ` | `angle` avec `h = b` | `b, t, r1, r2` |
| `RHS` | `rect_hollow` | `h, b, t, ro, ri` |
| `SHS` | `rect_hollow` avec `h = b` | `b, t, ro, ri` |
| `CHS` | `chs` | `D, t` |
| `FLAT` | `flat` | `b, t` |
| `ROUND` | `round_bar` | `D` |
| `SQUARE` | `square_bar` | `a` |
| `T_TAPERED` | `t_tapered` (refus explicite) | `h, b, tw, tf, r1, r2, slope_pct, x_tf` |

Règles de construction :

- **I/H** : quatre congés de racine `r`, bouts de semelle vifs ;
- **U et I à semelles inclinées** : face intérieure `z = c0 + s·y` avec
  `s = slope_pct/100`, congé de racine `r1`, arc de bout `r2`, rotation
  `90° − atan(s)` ; les points de tangence sont calculés, jamais approchés ;
- **cornières** : talon et extrémités vifs, congé de racine `r1`, arcs de bout
  `r2` ; une partie droite de longueur nulle est omise, une longueur négative
  est refusée ;
- **tubes** : paroi constante, quatre arcs extérieurs `ro` et quatre arcs
  intérieurs `ri` ; les rayons viennent des règles EN 10210-2 / EN 10219-2
  lorsqu'ils ne sont pas tabulés (origine `series_rule`) ;
- **pleins** : rectangle, disque ou carré exacts, sans congé non documenté.

Aucun générateur ne remplit une valeur manquante. `build_profile()` refuse un
profilé `incomplete` ou dont un paramètre requis est `NULL`.

## 5. Validation

Deux niveaux :

1. **Tests unitaires** (`python -m unittest discover -s tests`) : rectangle,
   disque, anneau, quart de disque, section I sans congé, section U sans congé,
   cornière, tube, plat, rond, carré, équivalence I / I_TAPERED à pente nulle,
   conventions de modules et d'unités. 33 tests, tous verts.
2. **Vérification sur la base** (`python -m app.geometry.verify`) : chaque
   profilé complet est reconstruit, puis comparé aux valeurs publiées de
   `derived_property` : `A, ys, zs, Iy, Iz, Iyz, Iu, Iv, alpha, i_y, i_z, i_u,
   i_v, Wel_y, Wel_y_top, Wel_y_bottom, Wel_z, Wel_z_left, Wel_z_right, mass,
   surface`.

Tolérances :

- séries normalisées : `1e-5` en relatif (valeurs publiées à 6 chiffres
  significatifs) ;
- séries commerciales : `A` et `mass` à demi-unité du dernier chiffre imprimé
  (2 décimales ou 3 chiffres significatifs), les autres propriétés à `2e-3` ;
- `Iyz` est comparé en absolu, rapporté à `max(Iy, Iz)`, car les sections
  symétriques publient exactement `0`.

Résultat au 30 octobre 2026 :

| Population | Références | Échecs géométriques | Erreur relative max |
|---|---:|---:|---:|
| Normalisées | 1 792 | 0 | `4,87 × 10⁻⁶` |
| Commerciales | 439 | 0 | `4,44 × 10⁻³` (A, arrondi catalogue) |
| **Total** | **2 231** | **0** | — |

L'erreur maximale des séries normalisées (`4,87 × 10⁻⁶`, CHS-CF 168,3×6 sur
`Iy`/`Iz`) est celle de l'arrondi des valeurs publiées, pas du moteur : les
valeurs SSDB sont imprimées à 6 chiffres significatifs.

### Anomalies de masse commerciale

Le catalogue ArcelorMittal imprime une masse qui, pour sept références, ne
découle pas de l'aire à 7,85 kg/dm³ au-delà de la précision d'impression. Ce
sont des incohérences de la source, sans mise en cause de la géométrie :

| Référence | Masse calculée | Masse publiée |
|---|---:|---:|
| `AM-CARRES/Carré 120` | 113,04 | 111 |
| `AM-PLATS/Plat 25x15` | 2,94375 | 2,91 |
| `AM-PLATS/Plat 30x14` | 3,297 | 3,2 |
| `AM-PLATS/Plat 100x10` | 7,85 | 7,8 |
| `AM-PLATS/Plat 110x30` | 25,905 | 25,2 |
| `AM-PLATS/Plat 130x50` | 51,025 | 50,6 |
| `AM-RONDS/Rond 16` | 1,57834 | 1,59 |

Elles sont signalées par `verify` (sortie `ANOMALIES DE MASSE PUBLIÉE`) et ne
sont jamais corrigées. `--strict` les traite comme des échecs ; le mode par
défaut ne fait échouer que les écarts géométriques.

## 6. Limites assumées

- **T** : `slope_pct` et `x_tf` manquent pour les 7 références `AM-TES` ;
  `t_tapered()` refuse explicitement de construire. La géométrie T exige
  EN 10055.
- **Modules plastiques `Wpl_y`, `Wpl_z`** : non calculés en Phase 2. Ils
  demandent la recherche de l'axe de flexion plastique (aire coupée en deux),
  pas seulement les intégrales élastiques.
- **`It`, `Wt`, `Iw`, `Avy`, `Avz`, `ym`** : propriétés dépendant d'une
  convention (voir `docs/CONVENTIONS.md` du SSDB) ; elles ne font pas partie de
  la géométrie exacte et ne sont pas publiées par ce moteur.
- **Export** : traité en Phase 3 ; voir [`docs/exports.md`](exports.md) pour
  les formats, l'exactitude et les limites des maillages.
- **Vérification normative** : aucune. Les valeurs SSDB sont une source
  normalisée mais leur contrôle contre une copie licite de la norme reste à
  faire ; `verified = 0` partout.

## 7. Utilisation

```bash
# Tests unitaires et d'intégration
python -m unittest discover -s tests

# Vérification complète (code 0 si aucune erreur géométrique)
python -m app.geometry.verify

# Une série, ou une catégorie
python -m app.geometry.verify --series IPE
python -m app.geometry.verify --category standard --verbose

# Traiter aussi les anomalies de masse comme des échecs
python -m app.geometry.verify --strict
```

Utilisation comme bibliothèque :

```python
from app.geometry.build import connect, build_profile
from app.geometry.properties import section_properties

con = connect()
section = build_profile(con, "IPE/IPE 200")
properties = section_properties(section)
print(properties.catalogue_values()["Iy"], "cm4")
```

## 8. Provenance et licence

Le code du moteur est original (à licencier avec le projet, MIT recommandée).
Le dépôt SSDB (MIT, © 2026 Adam Koudelka) est utilisé comme référence
documentaire et oracle de validation ; aucun fichier de son moteur n'est
recopié. Les dimensions commerciales ArcelorMittal restent `local_only` et
`restricted` : elles ne sont ni publiées ni livrées avec le projet.
