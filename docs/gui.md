# Interface de bureau — Phase 4

Rapport d'état de l'interface PySide6. La fenêtre est un **client** du moteur
(`app.geometry`) et des exports (`app.exports`) : elle ne contient aucune
formule de géométrie, aucune règle de construction et aucune règle d'écriture de
fichier. Elle lit le catalogue, affiche le résultat du moteur et délègue
l'export au même code que la ligne de commande.

> État : **Phase 4 terminée**. La fenêtre parcourt les 7 familles et les
> 21 séries, affiche l'aperçu exact des 2 231 profilés constructibles et refuse
> les 7 T incomplets sans compléter aucune valeur. `verified` reste `false`
> partout. PySide6 n'est requis **que** pour cette couche : le moteur et les
> exports continuent de fonctionner sans Qt.

## 1. Lancement

```bash
python -m pip install -r requirements-gui.txt   # PySide6 ≥ 6.6
python -m app.gui
python -m app.gui --profile "IPE/IPE 200"
python -m app.gui --db autre/profiles.db
```

Le paquet `app.gui` n'importe pas Qt à l'import : `import app.gui` et
`from app.geometry...` fonctionnent sans PySide6. `python -m app.gui` charge
`app.gui.app`, qui importe Qt ; si PySide6 manque, le message indique la commande
d'installation et le programme sort avec le code 2, sans traceback.

La base n'est jamais modifiée : l'interface ne fait que lire. Si elle est
absente, une boîte de dialogue rappelle la commande de reconstruction
(`python app/database/import_data.py`) ; rien n'est créé implicitement.

## 2. Architecture

| Fichier | Rôle | Qt |
|---|---|---|
| `app/gui/catalog.py` | familles, séries, profilés, recherche, détail, propriétés calculées/publiées, réserves | **non** |
| `app/gui/main_window.py` | fenêtre, arbre, filtres, tableaux, menus, portée de l'export | oui |
| `app/gui/preview.py` | chemin Qt exact de la section, zoom, déplacement, axes | oui |
| `app/gui/export_dialog.py` | formats, longueur, tolérance, destination, `QThread` d'export | oui |
| `app/gui/app.py` | arguments, `QApplication`, ouverture de la fenêtre | oui |
| `app/gui/__main__.py` | `python -m app.gui`, message si PySide6 manque | non |
| `tests/test_gui.py` | 13 tests : catalogue sans Qt, fenêtre hors écran, export réel | les deux |

La séparation est stricte :

- `catalog.py` ne fait que des requêtes SQLite et des appels à
  `build_section` / `section_properties`. C'est la seule couche testable sans
  écran, et elle l'est sans Qt.
- `main_window.py` affiche les structures renvoyées. Aucun calcul de section,
  aucune conversion d'unité n'y est refaite : `SectionProperties.catalogue_values()`
  fournit déjà cm², cm⁴, cm³, cm, kg/m et m²/m.
- `preview.py` réutilise `contour_segments()` d'`app.exports.curve`, donc les
  mêmes tronçons d'arcs ≤ 90° que le DXF et le STEP.
- `export_dialog.py` appelle `export_selection`, `build_manifest` et
  `write_manifest` d'`app.exports.cli`, exactement comme `main()`.

## 3. Ce que montre la fenêtre

Trois panneaux redimensionnables :

1. **Catalogue** — arbre famille → série → profilé, recherche et filtre de
   catégorie.
2. **Aperçu** — section exacte, zoom molette sous le curseur, glisser pour
   déplacer, double-clic ou `Ctrl+0` pour ajuster, marqueur du centre de gravité,
   axes principaux, grille, cotes du cadre et lecture du coin.
3. **Informations** — badges, onglets *Dimensions*, *Propriétés* et
   *Notes et réserves*.

### 3.1 Recherche

La recherche est faite **en mémoire** sur les 2 238 lignes, avec la même
normalisation que le catalogue (`search_key`) : majuscules, sans accent, sans
espace, point conservé. Une saisie libre trouve donc :

