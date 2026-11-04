"""Tests de la couche catalogue et de la fenêtre, sans affichage réel.

Les tests de `app.gui.catalog` ne demandent pas Qt : c'est la couche qui porte
toute la logique de lecture. Les tests de widgets utilisent la plateforme
« offscreen » de Qt, donc sans écran ni fenêtre visible ; ils sont ignorés si
PySide6 ou `data/profiles.db` sont absents.

Aucun test ne vérifie une valeur de géométrie : le moteur et les exports ont
leurs propres tests. Ici on vérifie seulement que l'interface *affiche* ce que
le catalogue et le moteur renvoient, et qu'elle refuse ce qui est incomplet.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Doit être posé avant le premier import de PySide6.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.database.bootstrap import ensure_catalogue  # noqa: E402
from app.geometry.build import DEFAULT_DB  # noqa: E402
from app.gui.catalog import (  # noqa: E402
    PROPERTY_LABELS,
    Catalogue,
    search_key,
)

try:  # Qt n'est requis que pour les tests de widgets.
    from PySide6.QtCore import QPointF  # noqa: E402
    from PySide6.QtWidgets import QApplication  # noqa: E402
except ImportError:  # pragma: no cover - dépend de l'environnement
    QApplication = None  # type: ignore[assignment]
    QPointF = None  # type: ignore[assignment]

# Un clone ne versionne pas la base : on la construit comme au premier lancement.
ensure_catalogue()
HAS_DB = Path(DEFAULT_DB).is_file()
HAS_QT = QApplication is not None


@unittest.skipUnless(HAS_DB, f"base absente : {DEFAULT_DB}")
class CatalogueTests(unittest.TestCase):
    """Lecture du catalogue, indépendamment de toute interface."""

    def setUp(self) -> None:
        self.catalogue = Catalogue()

    def tearDown(self) -> None:
        self.catalogue.close()

    def test_totals_and_families(self) -> None:
        totals = self.catalogue.totals()
        self.assertGreaterEqual(totals["profiles"], 1792)
        self.assertEqual(totals["profiles"],
                         totals["complete"] + totals["incomplete"])
        families = self.catalogue.families()
        self.assertEqual(len(families), 7)
        self.assertEqual(sum(f.profile_count for f in families),
                         totals["profiles"])
        self.assertEqual(sum(f.complete_count for f in families),
                         totals["complete"])
        # Les 1 792 références normalisées MIT sont toujours constructibles.
        standard = self.catalogue.profiles(category="standard")
        self.assertEqual(len(standard), 1792)
        self.assertTrue(all(row.is_complete for row in standard))

    def test_series_categories_are_separated(self) -> None:
        series = self.catalogue.series()
        standard = [s for s in series if s.category == "standard"]
        commercial = [s for s in series if s.category == "commercial"]
        self.assertEqual(len(standard), 16)
        self.assertEqual(len(standard) + len(commercial), len(series))
        self.assertTrue(all(s.is_commercial for s in commercial))
        self.assertFalse(any(s.is_commercial for s in standard))
        self.assertEqual(sum(s.profile_count for s in standard), 1792)

        tes = self.catalogue.series_by_id().get("AM-TES")
        if tes is not None:  # présent seulement dans la base locale complète
            self.assertTrue(tes.is_commercial)
            self.assertEqual(tes.profile_count, 7)
            self.assertEqual(tes.complete_count, 0)

    def test_search_key_normalises_accents_and_spaces(self) -> None:
        self.assertEqual(search_key("ipé 200"), "IPE200")
        self.assertEqual(search_key("IPE/IPE 200"), "IPEIPE200")
        self.assertEqual(search_key("Té 20x20x3"), "TE20X20X3")
        self.assertEqual(search_key("CHS 168.3x6"), "CHS168.3X6")
        self.assertEqual(search_key("  "), "")

    def test_find_accepts_free_text_and_full_ids(self) -> None:
        self.assertEqual(self.catalogue.find("ipé 200")[0].profile_id,
                         "IPE/IPE 200")
        self.assertEqual(self.catalogue.find("IPE/IPE 200")[0].profile_id,
                         "IPE/IPE 200")
        self.assertEqual(self.catalogue.find("IPE 200")[0].designation, "IPE 200")
        tubes = self.catalogue.find("CHS 168.3x6")
        self.assertTrue(tubes)
        self.assertTrue(all("CHS168.3X6" in search_key(row.profile_id)
                            or "CHS168.3X6" in search_key(row.designation)
                            for row in tubes))

    def test_filters_keep_standard_and_commercial_apart(self) -> None:
        commercial = self.catalogue.profiles(category="commercial")
        standard = self.catalogue.profiles(category="standard")
        self.assertEqual(len(standard), 1792)
        self.assertEqual(len(commercial) + len(standard),
                         self.catalogue.totals()["profiles"])
        self.assertTrue(all(row.category == "commercial" for row in commercial))
        self.assertTrue(all(row.category == "standard" for row in standard))
        tes = self.catalogue.profiles(series_id="AM-TES")
        if tes:  # série locale uniquement
            self.assertEqual(len(tes), 7)
            self.assertTrue(all(not row.is_complete for row in tes))

    def test_complete_detail_has_exact_geometry_and_published_values(self) -> None:
        detail = self.catalogue.detail("IPE/IPE 200")
        self.assertTrue(detail.is_complete)
        self.assertIsNotNone(detail.section)
        self.assertIsNotNone(detail.properties_exact)
        self.assertEqual(detail.missing, ())
        self.assertEqual(len(detail.properties), len(PROPERTY_LABELS))
        self.assertEqual(detail.nonconforming, ())
        self.assertTrue(all(d.value is not None for d in detail.dimensions))
        self.assertTrue(all(line.published is not None for line in detail.properties))
        self.assertTrue(all(line.ratio is not None and line.ratio <= 1.0
                            for line in detail.properties))

    def test_incomplete_detail_is_refused_without_substitution(self) -> None:
        if "AM-TES/Té 20x20x3" not in {
                row.profile_id for row in self.catalogue.profiles()}:
            self.skipTest("catalogue standard seul : aucun T commercial local")
        detail = self.catalogue.detail("AM-TES/Té 20x20x3")
        self.assertFalse(detail.is_complete)
        self.assertIsNone(detail.section)
        self.assertIsNone(detail.properties_exact)
        self.assertEqual(detail.missing, ("slope_pct", "x_tf"))
        self.assertIn("aucune valeur n'est inventée", detail.error or "")
        self.assertIn("paramètres manquants", detail.error or "")
        self.assertEqual(detail.properties, ())
        self.assertTrue(detail.dimensions)
        self.assertTrue(any(param.value is None for param in detail.dimensions))


@unittest.skipUnless(HAS_DB and HAS_QT,
                     "base ou PySide6 absents : tests de fenêtre ignorés")
class WindowTests(unittest.TestCase):
    """Fenêtre construite hors écran : arbre, tableaux, refus d'export."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])
        cls.catalogue = Catalogue()
        from app.gui.main_window import MainWindow
        cls.window = MainWindow(cls.catalogue, Path(DEFAULT_DB))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.window.close()  # ferme la connexion du catalogue

    def test_tree_shows_all_families(self) -> None:
        expected = sum(1 for family in self.catalogue.families()
                       if family.profile_count)
        self.assertEqual(self.window._tree.topLevelItemCount(), expected)
        self.assertGreaterEqual(expected, 6)

    def test_selecting_a_profile_fills_the_tables(self) -> None:
        self.assertTrue(self.window.select_profile("IPE/IPE 200"))
        self.assertEqual(self.window._title.text(), "IPE 200")
        self.assertEqual(self.window._property_table.rowCount(), 21)
        self.assertEqual(self.window._dimension_table.rowCount(), 5)
        self.assertTrue(self.window._export_action.isEnabled())
        self.assertTrue(self.window._export_button.isEnabled())
        self.assertEqual(self.window._export_button.text(), "Exporter ce profilé…")
        self.assertIsNotNone(self.window._current_detail)
        self.assertTrue(self.window._current_detail.is_complete)

    def test_incomplete_profile_disables_export(self) -> None:
        if not self.window.select_profile("AM-TES/Té 20x20x3"):
            self.skipTest("catalogue standard seul : aucun T commercial local")
        self.assertFalse(self.window._export_action.isEnabled())
        self.assertFalse(self.window._export_button.isEnabled())
        self.assertEqual(self.window._export_button.text(), "Export refusé")
        self.assertIn("refusé", self.window._export_button.toolTip())
        detail = self.window._current_detail
        self.assertIsNotNone(detail)
        self.assertFalse(detail.is_complete)
        self.assertIn("Refus de construction", self.window._notes.toPlainText())
        self.assertIn("aucune valeur n'est inventée",
                      self.window._notes.toPlainText())

    def test_preview_path_is_exact_for_a_hollow_section(self) -> None:
        from app.gui.preview import section_path
        detail = self.catalogue.detail("CHS-CF/CHS 168.3x6")
        path = section_path(detail.section)
        bounds = path.boundingRect()
        self.assertAlmostEqual(bounds.left(), -84.15, places=9)
        self.assertAlmostEqual(bounds.right(), 84.15, places=9)
        self.assertAlmostEqual(bounds.top(), -84.15, places=9)
        self.assertAlmostEqual(bounds.bottom(), 84.15, places=9)
        # Le centre est dans le trou : le remplissage pair-impair doit l'exclure.
        self.assertFalse(path.contains(QPointF(0.0, 0.0)))
        self.assertGreater(path.elementCount(), 8)

    def test_export_dialog_exports_and_releases_worker(self) -> None:
        """Le QThread n'est relâché qu'après son arrêt effectif (pas de qFatal)."""
        from PySide6.QtCore import QEventLoop, QTimer

        from app.gui.export_dialog import ExportDialog

        with tempfile.TemporaryDirectory() as directory:
            dialog = ExportDialog(db_path=Path(DEFAULT_DB),
                                  profile_ids=["IPE/IPE 200"], title="test")
            dialog._directory.setText(directory)
            for fmt, box in dialog._format_boxes.items():
                box.setChecked(fmt == "dxf")
            dialog.show()
            self.application.processEvents()
            dialog._start()
            self.assertIsNotNone(dialog._worker)
            # Un setWindowFlag() ici masquerait la boîte modale et ferait sortir
            # exec() avant la fin du thread (cause du qFatal corrigé).
            self.assertTrue(dialog.isVisible())

            loop = QEventLoop()

            def finished() -> None:
                if dialog._worker is None:
                    loop.quit()
                else:
                    QTimer.singleShot(20, finished)

            finished()
            QTimer.singleShot(30_000, loop.quit)
            loop.exec()
            self.application.processEvents()

            self.assertIsNone(dialog._worker)
            self.assertTrue((Path(directory) / "IPE-IPE-200.dxf").is_file())
            self.assertIn("exporté", dialog._result.text())
            dialog.reject()

    def test_number_formatting_is_compact_and_stable(self) -> None:
        from app.gui.main_window import format_number, format_ratio
        self.assertEqual(format_number(None), "—")
        self.assertEqual(format_number(0.0), "0")
        self.assertEqual(format_number(1.3e-13), "0")
        self.assertEqual(format_number(1125.0), "1125")
        self.assertEqual(format_ratio(None), "—")
        self.assertEqual(format_ratio(0.5), "0.50 × tol.")


if __name__ == "__main__":
    unittest.main()
