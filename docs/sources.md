# Sources de données — analyse Phase 1

Date d'examen : 30 octobre 2026.

Chaque source annoncée au §4 du cahier des charges a été ouverte, examinée et
classée. Le verdict final est dans la colonne « décision ».

| # | Source | Type | Décision |
|---|--------|------|----------|
| 1 | Steel Section Database (GitHub) | dépôt de données | **retenue** comme source unique |
| 2 | Ahan Assa | site commercial | écartée |
| 3 | ArcelorMittal Constructalia | site fabricant | **référence de contrôle uniquement** |
| 4 | CADXChange | bibliothèque DXF | écartée (injoignable) |
| 5 | Normes EN / DIN | normes | **référence normative uniquement** |
| 6 | theolternative.com | site d'applications iOS | écartée (deux motifs indépendants) |
| 7 | Montanstahl / Edelstahl Lechner | sites fabricants | écartés (produit différent : T soudés) |
| 8 | Dlubal | outil de propriétés de sections | **référence de contrôle uniquement** |
| 9 | BSSA | association technique | **référence de contrôle uniquement** |
| 10 | Dépôts de recherche (Zenodo, DataCite, figshare) | jeux de données | sans résultat |
| 11 | ArcelorMittal — catalogue général 2020 (PDF) | catalogue fabricant | **retenue** en catégorie commerciale, `local_only` (§12) |

---

## 1. Steel Section Database — retenue

- URL : https://github.com/ulmewix/Steel_Section_Database
- Auteur : Adam Koudelka (`ulmewix`), licence MIT, `main` au 2026-09-28.
- Archive collectée : `data/sources/Steel_Section_Database.zip`
  — 559 304 octets — SHA-256 `b4345c97490be6ad909d21c655eb55299b5c43eba56943c6253a58c06280123f`
- Extraction : `data/sources/Steel_Section_Database-main/` (155 fichiers).
- Dépôt non cloné par `git` (absent de la machine) : l'archive ZIP de la branche
  `main` est équivalente pour l'analyse et permet d'en figer l'empreinte.

### Ce qui a été examiné

| Élément | Contenu | Exploité |
|---|---|---|
| `data/<famille>/<SÉRIE>.csv` | 16 tables de géométrie primaire | oui, intégralement |
| `data/<famille>/<SÉRIE>.toml` | métadonnées de série (norme, procédé, règle de rayon, alias) | oui |
| `docs/DATA_MODEL.md` | sémantique exacte des colonnes, contrôles de faisabilité, notes de série | oui |
| `docs/CONVENTIONS.md` | conventions de calcul, axes, statuts `unsupported` | consulté |
| `generated/properties/<SÉRIE>.csv` | propriétés dérivées (A, I, W, masse…) | recopiées à part, marquées non indépendantes |
| `generated/web/*.json` | contrat JSON public (schéma v2) | non utilisé (redondant avec les CSV) |
| `schema/*.json` | schémas de validation des fichiers | consulté |
| `section_properties/shapes/*.py` | constructeurs de contour (référence pour la Phase 2) | consulté, non copié |
| `LICENSE` | MIT | oui |

Aucun fichier DXF n'est présent dans ce dépôt : la géométrie y est décrite
paramétriquement (`h, b, tw, tf, r…`), ce qui est préférable pour la Phase 2 —
une reconstruction depuis un DXF apporterait des approximations de polylignes.

### Contenu réel

16 séries, 1 792 profils, 6 familles sur les 7 du cahier des charges :

| Famille | Séries | Références |
|---|---|---|
| I | IPE 18, IPN 21 | 39 |
| H | HEA 24, HEB 24, HEM 24 | 72 |
| U | UPN 18, UPE 14 | 32 |
| L | L-EQ 42, L 39 | 81 |
| T | — | 0 |
| Creux | SHS-HF 243, SHS-CF 163, RHS-HF 496, RHS-CF 260, CHS-HF 114, CHS-CF 230 | 1 506 |
| Pleins | FLAT 62 | 62 |

