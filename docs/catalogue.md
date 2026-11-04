# Catalogue Phase 1 — rapport d'analyse des sources

**Projet :** SteelProfile — générateur local de profilés métalliques normalisés européens
**Phase :** 1 — analyse des sources et constitution du catalogue
**Date :** 30 octobre 2026
**Périmètre de cette phase :** données uniquement. Aucune interface, aucune géométrie.

---

## 1. Résumé

| Indicateur | Valeur |
|---|---|
| Sources examinées | 11 pistes (5 du §4 + 6 recherches complémentaires) |
| Sources retenues | **2** : Steel Section Database (MIT, normalisée) et catalogue ArcelorMittal 2020 (commerciale, locale) |
| Séries intégrées | **21** — 16 normalisées, 5 commerciales |
| Références au catalogue | **2 238** — 1 792 normalisées, 446 commerciales |
| Références exploitables (géométrie complète) | **2 231 (99,7 %)** |
| dont géométrie entièrement tabulée | 1 076 (630 normalisées + 446 commerciales) |
| dont rayons d'angle déduits d'une règle normative | 1 162 |
| Références incomplètes | **7** (profilés T commerciaux : pente et `x_tf` non publiés) |
| Familles du cahier des charges couvertes | **7 sur 7** ont des données ; 5 entièrement normalisées, **pleins complets mais partiellement commerciaux**, **T non reconstructible** |
| Paramètres obligatoires manquants | **14** (7 × `slope_pct`, 7 × `x_tf`) |
| Valeurs inventées ou interpolées | **0** |
| Références vérifiées contre une norme | **0** (aucune copie licite consultée) |
| Anomalies consignées | **63** (8 bloquantes, 39 avertissements, 16 informations) |
| Export redistribuable | **1 792** références, **aucune** commerciale |

La base `data/profiles.db` est construite et interrogeable. Le catalogue
normalisé (1 792 références) est utilisable pour la Phase 2 **sous réserve** des
limites du §9 : les dimensions sont documentées, mais aucune n'a été contrôlée
ligne à ligne contre la norme. Les 446 références commerciales sont isolées
(`category = 'commercial'`), ne portent aucune norme et ne sont jamais livrées.

---

## 2. Méthode

1. Lecture intégrale du cahier des charges (610 lignes).
2. Revue des 5 sources du §4 : ouverture réelle, pas de supposition.
3. Recherche complémentaire pour les familles T et pleins (theolternative,
   Montanstahl, Lechner, Dlubal, BSSA, dépôts de recherche, catalogue
   ArcelorMittal 2020) — voir `docs/sources.md` §6 à §12.
4. Collecte de Steel Section Database (archive ZIP de `main`, empreinte SHA-256
   figée dans `docs/sources.md`).
5. Lecture des métadonnées de série (TOML) et des tables de géométrie (CSV).
6. Import dans SQLite avec contrôle de cohérence et de faisabilité par référence.
7. Consignation de chaque anomalie dans la table `catalog_issue`.
8. Génération du présent rapport et de l'inventaire CSV depuis la base.

Deux régimes de données coexistent, sans jamais se mélanger :

- **normalisé** : Steel Section Database (MIT), 1 792 références, `category =
  'standard'` ;
- **commercial** : catalogue ArcelorMittal 2020, 446 références, `category =
  'commercial'`, `standard_id` NULL, `local_only`.

Aucune valeur n'a été saisie à la main, complétée par interpolation ou déduite
d'une figure. Les seules valeurs calculées sont les rayons d'angle des profilés
creux, par la règle explicite de la norme, et elles sont marquées comme telles
(`origin = 'series_rule'`). Les dimensions commerciales sont recopiées des
tableaux du fabricant et recoupées par ses colonnes de masse et de surface
(`docs/sources.md` §12).

Fichiers produits :

| Fichier | Rôle |
|---|---|
| `data/profiles.db` | base SQLite du catalogue de travail (2 238 références) |
| `data/catalogue_inventory.csv` | catalogue à plat, 1 ligne par référence (2 238) |
| `data/catalogue_inventory_redistributable.csv` | 1 792 références normalisées, aucune commerciale |
| `data/catalogue_stats.json` | comptages et anomalies, source des chiffres de ce rapport |
| `data/staging/README.md` | contrat d'import des séries locales (non redistribuées) |
| `data/staging/AM-*` | dépôt local du catalogue commercial (jamais livré) |
| `data/staging/tools/` | utilitaires d'extraction du catalogue commercial (jamais livrés) |
| `app/database/schema.sql` | schéma SQL commenté |
| `app/database/import_data.py` | import reproductible (bibliothèque standard seule) |
| `app/database/check_catalogue.py` | contrôle de cohérence, modes travail et `--publish` |
| `docs/sources.md` | analyse détaillée des sources |
| `docs/licenses.md` | licences et droits de redistribution |
| `docs/catalogue.md` | ce rapport |

Reproduction :

```bash
python app/database/import_data.py                                   # base de travail
python app/database/import_data.py --staging <dir-vide> \
       --db <tmp>/profiles.db --stats <tmp>/catalogue_stats.json     # base publiable
python data/staging/tools/am_staging.py                              # régénère le dépôt AM-*
```

---

## 3. Inventaire des familles et des références

### 3.1 Vue par famille

| Famille | Séries | Références | Exploitables | Rayons tabulés | Rayons par règle |
|---|---|---|---|---|---|
| I — profilés en I | 2 | 39 | 39 | 39 | 0 |
| H — profilés en H | 3 | 72 | 72 | 72 | 0 |
| U — profilés en U | 2 | 32 | 32 | 32 | 0 |
| L — cornières | 2 | 81 | 81 | 81 | 0 |
| T — profilés en T | 1 (commerciale) | **7** | **0** | 7 | 0 |
| Creux — SHS/RHS/CHS | 6 | 1 506 | 1 506 | 344 | 1 162 |
| Pleins — plats, ronds, carrés | 5 (dont 4 commerciales) | 501 | 501 | 501 | 0 |
| **Total** | **21** | **2 238** | **2 231** | **1 076** | **1 162** |

