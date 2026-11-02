"""Point d'entrée de la fenêtre SteelProfile.

    python -m app.gui
    python -m app.gui --profile "IPE/IPE 200"
    python -m app.gui --db autre/profiles.db

L'interface est un client du moteur : elle ne contient aucune formule de
géométrie et aucune règle d'export. PySide6 n'est requis que pour cette couche.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):  # exécution directe : python app/gui/app.py
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from app.geometry.build import DEFAULT_DB  # noqa: E402
from app.gui.catalog import Catalogue  # noqa: E402
from app.gui.main_window import MainWindow  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.gui",
        description="Interface de SteelProfile : catalogue, aperçu exact et export.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB,
                        help=f"base SQLite (défaut : {DEFAULT_DB})")
    parser.add_argument("--profile", help="profilé à sélectionner au démarrage")
    parser.add_argument("--version", action="version", version="SteelProfile (Phase 4)")
    args = parser.parse_args(argv)

    application = QApplication(sys.argv[:1])
    application.setApplicationName("SteelProfile")
    application.setApplicationDisplayName("SteelProfile")
    application.setOrganizationName("SteelProfile")

    if not args.db.exists():
        QMessageBox.critical(
            None, "SteelProfile",
            f"Base introuvable :\n{args.db}\n\n"
            "Reconstruire le catalogue avec :\n"
            "    python app/database/import_data.py")
        return 2

    catalogue = Catalogue(args.db)
    window = MainWindow(catalogue, args.db)
    window.show()
    if args.profile:
        if not window.select_profile(args.profile):
            QMessageBox.warning(
                None, "SteelProfile",
                f"Profilé introuvable dans le catalogue : {args.profile}")
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
