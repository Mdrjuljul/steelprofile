"""Chargement des profilés depuis SQLite et construction de leur géométrie exacte.

Aucune dimension n'est inventée : si un paramètre requis est NULL ou absent, la
construction échoue avec la liste des paramètres manquants. Un profilé dont
`geometry_status` n'est pas `complete` est refusé par défaut, même si tous ses
paramètres sont présents.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from app.geometry.contour import GeometryError, Section
from app.geometry.shapes import build_section

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "profiles.db"


@dataclass(frozen=True)
class ProfileGeometry:
    """Un profilé et ses dimensions primaires [mm], telles que stockées."""

    profile_id: str
    series_id: str
    designation: str
    shape_id: str
    category: str
    geometry_status: str
    params: dict[str, float | None]
    missing: tuple[str, ...]

    def require_complete(self) -> None:
        if self.geometry_status != "complete":
            raise GeometryError(
                f"{self.profile_id} : géométrie incomplète (statut {self.geometry_status!r})"
            )
        if self.missing:
            raise GeometryError(
                f"{self.profile_id} : paramètres manquants {', '.join(self.missing)}"
            )


def connect(db_path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    """Ouvre le catalogue en refusant une base absente, vide ou incomplète.

    `sqlite3.connect()` crée silencieusement un fichier vide : sans ce contrôle,
    un premier lancement sans catalogue produisait une base de 0 octet puis
    échouait sur `no such table: profile`. Le message renvoie vers la
    construction (ou vers `app.database.bootstrap`).
    """
    path = Path(db_path)
    if not path.is_file():
        raise FileNotFoundError(
            f"Catalogue introuvable : {path}\n"
            "Construisez-le avec : python app/database/import_data.py\n"
            "ou relancez l'interface, qui le construit au premier lancement.")
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    has_tables = con.execute(
        "SELECT count(*) FROM sqlite_master "
        "WHERE type = 'table' AND name IN ('profile', 'series')").fetchone()[0]
    if has_tables < 2:
        con.close()
        raise FileNotFoundError(
            f"Catalogue vide ou incomplet : {path}\n"
            "Reconstruisez-le avec : python app/database/import_data.py")
    return con


def required_params(con: sqlite3.Connection, shape_id: str) -> tuple[str, ...]:
    return tuple(
        row["param"]
        for row in con.execute(
            "SELECT param FROM param_def WHERE shape_id = ? AND required = 1 ORDER BY sort_order",
            (shape_id,),
        )
    )


def load_profile(con: sqlite3.Connection, profile_id: str) -> ProfileGeometry:
    row = con.execute(
        """
        SELECT p.profile_id, p.series_id, p.designation, p.geometry_status,
               s.shape_id, s.category
        FROM profile p
        JOIN series s ON s.series_id = p.series_id
        WHERE p.profile_id = ?
        """,
        (profile_id,),
    ).fetchone()
    if row is None:
        raise GeometryError(f"profilé inconnu : {profile_id!r}")
    params: dict[str, float | None] = {
        r["param"]: (None if r["value"] is None else float(r["value"]))
        for r in con.execute(
            "SELECT param, value FROM profile_param WHERE profile_id = ?", (profile_id,)
        )
    }
    missing = tuple(name for name in required_params(con, row["shape_id"]) if params.get(name) is None)
    return ProfileGeometry(
        profile_id=row["profile_id"],
        series_id=row["series_id"],
        designation=row["designation"],
        shape_id=row["shape_id"],
        category=row["category"],
        geometry_status=row["geometry_status"],
        params=params,
        missing=missing,
    )


def build_profile(con: sqlite3.Connection, profile_id: str, *, allow_incomplete: bool = False) -> Section:
    """Construit la section exacte d'un profilé ; refuse toute donnée manquante."""
    profile = load_profile(con, profile_id)
    if not allow_incomplete:
        profile.require_complete()
    if profile.missing:
        raise GeometryError(
            f"{profile.profile_id} : paramètres manquants {', '.join(profile.missing)} ; "
            "aucune valeur n'est inventée"
        )
    params = {k: v for k, v in profile.params.items() if v is not None}
    return build_section(profile.shape_id, params)


def iter_profile_ids(
    con: sqlite3.Connection,
    *,
    category: str | None = None,
    series_id: str | None = None,
    status: str | None = "complete",
) -> Iterator[str]:
    query = ["SELECT p.profile_id FROM profile p JOIN series s ON s.series_id = p.series_id WHERE 1 = 1"]
    args: list[str] = []
    if category is not None:
        query.append("AND s.category = ?")
        args.append(category)
    if series_id is not None:
        query.append("AND p.series_id = ?")
        args.append(series_id)
    if status is not None:
        query.append("AND p.geometry_status = ?")
        args.append(status)
    query.append("ORDER BY p.series_id, p.sort_key, p.designation")
    for row in con.execute(" ".join(query), args):
        yield row["profile_id"]


def load_derived(con: sqlite3.Connection, profile_id: str) -> dict[str, float]:
    """Valeurs publiées de `derived_property` (uniquement les lignes non NULL)."""
    return {
        row["param"]: float(row["value"])
        for row in con.execute(
            "SELECT param, value FROM derived_property WHERE profile_id = ? AND value IS NOT NULL",
            (profile_id,),
        )
    }