Sur ces 2 238 références, **1 792 sont normalisées** (16 séries, Steel Section
Database) et **446 sont commerciales** (5 séries `AM-*`, catalogue ArcelorMittal
2020). Les secondes ne portent aucune norme et ne sont jamais confondues avec les
premières (`category`, §7.3).

### 3.2 Vue par série

| Série | Catégorie | Forme | Procédé | Norme citée | Réf. | Étendue dimensionnelle (mm) |
|---|---|---|---|---|---|---|
| IPE | standard | I | laminé à chaud | EN 10365:2017 | 18 | h 80–600 · b 46–220 · tw 3,8–12 · tf 5,2–19 · r 5–24 |
| IPN | standard | I à semelles inclinées | laminé à chaud | EN 10365:2017 + DIN 1025-1 | 21 | h 80–600 · b 42–215 · tw 3,9–21,6 · tf 5,9–32,4 · r1 3,9–21,6 · r2 2,3–13 · pente 14 % |
| HEA | standard | I | laminé à chaud | EN 10365:2017 | 24 | h 96–990 · b 100–300 · tw 5–16,5 · tf 8–31 · r 12–30 |
| HEB | standard | I | laminé à chaud | EN 10365:2017 | 24 | h 100–1 000 · b 100–300 · tw 6–19 · tf 10–36 · r 12–30 |
| HEM | standard | I | laminé à chaud | EN 10365:2017 | 24 | h 120–1 008 · b 106–310 · tw 12–21 · tf 20–40 · r 12–30 |
| UPN | standard | U à semelles inclinées | laminé à chaud | EN 10365:2017 + DIN 1026-1 | 18 | h 50–400 · b 38–110 · tw 5–14 · tf 7–18 · r1 7–18 · r2 3,5–9 · pente 8 % (h ≤ 300) / 5 % |
| UPE | standard | U à semelles parallèles | laminé à chaud | EN 10365:2017 + DIN 1026-2 | 14 | h 80–400 · b 50–115 · tw 4–13,5 · tf 7–18 · r 10–18 |
| L-EQ | standard | cornière à ailes égales | laminé à chaud | gamme mixte EN 10056-1:1998 / DIN 1028 | 42 | b 40–200 · t 4–26 · r1 6–18 · r2 3–9 |
| L | standard | cornière à ailes inégales | laminé à chaud | gamme mixte EN 10056-1:1998 / DIN 1029 | 39 | h 50–200 · b 30–100 · t 4–16 · r1 5–15 · r2 2,5–7,5 |
| SHS-HF | standard | tube carré fini à chaud | fini à chaud | EN 10210-2:2006 | 243 | b 40–400 · t 2,6–20 |
| SHS-CF | standard | tube carré formé à froid | formé à froid | EN 10219-2:2006 | 163 | b 15–600 · t 1,5–20 |
| RHS-HF | standard | tube rectangulaire fini à chaud | fini à chaud | EN 10210-2:2006 | 496 | h 50–500 · b 30–350 · t 2,6–20 |
| RHS-CF | standard | tube rectangulaire formé à froid | formé à froid | EN 10219-2:2006 | 260 | h 20–400 · b 10–300 · t 1,5–16 |
| CHS-HF | standard | tube circulaire fini à chaud | fini à chaud | EN 10210-2:2006 | 114 | D 33,7–406,4 · t 2,3–16 |
| CHS-CF | standard | tube circulaire formé à froid | formé à froid | EN 10219-2:2006 | 230 | D 21,3–508 · t 1,5–16 |
| FLAT | standard | plat | laminé à chaud | EN 10058:2018 (**hypothèse**) | 62 | b 160–230 · t 5–50 |
| AM-RONDS | **commerciale** | rond plein | laminé à chaud | aucune | 69 | D 5–250 |
| AM-CARRES | **commerciale** | carré plein | laminé à chaud | aucune | 28 | a 5–120 |
| AM-PLATS | **commerciale** | plat | laminé à chaud | aucune | 288 | b 10–150 · t 3–60 |
| AM-LARGES-PLATS | **commerciale** | plat | laminé à chaud | aucune | 54 | b 160–450 · t 5–35 |
| AM-TES | **commerciale** | T à semelles inclinées | laminé à chaud | aucune | 7 | h = b 20–80 · e 3–9 · e1 3–9 |

Les cinq séries `AM-*` proviennent du catalogue ArcelorMittal 2020, sont
`local_only` et **exclues** de l'export redistribuable. Le détail de l'extraction,
des recoupements et des lignes écartées est dans `docs/sources.md` §12.

Le détail référence par référence (dimensions, rayons, statut, alias, fichier
d'origine) est dans `data/catalogue_inventory.csv` (2 238 lignes, 29 colonnes).

### 3.3 Doublons

- Aucune désignation n'est dupliquée **à l'intérieur** d'une série.
- Les séries creuses se recouvrent volontairement entre procédés :

| Base | HF | CF | Désignations communes | HF seules | CF seules |
|---|---|---|---|---|---|
| SHS | 243 | 163 | 92 | 151 | 71 |
| RHS | 496 | 260 | 115 | 381 | 145 |
| CHS | 114 | 230 | 96 | 18 | 134 |

Une désignation identique en HF et en CF **n'est pas un doublon** : la géométrie
diffère par les rayons d'angle. Exemple avec `RHS 100x50x4` :

| Série | ro | ri |
|---|---|---|
| RHS-HF | 6,0 | 4,0 |
| RHS-CF | 8,0 | 4,0 |

Le procédé fait donc partie de l'identité (`profile_id = SHS-HF/SHS 100x100x5` ≠
`SHS-CF/SHS 100x100x5`).

