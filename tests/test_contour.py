"""Tests du noyau de contours : intégrales exactes contre formes closes.

Chaque test compare les moments calculés par intégration de Green le long de
segments et d'arcs exacts aux valeurs analytiques connues. Aucune tolérance
large : on attend l'accord à l'arrondi machine (1e-12 relatif).
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.geometry.contour import (  # noqa: E402
    Arc,
    Contour,
    ContourBuilder,
    GeometryError,
    Line,
    Moments,
    Section,
)

REL = 1e-12


def relative(actual: float, expected: float) -> float:
    scale = max(abs(expected), 1e-12)
    return abs(actual - expected) / scale


class RectangleTests(unittest.TestCase):
    def rectangle(self, y0: float, z0: float, b: float, h: float) -> Contour:
        pts = [(y0, z0), (y0 + b, z0), (y0 + b, z0 + h), (y0, z0 + h)]
        return Contour(tuple(Line(pts[i], pts[(i + 1) % 4]) for i in range(4)))

    def test_unit_rectangle_at_origin(self) -> None:
        m = self.rectangle(0.0, 0.0, 1.0, 1.0).moments()
        self.assertAlmostEqual(m.A, 1.0, places=14)
        self.assertAlmostEqual(m.Qy, 0.5, places=14)   # ∫ z dA
        self.assertAlmostEqual(m.Qz, 0.5, places=14)   # ∫ y dA
        self.assertAlmostEqual(m.Iy, 1.0 / 3.0, places=14)
        self.assertAlmostEqual(m.Iz, 1.0 / 3.0, places=14)
        self.assertAlmostEqual(m.Iyz, 0.25, places=14)

    def test_offset_rectangle(self) -> None:
        y0, z0, b, h = 2.0, -3.0, 5.0, 4.0
        m = self.rectangle(y0, z0, b, h).moments()
        A = b * h
        yc, zc = y0 + b / 2.0, z0 + h / 2.0
        self.assertTrue(math.isclose(m.A, A, rel_tol=REL))
        self.assertTrue(math.isclose(m.Qy, A * zc, rel_tol=REL))
        self.assertTrue(math.isclose(m.Qz, A * yc, rel_tol=REL))
        self.assertTrue(math.isclose(m.Iy, b * h ** 3 / 12.0 + A * zc ** 2, rel_tol=REL))
        self.assertTrue(math.isclose(m.Iz, h * b ** 3 / 12.0 + A * yc ** 2, rel_tol=REL))
        self.assertTrue(math.isclose(m.Iyz, A * yc * zc, rel_tol=REL))

    def test_clockwise_is_negative(self) -> None:
        outer = self.rectangle(0.0, 0.0, 2.0, 3.0)
        rev = Contour(tuple(Line(p.end, p.start) for p in reversed(outer.primitives)))
        self.assertLess(rev.signed_area(), 0.0)
        with self.assertRaises(GeometryError):
            Section(outer=(rev,))

    def test_perimeter(self) -> None:
        self.assertAlmostEqual(self.rectangle(0, 0, 3, 4).perimeter(), 14.0, places=13)


class CircleTests(unittest.TestCase):
    def circle(self, a: float, b: float, R: float, clockwise: bool = False) -> Contour:
        sweep = -2.0 * math.pi if clockwise else 2.0 * math.pi
        return Contour((Arc((a, b), R, 0.0, sweep),))

    def test_full_circle(self) -> None:
        a, b, R = 3.0, -2.0, 5.0
        m = self.circle(a, b, R).moments()
        A = math.pi * R ** 2
        self.assertTrue(math.isclose(m.A, A, rel_tol=1e-12))
        self.assertTrue(math.isclose(m.Qy, A * b, rel_tol=1e-12))
        self.assertTrue(math.isclose(m.Qz, A * a, rel_tol=1e-12))
        self.assertTrue(math.isclose(m.Iy, math.pi * R ** 4 / 4 + A * b ** 2, rel_tol=1e-12))
        self.assertTrue(math.isclose(m.Iz, math.pi * R ** 4 / 4 + A * a ** 2, rel_tol=1e-12))
        self.assertTrue(math.isclose(m.Iyz, A * a * b, rel_tol=1e-12))

    def test_quarter_disc(self) -> None:
        # Quart de disque : centre (0,0), rayon R, du point (R,0) au point (0,R),
        # refermé par deux segments. A = πR²/4 ; Qy = Qz = R³/3.
        R = 4.0
        contour = Contour((
            Arc((0.0, 0.0), R, 0.0, math.pi / 2.0),
            Line((0.0, R), (0.0, 0.0)),
            Line((0.0, 0.0), (R, 0.0)),
        ))
        m = contour.moments()
        self.assertTrue(math.isclose(m.A, math.pi * R ** 2 / 4, rel_tol=1e-12))
        self.assertTrue(math.isclose(m.Qy, R ** 3 / 3, rel_tol=1e-12))
        self.assertTrue(math.isclose(m.Qz, R ** 3 / 3, rel_tol=1e-12))
        # Iy = Iz = πR⁴/16 (quart de disque plein).
        self.assertTrue(math.isclose(m.Iy, math.pi * R ** 4 / 16, rel_tol=1e-12))
        self.assertTrue(math.isclose(m.Iz, math.pi * R ** 4 / 16, rel_tol=1e-12))
        # Iyz = ∫ y z dA = R⁴/8 sur le quart de disque.
        self.assertTrue(math.isclose(m.Iyz, R ** 4 / 8, rel_tol=1e-12))

    def test_annulus(self) -> None:
        Ro, Ri = 10.0, 6.0
        outer = self.circle(0.0, 0.0, Ro)
        hole = self.circle(0.0, 0.0, Ri, clockwise=True)
        section = Section(outer=(outer,), holes=(hole,))
        m = section.moments()
        A = math.pi * (Ro ** 2 - Ri ** 2)
        self.assertTrue(math.isclose(m.A, A, rel_tol=1e-12))
        self.assertTrue(math.isclose(m.Iy, math.pi / 4 * (Ro ** 4 - Ri ** 4), rel_tol=1e-12))
        self.assertTrue(math.isclose(m.Iz, math.pi / 4 * (Ro ** 4 - Ri ** 4), rel_tol=1e-12))
        self.assertTrue(math.isclose(m.Iyz, 0.0, abs_tol=1e-9))

    def test_bounds_include_arc_extrema(self) -> None:
        # Arc de 90° à 180° : extrémité gauche atteinte en 180°, pas en 90°/270°.
        arc = Arc((0.0, 0.0), 10.0, math.pi / 2.0, math.pi / 2.0)
        ymin, ymax, zmin, zmax = Contour((arc, Line(arc.end, arc.start))).bounds()
        self.assertAlmostEqual(ymin, -10.0, places=12)
        self.assertAlmostEqual(ymax, 0.0, places=12)
        self.assertAlmostEqual(zmin, 0.0, places=12)
        self.assertAlmostEqual(zmax, 10.0, places=12)


class BuilderTests(unittest.TestCase):
    def test_rectangle_builder(self) -> None:
        # Départ (0,0), cap 0° (+y), 4 segments à angle droit.
        c = (ContourBuilder((0.0, 0.0), 0.0)
             .line(2.0).line(3.0, 90.0).line(2.0, 180.0).line(3.0, 270.0)
             .close())
        self.assertAlmostEqual(c.signed_area(), 6.0, places=12)
        self.assertAlmostEqual(c.perimeter(), 10.0, places=12)

    def test_rounded_corner_is_tangent(self) -> None:
        # Carré 10×10 à coins arrondis r=2 : aire = 100 − (4−π)·r².
        r = 2.0
        side = 10.0
        c = (ContourBuilder((r, 0.0), 0.0)
             .line(side - 2 * r)
             .arc(90.0, r)
             .line(side - 2 * r)
             .arc(90.0, r)
             .line(side - 2 * r)
             .arc(90.0, r)
             .line(side - 2 * r)
             .arc(90.0, r)
             .close())
        self.assertAlmostEqual(c.signed_area(), side ** 2 - (4.0 - math.pi) * r ** 2, places=10)
        self.assertAlmostEqual(c.perimeter(), 4.0 * (side - 2 * r) + 2.0 * math.pi * r, places=10)

    def test_negative_arc_sweep(self) -> None:
        # Cercle parcouru dans le sens horaire : aire signée négative.
        c = (ContourBuilder((10.0, 0.0), -90.0)
             .arc(-360.0, 10.0)
             .close())
        self.assertLess(c.signed_area(), 0.0)
        self.assertAlmostEqual(-c.signed_area(), math.pi * 100.0, places=10)

    def test_open_contour_rejected(self) -> None:
        builder = ContourBuilder((0.0, 0.0), 0.0).line(10.0).line(10.0, 90.0)
        with self.assertRaises(GeometryError):
            builder.close()


if __name__ == "__main__":
    unittest.main()