- `ipé 200`, `IPE200`, `Ipe 200` → `IPE/IPE 200` ;
- `IPE/IPE 200` (identifiant complet) → la même ligne ;
- `168.3x6` → les CHS correspondants ;
- `Té 20x20x3` → le T commercial, même incomplet.

La correspondance exacte (désignation, alias, identifiant) est prioritaire ;
à défaut, la recherche par sous-chaîne filtre l'arbre. Le filtre de catégorie
sépare *normalisées* et *commerciales* sans jamais mélanger les deux lectures
(§3.7 du cahier des charges).

### 3.2 Dimensions et provenance

Chaque dimension affiche son symbole, son libellé, sa valeur et son **origine** :
`table`, `règle de série` ou `valeur imprimée`. Une valeur absente s'affiche
`—` avec l'origine `manquant`, et l'onglet rappelle la liste exacte des
paramètres manquants.

### 3.3 Propriétés : calculé, publié, écart

Les 21 grandeurs publiées au catalogue sont affichées sur cinq colonnes :
grandeur, unité, valeur calculée, valeur publiée et écart rapporté à la
tolérance. La tolérance est celle de `verify`, via
`app.geometry.verify.comparison_tolerance()` : `10⁻⁵` relatif pour les séries
normalisées, demi-unité de la précision imprimée pour les données commerciales.

Un écart supérieur à la tolérance colore la ligne et affiche le ratio ; la
valeur publiée **reste affichée telle quelle**, elle n'est jamais corrigée. Le
bandeau précise que les valeurs publiées ne sont pas indépendantes : elles
servent de contrôle, pas de preuve.

### 3.4 Profilés incomplets

Un profilé dont la géométrie n'est pas constructible reste visible, marqué
`— incomplète`. Sa fiche montre :

- les dimensions connues, avec les paramètres absents ;
- l'erreur exacte, par exemple
  `AM-TES/Té 20x20x3 : géométrie incomplète — paramètres manquants : slope_pct, x_tf ; aucune valeur n'est inventée` ;
- aucune propriété calculée, aucun aperçu, et l'action d'export **désactivée**.

L'aperçu affiche alors un message explicite plutôt qu'une section vide ou
approximative.

## 4. Aperçu exact

`section_path()` construit un `QPainterPath` à partir des contours du moteur :

- les droites deviennent `lineTo` ;
- les arcs deviennent `arcTo` sur le cercle exact, avec le même centre, le même
  rayon et la même ouverture, découpés en tronçons ≤ 90° par
  `contour_segments()` ;
- le remplissage est `OddEvenFill`, ce qui traite les trous (creux, rainures)
  sans dépendre de l'orientation des contours, comme le fait le DXF.

Qt mesure les angles dans un repère où `y` descend ; la vue applique
`scale(s, -s)` et appelle `arcTo(rect, -deg(theta0), -deg(sweep))`, ce qui
restitue l'arc du repère section (`y` à droite, `z` en haut). **Rien n'est
facetté pour l'affichage** : le lissage perçu vient de l'antialiasing, pas d'une
polyline.

Le test `test_preview_path_is_exact_for_a_hollow_section` vérifie sur
`CHS-CF/CHS 168.3x6` que le cadre vaut exactement `±84,15 mm` et que le centre
est exclu du remplissage (le trou est bien un trou).

## 5. Export

La fenêtre exporte soit le profilé sélectionné, soit **toute la série** quand
un nœud de série est sélectionné. Les cinq formats, la longueur d'extrusion
(1 000 mm par défaut) et la tolérance de corde (0,05 mm par défaut) sont
choisis dans la boîte de dialogue ; `manifest.json` est écrit par défaut.

L'export tourne dans un `ExportWorker` (`QThread`) qui ouvre sa **propre**
connexion SQLite : une connexion SQLite ne traverse pas les threads. La fenêtre
reste réactive, une barre de progression suit les profilés, et la fermeture est
bloquée pendant l'écriture. Le résultat indique le nombre de profilés et de
fichiers écrits et, le cas échéant, les **refus** — un T incomplet est refusé
avec son message, jamais exporté avec une valeur inventée.

