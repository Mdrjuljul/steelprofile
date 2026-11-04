"""Vérification du moteur géométrique contre les propriétés publiées.

Le moteur reconstruit chaque profilé complet à partir de ses dimensions
primaires, puis compare ses propriétés élastiques aux valeurs publiées dans
`derived_property`. Les tolérances distinguent :

- les séries normalisées, dont les valeurs sont publiées à 6 chiffres
  significatifs : tolérance relative 1e-5 ;
- les séries commerciales ArcelorMittal, dont l'aire et la masse sont publiées
  avec deux décimales : tolérance relative 2e-3.

Le produit d'inertie Iyz est comparé en valeur absolue, rapportée à max(Iy, Iz),
car les sections symétriques publient exactement 0.

Usage :
    python -m app.geometry.verify
    python -m app.geometry.verify --series IPE --verbose
    python -m app.geometry.verify --category standard --rel-tol 5e-6
"""
from __future__ import annotations

import argparse
import math
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

if __package__ in (None, ""):  # exécution directe : python app/geometry/verify.py
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.geometry.build import (  # noqa: E402
    DEFAULT_DB,
    connect,
    iter_profile_ids,
    load_derived,
    load_profile,
)
from app.geometry.contour import GeometryError  # noqa: E402
from app.geometry.properties import section_properties  # noqa: E402
from app.geometry.shapes import build_section  # noqa: E402

STANDARD_REL_TOL = 1e-5
COMMERCIAL_REL_TOL = 2e-3

COMPARED_PARAMS = (
    "A", "ys", "zs", "Iy", "Iz", "Iyz", "Iu", "Iv", "alpha",
    "i_y", "i_z", "i_u", "i_v",
    "Wel_y", "Wel_y_top", "Wel_y_bottom", "Wel_z", "Wel_z_left", "Wel_z_right",
    "mass", "surface",
)


@dataclass
class Failure:
    profile_id: str
    series_id: str
    param: str
    computed: float
    published: float
    error: float
    tolerance: float


@dataclass
class MassAnomaly:
    profile_id: str
    series_id: str
    computed: float
    published: float
    error: float
    tolerance: float


@dataclass
class ParamStat:
    n: int = 0
    max_error: float = 0.0
    max_tolerance: float = 0.0
    worst_profile: str = ""

    def add(self, error: float, tolerance: float, profile_id: str) -> None:
        self.n += 1
        if error > self.max_error:
            self.max_error = error
            self.max_tolerance = tolerance
            self.worst_profile = profile_id


@dataclass
class SeriesStat:
    n: int = 0
    failures: int = 0
    max_ratio: float = 0.0
    worst_profile: str = ""
    worst_param: str = ""


@dataclass
class Report:
    profiles: int = 0
    standard: int = 0
    commercial: int = 0
    build_errors: list[tuple[str, str]] = field(default_factory=list)
    failures: list[Failure] = field(default_factory=list)
    mass_anomalies: list[MassAnomaly] = field(default_factory=list)
    params: dict[str, ParamStat] = field(default_factory=lambda: {p: ParamStat() for p in COMPARED_PARAMS})
    series: dict[str, SeriesStat] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.failures and not self.build_errors


def _tolerance(param: str, published: float, rel_tol: float, derived: dict[str, float],
               *, commercial: bool) -> float:
    if commercial:
        # A et la masse sont imprimées avec 2 décimales ou 3 chiffres
        # significatifs selon la série : tolérance de demi-unité, arrondie vers
        # le haut pour absorber la troncature du catalogue.
        if param == "A":
            return max(0.005, 5e-3 * abs(published))
        if param == "mass":
            return max(0.01, 5e-3 * abs(published))
    if param == "Iyz":
        scale = max(abs(derived.get("Iy", 0.0)), abs(derived.get("Iz", 0.0)), 1.0)
        return rel_tol * scale
    if param == "alpha":
        return max(rel_tol * max(abs(published), 1.0), 1e-9)
    return rel_tol * max(abs(published), 1.0)


def comparison_tolerance(param: str, published: float, derived: dict[str, float],
                         *, commercial: bool) -> float:
    """Tolérance de comparaison d'un paramètre, dans les unités du catalogue.

    Mêmes règles que `verify`, avec les tolérances par défaut : relative `1e-5`
    pour une série normalisée, demi-unité d'impression pour l'aire et la masse
    d'une série commerciale. Exposée pour que l'interface affiche exactement le
    même critère de conformité que la vérification en ligne de commande.
    """
    rel_tol = COMMERCIAL_REL_TOL if commercial else STANDARD_REL_TOL
    return _tolerance(param, published, rel_tol, derived, commercial=commercial)