### Qualité — ce que le dépôt déclare lui-même

Le dépôt est méthodiquement honnête, et c'est la raison principale de le retenir :

- `standard` désigne la norme qui *définit* la série, pas une vérification :
  « The dimensions have not yet been checked row by row against licensed copies
  of the standards' tables » (`docs/DATA_MODEL.md`).
- Les rayons d'angle des profilés creux ne sont pas tabulés : ils sont *calculés*
  par la règle de EN 10210-2:2006 §A.3 / EN 10219-2:2006 §B.3, en arithmétique
  décimale exacte.
- Les valeurs infaisables sont rejetées, jamais corrigées (2 RHS-HF exclues).
- Les propriétés dépendant d'une convention (`It`, `Wt`, `Iw`, `ym`, `Avy`, `Avz`)
  sont publiées avec leur méthode ou laissées `unsupported`.

### Réserves

1. **Provenance ligne à ligne absente** : la source primaire (édition de la
   norme, tableau, catalogue) n'est pas identifiée pour chaque valeur, seulement
   au niveau de la série et dans les notes.
2. **Éditions non vérifiées** : EN 10365:2017 est remplacée par EN 10365:2026 ;
   l'écart n'est pas évalué. Même situation pour EN 10056-1:1998 → 2017.
3. **Gammes mixtes** : les cornières ne sont pas la gamme d'une seule norme
   (43 tailles sur 81 seulement sont dans EN 10056-1:1998).
4. **Plats** : l'appartenance à EN 10058 est une hypothèse explicite, non
   vérifiée. La gamme est étroite (largeurs 160 à 230 mm).
5. **Masse** : `mass_kg_m` est recalculée depuis la géométrie (ρ = 7 850 kg/m³
   par défaut) — ce n'est pas une masse catalogue indépendante.

---

## 2. Ahan Assa — écartée

- URL : https://www.ahanassa.com/ (site en persan, négociant iranien).
- Pages examinées : accueil, `/about`, `/contact`.
- Contenu : catalogue commercial (میلگرد, تیرآهن, نبشی, ناودانی, قوطی, ورق,
  لوله), prix du jour, services de transformation.
