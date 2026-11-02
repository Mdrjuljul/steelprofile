# Licences et droits de redistribution

Le cahier des charges (§4) met en garde : *la licence du code d'un dépôt ne donne
pas automatiquement les droits sur toutes les données qu'il contient*. Cette note
tranche, source par source, ce que le projet peut stocker, modifier et
redistribuer.

## Synthèse

| Source | Licence / conditions | Stockage local | Redistribution | Décision |
|---|---|---|---|---|
| Steel Section Database | MIT (© 2026 Adam Koudelka) | oui | **oui**, avec conservation de la mention de copyright et de la licence | source de données |
| Constructalia | propriétaire, tous droits réservés | consultation seulement | **non** | référence de contrôle |
| Ahan Assa | non déclarée → droits réservés | non | non | écartée |
| CADXChange | non vérifiable | non | non | écartée |
| Normes EN / DIN | © CEN / DIN, texte non libre | citation des désignations et éditions | **non** (pas de reproduction de tableaux) | référence normative |
| theolternative.com | aucune licence, aucun copyright → droits réservés | non | non | écartée |
| Montanstahl / Edelstahl Lechner | © fabricants, pas de licence de réutilisation | non | non | écartés |
| Dlubal | outil propriétaire, consultation gratuite | non | non | référence de contrôle |
| BSSA | © BSSA, article technique public | non | non | référence de contrôle |
| `data/staging/` (données fournies) | selon la source déclarée dans le TOML | **oui** | **non** (sauf `redistribution = "allowed"`) | catégorie locale |
| Catalogue ArcelorMittal 2020 (PDF) | propriétaire, tous droits réservés | **oui** | **non** | séries commerciales locales, jamais livrées |
| PySide6 / Qt (interface) | LGPLv3 | installé par l'utilisateur, non modifié | **non distribué avec le code** | dépendance d'interface, import dynamique |

## 1. Steel Section Database — MIT

Le fichier `LICENSE` du dépôt est la licence MIT, « Copyright (c) 2026 Adam
Koudelka ». Elle autorise explicitement :

> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software

Elle couvre le dépôt tel qu'il est publié, données comprises : les fichiers
`data/*.csv` et `data/*.toml` ne portent aucune mention de source tierce ni de
restriction supplémentaire. Il n'y a donc pas de « licence de code » distincte de
la « licence des données » dans ce dépôt.

**Obligations du projet :**

1. Conserver la mention de copyright et le texte de la licence MIT dans toute
   redistribution des données, y compris sous forme de base SQLite dérivée.
2. Ne pas laisser croire que l'auteur d'origine cautionne le projet.
3. Fournir le texte de la licence avec `data/profiles.db`.

Ces obligations sont satisfaites par `THIRD-PARTY-NOTICES.md`, qui reprend le
texte de la licence et cite la colonne `source.license` de la base.

**Point d'attention** : la licence MIT porte sur le *fichier tel que publié*.
Elle ne garantit pas que l'auteur d'origine avait lui-même le droit de publier
chaque valeur dimensionnelle. Une dimension nominale est un fait, non une œuvre ;
le risque résiduel porte sur la sélection et l'organisation d'un tableau complet,
qui pourrait relever du droit *sui generis* des bases de données (directive
96/9/CE). C'est un risque faible pour des dimensions normalisées, mais il existe.

## 2. Constructalia — interdiction explicite

Conditions d'utilisation (https://constructalia.arcelormittal.com/en/links/terms-of-use) :

> The content may not be sold, distributed, transmitted, copied, modified, or
> decompiled, in any way, without the prior written consent of ArcelorMittal.

> Visitors may download, display, and print one copy of the Website on their
> personal computer for private and non-commercial use.

> Users shall not: … create derivative works of Website content.

Conséquence : Constructalia ne peut servir qu'à **lire et vérifier** une valeur.
Aucun tableau, aucune capture, aucun fichier CAO n'en est intégré. Si le projet
veut un jour s'appuyer dessus, il faut une autorisation écrite d'ArcelorMittal.

## 3. Ahan Assa — pas de licence

Aucune page de mentions légales, aucune licence, aucun fichier téléchargeable.
En droit d'auteur, l'absence d'autorisation vaut interdiction. Source écartée,
aucune donnée reprise.

## 4. CADXChange — non vérifiable

