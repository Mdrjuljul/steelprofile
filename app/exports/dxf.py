"""Export DXF R12 : contours exacts du profilé, arcs réels (bulges).

Chaque contour devient une POLYLINE fermée 2D. Un arc n'est jamais une corde :
il est porté par le *bulge* `tan(θ/4)` du sommet de départ, avec `θ` l'ouverture
signée du tronçon (au plus 90°, voir `curve.py`). Le dessin est donc exact à la
précision du DXF, sans facettage.

Le format R12 (AC1009) est choisi pour sa compatibilité maximale : pas de
poignées, pas de tables obligatoires au-delà des calques, et support natif du
bulge sur les VERTEX.

Repère : plan (X, Y) avec `X = y` et `Y = z` du repère de section, en mm.
"""
from __future__ import annotations

from pathlib import Path

from app.geometry.contour import Section

from app.exports.curve import ascii_text, contour_segments

OUTER_LAYER = "PROFILE"
HOLE_LAYER = "HOLES"


def _ascii(text: str) -> str:
    return ascii_text(text)


def _pair(fh, code: int, value) -> None:
    fh.write(f"{code}\n{value}\n")


def _polyline(fh, layer: str, points: list[tuple[float, float]],
              bulges: list[float], closed: bool = True) -> None:
    _pair(fh, 0, "POLYLINE")
    _pair(fh, 8, layer)
    _pair(fh, 66, 1)
    _pair(fh, 70, 1 if closed else 0)
    _pair(fh, 10, 0.0)
    _pair(fh, 20, 0.0)
    _pair(fh, 30, 0.0)
    for (x, y), bulge in zip(points, bulges):
        _pair(fh, 0, "VERTEX")
        _pair(fh, 8, layer)
        _pair(fh, 10, f"{x:.12g}")
        _pair(fh, 20, f"{y:.12g}")
        _pair(fh, 30, 0.0)
        if bulge:
            _pair(fh, 42, f"{bulge:.12g}")
        _pair(fh, 70, 0)
    _pair(fh, 0, "SEQEND")
    _pair(fh, 8, layer)


def write_dxf(section: Section, path: str | Path, *, name: str = "") -> Path:
    """Écrit les contours exacts de la section en DXF R12 (mm)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    y_min, y_max, z_min, z_max = section.bounds()
    groups = [(OUTER_LAYER, contour) for contour in section.outer]
    groups += [(HOLE_LAYER, contour) for contour in section.holes]

    with open(path, "w", encoding="ascii", newline="\n") as fh:
        _pair(fh, 999, _ascii(f"SteelProfile - {name or 'section'} - unites mm, arcs exacts"))
        _pair(fh, 0, "SECTION")
        _pair(fh, 2, "HEADER")
        _pair(fh, 9, "$ACADVER")
        _pair(fh, 1, "AC1009")
        _pair(fh, 9, "$INSBASE")
        _pair(fh, 10, 0.0)
        _pair(fh, 20, 0.0)
        _pair(fh, 30, 0.0)
        _pair(fh, 9, "$EXTMIN")
        _pair(fh, 10, f"{y_min:.12g}")
        _pair(fh, 20, f"{z_min:.12g}")
        _pair(fh, 30, 0.0)
        _pair(fh, 9, "$EXTMAX")
        _pair(fh, 10, f"{y_max:.12g}")
        _pair(fh, 20, f"{z_max:.12g}")
        _pair(fh, 30, 0.0)
        _pair(fh, 9, "$INSUNITS")
        _pair(fh, 70, 4)  # millimètres
        _pair(fh, 9, "$MEASUREMENT")
        _pair(fh, 70, 1)  # système métrique
        _pair(fh, 0, "ENDSEC")

        _pair(fh, 0, "SECTION")
        _pair(fh, 2, "TABLES")
        _pair(fh, 0, "TABLE")
        _pair(fh, 2, "LAYER")
        _pair(fh, 70, 2)
        for layer, color in ((OUTER_LAYER, 7), (HOLE_LAYER, 8)):
            _pair(fh, 0, "LAYER")
            _pair(fh, 2, layer)
            _pair(fh, 70, 0)
            _pair(fh, 62, color)
            _pair(fh, 6, "CONTINUOUS")
        _pair(fh, 0, "ENDTAB")
        _pair(fh, 0, "ENDSEC")

        _pair(fh, 0, "SECTION")
        _pair(fh, 2, "ENTITIES")
        for layer, contour in groups:
            segments = contour_segments(contour)
            points = [segment.start for segment in segments]
            bulges = [segment.bulge() for segment in segments]
            _polyline(fh, layer, points, bulges)
        _pair(fh, 0, "ENDSEC")

        _pair(fh, 0, "EOF")
    return path