- Constats :
  - aucune table dimensionnelle normalisée téléchargeable ;
  - aucune licence, aucune mention de réutilisation, aucun fichier CAO ;
  - désignations locales, non alignées sur les séries EN (pas d'IPE/HEA/UPN) ;
  - l'essentiel du site est en persan, sans tableaux de dimensions.
- Verdict : **aucune donnée exploitable**. Par défaut, l'absence de licence vaut
  « tous droits réservés ». Écartée.

## 3. ArcelorMittal Constructalia — référence de contrôle seulement

- URL : https://constructalia.arcelormittal.com/
- Conditions d'utilisation examinées :
  https://constructalia.arcelormittal.com/en/links/terms-of-use
- Extraits déterminants :
  - « The content may not be sold, distributed, transmitted, copied, modified,
    or decompiled, in any way, without the prior written consent of
    ArcelorMittal. »
  - « Visitors may download, display, and print one copy of the Website on their
    personal computer for private and non-commercial use. »
  - « create derivative works of Website content » figure parmi les usages
    interdits.
- Verdict : **interdiction explicite de redistribution et de création d'œuvres
  dérivées**. Constructalia reste utile pour *vérifier à la lecture* une valeur
  douteuse (par exemple L 150×100×14), mais ne peut ni alimenter la base ni
  servir de source d'export. Aucun tableau n'en a été recopié.

## 4. CADXChange — écartée (injoignable)

- URL : https://www.cadxchange.com/ — résolution DNS vers 207.148.248.143.
- Deux tentatives depuis cet environnement :
  - `https://www.cadxchange.com/` → délai dépassé ;
  - `http://www.cadxchange.com/` → connexion réinitialisée par l'hôte.
- Aucune page, aucun fichier DXF, aucune condition d'utilisation n'a pu être lue.
- Verdict : **non vérifiable ; écartée**. À réexaminer depuis un navigateur si
  l'on veut des DXF de constructeurs, en gardant à l'esprit que ces fichiers
  sont presque toujours sous licence propre au constructeur.

## 5. Normes EN / DIN — référence normative seulement

Normes citées par les données (jamais reproduites) :

| Norme | Édition | Rôle | Statut |
|---|---|---|---|
| EN 10365 | 2017 | IPE, IPN, HEA, HEB, HEM, UPN, UPE | remplacée par 2026 (non évalué) |
| EN 10365 | 2026 | édition en vigueur | non consultée |
| EN 10056-1 | 1998 | cornières : géométrie et convention de calcul | remplacée par 2017 |
| EN 10056-1 | 2017 | cornières : rayons de certaines tailles (L 110×110×10) | citée par la source |
| EN 10024 | 1995 | IPN : position de mesure de `tf` (§4.4) | citée |
| DIN 1025-1 | 2009 | IPN : rayons `r1`, `r2` | citée |
| DIN 1026-1 | 2009 | UPN : rayons, pente | citée |
| DIN 1026-2 | 2002 | UPE : rayons | citée |
| EN 10210-2 | 2006 | creux finis à chaud : rayons, tolérances | citée |
| EN 10219-2 | 2006 | creux formés à froid : rayons, tolérances | citée |
| EN 10058 | 2018 | plats | **hypothèse**, non vérifiée |
| EN 10055 | 1995 | profilés T laminés : dimensions et tolérances | citée, **aucune donnée** |
| EN 10059 | 2003 | carrés pleins laminés : dimensions et tolérances | citée, **aucune donnée** |
| EN 10060 | 2003 | ronds pleins laminés : dimensions et tolérances | citée, **aucune donnée** |

Ces trois dernières normes sont enregistrées au catalogue (`standard`) pour que la
provenance d'une future série locale soit déclarable. Aucune valeur n'en est issue
à ce jour : les dimensions T viennent du catalogue commercial ArcelorMittal, pas
de EN 10055, et les ronds/carrés pleins ne sont couverts que commercialement
(§11 et §12).

Les normes EN sont protégées : l'achat d'une copie n'autorise pas la
redistribution des tableaux. Le catalogue ne stocke donc que des **faits
dimensionnels** (une hauteur, une épaisseur) avec citation de la norme et de
l'édition, sans reproduction de texte normatif. Voir `docs/licenses.md`.

---

## 6. theolternative.com — écartée, sur deux motifs indépendants

- URL : https://theolternative.com/ (applications iOS « Steel Profiles » /
  « Steel Profiles Pro » par Matteo Rossi). Pages examinées : accueil,
  `/steel-sections/`, `/apps/steel-profiles-free/`.
- **Motif 1 — aucun droit.** Le site n'a **aucune page de mentions légales**, aucune
  page de conditions d'utilisation, aucune ligne de copyright, aucune licence,
  aucun lien vers un document juridique. L'ensemble des liens du site a été
  énuméré : uniquement des liens internes vers les applications et l'App Store.
  En droit d'auteur, l'absence d'autorisation vaut « tous droits réservés » :
  aucune donnée ne peut être reprise, ni même stockée localement.
- **Motif 2 — la table T est géométriquement insuffisante.** Elle ne fournit que
  `(h, b, t, r, r1, r2)` avec `r = t` pour les 7 tailles annoncées, donc **sans
  séparation `tw` / `tf` et sans pente**, alors que les profilés T de EN 10055
  sont à semelles *et* âme inclinées (§8). Une telle table ne permet pas de
  reconstruire la section. Elle contredit par ailleurs Dlubal, qui documente un
  **T 100** sous EN 10055 : la gamme annoncée « T 30 à T 80 » est incomplète.
- Verdict : **écartée**. Le second motif suffirait à lui seul ; le premier rend la
  question sans objet.

## 7. Montanstahl / Edelstahl Lechner — écartés (produit différent)