Deux précautions empêchent un `qFatal` de Qt pendant l'export :

1. la boîte de dialogue ne modifie **jamais** ses `WindowFlags` pendant le
   travail. Sur une boîte modale, `setWindowFlag()` la masque, ce qui fait sortir
   `exec()` prématurément ; la fenêtre serait détruite avec un `QThread` encore
   actif. La fermeture est déjà bloquée par `closeEvent()` et `reject()`.
2. le `QThread` n'est relâché qu'une fois réellement arrêté : `finished` peut
   être émis alors que `isRunning()` est encore vrai, et détruire l'objet à cet
   instant avorte Qt (`QThread: Destroyed while thread is still running`). La
   référence est conservée puis relâchée par un `QTimer` qui vérifie
   `isRunning()`.

Le nommage, les empreintes SHA-256 et le manifeste sont ceux d'`app.exports` :
l'interface n'a pas de règle à elle. Voir [`docs/exports.md`](exports.md).

## 6. Tests

`tests/test_gui.py` contient 13 tests :

- **catalogue, sans Qt** : comptages (2 238 / 2 231 / 7), 7 familles,
  16 séries normalisées + 5 commerciales, normalisation de recherche,
  `find("ipé 200")`, filtres par catégorie, détail complet d'IPE 200 (21 lignes,
  aucune hors tolérance), refus du T avec `slope_pct` et `x_tf` manquants ;
- **fenêtre, hors écran** : 7 familles dans l'arbre, sélection d'IPE 200
  (5 dimensions, 21 propriétés, export activé), sélection du T (export
  désactivé, texte de refus présent), exactitude du chemin Qt d'un creux,
  formatage des nombres ;
- **export réel** : la boîte de dialogue reste visible pendant le travail, écrit
  un DXF et ne relâche le `QThread` qu'après son arrêt effectif — le scénario
  qui faisait auparavant avorter Qt.

Les tests de widgets posent `QT_QPA_PLATFORM=offscreen` avant le premier import
de PySide6 ; ils sont ignorés si PySide6 ou `data/profiles.db` manquent. Aucun
test ne recalcule une valeur de géométrie : le moteur et les exports ont leurs
propres tests.

```bash
python -m unittest discover -s tests
```

## 7. Limites assumées

- **`verified = false` partout** : aucune copie licite des normes n'est
  enregistrée. L'interface l'affiche dans chaque fiche et dans *À propos*.
- **Les 7 T restent incomplets** : la pente de semelle et `x_tf` ne sont pas
  documentées (EN 10055 requis). L'interface le montre, elle ne le masque pas.
- **Pas d'édition** : l'interface ne propose aucune saisie ni correction de
  dimension ; elle ne modifie jamais le catalogue.
- **Pas de vue 3D** : l'aperçu est une section 2D exacte ; l'extrusion est
  visible dans les fichiers exportés, pas dans la fenêtre.
- **Pas de sélecteur d'unités ni de norme de dessin** : les unités sont celles
  du catalogue (mm, cm², cm⁴, cm³, cm, kg/m) et les conventions d'export sont
  fixes (voir `docs/exports.md` §2).
- **Données commerciales locales** : les 446 références `AM-*` restent
  `local_only`. L'interface les marque `COMMERCIAL` et ne les présente jamais
  comme normalisées ; une base publiable se reconstruit sans `data/staging/`.
- **Pas d'empaquetage** : l'application se lance depuis le dépôt, avec Python
  et PySide6 installés ; aucun exécutable autonome n'est fourni.

## 8. Licences

Le code du projet est sous **MIT** (voir `LICENSE`). PySide6 / Qt est distribué
sous **LGPLv3** : il est utilisé comme bibliothèque externe, non modifiée et
importée dynamiquement, sans être lié statiquement ni vendu avec le projet. La
mention et les obligations sont dans `THIRD-PARTY-NOTICES.md` et
[`docs/licenses.md`](licenses.md) §8. Les données gardent leurs licences
propres : Steel Section Database (MIT) et catalogue ArcelorMittal (propriétaire,
non redistribué).
