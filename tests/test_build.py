"""Tests d'intégration : chargement SQLite, refus des données manquantes, vérification.

Les tests qui utilisent la base sont ignorés si `data/profiles.db` est absent.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database.bootstrap import ensure_catalogue  # noqa: E402
from app.geometry.build import DEFAULT_DB, build_profile, connect, load_profile  # noqa: E402
from app.geometry.contour import GeometryError  # noqa: E402
from app.geometry.verify import verify  # noqa: E402

ensure_catalogue()


@unittest.skipUnless(DEFAULT_DB.exists(), "data/profiles.db absent")
class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.con = connect()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.con.close()

    def test_build_ipe(self) -> None:
        section = build_profile(self.con, "IPE/IPE 200")
        self.assertGreater(section.moments().A, 0.0)

    def test_missing_parameters_refused(self) -> None:
        profile_id = "AM-TES/Té 20x20x3"
        try:
            profile = load_profile(self.con, profile_id)
        except GeometryError:
            self.skipTest("catalogue standard seul : aucun T commercial local")
        self.assertEqual(profile.geometry_status, "incomplete")
        self.assertIn("slope_pct", profile.missing)
        self.assertIn("x_tf", profile.missing)
        with self.assertRaises(GeometryError):
            build_profile(self.con, profile_id)

    def test_unknown_profile_refused(self) -> None:
        with self.assertRaises(GeometryError):
            load_profile(self.con, "INCONNU/Profilé 1")

    def test_verify_series_ipe(self) -> None:
        report = verify(self.con, series_id="IPE")
        self.assertTrue(report.ok)
        self.assertEqual(report.profiles, 18)

    def test_verify_all_standard(self) -> None:
        report = verify(self.con, category="standard")
        self.assertTrue(report.ok)
        self.assertEqual(report.profiles, 1792)

    def test_verify_all_commercial_geometry(self) -> None:
        expected = self.con.execute(
            "SELECT count(*) FROM profile p JOIN series s USING (series_id) "
            "WHERE s.category = 'commercial' AND p.geometry_status = 'complete'"
        ).fetchone()[0]
        if not expected:
            self.skipTest("catalogue standard seul : aucune série commerciale")
        report = verify(self.con, category="commercial")
        self.assertTrue(report.ok)
        self.assertEqual(report.profiles, expected)


if __name__ == "__main__":
    unittest.main()