- URLs : https://www.montanstahl.com/…/stainless-steel-tees/equal-t-bars/ et
  https://www.edelstahl-lechner.de/en/stock-range/t-sections-polished-raw/t-sections.html
- Ces fabricants vendent des **T soudés au laser à épaisseur constante** : les
  deux ailes et l'âme ont la même épaisseur, les rayons valent 2 mm, et la norme
  EN 10055 n'est citée que pour les *tolérances*, pas pour la géométrie.
- Ce n'est **pas** le produit de EN 10055 (T laminés à semelles et âme inclinées).
  Mélanger les deux créerait une série homogène en apparence et fausse en
  géométrie.
- Contenu sous copyright du fabricant, sans licence de réutilisation.
- Verdict : **écartés** comme source de données ; conservés comme illustration de
  la confusion à éviter.

## 8. Dlubal — vérification de la géométrie des T

- URL : https://www.dlubal.com/en/cross-section-properties/t-100-din-en-10055-1995-12
- Outil gratuit de propriétés de sections ; la fiche consultée décrit un **T 100**
  sous « DIN EN 10055:1995-12 » (également rattaché à EN 10055:1995, DIN 1024 et
  ČSN EN 10055).
- Ce que la fiche établit, et qui est **retenu comme fait de référence** :
  - les T de EN 10055 sont **laminés à chaud**, à **semelles inclinées et âme
    inclinée** ;
  - le jeu de paramètres est `h, b, tw, tf, r1, r2` (plus la pente et la position
    du raccordement), c'est-à-dire que `tw ≠ tf` — un T n'est pas décrit par une
    seule épaisseur ;
  - **un T 100 existe** dans la série.
- L'outil ne publie pas de table complète exportable et son contenu n'est pas
  sous licence libre : il sert à **contrôler** un modèle, pas à alimenter la base.
- Verdict : **référence de contrôle uniquement**. Aucune valeur n'en est reprise.

## 9. BSSA — ce que sont réellement EN 10058/59/60

- URL : https://bssa.org.uk/bssa_articles/tolerances-to-bs-en-10059-for-hot-rolled-square-stainless-steel-bars/
- La note décrit la structure du **tableau 2 de BS EN 10059** : des **bandes de
  taille** (8–14, 15–25, 26–35, 40–50, 55–90, 100, 110–120, 130–150 mm) et, pour
  chaque bande, un **rayon d'angle maximal**, pas un rayon nominal.
- Conséquence, décisive pour la conception : **EN 10058, EN 10059 et EN 10060 sont
  des normes de tolérances, pas des catalogues de tailles.** Elles ne publient pas
  de « liste officielle des diamètres et des côtés » à recopier. Un carré plein n'a
  donc pas de rayon nominal : son `r` est une *borne de tolérance*.
- Verdict : **référence de contrôle uniquement**, et source de la conclusion du
  §11.

## 10. Recherche d'un jeu de données sous licence libre — sans résultat

Recherche menée sur les dépôts de données et de code, pour les familles T et
pleins :

| Piste | Constat |
|---|---|
| GitHub (recherche de dépôts) | `section_library`, `sectionproperties` : pas de table EN 10055 ; `steelpy` et `steelsections-cisc` : AISC / CISC uniquement |
| grep.app | HTTP 429 (limitation), aucun résultat exploitable |
| searchcode | API HTTP 404 |
| Sourcegraph (API stream) | délai dépassé |
| Zenodo | aucune table de profilés EN ; les résultats « steel » concernent la recherche, pas les catalogues |
| DataCite | idem |
| figshare | idem |

**Aucun jeu de données EN 10055 / 10058 / 10059 / 10060 sous licence permissive
n'existe publiquement.** Les seules tables complètes disponibles sont soit des
normes (payantes, non redistribuables), soit des sites commerciaux sans licence.

---

## 11. Conclusion sur les familles T et pleins

Deux situations distinctes, souvent confondues :