- Les séries **commerciales** recouvrent en partie `FLAT` : 33 largeurs
  `AM-LARGES-PLATS` sont comprises entre 160 et 230 mm, dont 27 couples
  `(b, t)` identiques à une référence `FLAT`. Les désignations diffèrent
  (`Large plat 160x10` contre `FLAT 160x10`) et la catégorie diffère
  (`commercial` contre `standard`) : ce ne sont pas des doublons, mais deux
  qualifications du même fait dimensionnel. Aucune fusion n'est faite : la
  référence normalisée reste la seule à porter une norme.

---

## 4. Dimensions et rayons disponibles, par forme

Chaque forme a un jeu de paramètres obligatoires. Aucun n'est facultatif : un
paramètre absent rend la référence « incomplète ».

| Forme | Paramètres obligatoires | Rayons | Source du rayon |
|---|---|---|---|
| `I` | h, b, tw, tf, r | 4 congés de racine | tabulé |
| `I_TAPERED` | h, b, tw, tf, r1, r2, slope_pct, x_tf | r1 racine, r2 extrémité d'aile | tabulé |
| `U` | h, b, tw, tf, r | 2 congés de racine | tabulé |
| `U_TAPERED` | h, b, tw, tf, r1, r2, slope_pct, x_tf | r1 racine, r2 extrémité | tabulé |
| `SHS` / `RHS` | b (et h), t, ro, ri | ro extérieur, ri intérieur | **règle normative**, calculée depuis t |
| `CHS` | D, t | aucun (deux cercles) | — |
| `L_EQ` / `L` | b (et h), t, r1, r2 | r1 racine, r2 extrémité d'aile | tabulé |
| `FLAT` | b, t | aucun (angles vifs) | — |
| `ROUND` | D | aucun | — |
| `SQUARE` | a | aucun | — |
| `T_TAPERED` | h, b, tw, tf, r1, r2, slope_pct, x_tf | r1 racine, r2 extrémité d'aile | tabulé (r1, r2) ; `r3` non repris |

Les formes `ROUND`, `SQUARE` et `T_TAPERED` sont désormais **peuplées**, mais
uniquement par des séries commerciales locales : 69 ronds, 28 carrés, 7 T.
`T_TAPERED` reste marquée **provisoire** — sa géométrie n'a pas été validée
contre EN 10055, et les 7 références sont incomplètes (pente et `x_tf` non
publiés, voir §5.1.1).

### 4.1 Règles de rayon des profilés creux

Le dépôt ne stocke pas `ro` / `ri` : il nomme une règle, appliquée en
arithmétique décimale exacte (aucun arrondi). Ces valeurs sont marquées
`origin = 'series_rule'`.

| Règle | Procédé | Épaisseur | ro | ri |
|---|---|---|---|---|
| EN 10210-2:2006 §A.3 | fini à chaud | toute | 1,5 · t | 1,0 · t |
| EN 10219-2:2006 §B.3 | formé à froid | t ≤ 6 | 2,0 · t | 1,0 · t |
| EN 10219-2:2006 §B.3 | formé à froid | 6 < t ≤ 10 | 2,5 · t | 1,5 · t |
| EN 10219-2:2006 §B.3 | formé à froid | t > 10 | 3,0 · t | 2,0 · t |

Deux réserves importantes :

1. Ce sont des **rayons de calcul**, pas des rayons mesurés. Le rayon réel est
   dans une bande de tolérance (EN 10219-2 Tableau 3 : 1,6–2,4 T, 2,0–3,0 T,
   2,4–3,6 T) ; le rayon de calcul est le milieu de la bande.
2. `ri` n'est spécifié par aucune des deux normes : c'est une **convention de
   calcul**. Elle est nécessaire pour fermer le contour intérieur, mais elle ne
   doit pas être présentée comme une dimension fabricant.

### 4.2 Rayons des profilés ouverts

- **I / H** : un seul rayon `r`, quatre congés identiques entre âme et semelles.
  Les extrémités de semelles sont vives. Aucun rayon extérieur n'est documenté
  → aucun n'est ajouté.
