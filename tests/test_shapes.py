"""Tests des générateurs de formes : formes closes et équivalences.

Les sections sans congé ont des formules analytiques exactes ; les sections avec
arcs sont vérifiées par les invariants géométriques et par la base publiée
(tests/test_verify.py). Aucun test ne remplace un arc par une corde.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.geometry.properties import section_properties  # noqa: E402
from app.geometry.contour import GeometryError  # noqa: E402
from app.geometry.shapes import (  # noqa: E402
    angle,
    channel,
    chs,
    flat,
    i_section,
    i_tapered,
    rect_hollow,
    round_bar,
    sinusoidal_sheet,
    square_bar,
    trapezoid_angle_deg,
    trapezoidal_sheet,
)


class ISectionTests(unittest.TestCase):
    def test_area_and_inertia_without_fillets(self) -> None:
        h, b, tw, tf = 400.0, 200.0, 8.0, 13.0
        p = section_properties(i_section(h, b, tw, tf, 0.0))
        A = b * h - (b - tw) * (h - 2.0 * tf)
        self.assertAlmostEqual(p.A, A, places=9)
        self.assertAlmostEqual(p.Iy, (b * h ** 3 - (b - tw) * (h - 2.0 * tf) ** 3) / 12.0, places=6)
        self.assertAlmostEqual(p.Iz, (2.0 * tf * b ** 3 + (h - 2.0 * tf) * tw ** 3) / 12.0, places=6)
        self.assertAlmostEqual(p.y_c, 0.0, places=12)
        self.assertAlmostEqual(p.z_c, 0.0, places=12)
        self.assertAlmostEqual(p.Iyz, 0.0, places=6)

    def test_fillet_area_is_exact(self) -> None:
        # Quatre congés pleins ajoutent 4·(1 − π/4)·r² à l'aire de la section
        # à angles vifs (le congé remplace un coin carré par un quart de disque).
        h, b, tw, tf, r = 400.0, 200.0, 8.0, 13.0, 21.0
        sharp = section_properties(i_section(h, b, tw, tf, 0.0)).A
        rounded = section_properties(i_section(h, b, tw, tf, r)).A
        self.assertAlmostEqual(rounded - sharp, 4.0 * (1.0 - math.pi / 4.0) * r * r, places=8)

    def test_invalid_parameters_rejected(self) -> None:
        with self.assertRaises(Exception):
            i_section(100.0, 50.0, 60.0, 10.0, 0.0)  # âme plus épaisse que la semelle


class ChannelTests(unittest.TestCase):
    def test_parallel_channel_without_fillets(self) -> None:
        h, b, tw, tf = 200.0, 80.0, 6.0, 11.0
        p = section_properties(channel(h, b, tw, tf, 0.0, 0.0, 0.0, 0.0))
        A = b * h - (b - tw) * (h - 2.0 * tf)
        self.assertAlmostEqual(p.A, A, places=9)
        self.assertAlmostEqual(p.Iy, (b * h ** 3 - (b - tw) * (h - 2.0 * tf) ** 3) / 12.0, places=6)
        self.assertAlmostEqual(p.z_c, 0.0, places=12)
        self.assertAlmostEqual(p.Iyz, 0.0, places=6)
        # y_c mesuré depuis le dos de l'âme
        self.assertGreater(p.y_c, 0.0)
        self.assertAlmostEqual(p.ys, p.y_c, places=12)

    def test_slope_zero_ignores_x_tf(self) -> None:
        a = section_properties(channel(300.0, 100.0, 8.0, 12.0, 15.0, 7.0, 0.0, 0.0))
        b = section_properties(channel(300.0, 100.0, 8.0, 12.0, 15.0, 7.0, 0.0, 40.0))
        self.assertAlmostEqual(a.A, b.A, places=9)
        self.assertAlmostEqual(a.Iy, b.Iy, places=6)
        self.assertAlmostEqual(a.Iz, b.Iz, places=6)


class AngleTests(unittest.TestCase):
    def test_equal_leg_angle_area_and_symmetry(self) -> None:
        b, t = 100.0, 10.0
        p = section_properties(angle(b, b, t, 0.0, 0.0))
        self.assertAlmostEqual(p.A, t * (2.0 * b - t), places=9)
        self.assertAlmostEqual(p.Iy, p.Iz, places=6)
        self.assertLess(p.Iyz, 0.0)
        self.assertAlmostEqual(p.alpha_deg, 45.0, places=8)

    def test_unequal_leg_area(self) -> None:
        h, b, t = 100.0, 50.0, 8.0
        p = section_properties(angle(h, b, t, 0.0, 0.0))
        self.assertAlmostEqual(p.A, t * (h + b - t), places=9)
        self.assertGreater(p.z_c, p.y_c)  # l'aile longue porte la matière loin du talon


class HollowTests(unittest.TestCase):
    def test_rect_hollow_without_radii(self) -> None:
        b, h, t = 100.0, 200.0, 8.0
        p = section_properties(rect_hollow(b, h, t, 0.0, 0.0))
        A = b * h - (b - 2.0 * t) * (h - 2.0 * t)
        self.assertAlmostEqual(p.A, A, places=9)
        self.assertAlmostEqual(p.Iy, (b * h ** 3 - (b - 2.0 * t) * (h - 2.0 * t) ** 3) / 12.0, places=6)
        self.assertAlmostEqual(p.Iz, (h * b ** 3 - (h - 2.0 * t) * (b - 2.0 * t) ** 3) / 12.0, places=6)
        self.assertAlmostEqual(p.perimeter, 2.0 * (b + h), places=9)

    def test_rect_hollow_corner_area(self) -> None:
        b, h, t, ro, ri = 100.0, 200.0, 8.0, 12.0, 4.0
        p = section_properties(rect_hollow(b, h, t, ro, ri))
        bi, hi = b - 2.0 * t, h - 2.0 * t
        A = b * h - bi * hi - (4.0 - math.pi) * (ro * ro - ri * ri)
        self.assertAlmostEqual(p.A, A, places=8)

    def test_chs_closed_form(self) -> None:
        D, t = 168.3, 6.3
        d = D - 2.0 * t
        p = section_properties(chs(D, t))
        self.assertAlmostEqual(p.A, math.pi / 4.0 * (D * D - d * d), places=7)
        self.assertAlmostEqual(p.Iy, math.pi / 64.0 * (D ** 4 - d ** 4), places=4)
        self.assertAlmostEqual(p.Iz, p.Iy, places=4)
        self.assertAlmostEqual(p.perimeter, math.pi * D, places=7)


class SolidTests(unittest.TestCase):
    def test_flat_on_edge(self) -> None:
        b, t = 160.0, 10.0
        p = section_properties(flat(b, t))
        self.assertAlmostEqual(p.A, b * t, places=9)
        self.assertAlmostEqual(p.Iy, t * b ** 3 / 12.0, places=6)
        self.assertAlmostEqual(p.Iz, b * t ** 3 / 12.0, places=6)
        self.assertAlmostEqual(p.mass, b * t * 1e-6 * 7850.0, places=9)

    def test_round_and_square(self) -> None:
        D = 40.0
        p = section_properties(round_bar(D))
        self.assertAlmostEqual(p.A, math.pi * D * D / 4.0, places=8)
        self.assertAlmostEqual(p.Iy, math.pi * D ** 4 / 64.0, places=4)
        self.assertAlmostEqual(p.Iz, p.Iy, places=4)

        a = 40.0
        q = section_properties(square_bar(a))
        self.assertAlmostEqual(q.A, a * a, places=9)
        self.assertAlmostEqual(q.Iy, a ** 4 / 12.0, places=5)
        self.assertAlmostEqual(q.Iz, q.Iy, places=5)


class TaperedEquivalenceTests(unittest.TestCase):
    def test_tapered_with_zero_slope_equals_parallel_i(self) -> None:
        args = (400.0, 200.0, 8.0, 13.0, 21.0)
        flat_i = section_properties(i_section(*args))
        tapered = section_properties(i_tapered(*args, 0.0, 0.0, 0.0))
        for name in ("A", "Iy", "Iz", "Iyz", "Wel_y", "Wel_z", "perimeter"):
            self.assertAlmostEqual(getattr(flat_i, name), getattr(tapered, name), places=6, msg=name)


class CoverSheetTests(unittest.TestCase):
    """Tôle trapézoïdale : module d'une onde, plis en arcs vrais, centrage déclaré."""

    def test_module_is_centered_and_closed(self) -> None:
        pitch, depth, crest, trough = 100.0, 7.5, 55.0, 30.0
        section = trapezoidal_sheet(pitch, depth, crest, trough, 0.63, 2.0)
        y0, y1, z0, z1 = section.bounds()
        self.assertAlmostEqual(y0, -pitch / 2.0, places=9)
        self.assertAlmostEqual(y1, pitch / 2.0, places=9)
        self.assertAlmostEqual(z0, -0.63, places=9)
        self.assertAlmostEqual(z1, depth, places=9)

        primitives = section.outer[0].primitives
        self.assertEqual(len(primitives), 20)
        self.assertEqual(sum(1 for p in primitives if type(p).__name__ == "Arc"), 8)
        # Les deux bords libres sont verticaux et ferment le bandeau.
        self.assertAlmostEqual(section.perimeter(), 212.997943489613, places=6)

    def test_area_and_derived_angle(self) -> None:
        section = trapezoidal_sheet(100.0, 7.5, 55.0, 30.0, 0.63, 2.0)
        properties = section_properties(section)
        self.assertAlmostEqual(properties.A, 66.6974521992281, places=6)
        # Aire par pas -> masse surfacique à 7,85 kg/dm3 (5,33 publiés).
        self.assertAlmostEqual(7.85 * properties.A / 100.0, 5.235749997639406, places=9)
        self.assertAlmostEqual(trapezoid_angle_deg(100.0, 7.5, 55.0, 30.0), 45.0, places=9)

    def test_bend_radius_must_exceed_thickness(self) -> None:
        with self.assertRaises(GeometryError):
            trapezoidal_sheet(100.0, 7.5, 55.0, 30.0, 2.0, 2.0)

    def test_flat_left_after_bends_must_be_positive(self) -> None:
        # r = 20 consomme tout le plateau haut (crest = 3) : les congés se chevauchent.
        with self.assertRaises(GeometryError):
            trapezoidal_sheet(100.0, 7.5, 3.0, 30.0, 0.63, 20.0)

    def test_sinusoid_is_refused_explicitly(self) -> None:
        with self.assertRaises(GeometryError) as caught:
            sinusoidal_sheet(76.0, 18.0, 0.63)
        self.assertIn("sinusoïdale", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
