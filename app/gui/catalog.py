"""Accès en lecture seule au catalogue, **sans aucune dépendance à Qt**.

Cette couche est testable seule : elle ne fait que des requêtes SQLite et des
appels au moteur de géométrie. L'interface ne contient ainsi aucune logique de
catalogue et aucune règle de construction ; elle se contente d'afficher ce que
ces structures décrivent.

Rien n'est inventé ici non plus : un profilé dont la géométrie est incomplète
est renvoyé avec ses dimensions connues, la liste de ce qui manque et l'erreur
de construction exacte, jamais avec une valeur de remplacement.
"""
from __future__ import annotations

import sqlite3
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from app.geometry.build import DEFAULT_DB, connect, load_derived, load_profile
from app.geometry.contour import GeometryError, Section
from app.geometry.properties import SectionProperties, section_properties
from app.geometry.shapes import build_section
from app.geometry.verify import COMPARED_PARAMS, comparison_tolerance

# Libellés et unités des propriétés publiées au catalogue (cm², cm⁴, cm³, cm, kg/m).
PROPERTY_LABELS: dict[str, tuple[str, str]] = {
    "A": ("Aire", "cm²"),
    "mass": ("Masse linéique", "kg/m"),
    "surface": ("Surface développée", "m²/m"),
    "ys": ("Position du cdg y", "cm"),
    "zs": ("Position du cdg z", "cm"),
    "Iy": ("Moment quadratique Iy", "cm⁴"),
    "Iz": ("Moment quadratique Iz", "cm⁴"),
    "Iyz": ("Produit d'inertie Iyz", "cm⁴"),
    "Iu": ("Moment principal Iu", "cm⁴"),
    "Iv": ("Moment principal Iv", "cm⁴"),
    "alpha": ("Angle de l'axe principal", "°"),
    "i_y": ("Rayon de giration iy", "cm"),
    "i_z": ("Rayon de giration iz", "cm"),
    "i_u": ("Rayon de giration iu", "cm"),
    "i_v": ("Rayon de giration iv", "cm"),
    "Wel_y": ("Module Wel,y", "cm³"),
    "Wel_y_top": ("Wel,y fibre sup.", "cm³"),
    "Wel_y_bottom": ("Wel,y fibre inf.", "cm³"),
    "Wel_z": ("Module Wel,z", "cm³"),
    "Wel_z_left": ("Wel,z fibre gauche", "cm³"),
    "Wel_z_right": ("Wel,z fibre droite", "cm³"),
}

ORIGIN_LABELS: dict[str, str] = {
    "table": "table",
    "series_rule": "règle de série",
    "printed_override": "valeur imprimée",
}

STATUS_LABELS: dict[str, str] = {
    "complete": "constructible",
    "incomplete": "incomplète",
    "infeasible": "irréalisable",
}

CATEGORY_LABELS: dict[str, str] = {
    "standard": "normalisé",
    "commercial": "commercial",
}

SEVERITY_LABELS: dict[str, str] = {
    "blocking": "bloquant",
    "warning": "avertissement",
    "info": "information",
}