- **UPN / IPN** : `r1` (racine) et `r2` (extrémité d'aile), plus la pente des
  faces intérieures de semelle (8 %, 5 % ou 14 %) et l'abscisse `x_tf` du point
  de mesure de `tf`.
- **UPE** : `r` unique, semelles parallèles, extrémités vives.
- **Cornières** : `r1` (racine) et `r2` (extrémité d'aile). Le talon est vif.
  Le rayon de talon `r3` des cornières lourdes **n'est pas modélisé** (aucune
  taille concernée dans la gamme actuelle, qui s'arrête à 200 × 200 × 26).
- **T commerciaux** : `r1` (racine) et `r2` (extrémité de semelle) sont tabulés.
  Le troisième rayon du catalogue (`r3`, 1,00 à 2,00 mm) **n'est pas repris** :
  sa signification n'est pas documentée par le fabricant.

### 4.3 Cohérence interne vérifiée

Chaque référence a été soumise aux contrôles de faisabilité documentés
(semelle plane > 0, âme plane > 0, trou intérieur > 0, plats extérieurs ≥ 0,
épaisseur de paroi positive dans l'angle, `h ≥ b`, etc.) :

- **2 231 / 2 238** références passent les contrôles (les 7 T, incomplets, sont
  contrôlés sur leurs seuls paramètres présents) ;
- **0** géométrie infaisable parmi les références complètes, **14** paramètres
  manquants (7 pentes et 7 `x_tf`, tous déclarés par la source).

C'est un contrôle de cohérence, pas une validation normative : il vérifie que la
géométrie est *constructible*, pas qu'elle est *conforme à la norme*.

---

## 5. Données manquantes

### 5.1 Manques de périmètre

| Manque | Impact | Références concernées |
|---|---|---|
| Profilés **T** reconstructibles | dimensions commerciales présentes (7 tailles), mais pente et `x_tf` non publiées : géométrie non constructible | 7 incomplètes |
| **T 100×100×11** (§1) | hors gamme du catalogue, qui s'arrête à T 80 | 0 |
| Séries **IPE A / AA / O / V** | §3.1 les demande « lorsque documentées » | 0 |
| Série **HE C** | dont la section 320 × 305, souvent appelée à tort « HEM 320/305 » | 0 |
| **HEM 320/305** | n'existe pas : appartient à HE C (HE 300 C) | 0 |
| **Cornière L 80×60×8** (§1) | absente des 39 cornières inégales, qui contiennent 80×40×8 | 0 |
| **Vérification normative** | aucune référence contrôlée contre une copie licite | 2 238 |

Les manques « carrés pleins », « ronds pleins » et « petits plats », qui
figuraient ici dans la version précédente, sont **couverts** par le programme
commercial (§5.1.2) — sans devenir pour autant des références normalisées.

#### 5.1.1 Profilés T — dimensions présentes, géométrie non reconstructible

Trois faits, établis pendant cette phase :

1. **La géométrie exige plus que les dimensions du catalogue.** Les T de
   EN 10055 sont laminés à chaud, à **semelles inclinées**. Le jeu de paramètres
   est `h, b, tw, tf, r1, r2` — avec **`tw ≠ tf`** — plus la pente des faces et
   la position de mesure de `tf`. Un T ne peut pas être décrit par une seule
   épaisseur.
2. **Le catalogue 2020 publie 7 tailles, T 20 à T 80.** Il donne `h, b, e, e1,
   r1, r2` mais **ni la pente ni `x_tf`**. Ces 7 lignes sont importées et
   documentées ; elles ne permettent aucune reconstruction. Dlubal documente par
   ailleurs un **T 100** sous EN 10055 : la gamme du fabricant est donc un
   sous-ensemble commercial, pas l'étendue de la norme.
3. **Aucune table complète sous licence.** Les tables publiques sont soit la
   norme elle-même (payante, non redistribuable), soit des sites commerciaux sans
   licence (theolternative), soit des fabricants de **T soudés au laser à
   épaisseur constante** (Montanstahl, Lechner) — un produit différent, qui ne
   cite EN 10055 que pour les tolérances.

Conséquence : les 7 références `AM-TES` sont `incomplete`, avec `slope_pct` et
`x_tf` déclarés manquants dans le TOML (`[missing]`) et une anomalie bloquante
`MISSING_PARAMETER` par référence. La forme `T_TAPERED` reste **provisoire** et
ne doit pas servir à reconstruire une section avant confrontation à une copie
licite de EN 10055. Le rayon `r3` du catalogue n'est pas repris (signification
non documentée).

#### 5.1.2 Plats, carrés et ronds — un problème de liste, désormais fourni

Les trois normes EN 10058 / 10059 / 10060 sont des **normes de tolérances, pas des
catalogues de tailles**. La structure du tableau 2 de EN 10059, telle que la décrit
la BSSA, le montre : des **bandes de taille** (8–14, 15–25, 26–35, 40–50, 55–90,
100, 110–120, 130–150 mm) et, pour chaque bande, un **rayon d'angle maximal** —
pas un rayon nominal, pas une liste de côtés.

Deux conséquences :

- **La géométrie est exacte sans aucune table.** Un plat est `b × t`, un carré
  `a × a`, un rond `Ø D` : trois nombres, aucun rayon, aucune pente. Le schéma
  porte les formes `FLAT`, `SQUARE` et `ROUND` (paramètres `b,t` / `a` / `D`).
- **Seule la liste des tailles manquait**, et elle est commerciale. Le §3.7 du
  cahier des charges autorise explicitement ces dimensions commerciales « dans une
  catégorie distincte, sans les confondre avec les références normalisées ».

Cette liste est désormais fournie par le **catalogue ArcelorMittal 2020**
(`docs/sources.md` §12), importé via `data/staging/` :

| Série | Forme | Références | Étendue |
|---|---|---:|---|
| `AM-RONDS` | `ROUND` | 69 | Ø 5 à 250 mm |
| `AM-CARRES` | `SQUARE` | 28 | côté 5 à 120 mm |
| `AM-PLATS` | `FLAT` | 288 | largeur 10 à 150 mm |
| `AM-LARGES-PLATS` | `FLAT` | 54 | largeur 160 à 450 mm |

Ces séries sont `local_only`, `redistribution = 'restricted'`, tracées par
`LOCAL_ONLY_DATA` et **exclues** de l'export redistribuable. Les exemples du §1
(`Plat 50×8`, `Rond Ø20`, `Carré 30×30`) sont couverts.

La séparation exigée par le §3.7 est **implémentée dans le schéma** : une série
porte `category = 'standard'` ou `'commercial'`. Une série commerciale ne peut pas
déclarer de norme, doit citer son programme (`commercial_ref`), reçoit une anomalie
`COMMERCIAL_DATA` et reste hors de l'export redistribuable. Une dimension
commerciale n'est donc jamais confondue avec une référence normalisée, même quand
sa géométrie est exacte.

### 5.2 Manques de données par référence

Sept références sont incomplètes, toutes dans `AM-TES` : `slope_pct` et `x_tf`
manquent à chaque fois (14 valeurs NULL, déclarées par la source). Aucune autre
référence n'a de paramètre obligatoire manquant.

Deux références normalisées sont explicitement **exclues par la source** car
infaisables avec la règle de rayon : `RHS 80x40x11` et `RHS 80x40x12.5` (plat
intérieur négatif). Les intégrer exigerait un `ri` explicite documenté.

### 5.3 Manques transverses

| Donnée demandée au §4 / §6 | État |
|---|---|
| Dimensions nominales | **présentes**, 2 238 / 2 238 |
| Rayons de congé | présents, déduits d'une règle, ou sans objet (formes pleines) — 2 238 / 2 238 |
| Épaisseurs | présentes pour 2 141 références : `t` (1 649 normalisées + 342 plats commerciaux) ou `tw`/`tf` (143 normalisées + 7 T) ; les 97 ronds et carrés sont définis par `D` ou `a` |
| **Tolérances** | **absentes, 0 / 2 238** |
| **Édition de la norme** | présente au niveau des 16 séries normalisées, **pas par référence** ; sans objet pour les 5 séries commerciales |
| **Source primaire par valeur** | **absente** : provenance au niveau série seulement |
| **Date de vérification** | **aucune** (`verified = 0` partout) |
| Masse linéique indépendante | publiée par le fabricant pour les 446 commerciales, mais stockée `independent = 0` ; recalculée pour les 1 792 normalisées |
| **Liste des tailles de plats / carrés / ronds** | **fournie** par le catalogue commercial (`AM-*`), catégorie distincte ; aucune liste normative |
| **Pente et `x_tf` des T** | **absents** : les 7 T commerciaux sont incomplets et bloqués |

Le point le plus structurant reste la **provenance ligne à ligne** : la base sait
que `IPE 200` vient du fichier `data/ipe/IPE.csv` de Steel Section Database, mais
pas de quel tableau de quelle édition de EN 10365. Pour les séries commerciales,
la provenance est plus fine (page et tableau du catalogue, ligne de contrôle)
mais reste au niveau de la série. Le schéma prévoit les colonnes
(`profile.source_row`, `profile_param.origin`) ; il manque le document
intermédiaire pour les séries normalisées. C'est un chantier de Phase 1.5, pas un
blocage de Phase 2.

### 5.4 Cas particuliers signalés

| Référence | Problème |
|---|---|
| `L 75x50x7` | rayons **non tranchés** : 7 / 3,5 (retenu) contre 6,5 / 3,5 chez un stockiste ; une table DIN 1029 primaire est nécessaire |
| `IPN 600` | hors DIN 1025-1:2009 (qui s'arrête à 550) : l'origine des rayons n'est pas explicitée |
| `L 150x75x11` | seule cornière avec `r2 ≠ r1/2` (10,5 / 5,5, valeurs DIN 1029) |
| `L 150x100x14` | rayons 12 / 6 retenus (ArcelorMittal) contre 13 / 6,5 dans DIN 1029 |
| `L 110x110x10` | rayons 13 / 6,5 de EN 10056-1:2017, contre 12 / 6 dans DIN 1028 retirée |
| Plats normalisés | appartenance à EN 10058 **supposée**, non vérifiée |
| `Té 25*` / `Té 45*` | **écartées** : dimensions contredites par la section et la masse ; jamais corrigées (`docs/sources.md` §12) |
| `Té 20x20x3` | hors NF EN 10055 (astérisque du catalogue) ; importée tout de même, en catégorie commerciale |
| `Plat 80x35` | masse (21,2) et surface (0,25) incohérentes, coïncident avec 90x30 / 90x35 ; seules les dimensions 80 et 35 retenues |
| `Carré 5` | masse imprimée 0,126 kg/m incohérente (0,196 attendu) ; côté 5 confirmé par `A = 0,25 cm²` |
| 17 plats `AM-PLATS` | 12 coquilles de surface et 6 de masse, dont 1 ligne (80x35) cumulant les deux ; consignées en note, valeurs fautives non recopiées |
| `Large plat 250x12` | surface imprimée 0,54 m²/m au lieu de 0,524 ; dimensions confirmées par la masse 23,55 kg/m |

---

## 6. Licences

Synthèse (détail dans `docs/licenses.md`) :

| Source | Redistribution | Usage |
|---|---|---|
| Steel Section Database | **autorisée** (MIT, © 2026 Adam Koudelka) | source unique de données normalisées |
| Catalogue ArcelorMittal 2020 | **interdite** (propriétaire, tous droits réservés) | séries commerciales locales, jamais livrées |
| Constructalia | **interdite** sans accord écrit | contrôle visuel seulement |
| Ahan Assa | aucune licence → interdite | écartée |
| CADXChange | non vérifiable | écartée |
| Normes EN / DIN | citation seulement, pas de reproduction de tableaux | référence |
| theolternative.com | aucune licence → interdite | écartée |
| Montanstahl / Lechner | © fabricants | écartés (produit différent) |
| Dlubal / BSSA | contenu propriétaire | contrôle seulement |
| `data/staging/` | selon la source déclarée ; **non** par défaut | catégorie locale |

Conséquence pratique : la **base publiable** (1 792 références, reconstruite avec
`data/staging/` vide) est redistribuable, à condition de joindre la licence MIT de
la source et sa mention de copyright — c'est l'objet de
`THIRD-PARTY-NOTICES.md`. En revanche, la **base de travail** (2 238 références)
contient les 446 références commerciales et n'est **pas** redistribuable telle
quelle. Aucune donnée de Constructalia, Ahan Assa, CADXChange, theolternative,
Montanstahl, Lechner, Dlubal ou BSSA n'est présente dans la base. Les séries de
`data/staging/` et le PDF ArcelorMittal ne sont jamais livrés.

---

## 7. Schéma SQLite

Base : `data/profiles.db` — 2 238 profils, 8 248 paramètres, 2 600 alias,
55 098 propriétés dérivées. `PRAGMA integrity_check` et `PRAGMA foreign_key_check`
sont propres.

### 7.1 Tables

| Table | Rôle | Lignes |
|---|---|---|
| `source` | provenance documentaire, licence, droit de redistribution | 6 |
| `standard` | norme, édition, statut, indicateur de vérification | 14 |
| `family` | les 7 familles du §3 | 7 |
| `shape` | formes géométriques et générateur prévu (Phase 2) | 13 |
| `param_def` | paramètres obligatoires par forme | 58 |
| `series` | série = un fichier de données, avec norme, procédé, règle de rayon, **catégorie** | 21 |
| `corner_radius_rule` / `corner_radius_band` | règles de rayon des creux, par bande d'épaisseur | 2 / 4 |
| `profile` | une ligne par référence, avec statut et provenance | 2 238 |
| `profile_param` | géométrie primaire, une ligne par paramètre | 8 248 |
| `profile_alias` | désignations alternatives pour la recherche | 2 600 |
| `derived_property` | A, I, W, masse… **dérivées**, `independent = 0` | 55 098 |
| `catalog_issue` | anomalies, manques et réserves | 63 |

### 7.2 Vues

| Vue | Usage |
|---|---|
| `v_profile_geometry` | une ligne par référence, une colonne par paramètre |
| `v_family_stats` | comptage par famille (total / complètes / incomplètes) |
| `v_series_stats` | comptage par série, avec norme et procédé |

### 7.3 Conventions structurantes

1. **Une valeur absente est `NULL`**, jamais 0, jamais une valeur par défaut.
   `profile_param` contient une ligne même quand la valeur manque : la ligne
   existe et dit « ce paramètre est requis et inconnu ».
2. **`origin`** distingue `table` (valeur publiée), `series_rule` (règle
   normative) et `printed_override` (valeur explicite qui déroge à la règle —
   aucune occurrence aujourd'hui).
3. **`geometry_status`** vaut `complete`, `incomplete` ou `infeasible`. Aucune
   référence n'est forcée dans un statut supérieur à ce que les données
   permettent.
4. **`verified`** vaut 0 partout : aucune référence n'a été contrôlée contre une
   copie licite de la norme. Ce champ ne pourra passer à 1 qu'après un contrôle
   documenté, avec `verified_on` renseigné.
5. **Le procédé fait partie de l'identité** : `SHS-HF` et `SHS-CF` sont deux
   séries distinctes, même à désignation égale.
6. **Les propriétés de section ne sont pas des données primaires.** Elles sont
   stockées à part, marquées `independent = 0`, parce qu'elles sont recalculées
   depuis la même géométrie : elles ne peuvent pas valider le modèle.
7. **Une série locale ne se confond jamais avec une référence normalisée.**
   Les séries importées de `data/staging/` portent `usage = 'local_only'` et une
   anomalie `LOCAL_ONLY_DATA`; elles sont exclues de
   `catalogue_inventory_redistributable.csv`. Le §3.7 du cahier des charges
   l'exige : les dimensions commerciales restent « dans une catégorie distincte ».
8. **`category` sépare le normalisé du commercial.** Une série `commercial` ne
   peut pas porter de `standard_id` (garanti à l'import), cite son programme dans
   `commercial_ref` et est signalée par `COMMERCIAL_DATA`. Une requête sur
   `standard_id IS NOT NULL` ne renvoie donc que des séries rattachées à une norme.
9. **Un manque déclaré n'est pas une faute de saisie.** Le bloc TOML `[missing]`
   énumère les paramètres que la source ne publie pas, avec leur motif ; la
   référence est alors importée `incomplete` avec une anomalie bloquante
   `MISSING_PARAMETER` citant ce motif. Un paramètre manquant **non déclaré** fait
   au contraire échouer tout l'import local.
10. **Une note de ligne porte la réserve de la source.** La colonne CSV `note`
    alimente `profile.notes` : coquille d'une colonne dérivée, taille hors norme,
    valeur écartée. La valeur fautive n'est jamais recopiée dans
    `derived_property`.
11. **Les valeurs publiées par le fabricant ne valident pas la géométrie.** La
    masse, la section et la surface des séries `AM-*` sont recopiées dans
    `derived_property` avec `independent = 0`, comme toutes les autres
    propriétés : elles documentent la source, elles ne servent pas de preuve.

### 7.4 Exemples de requêtes

```sql
-- Recherche par désignation ou alias
SELECT p.profile_id, p.geometry_status
FROM profile p
LEFT JOIN profile_alias a ON a.profile_id = p.profile_id
WHERE p.designation_key LIKE 'IPE2%' OR a.alias_key LIKE 'IPE2%'
GROUP BY p.profile_id;

-- Géométrie d'une référence
SELECT * FROM v_profile_geometry WHERE profile_id = 'UPN/UPN 200';

-- Références avec rayons issus d'une règle plutôt que tabulés
SELECT series_id, COUNT(*) FROM profile
WHERE geometry_source = 'table+rule' GROUP BY series_id;

-- Anomalies bloquantes
SELECT ref, code, message FROM catalog_issue WHERE severity = 'blocking';

-- Couverture par famille
SELECT * FROM v_family_stats;

-- Séries commerciales, jamais confondues avec les références normalisées
SELECT series_id, commercial_ref FROM series WHERE category = 'commercial';

-- Références incomplètes et paramètres manquants déclarés
SELECT pp.profile_id, pp.param, pp.note
FROM profile_param pp WHERE pp.value IS NULL;
```

---

## 8. Nombre de références exploitables par famille

« Exploitable » = tous les paramètres obligatoires de la forme sont présents et
la géométrie passe les contrôles de faisabilité. Cela signifie « reconstructible
exactement en Phase 2 », pas « vérifié conforme à la norme ».

| Famille | Séries | dont commerciales | Réf. au catalogue | **Exploitables** | Incomplètes |
|---|---|---|---|---|---|
| I | IPE, IPN | 0 | 39 | **39** | 0 |
| H | HEA, HEB, HEM | 0 | 72 | **72** | 0 |
| U | UPN, UPE | 0 | 32 | **32** | 0 |
| L | L-EQ, L | 0 | 81 | **81** | 0 |
| T | AM-TES | 1 | 7 | **0** | 7 |
| Creux | SHS-HF/CF, RHS-HF/CF, CHS-HF/CF | 0 | 1 506 | **1 506** | 0 |
| Pleins | FLAT, AM-PLATS, AM-LARGES-PLATS, AM-CARRES, AM-RONDS | 4 | 501 | **501** | 0 |
| **Total** | **21** | **5** | **2 238** | **2 231** | **7** |

Ventilation par régime :

| Régime | Séries | Références | Exploitables | Incomplètes |
|---|---|---|---|---|
| normalisé (MIT) | 16 | 1 792 | **1 792** | 0 |
| commercial (ArcelorMittal 2020) | 5 | 446 | **439** | 7 |
| **Total** | **21** | **2 238** | **2 231** | **7** |

Détail par série :

| Série | Cat. | Réf. | Exploitables | Rayons tabulés | Rayons par règle |
|---|---|---|---:|---:|---:|
| IPE | standard | 18 | 18 | 18 | 0 |
| IPN | standard | 21 | 21 | 21 | 0 |
| HEA | standard | 24 | 24 | 24 | 0 |
| HEB | standard | 24 | 24 | 24 | 0 |
| HEM | standard | 24 | 24 | 24 | 0 |
| UPN | standard | 18 | 18 | 18 | 0 |
| UPE | standard | 14 | 14 | 14 | 0 |
| L-EQ | standard | 42 | 42 | 42 | 0 |
| L | standard | 39 | 39 | 39 | 0 |
| SHS-HF | standard | 243 | 243 | 0 | 243 |
| SHS-CF | standard | 163 | 163 | 0 | 163 |
| RHS-HF | standard | 496 | 496 | 0 | 496 |
| RHS-CF | standard | 260 | 260 | 0 | 260 |
| CHS-HF | standard | 114 | 114 | — | 0 |
| CHS-CF | standard | 230 | 230 | — | 0 |
| FLAT | standard | 62 | 62 | — | 0 |
| AM-RONDS | commercial | 69 | 69 | — | 0 |
| AM-CARRES | commercial | 28 | 28 | — | 0 |
| AM-PLATS | commercial | 288 | 288 | — | 0 |
| AM-LARGES-PLATS | commercial | 54 | 54 | — | 0 |
| AM-TES | commercial | 7 | **0** | 7 | 0 |

### Formes peuplées uniquement par le commercial

| Forme | Paramètres | Références | Statut |
|---|---|---|---|
| `ROUND` | D | 69 | complet, catégorie commerciale |
| `SQUARE` | a | 28 | complet, catégorie commerciale |
| `T_TAPERED` | h, b, tw, tf, r1, r2, slope_pct, x_tf | 7 | `incomplete` : `slope_pct` et `x_tf` non publiés ; modèle **provisoire** (§5.1.1) |

Ces trois formes sont importables depuis `data/staging/` sans modification du
code ; elles ne contiennent aucune référence normalisée.

### Couverture des exemples du cahier des charges (§1)

| Exemple demandé | Présent |
|---|---|
| IPE 200 | oui |
| HEA 160 | oui |
| HEB 200 | oui |
| UPN 100 | oui |
| UPE 120 | oui |
| Cornière L 60 × 60 × 6 | oui |
| Cornière L 80 × 60 × 8 | **non** |
| Profilé T 100 × 100 × 11 | **non** (gamme commerciale arrêtée à T 80, et non reconstructible) |
| Tube RHS 100 × 50 × 4 | oui (HF et CF) |
| Tube SHS 80 × 80 × 5 | oui (HF et CF) |
| Tube CHS 60,3 × 3,2 | oui (HF et CF) |
| Plat 50 × 8 | oui (commercial : `AM-PLATS/Plat 50x8`) |
| Rond plein Ø20 | oui (commercial : `AM-RONDS/Rond 20`) |
| Carré plein 30 × 30 | oui (commercial : `AM-CARRES/Carré 30`) |

**12 exemples sur 14** sont couverts. Les 3 ajouts par rapport à la version
précédente (`Plat 50×8`, `Rond Ø20`, `Carré 30×30`) viennent du programme
commercial ; ils ne sont pas des références normalisées. Les 2 manques restants
sont la cornière `L 80×60×8` et le `T 100×100×11`.

---

## 9. Limites du catalogue

### 9.1 Limites de confiance (les plus importantes)

1. **Aucune vérification normative.** `verified = 0` pour les 2 238 références.
   Le dépôt source l'annonce lui-même : les dimensions n'ont pas été contrôlées
   ligne à ligne contre des copies licites des normes. La base ne peut donc pas
   prétendre à une conformité EN, seulement à une « géométrie documentée ».
2. **Deux sources, deux niveaux de contrôle.** Les 1 792 références normalisées
   reposent sur un dépôt unique, sans recoupement indépendant. Les 446
   commerciales sont, elles, recoupées par deux colonnes dérivées du fabricant
   (masse, surface) — mais ces colonnes proviennent du même document, pas d'une
   source tierce.
3. **Provenance au niveau série, pas par valeur.** Voir §5.3.
4. **Éditions non vérifiées.** EN 10365:2017 est remplacée par 2026 ; l'écart
   n'est pas évalué. Même situation pour EN 10056-1 (1998 → 2017).
5. **Rayons de calcul ≠ rayons mesurés** pour les 1 162 profilés creux. `ri` est
   une convention, pas une dimension fabricant.

### 9.2 Limites de couverture

- Famille **T** : 7 dimensions commerciales, **0 référence reconstructible**. La
  pente et `x_tf` ne sont pas publiés (§5.1.1) ; EN 10055 reste à acquérir.
- Famille **pleins** : couverte commercialement (plats, ronds, carrés), sans
  aucune référence normalisée hors `FLAT`. Les listes de tailles viennent du
  fabricant, pas de EN 10058/59/60 (§5.1.2).
- Séries **IPE A/AA/O/V**, **HE C** : absentes.
- `T 100×100×11` et `L 80×60×8` : absents.
- Deux **RHS-HF** exclues volontairement.
- **Aucune tolérance** : le §4 les demande « lorsqu'elles sont disponibles » —
  elles ne le sont pas, et ne doivent pas être reconstituées de mémoire.

### 9.3 Limites de modèle

- Le **rayon de talon `r3`** des cornières lourdes n'est pas modélisé. Sans
  effet sur la gamme actuelle (max 200 × 200 × 26), bloquant au-delà.
- Le modèle **`T_TAPERED`** n'est pas validé contre EN 10055 : sa reconstruction
  est interdite tant que ce n'est pas fait. Les 7 références importées n'ont ni
  pente ni `x_tf`, et `r3` n'est pas mappé.
- **`x_tf` et la pente** sont des paramètres de premier ordre pour UPN/IPN : les
  ignorer fausse l'aire de 0,7 à 1 % (mesuré par la source sur UPN 320 à 400).
  Ils sont présents et doivent être consommés par le générateur.
- **L'orientation locale** (axes y/z, origine) est définie par forme dans la
  source ; elle devra être reprise telle quelle en Phase 2, sinon les propriétés
  de section publiées ne correspondront plus.
- Les **plats** sont stockés « debout » (largeur b selon z), convention à
  conserver pour que `Iy` reste l'axe fort.

### 9.4 Limites de licence

- La **base publiable** est redistribuable, mais la **notice MIT de la source est
  obligatoire**. La base de travail, qui contient les séries commerciales, ne
  l'est pas telle quelle.
- Les **tolérances** ne pourront pas être ajoutées par recopie d'une norme.
- Constructalia est utilisable pour vérifier, **jamais** pour alimenter la base.
- Les séries de `data/staging/` et le catalogue ArcelorMittal **ne sont jamais
  redistribués** : elles ne figurent que dans `catalogue_inventory.csv`, jamais
  dans l'export redistribuable.

---

## 10. Conclusion et entrée en Phase 2

### Ce qui est prêt

- **2 231 références exploitables** sur 2 238, 21 séries, **7 familles sur 7**
  couvertes : 1 792 normalisées (16 séries) et 439 commerciales exploitables
  (4 séries).
- Une base SQLite propre, avec statut et provenance par référence.
- Une séparation stricte normalisé / commercial (`category`, `commercial_ref`,
  `COMMERCIAL_DATA`, export redistribuable séparé).
- Les règles de rayon des creux explicitées et appliquées sans arrondi.
- Un import reproductible, sans dépendance externe, pour les deux régimes.
- Un chemin d'import local (`data/staging/`) pour les données sous licence, isolé
  de l'export redistribuable, avec déclaration explicite des manques (`[missing]`)
  et des réserves de ligne (`note`).

### Ce qui n'est pas prêt

- La famille **T** : 7 dimensions commerciales, **0 référence reconstructible**
  (pente et `x_tf` non publiés). EN 10055 reste à acquérir.
- Les **ronds et carrés pleins** ne sont couverts que commercialement : aucune
  référence normalisée, aucune liste normative.
- La **vérification normative** : 0 référence vérifiée sur 2 238.
- La **provenance ligne à ligne** des séries normalisées.
- Les **tolérances**.
- La **redistribution** de la base de travail : elle contient les séries
  commerciales et doit être reconstruite sans `data/staging/` pour être publiée.

### Recommandation pour la Phase 2

Commencer par le noyau dur, dans cet ordre, en s'appuyant sur les données déjà
en base :

1. **IPE** — 18 références, 5 paramètres, un seul rayon. Le cas d'école du §16.
   Prototype `IPE 200` : h 200 · b 100 · tw 5,6 · tf 8,5 · r 12.
2. **HEA / HEB** — même forme `I`, 48 références supplémentaires.
3. **UPN / UPE** — introduit la pente de semelle et la double paire de rayons.
4. **Cornières L** — introduit le talon vif et les ailes inégales.
5. **Creux SHS / RHS / CHS** — introduit la règle de rayon et le double contour.

Les profilés **T** relèvent de la Phase 5 : leurs dimensions sont documentées,
mais la géométrie n'est pas reconstructible sans EN 10055. Les **plats, ronds et
carrés** commerciaux sont utilisables localement dès la Phase 2 (leur géométrie
est exacte par désignation), mais ne doivent pas être présentés comme normalisés
ni figurer dans une publication de la base.

Deux décisions à prendre avant la Phase 2 :

1. **Licence du projet** : MIT (recommandé, compatible avec la source) ou
   GPL-3.0.
2. **Traitement du champ `verified`** : faut-il acquérir les normes et lancer un
   contrôle ligne à ligne (coût réel, mais condition d'un catalogue qualifié),
   ou assumer un catalogue « documenté, non vérifié » et l'afficher clairement
   dans l'interface ?

Une troisième décision conditionne les familles T et pleins :

3. **Alimentation des familles T / ronds / carrés** — trois voies possibles :
   (a) acheter EN 10055 / 10058 / 10059 / 10060 et saisir les tableaux en local ;
   (b) fournir un programme fabricant autorisé pour les tailles commerciales,
   dans la catégorie distincte du §3.7 ; (c) assumer une base partielle et
   documenter l'absence.

   **Voie retenue et exécutée : (b), catégorie commerciale assumée.** Le
   programme est nommé : catalogue général ArcelorMittal Distribution Solutions
   France, édition 2020, pages 49–52 / 57 / 59 / 60 (`docs/sources.md` §12).
   446 références sont importées, isolées et non redistribuables. Les manques
   résiduels sont la pente et `x_tf` des T : ils ne peuvent être comblés que par
   une copie licite de EN 10055 (voie a, pour la seule famille T).

### État après la Phase 2 (30 octobre 2026)

Les cinq étapes recommandées ont été exécutées dans l'ordre, plus les plats,
ronds et carrés commerciaux : **2 231 profilés complets reconstruits, 0 échec
géométrique**. Les 7 T restent refusés explicitement, faute de pente et de
`x_tf`. Détail, conventions et résultats de validation :
[`docs/geometry.md`](geometry.md).

Les deux décisions de licence et de champ `verified` restent ouvertes : le
catalogue est aujourd'hui « documenté, non vérifié », avec `verified = 0`
partout.
