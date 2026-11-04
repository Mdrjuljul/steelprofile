"""Premier lancement : construire le catalogue s'il manque.

Le dépôt publié ne contient **pas** `data/profiles.db` : la base de travail
locale peut inclure des séries commerciales non redistribuables (voir
`docs/sources.md`). En revanche les données normalisées MIT sont livrées dans
`data/sources/Steel_Section_Database-main/`, et la construction ne prend que
quelques secondes.

Ce module est volontairement sans Qt : l'interface et la ligne de commande
l'appellent avant d'ouvrir la base. Il ne calcule aucune géométrie ; il délègue
tout l'import à `app.database.import_data.build`.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from app.database import import_data

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPO = ROOT / "data" / "sources" / "Steel_Section_Database-main"
DEFAULT_STATS = ROOT / "data" / "catalogue_stats.json"


class CatalogueMissing(RuntimeError):
    """Le catalogue n'existe pas et les données sources sont absentes."""


def is_ready(db_path: str | Path) -> bool:
    """Vrai si la base contient un catalogue utilisable (tables + références)."""
    path = Path(db_path)
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        con = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        tables = {
            row[0]
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        if not {"profile", "series"} <= tables:
            return False
        return con.execute("SELECT count(*) FROM profile").fetchone()[0] > 0
    except sqlite3.Error:
        return False
    finally:
        con.close()


def ensure_catalogue(db_path: str | Path = import_data.DEFAULT_DB,
                     repo: str | Path = DEFAULT_REPO,
                     stats: str | Path = DEFAULT_STATS,
                     staging: str | Path = import_data.STAGING) -> bool:
    """Construit le catalogue s'il manque.

    `staging` suit la règle de `import_data` : seules les séries locales qui y
    sont déclarées sont importées. Un clone public n'en contient aucune, donc la
    base construite ne contient que les références normalisées MIT.

    Retourne `True` si la base vient d'être construite, `False` si elle était
    déjà utilisable. Lève `CatalogueMissing` avec un message actionnable si les
    données sources MIT sont absentes ; aucune géométrie n'est inventée.
    """
    db_path = Path(db_path)
    repo = Path(repo)

    if is_ready(db_path):
        return False
    if not (repo / "data").is_dir():
        raise CatalogueMissing(
            "Catalogue introuvable et données sources absentes.\n\n"
            f"Base attendue : {db_path}\n"
            f"Source attendue : {repo}\n\n"
            "Récupérez le dépôt complet (dossier data/sources), puis relancez.")
    if not (Path(__file__).resolve().parent / "schema.sql").is_file():
        raise CatalogueMissing(
            "Schéma SQL absent : app/database/schema.sql est requis pour "
            "construire le catalogue.")

    try:
        import_data.build(db_path, repo, Path(stats), Path(staging))
    except SystemExit as exc:  # build() signale ses refus par sys.exit
        raise CatalogueMissing(
            f"Construction du catalogue impossible : {exc}\n\n"
            "Aucune valeur n'est inventée ; corrigez la source puis relancez."
        ) from exc
    if not is_ready(db_path):
        raise CatalogueMissing(
            f"La construction s'est terminée sans produire de catalogue "
            f"utilisable : {db_path}")
    return True
