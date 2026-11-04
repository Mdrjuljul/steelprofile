"""Premier lancement : construction et validation du catalogue."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database.bootstrap import (  # noqa: E402
    DEFAULT_REPO,
    CatalogueMissing,
    ensure_catalogue,
    is_ready,
)
from app.geometry.build import connect  # noqa: E402


class BootstrapTests(unittest.TestCase):
    def test_missing_file_is_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(is_ready(Path(directory) / "absent.db"))

    def test_empty_file_is_not_ready(self) -> None:
        """Un `sqlite3.connect()` malencontreux laisse un fichier de 0 octet."""
        with tempfile.TemporaryDirectory() as directory:
            empty = Path(directory) / "vide.db"
            empty.touch()
            self.assertFalse(is_ready(empty))
            with self.assertRaises(FileNotFoundError):
                connect(empty)

    def test_ensure_builds_the_standard_catalogue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "profiles.db"
            stats = Path(directory) / "catalogue_stats.json"
            empty_staging = Path(directory) / "staging-vide"
            self.assertTrue(ensure_catalogue(db, repo=DEFAULT_REPO, stats=stats,
                                             staging=empty_staging))
            self.assertTrue(is_ready(db))
            con = sqlite3.connect(db)
            try:
                self.assertEqual(
                    con.execute("SELECT count(*) FROM profile").fetchone()[0], 1792)
                self.assertEqual(
                    con.execute("SELECT count(*) FROM series").fetchone()[0], 16)
                categories = {
                    row[0] for row in con.execute("SELECT DISTINCT category FROM series")
                }
                self.assertEqual(categories, {"standard"})
            finally:
                con.close()
            # Deuxième appel : rien à refaire.
            self.assertFalse(ensure_catalogue(db, repo=DEFAULT_REPO, stats=stats,
                                              staging=empty_staging))

    def test_missing_source_gives_an_actionable_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "profiles.db"
            with self.assertRaises(CatalogueMissing) as caught:
                ensure_catalogue(db, repo=Path(directory) / "absent",
                                 stats=Path(directory) / "stats.json")
            self.assertIn("data/sources", str(caught.exception))
            self.assertFalse(db.exists())


if __name__ == "__main__":
    unittest.main()
