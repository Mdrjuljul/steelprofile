"""Tests des propriétés dérivées et des unités de catalogue."""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.geometry.properties import principal_axes, section_properties  # noqa: E402
from app.geometry.shapes import flat  # noqa: E402


class PropertyTests(unittest.TestCase):
    def test_flat_units_and_modules(self) -> None:
        b, t = 160.0, 10.0
        p = section_properties(flat(b, t))
        self.assertAlmostEqual(p.Wel_y, p.Iy / (b / 2.0), places=6)
        self.assertAlmostEqual(p.Wel_z, p.Iz / (t / 2.0), places=6)
        self.assertAlmostEqual(p.Wel_y_top, p.Wel_y_bottom, places=9)
        self.assertAlmostEqual(p.Wel_z_left, p.Wel_z_right, places=9)
        self.assertAlmostEqual(p.i_y, math.sqrt(p.Iy / p.A), places=9)
        self.assertAlmostEqual(p.surface, 2.0 * (b + t) / 1000.0, places=12)

        values = p.catalogue_values()
        self.assertAlmostEqual(values["A"], 16.0, places=9)
        self.assertAlmostEqual(values["Iy"], 341.333333, places=5)
        self.assertAlmostEqual(values["Iz"], 1.333333, places=6)
        self.assertAlmostEqual(values["Wel_y"], 42.666667, places=5)
        self.assertAlmostEqual(values["ys"], 0.5, places=9)
        self.assertAlmostEqual(values["zs"], 8.0, places=9)
        self.assertAlmostEqual(values["mass"], 12.56, places=9)
        self.assertAlmostEqual(values["surface"], 0.34, places=12)

    def test_principal_axes(self) -> None:
        # Iy > Iz, Iyz = 0 : u = y, alpha = 0, Iu = Iy.
        Iu, Iv, alpha = principal_axes(100.0, 20.0, 0.0)
        self.assertAlmostEqual(Iu, 100.0, places=9)
        self.assertAlmostEqual(Iv, 20.0, places=9)
        self.assertAlmostEqual(alpha, 0.0, places=12)

        # Iy = Iz, Iyz < 0 : alpha = 45°, Iu = I + |Iyz|.
        Iu, Iv, alpha = principal_axes(100.0, 100.0, -30.0)
        self.assertAlmostEqual(Iu, 130.0, places=9)
        self.assertAlmostEqual(Iv, 70.0, places=9)
        self.assertAlmostEqual(alpha, 45.0, places=9)

        # Section isotrope : alpha = 0 par convention.
        Iu, Iv, alpha = principal_axes(50.0, 50.0, 0.0)
        self.assertAlmostEqual(Iu, 50.0, places=12)
        self.assertAlmostEqual(Iv, 50.0, places=12)
        self.assertAlmostEqual(alpha, 0.0, places=12)


if __name__ == "__main__":
    unittest.main()
