# Third-party notices

## SteelProfile

Le code de SteelProfile est distribué sous licence **MIT**
(voir [`LICENSE`](LICENSE), © 2026 SteelProfile contributors). Cette licence ne
couvre **pas** les données commerciales décrites plus bas.

## Steel Section Database

The profile catalogue in `data/profiles.db` is derived from **Steel Section
Database** by Adam Koudelka.

- Source : https://github.com/ulmewix/Steel_Section_Database
- Version utilisée : branche `main`, 2026-09-28
- Archive : `data/sources/Steel_Section_Database.zip`
  (SHA-256 `b4345c97490be6ad909d21c655eb55299b5c43eba56943c6253a58c06280123f`)
- Licence : MIT

```
MIT License

Copyright (c) 2026 Adam Koudelka

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Les données ainsi redistribuées ont été **transformées** : normalisation dans un
schéma relationnel, résolution des rayons d'angle des profilés creux par les
règles de EN 10210-2:2006 §A.3 et EN 10219-2:2006 §B.3, ajout des alias de
recherche et des statuts de validation. Ces transformations ne sont pas
endossées par l'auteur d'origine.

## ArcelorMittal — catalogue général 2020 (données locales, non redistribuées)

Cinq séries commerciales (`AM-RONDS` 69, `AM-CARRES` 28, `AM-PLATS` 288,
`AM-LARGES-PLATS` 54, `AM-TES` 7 — **446 références**) sont dérivées du
*catalogue général*, ArcelorMittal Distribution Solutions France, édition 2020.

- Document : `data/sources/Arcelor-Catalogue-Web-2020-avec-liens-bouton-light.pdf`
  (21 608 979 octets, SHA-256
  `3c23ac7d2b0af6c420343e23aa857326eaade571cd7e6b16b43d2e4fdbae0d82`)
- Statut : `category = 'commercial'`, `source_kind = 'manufacturer'`,
  `redistribution = 'restricted'`, `usage = 'local_only'`.
- Licence : **propriétaire, tous droits réservés**. Aucune autorisation de
  redistribution n'a été obtenue.

Ces données **ne sont pas couvertes** par la licence MIT ci-dessus. Elles ne
figurent ni dans `data/catalogue_inventory_redistributable.csv`, ni dans une base
reconstruite sans `data/staging/`, et le PDF n'est pas joint à une publication du
projet. Toute redistribution exigerait l'accord écrit d'ArcelorMittal.

## PySide6 / Qt — interface de bureau (LGPLv3)

L'interface (`app/gui/`) utilise **PySide6**, les liaisons officielles Qt pour
Python, sous licence **GNU Lesser General Public License v3 (LGPLv3)**.

- Projet : https://www.qt.io/qt-for-python
- Paquet : https://pypi.org/project/PySide6/
- Licence : LGPLv3 — https://www.gnu.org/licenses/lgpl-3.0.html
- Version utilisée au développement : PySide6 6.12.0 (Python 3.13)

Conditions respectées par le projet :

1. PySide6/Qt n'est **pas modifié** et n'est **pas distribué** avec le code
   source : il est installé séparément par l'utilisateur
   (`pip install -r requirements-gui.txt`).
2. L'import est **dynamique** (`from PySide6...`), sans liaison statique ; le
   moteur et les exports restent utilisables sans Qt.
3. Le texte de la LGPLv3 et les sources de PySide6/Qt restent disponibles aux
   adresses ci-dessus ; toute redistribution d'un binaire qui embarquerait Qt
   devrait fournir ces sources et permettre le remplacement de la bibliothèque.
4. La licence MIT du code SteelProfile est compatible avec cette utilisation :
   elle ne s'applique qu'au code du projet, pas à Qt.

Les données du catalogue ne sont pas concernées par cette notice : voir les
sections ci-dessus.

## Standards cités

Les normes EN et DIN sont citées par désignation et édition uniquement
(`EN 10365:2017`, `EN 10056-1:1998`, `EN 10210-2:2006`, `EN 10219-2:2006`,
`EN 10024:1995`, `DIN 1025-1:2009`, `DIN 1026-1:2009`, `DIN 1026-2:2002`,
`EN 10058:2018`, `EN 10055:1995`, `EN 10059:2003`, `EN 10060:2003`). Aucun texte
normatif n'est reproduit ni distribué par ce projet. Les quatre dernières sont
citées comme intitulés des gammes commerciales ou comme hypothèse de
rattachement : **aucune valeur n'est tirée d'une copie de ces normes**. Voir
`docs/licenses.md`.

## Données locales (`data/staging/`)

Les séries importées depuis `data/staging/` ne proviennent pas de ce projet et ne
sont pas couvertes par la licence MIT ci-dessus. Leur provenance et leurs
conditions sont déclarées dans le TOML de chaque série (`source_name`,
`source_license`, `redistribution`) et recopiées dans la table `source` de la
base. Elles ne sont **jamais** incluses dans l'export redistribuable.

En conséquence, `data/profiles.db` **tel que construit avec le dépôt local** n'est
pas redistribuable : il contient les 446 références commerciales. La base
publiable se reconstruit avec un répertoire `data/staging/` vide (1 792
références, `check_catalogue.py --publish`).