Site injoignable depuis l'environnement d'analyse (délai dépassé puis connexion
réinitialisée). Aucune condition d'utilisation n'a pu être lue, donc aucune
donnée n'a été reprise. Les DXF de constructeurs qui circulent sur ce type de
plateforme sont en général sous licence propre : une vérification au cas par cas
serait nécessaire.

## 5. Normes EN et DIN — citation, pas reproduction

Les normes européennes sont protégées par le droit d'auteur du CEN et de ses
membres nationaux. L'achat d'une copie donne un droit d'usage personnel, pas un
droit de redistribution des tableaux.

Ce que le projet fait :

- il cite la norme par **désignation et édition** (`EN 10365:2017`,
  `EN 10210-2:2006`) ;
- il stocke des **faits dimensionnels** (h = 200 mm, r = 12 mm), qui ne sont pas
  une reproduction d'ouvrage ;
- il ne recopie **aucun texte normatif**, aucune note de bas de tableau, aucune
  figure ;
- il ne distribue **aucun PDF** de norme.

Ce que le projet ne fait pas, et ne doit pas faire :

- reprendre un tableau normatif complet « tel quel » avec sa mise en forme ;
- recopier les tolérances, annotations et règles de calcul qui ne sont pas de
  simples valeurs ;
- présenter la base comme une « copie de la norme ».

**Conséquence pour la Phase 2** : les valeurs de tolérance ne sont pas dans la
base, et ne doivent pas y être ajoutées par recopie d'une norme. Si un jour elles
sont nécessaires, il faudra soit une autorisation, soit se limiter à ce que la
norme publie gratuitement (avant-propos, sommaires) — ce qui ne couvre pas les
tableaux.

## 6. Sites commerciaux, outils et associations — aucun droit de reprise

Ces sources ont été examinées pour les familles T et pleins (voir
`docs/sources.md` §6 à §10). Aucune ne donne de droit de reprise.

**theolternative.com** — site d'applications iOS. Aucune page de mentions légales,
aucune condition d'utilisation, aucune ligne de copyright, aucune licence. En
droit d'auteur, l'absence d'autorisation vaut interdiction : rien ne peut être
stocké, même localement. S'y ajoute un motif technique (table T inutilisable),
mais le motif juridique suffit.

**Montanstahl / Edelstahl Lechner** — contenu sous copyright du fabricant, sans
licence de réutilisation ; les tables sont des T soudés au laser, produit distinct
de EN 10055. Écartés.

**Dlubal** — outil gratuit de consultation, contenu propriétaire. Sert uniquement
à *contrôler* un modèle de forme ; aucune valeur n'est reprise.

**BSSA** — article technique public, © BSSA. Sert à établir la *structure* des
normes EN 10058/59/60 (bandes de taille, rayon maximal), pas à fournir des
valeurs de catalogue.

## 7. `data/staging/` — données locales, jamais redistribuées

Le cahier des charges prévoit (§3.5, §3.7) que des dimensions commerciales ou
fournies par le fabricant puissent être ajoutées. Ces données ne sont pas
redistribuables par défaut, d'où un mécanisme séparé :

- chaque série locale déclare sa provenance dans son TOML (`source_id`,
  `source_name`, `source_license`, `redistribution`) ;
- elle est enregistrée avec `usage = 'local_only'` ;
- si `redistribution` n'est pas `allowed`, la série est exclue de
  `data/catalogue_inventory_redistributable.csv` ;
- une anomalie `LOCAL_ONLY_DATA` la signale dans `catalog_issue` ;
- le répertoire `data/staging/` n'est pas livré avec le projet.

**Règle** : une série locale ne peut jamais être présentée comme une référence
normalisée vérifiée. Le champ `verified` reste à 0 tant qu'aucune copie licite de
la norme n'a été confrontée ligne à ligne.

Le schéma distingue en outre `category = 'standard'` et `'commercial'` (§3.7) :
une série commerciale ne peut pas porter de norme, doit citer son programme
(`commercial_ref`) et est signalée par `COMMERCIAL_DATA`. Une dimension commerciale
reste donc identifiée comme telle dans toutes les vues et tous les exports.

### Cas concret : catalogue ArcelorMittal 2020

Cinq séries commerciales (`AM-RONDS` 69, `AM-CARRES` 28, `AM-PLATS` 288,
`AM-LARGES-PLATS` 54, `AM-TES` 7 — **446 références**) sont importées depuis ce
catalogue. Le TOML de chaque série déclare :