**Profilés T — dimensions trouvées, géométrie toujours non reconstructible.**
EN 10055 définit une géométrie à six paramètres (`h, b, tw, tf, r1, r2`) plus la
pente des faces et la position de mesure de `tf`. Le catalogue ArcelorMittal 2020
(§12) publie `h, b, e, e1, r1, r2` pour **7 tailles** (T 20 à T 80) : les
dimensions nominales sont donc disponibles, mais **ni la pente ni `x_tf`**. Ces
7 références sont importées `incomplete`, bloquées par `MISSING_PARAMETER` ; elles
documentent des dimensions, pas une géométrie reconstructible. Le modèle de forme
`T_TAPERED` reste **provisoire** : il n'est pas validé contre la norme.

**Plats, carrés et ronds — géométrie exacte sans table.** Un plat est `b × t`, un
carré `a × a`, un rond `Ø D` : la géométrie est **entièrement définie par la
désignation**, sans rayon, sans pente, sans raccordement. Il n'y a donc rien à
« tabuler » du point de vue géométrique. Seule la **liste des tailles** est
commerciale ou normative — et, comme le montre le §9, ces normes ne la publient
pas. Cette liste est désormais fournie par le catalogue ArcelorMittal 2020
(§12), en catégorie commerciale. Le cahier des charges l'autorise explicitement
(§3.7 : « les dimensions commerciales supplémentaires pourront être ajoutées dans
une catégorie distincte, sans les confondre avec les références normalisées »).

**Conséquence pratique.** Un dépôt local `data/staging/` permet d'importer une
gamme fournie par l'utilisateur (copie licite d'une norme, programme fabricant
autorisé) sans jamais la livrer : ces séries sont marquées
`usage = 'local_only'`, `redistribution = 'restricted'`, tracées par une anomalie
`LOCAL_ONLY_DATA`, et **exclues** de l'export
`catalogue_inventory_redistributable.csv`. Le contrat de fichier est décrit dans
`data/staging/README.md`. C'est ce mécanisme qui porte les cinq séries `AM-*`
du §12.

La séparation du §3.7 est de plus portée par la colonne `series.category`
(`standard` / `commercial`) : une série commerciale ne peut pas déclarer de norme,
doit citer son programme (`commercial_ref`) et reçoit l'anomalie `COMMERCIAL_DATA`.

Voies possibles pour remplir ces familles :

1. **Acheter EN 10055 / 10058 / 10059 / 10060** et saisir les tableaux en local
   (import `local_only`, jamais redistribué) ;
2. **Fournir un programme fabricant autorisé** pour les tailles commerciales,
   dans la catégorie distincte prévue au §3.7 — **voie retenue et exécutée** :
   catalogue général ArcelorMittal 2020, voir §12 ;
3. **Assumer une base partielle** : T à 0, plats/carrés/ronds limités aux tailles
   dont la géométrie est déjà connue, en documentant l'absence.

La voie 2 est en place : cinq séries commerciales (`AM-RONDS`, `AM-CARRES`,
`AM-PLATS`, `AM-LARGES-PLATS`, `AM-TES`) portent **446 références**, importées
depuis `data/staging/`, jamais incluses dans l'export redistribuable. Les
dimensions proviennent toutes du catalogue 2020, aucune n'est inventée ni
interpolée. Les 7 références T restent, elles, inconstructibles faute de pente et
de `x_tf`.

Aucune de ces voies n'autorise à inventer une dimension ni à présenter une donnée
commerciale comme une référence normalisée.

## 12. ArcelorMittal — catalogue général 2020 (catégorie commerciale)

### Source

- Document : *Catalogue général*, ArcelorMittal Distribution Solutions France,
  édition 2020, PDF de 21 608 979 octets.
- Emplacement local : `data/sources/Arcelor-Catalogue-Web-2020-avec-liens-bouton-light.pdf`
  — SHA-256 `3c23ac7d2b0af6c420343e23aa857326eaade571cd7e6b16b43d2e4fdbae0d82`.