def search_key(text: str) -> str:
    """Clé de recherche : majuscules, sans accent, sans espace.

    Même normalisation que `designation_key` et `alias_key` du catalogue, pour
    qu'une saisie libre (`ipé 200`, `IPE200`, `Ipe 200`) trouve la même ligne.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = decomposed.encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in ascii_text.upper() if ch.isalnum() or ch == ".")


@dataclass(frozen=True)
class Family:
    family_id: str
    label: str
    spec_section: str | None
    series_count: int
    profile_count: int
    complete_count: int

    @property
    def incomplete_count(self) -> int:
        return self.profile_count - self.complete_count

    @property
    def title(self) -> str:
        return f"{self.label} ({self.complete_count}/{self.profile_count})"


@dataclass(frozen=True)
class Series:
    series_id: str
    family_id: str
    label: str
    shape_id: str
    category: str
    standard_id: str | None
    process: str | None
    commercial_ref: str | None
    profile_count: int
    complete_count: int
    rule_radii_count: int
    notes: str | None

    @property
    def title(self) -> str:
        suffix = f" — {self.profile_count}"
        if self.complete_count != self.profile_count:
            suffix += f" ({self.complete_count} constructibles)"
        return f"{self.series_id}{suffix}"

    @property
    def is_commercial(self) -> bool:
        return self.category == "commercial"


@dataclass(frozen=True)
class ProfileRow:
    profile_id: str
    series_id: str
    designation: str
    status: str
    category: str
    family_id: str

    @property
    def is_complete(self) -> bool:
        return self.status == "complete"


@dataclass(frozen=True)
class Dimension:
    param: str
    label: str
    value: float | None
    unit: str
    origin: str

    @property
    def origin_label(self) -> str:
        return ORIGIN_LABELS.get(self.origin, self.origin)


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    scope: str
    ref: str | None

    @property
    def severity_label(self) -> str:
        return SEVERITY_LABELS.get(self.severity, self.severity)


@dataclass(frozen=True)
class PropertyLine:
    key: str
    label: str
    unit: str
    computed: float | None
    published: float | None
    tolerance: float | None

    @property
    def error(self) -> float | None:
        if self.computed is None or self.published is None:
            return None
        return abs(self.computed - self.published)

    @property
    def ratio(self) -> float | None:
        """Écart rapporté à la tolérance de comparaison (≤ 1 = conforme)."""
        error, tolerance = self.error, self.tolerance
        if error is None or not tolerance:
            return None
        return error / tolerance


@dataclass(frozen=True)
class ProfileDetail:
    row: ProfileRow
    series: Series
    aliases: tuple[str, ...]
    dimensions: tuple[Dimension, ...]
    properties: tuple[PropertyLine, ...]
    section: Section | None
    properties_exact: SectionProperties | None
    missing: tuple[str, ...]
    error: str | None
    notes: tuple[str, ...]
    issues: tuple[Issue, ...] = field(default_factory=tuple)

    @property
    def is_complete(self) -> bool:
        return self.section is not None

    @property
    def nonconforming(self) -> tuple[PropertyLine, ...]:
        """Propriétés publiées hors tolérance (sans les corriger)."""
        return tuple(line for line in self.properties
                     if line.ratio is not None and line.ratio > 1.0)


class Catalogue:
    """Lecture du catalogue pour l'interface ; une connexion, fermée par `close()`."""

    def __init__(self, db_path: str | Path = DEFAULT_DB) -> None:
        self.db_path = Path(db_path)
        self.con: sqlite3.Connection = connect(self.db_path)
        self._series_cache: dict[str, Series] | None = None
        self._rows: list[ProfileRow] | None = None
        self._haystack: dict[str, tuple[str, ...]] = {}

    def close(self) -> None:
        self.con.close()

    def __enter__(self) -> "Catalogue":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # -- référentiels ------------------------------------------------------
    def families(self) -> list[Family]:
        return [
            Family(
                family_id=row["family_id"],
                label=row["label_fr"],
                spec_section=row["spec_section"],
                series_count=row["series_count"],
                profile_count=row["profile_count"],
                complete_count=row["complete_count"],
            )
            for row in self.con.execute(
                """
                SELECT f.family_id, f.label_fr, f.spec_section,
                       (SELECT COUNT(*) FROM series se
                         WHERE se.family_id = f.family_id) AS series_count,
                       (SELECT COUNT(*) FROM profile p JOIN series se USING (series_id)
                         WHERE se.family_id = f.family_id) AS profile_count,
                       (SELECT COUNT(*) FROM profile p JOIN series se USING (series_id)
                         WHERE se.family_id = f.family_id
                           AND p.geometry_status = 'complete') AS complete_count
                FROM family f ORDER BY f.sort_order
                """
            )
        ]

    def series(self, family_id: str | None = None,
               category: str | None = None) -> list[Series]:
        query = ["SELECT * FROM v_series_stats WHERE 1 = 1"]
        args: list[str] = []
        if family_id is not None:
            query.append("AND family_id = ?")
            args.append(family_id)
        if category is not None:
            query.append("AND category = ?")
            args.append(category)
        query.append("ORDER BY family_id, series_id")
        result = []
        for row in self.con.execute(" ".join(query), args):
            notes = self.con.execute(
                "SELECT notes FROM series WHERE series_id = ?", (row["series_id"],)
            ).fetchone()
            result.append(Series(
                series_id=row["series_id"],
                family_id=row["family_id"],
                label=row["label"],
                shape_id=row["shape_id"],
                category=row["category"],
                standard_id=row["standard_id"],
                process=row["process"],
                commercial_ref=row["commercial_ref"],
                profile_count=row["profile_count"],
                complete_count=row["profile_complete"],
                rule_radii_count=row["profile_rule_radii"],
                notes=notes["notes"] if notes else None,
            ))
        return result

    def series_by_id(self) -> dict[str, Series]:
        if self._series_cache is None:
            self._series_cache = {series.series_id: series for series in self.series()}
        return self._series_cache

    def totals(self) -> dict[str, int]:
        row = self.con.execute(
            "SELECT COUNT(*) AS n, "
            "SUM(geometry_status = 'complete') AS complete, "
            "SUM(geometry_status <> 'complete') AS incomplete "
            "FROM profile"
        ).fetchone()
        return {"profiles": row["n"], "complete": row["complete"] or 0,
                "incomplete": row["incomplete"] or 0}

    # -- profilés ----------------------------------------------------------
    def _all_rows(self) -> list[ProfileRow]:
        """Toutes les lignes du catalogue, chargées une fois (2 238 références)."""
        if self._rows is None:
            self._rows = [
                ProfileRow(
                    profile_id=row["profile_id"],
                    series_id=row["series_id"],
                    designation=row["designation"],
                    status=row["geometry_status"],
                    category=row["category"],
                    family_id=row["family_id"],
                )
                for row in self.con.execute(
                    "SELECT p.profile_id, p.series_id, p.designation, p.geometry_status, "
                    "s.category, s.family_id FROM profile p JOIN series s USING (series_id) "
                    "ORDER BY s.family_id, p.series_id, p.sort_key, p.designation"
                )
            ]
            haystack: dict[str, list[str]] = {}
            for row in self.con.execute(
                "SELECT profile_id, designation_key FROM profile"
            ):
                haystack.setdefault(row["profile_id"], []).append(row["designation_key"])
            for row in self.con.execute("SELECT profile_id, alias_key FROM profile_alias"):
                haystack.setdefault(row["profile_id"], []).append(row["alias_key"])
            self._haystack = {
                profile_id: tuple(dict.fromkeys(
                    [*keys, search_key(profile_id), profile_id.split("/", 1)[0]]))
                for profile_id, keys in haystack.items()
            }
        return self._rows

    def _matches(self, row: ProfileRow, key: str) -> bool:
        return any(key in token for token in self._haystack.get(row.profile_id, ()))

    def profiles(self, *, series_id: str | None = None, text: str = "",
                 category: str | None = None, limit: int | None = None) -> list[ProfileRow]:
        """Profilés filtrés, dans l'ordre du catalogue.

        `text` est comparé aux clés normalisées de la désignation, des alias et
        de l'identifiant complet (`IPE/IPE 200`, `ipé 200`, `168.3x6`…). Le
        filtrage se fait en mémoire : 2 238 lignes, une seule requête.
        """
        key = search_key(text)
        selected = [
            row for row in self._all_rows()
            if (series_id is None or row.series_id == series_id)
            and (category is None or row.category == category)
            and (not key or self._matches(row, key))
        ]
        return selected[:limit] if limit else selected

    def find(self, text: str, limit: int = 1) -> list[ProfileRow]:
        """Recherche « meilleure correspondance » : correspondance exacte d'abord."""
        key = search_key(text)
        if not key:
            return []
        exact = [row for row in self._all_rows() if key in self._haystack.get(row.profile_id, ())]
        if exact:
            return exact[:limit]
        return self.profiles(text=text, limit=limit)

    # -- détail ------------------------------------------------------------
    def detail(self, profile_id: str) -> ProfileDetail:
        profile = load_profile(self.con, profile_id)
        series = self.series_by_id()[profile.series_id]
        row = ProfileRow(
            profile_id=profile.profile_id,
            series_id=profile.series_id,
            designation=profile.designation,
            status=profile.geometry_status,
            category=profile.category,
            family_id=series.family_id,
        )

        dimensions = tuple(
            Dimension(
                param=r["param"],
                label=r["label_fr"] or r["param"],
                value=None if r["value"] is None else float(r["value"]),
                unit=r["unit"],
                origin=r["origin"],
            )
            for r in self.con.execute(
                "SELECT pp.param, pp.value, pp.origin, COALESCE(pd.unit, pp.unit) AS unit, "
                "COALESCE(pd.label_fr, pp.param) AS label_fr, pd.sort_order "
                "FROM profile_param pp LEFT JOIN param_def pd "
                "ON pd.shape_id = ? AND pd.param = pp.param "
                "WHERE pp.profile_id = ? ORDER BY COALESCE(pd.sort_order, 99), pp.param",
                (profile.shape_id, profile_id),
            )
        )
        aliases = tuple(
            r["alias"] for r in self.con.execute(
                "SELECT alias FROM profile_alias WHERE profile_id = ? ORDER BY alias",
                (profile_id,),
            )
        )

        section: Section | None = None
        exact: SectionProperties | None = None
        error: str | None = None
        properties: tuple[PropertyLine, ...] = ()
        if profile.geometry_status == "complete" and not profile.missing:
            try:
                section = build_section(profile.shape_id, profile.params)
                exact = section_properties(section)
            except GeometryError as exc:  # pragma: no cover - garde-fou
                error = str(exc)
            else:
                properties = self._property_lines(profile_id, exact, profile.category)
        else:
            error = (
                f"{profile.profile_id} : géométrie {STATUS_LABELS.get(profile.geometry_status, profile.geometry_status)}"
            )
            if profile.missing:
                error += f" — paramètres manquants : {', '.join(profile.missing)}"
            error += " ; aucune valeur n'est inventée"

        issues = tuple(
            Issue(severity=r["severity"], code=r["code"], message=r["message"],
                  scope=r["scope"], ref=r["ref"])
            for r in self.con.execute(
                "SELECT severity, code, message, scope, ref FROM catalog_issue "
                "WHERE (scope = 'profile' AND ref = ?) "
                "   OR (scope = 'series' AND ref = ?) "
                "   OR (scope = 'family' AND ref = ?) "
                "ORDER BY CASE severity WHEN 'blocking' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, code",
                (profile_id, profile.series_id, series.family_id),
            )
        )

        notes: list[str] = []
        profile_notes = self.con.execute(
            "SELECT notes FROM profile WHERE profile_id = ?", (profile_id,)
        ).fetchone()
        if profile_notes and profile_notes["notes"]:
            notes.append(profile_notes["notes"])
        if series.notes:
            notes.append(series.notes)

        return ProfileDetail(
            row=row, series=series, aliases=aliases, dimensions=dimensions,
            properties=properties, section=section, properties_exact=exact,
            missing=profile.missing, error=error, notes=tuple(notes), issues=issues,
        )

    def _property_lines(self, profile_id: str, exact: SectionProperties,
                        category: str) -> tuple[PropertyLine, ...]:
        computed = exact.catalogue_values()
        published = load_derived(self.con, profile_id)
        commercial = category == "commercial"
        lines = []
        for param in COMPARED_PARAMS:
            if param not in PROPERTY_LABELS:
                continue
            label, unit = PROPERTY_LABELS[param]
            expected = published.get(param)
            lines.append(PropertyLine(
                key=param,
                label=label,
                unit=unit,
                computed=computed.get(param),
                published=expected,
                tolerance=None if expected is None else comparison_tolerance(
                    param, expected, published, commercial=commercial),
            ))
        return tuple(lines)