def verify(
    con: sqlite3.Connection,
    *,
    series_id: str | None = None,
    category: str | None = None,
    rel_tol: float = STANDARD_REL_TOL,
    commercial_rel_tol: float = COMMERCIAL_REL_TOL,
    params: tuple[str, ...] = COMPARED_PARAMS,
) -> Report:
    """Reconstruit et compare tous les profilés complets ; ne lève pas sur échec."""
    report = Report()
    for profile_id in iter_profile_ids(con, category=category, series_id=series_id):
        profile = load_profile(con, profile_id)
        report.profiles += 1
        if profile.category == "commercial":
            report.commercial += 1
        else:
            report.standard += 1
        stat = report.series.setdefault(profile.series_id, SeriesStat())
        stat.n += 1

        try:
            computed = section_properties(build_section(profile.shape_id, profile.params)).catalogue_values()
        except GeometryError as exc:
            report.build_errors.append((profile_id, str(exc)))
            continue

        derived = load_derived(con, profile_id)
        commercial = profile.category == "commercial"
        tol = commercial_rel_tol if commercial else rel_tol
        for param in params:
            if param not in derived or param not in computed:
                continue
            expected = derived[param]
            actual = computed[param]
            error = abs(actual - expected)
            tolerance = _tolerance(param, expected, tol, derived, commercial=commercial)
            report.params[param].add(error, tolerance, profile_id)
            if error > tolerance:
                if commercial and param == "mass":
                    report.mass_anomalies.append(MassAnomaly(
                        profile_id=profile_id, series_id=profile.series_id,
                        computed=actual, published=expected, error=error, tolerance=tolerance,
                    ))
                    continue
                report.failures.append(Failure(
                    profile_id=profile_id, series_id=profile.series_id, param=param,
                    computed=actual, published=expected, error=error, tolerance=tolerance,
                ))
                stat.failures += 1
            if tolerance > 0.0:
                ratio = error / tolerance
                if ratio > stat.max_ratio:
                    stat.max_ratio = ratio
                    stat.worst_profile = profile_id
                    stat.worst_param = param
    return report


def _fmt(value: float) -> str:
    return f"{value:.3e}"


def print_report(report: Report, *, verbose: bool = False, max_failures: int = 40) -> None:
    print(f"Profilés complets traités : {report.profiles} "
          f"(normalisés {report.standard}, commerciaux {report.commercial})")
    if report.build_errors:
        print(f"\nERREURS DE CONSTRUCTION : {len(report.build_errors)}")
        for profile_id, message in report.build_errors[:max_failures]:
            print(f"  {profile_id}: {message}")
        if len(report.build_errors) > max_failures:
            print(f"  … {len(report.build_errors) - max_failures} autre(s)")

    print("\nErreur maximale par paramètre (comparée à la tolérance du pire cas) :")
    print(f"  {'param':10s} {'n':>6s} {'err max':>11s} {'tol':>11s}  pire profilé")
    for param in COMPARED_PARAMS:
        stat = report.params[param]
        if stat.n == 0:
            continue
        if stat.max_error <= stat.max_tolerance:
            flag = ""
        elif param == "mass":
            flag = "  ANOMALIE"
        else:
            flag = "  ÉCHEC"
        print(f"  {param:10s} {stat.n:6d} {_fmt(stat.max_error):>11s} {_fmt(stat.max_tolerance):>11s}  "
              f"{stat.worst_profile}{flag}")

    print("\nPar série :")
    print(f"  {'série':22s} {'n':>5s} {'échecs':>7s} {'err/tol max':>12s}  pire cas")
    for series_id in sorted(report.series):
        stat = report.series[series_id]
        print(f"  {series_id:22s} {stat.n:5d} {stat.failures:7d} {stat.max_ratio:12.3e}  "
              f"{stat.worst_profile} {stat.worst_param}")

    if report.mass_anomalies:
        print(f"\nANOMALIES DE MASSE PUBLIÉE : {len(report.mass_anomalies)}")
        print("  La masse du catalogue ne découle pas de l'aire à 7,85 kg/dm³ : incohérence")
        print("  de la source, sans mettre en cause la géométrie. À ne jamais corriger en silence.")
        for anomaly in report.mass_anomalies:
            print(f"  {anomaly.profile_id} masse calculée={anomaly.computed:.6g} "
                  f"publiée={anomaly.published:.6g} écart={_fmt(anomaly.error)} "
                  f"tolérance={_fmt(anomaly.tolerance)}")

    if report.failures:
        print(f"\nÉCHECS : {len(report.failures)}")
        shown = report.failures if verbose else report.failures[:max_failures]
        for failure in shown:
            print(f"  {failure.profile_id} [{failure.param}] calculé={failure.computed:.10g} "
                  f"publié={failure.published:.10g} erreur={_fmt(failure.error)} "
                  f"tolérance={_fmt(failure.tolerance)}")
        if len(shown) < len(report.failures):
            print(f"  … {len(report.failures) - len(shown)} autre(s)")
    else:
        print("\nAucun échec.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="base SQLite à vérifier")
    parser.add_argument("--series", help="limiter à une série (ex. IPE)")
    parser.add_argument("--category", choices=("standard", "commercial"), help="limiter à une catégorie")
    parser.add_argument("--rel-tol", type=float, default=STANDARD_REL_TOL,
                        help=f"tolérance relative des séries normalisées (défaut {STANDARD_REL_TOL:g})")
    parser.add_argument("--commercial-rel-tol", type=float, default=COMMERCIAL_REL_TOL,
                        help=f"tolérance relative des séries commerciales (défaut {COMMERCIAL_REL_TOL:g})")
    parser.add_argument("--verbose", action="store_true", help="afficher tous les échecs")
    parser.add_argument("--strict", action="store_true",
                        help="échouer aussi sur les anomalies de masse publiée (incohérences de source)")
    args = parser.parse_args(argv)

    if not args.db.exists():
        print(f"base introuvable : {args.db}", file=sys.stderr)
        return 2
    con = connect(args.db)
    try:
        report = verify(
            con,
            series_id=args.series,
            category=args.category,
            rel_tol=args.rel_tol,
            commercial_rel_tol=args.commercial_rel_tol,
        )
    finally:
        con.close()
    print_report(report, verbose=args.verbose)
    if report.ok and not (args.strict and report.mass_anomalies):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