- Licence : **propriétaire, tous droits réservés**. Aucune autorisation écrite de
  redistribution n'a été obtenue.
- Statut dans la base : `source_kind = 'manufacturer'`, `redistribution = 'restricted'`,
  `usage = 'local_only'`, `category = 'commercial'`.

Ce document est la **voie 2** du §11 : il fournit les listes de tailles qui
manquaient aux familles T et pleins, sans jamais les faire passer pour des séries
normalisées. Le PDF reste dans `data/sources/`, mais **ne doit pas être publié** ;
la base construite avec `data/staging/` peuplé n'est pas redistribuable telle
quelle (voir `docs/licenses.md` §9).

### Méthode d'extraction

Aucune valeur n'a été recopiée à la main ni lue par OCR :

1. Les flux de texte du PDF ont été décompressés avec la bibliothèque standard
   (`zlib`) ; les tableaux ont été localisés par leur flux (pages 49–51 pour les
   plats, 52 pour les larges plats, 57 pour les T, 59 pour les ronds, 60 pour les
   carrés).
2. Chaque valeur a été affectée à une colonne par sa **coordonnée horizontale**
   (bandes de colonnes fixes), pas par l'ordre de lecture du flux.
3. La fenêtre verticale d'extraction a été calée sur les filets du tableau. Un
   défaut initial (`y ≥ 430`) coupait silencieusement la première ligne de chaque
   page : il a été corrigé (`y ≥ 60`), ce qui a rétabli le rond Ø5, les plats
   14×3 / 18×5 / 55×6 et les T 20\* / 25\*.
4. Aucun arrondi, aucune conversion d'unité : les valeurs sont celles du tableau,
   en millimètres.
5. Les utilitaires (`extract_pdf.py`, `am_parse.py`, `am_extract.py`,
   `am_staging.py`) sont conservés dans `data/staging/tools/`, avec le PDF
   attendu à cet emplacement et son empreinte vérifiée. Relancés, ils
   reproduisent les 15 fichiers `AM-*` **à l'octet près** ; ils ne sont jamais
   distribués (voir `data/staging/tools/README.md`).

### Double recoupement des lignes

Le catalogue publie, pour chaque ligne, deux colonnes dérivées indépendantes des
dimensions. Elles servent de contrôle, jamais de source :

| Colonne | Relation utilisée |
|---|---|
| Masse linéique | `m [kg/m] = A [cm²] × 0,785` (soit 7,85 kg/dm³) |
| Surface de peinture | `s [m²/m] = 2 × (l + e) / 1000` (plats, larges plats, T) |
| Section des ronds | `A = π D² / 4` |
| Section des carrés | `A = a²` |
| Section des T | `A = b·e1 + (h − e1)·e` (à ±0,5 %) |

Règle d'arbitrage appliquée ligne à ligne :

- **les deux colonnes confirment** → ligne retenue ;
- **une seule confirme** → dimensions retenues, coquille de l'autre colonne
  consignée en note (`profile.notes`), valeur fautive **non recopiée** dans
  `derived_property` ;
- **aucune ne confirme** → ligne **écartée**, jamais corrigée.

Une coquille porte toujours sur une colonne *dérivée*. Aucune ligne n'a été
corrigée à partir d'un calcul : une dimension contredite par plusieurs colonnes
publiées est un défaut de la source, pas une invitation à la corriger.

### Références retenues, par série

| Série | Forme | Lignes publiées | Retenues | Écartées | Notes |
|---|---|---:|---:|---:|---|
| `AM-RONDS` | `ROUND` | 69 | **69** | 0 | aucune anomalie ; Ø 6 à 250 mm |
| `AM-CARRES` | `SQUARE` | 28 | **28** | 0 | 1 coquille de masse (carré 5) |
| `AM-PLATS` | `FLAT` | 288 | **288** | 0 | 12 coquilles de surface, 6 de masse (dont 1 ligne cumulant les deux) |
| `AM-LARGES-PLATS` | `FLAT` | 54 | **54** | 0 | 1 coquille de surface |
| `AM-TES` | `T_TAPERED` | 9 | **7** | **2** | voir ci-dessous |
| **Total** | | **448** | **446** | **2** | |