```toml
source_id = "arcelormittal-catalogue-2020"
source_kind = "manufacturer"
source_license = "Propriétaire — tous droits réservés (catalogue fabricant)"
redistribution = "restricted"
```

Conséquences, toutes vérifiées par `app/database/check_catalogue.py` :

- `source.usage = 'local_only'` et `source.redistribution = 'restricted'` ;
- anomalie `LOCAL_ONLY_DATA` sur chacune des cinq séries ;
- `standard_id` **NULL** partout (les intitulés EN du catalogue ne sont pas des
  références vérifiées) ;
- **aucune** des 446 références dans
  `catalogue_inventory_redistributable.csv` ;
- le PDF lui-même n'est pas redistribuable : il ne doit pas être joint à une
  publication du projet.

Une base reconstruite avec `data/staging/` vide (mode `--publish`) ne contient
que les 1 792 références MIT et reste, elle, redistribuable sous notice.

## 8. Licence du projet

La licence est **MIT**, tranchée en Phase 4. Le texte est dans
[`LICENSE`](../LICENSE), « Copyright (c) 2026 SteelProfile contributors ». Elle
couvre le code du projet (catalogue, moteur, exports, interface, tests,
outils), pas les données décrites ci-dessus.

- **MIT** : compatible avec la licence MIT de Steel Section Database, publication
  simple, intégration possible dans des outils propriétaires.
- **GPL-3.0** : également compatible (MIT → GPL est autorisé), mais imposerait
  de redistribuer le code sous GPL.

Les données normalisées restent sous MIT avec conservation de la mention de
copyright (voir `THIRD-PARTY-NOTICES.md`). Les données commerciales restent
**hors licence** et `local_only`.

### PySide6 / Qt — LGPLv3

`app/gui/` dépend de **PySide6**, sous **LGPLv3**. Cette dépendance est utilisée
comme bibliothèque externe :

- elle est installée séparément (`requirements-gui.txt`), jamais recopiée dans
  le dépôt ni vendue avec lui ;
- elle est importée dynamiquement, sans modification ni liaison statique ;
- le moteur et les exports fonctionnent sans elle, ce qui garde la partie
  essentielle du projet indépendante de Qt.

Une redistribution d'un exécutable qui embarquerait Qt devrait joindre le texte
de la LGPLv3, les sources de PySide6/Qt et un moyen de remplacer la
bibliothèque. Le projet ne fournit pas un tel exécutable. Voir
`THIRD-PARTY-NOTICES.md`.

## 9. Ce que contient `data/profiles.db` au regard des licences

| Contenu | Origine | Redistribuable |
|---|---|---|
| 1 792 géométries primaires | Steel Section Database (MIT) | oui, avec notice |
| 2 147 alias de désignation | dérivés des motifs TOML (MIT) | oui, avec notice |
| Rayons d'angle des creux | règle EN 10210-2 / EN 10219-2, recalculée | oui (règle de calcul, pas un tableau) |
| 53 760 propriétés dérivées | recalculées par le dépôt (MIT) | oui, avec notice — **et non indépendantes** |
| Désignations et éditions de normes | faits | oui (citation) |
| **446 références commerciales** (`AM-*`) | catalogue ArcelorMittal 2020 | **non** — absentes de l'export redistribuable |
| **453 alias et 1 338 propriétés dérivées commerciales** | mêmes séries | **non** |
| Séries locales (`data/staging`) | selon la source déclarée | **non** — exclues de l'export redistribuable |
| Tolérances | — | non présentes |
| Fichiers CAO / DXF | — | aucun dans la base ; les exports sont générés à la demande (voir `docs/exports.md`) |

Aucune donnée issue de Constructalia, Ahan Assa, CADXChange, theolternative,
Montanstahl, Lechner, Dlubal ou BSSA n'est présente dans la base. Aucune donnée de
`data/staging/` n'est livrée avec le projet.

La base de travail (`data/profiles.db`, 2 238 références) contient les séries
commerciales ; elle **n'est donc pas redistribuable telle quelle**. La base
publiable se reconstruit avec un répertoire `data/staging/` vide : 1 792
références, 6 sources, aucune série commerciale, aucun PDF fabricant.
