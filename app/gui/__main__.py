"""Lancement de la fenêtre : `python -m app.gui`."""
from __future__ import annotations

import sys

try:
    from app.gui.app import main
except ImportError as exc:  # pragma: no cover - dépend de l'environnement
    print("L'interface requiert PySide6 :", file=sys.stderr)
    print("    python -m pip install PySide6", file=sys.stderr)
    print(f"({exc})", file=sys.stderr)
    raise SystemExit(2) from exc

raise SystemExit(main())
