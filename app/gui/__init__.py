"""SteelProfile — interface de bureau (Phase 4).

Le sous-paquet n'importe **pas** Qt à l'import : `import app.gui` fonctionne
même sans PySide6, et le moteur (`app.geometry`) comme les exports
(`app.exports`) restent utilisables sans interface. L'import de Qt est fait par
`app.gui.app`, chargé uniquement au lancement de la fenêtre.
"""
from __future__ import annotations

__all__ = ["main"]


def __getattr__(name: str):
    """Expose `main` sans charger Qt tant qu'on ne l'appelle pas."""
    if name == "main":
        from app.gui.app import main

        return main
    raise AttributeError(f"module {__name__!r} n'a pas d'attribut {name!r}")