Les 446 références sont `geometry_complete` pour les ronds, carrés et plats (leurs
paramètres obligatoires suffisent), et `incomplete` pour les 7 T.

### Lignes T écartées

| Ligne | Motif d'exclusion |
|---|---|
| **T 25\*** | `e1 = 0,5 mm` et `r1 = 0,5 mm` sont physiquement impossibles ; la section publiée (1,64 cm²) et la masse (1,29 kg/m) impliquent 3,5 mm. La ligne n'est pas corrigée : elle est écartée. |
| **T 45\*** | `e = 5 mm` contredit la section (4,67 cm²), la masse (3,67 kg/m) et `r1 = 5,5 mm`, qui décrivent tous une section uniforme de 5,5 mm. Écartée, non corrigée. |

L'astérisque du catalogue signale en outre les tailles **hors NF EN 10055**
(T 20 et T 25) ; l'information est conservée en note pour T 20.

### Cas conservé avec réserve : plat 80 × 35

Ses deux colonnes dérivées (masse 21,2 kg/m, surface 0,25 m²/m) sont
incohérentes avec 80 × 35 (attendu 21,98 kg/m et 0,23 m²/m) et **coïncident avec
les lignes voisines 90×30 / 90×35**. Les colonnes *Dimensions* (80 et 35),
seules valeurs primaires de la ligne, sont retenues telles quelles ; les deux
valeurs dérivées sont écartées et la réserve est écrite dans `profile.notes`,
sans correction.

### Ce que le catalogue ne permet pas

- **T : géométrie non reconstructible.** Le catalogue ne publie ni la pente des
  semelles ni la position de mesure de `tf`. Les 7 T sont donc `incomplete` avec
  `slope_pct` et `x_tf` déclarés manquants (`[missing]`), et bloqués par
  `MISSING_PARAMETER`.
- **`r3` non repris.** Le troisième rayon du tableau T (1,00 à 2,00 mm) n'a pas
  de signification documentée : il n'est pas mappé, seulement signalé.
- **T 100 × 100 × 11** (exemple du cahier des charges) n'est pas au catalogue :
  la gamme s'arrête à T 80.
- **Aucune norme.** Les intitulés « EN 10058 / 10059 / 10060 / 10055 » du
  catalogue ne sont pas des références vérifiées : `standard_id` reste `NULL`
  pour les cinq séries.

### Droits et portée

- Le PDF et les fichiers `data/staging/AM-*` sont **locaux** ; ils ne sont jamais
  livrés avec le projet.
- Les cinq séries sont exclues de
  `data/catalogue_inventory_redistributable.csv` (1 792 lignes, aucune
  commerciale).
- Une reconstruction publiée avec `data/staging/` vide ne contient que les
  1 792 références normalisées ; `check_catalogue.py --publish` le vérifie.
- Aucune valeur du catalogue n'est déclarée `verified`.

---

## Sources non retenues mais à prévoir pour la Phase 5

1. **EN 10055** (profilés T laminés) — tableaux de dimensions, à acquérir ou à
   faire vérifier par un bureau d'études disposant d'une copie licite.
2. **EN 10059** (carrés pleins) et **EN 10060** (ronds pleins) — la norme ne
   publie pas de liste de tailles (§9) ; c'est le programme commercial du
   fabricant qu'il faut documenter, ou la liste de tailles choisie par le projet.
3. **Catalogues fabricants** (ArcelorMittal, Tata, voestalpine) — utilisables
   pour *vérifier*, sous réserve d'autorisation écrite pour la redistribution.
4. **Séries IPE A / AA / O / V et HE C** — mêmes réserves ; la section HE 300 C
   (320 × 305) est le cas le plus fréquent, souvent appelée à tort « HEM 320/305 ».
