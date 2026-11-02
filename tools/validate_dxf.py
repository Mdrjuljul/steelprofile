"""Validation de développement des DXF avec ezdxf — outil optionnel.

ezdxf n'est pas une dépendance du projet ; il relit les fichiers R12 produits
par `app.exports.dxf`, vérifie leur structure et reconstruit l'aire **exacte**
des polylignes à partir des bulges (formule du segment circulaire), puis la
compare à l'aire publiée dans le manifeste.

    python -m venv %TEMP%\\dxfcheck
    %TEMP%\\dxfcheck\\Scripts\\python -m pip install ezdxf
    %TEMP%\\dxfcheck\\Scripts\\python tools\\validate_dxf.py exports
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

try:
    import ezdxf
except ImportError:  # pragma: no cover - dépend de l'environnement de dev
    raise SystemExit(
        "ezdxf est absent. Créer un environnement virtuel jetable et installer "
        "ezdxf (voir l'en-tête du script).")


def segment_area(x0: float, y0: float, x1: float, y1: float, bulge: float) -> float:
    """Aire signée exacte d'un segment de polyligne, bulge compris.

    Le bulge vaut `tan(θ/4)`. L'aire se décompose en l'aire du triangle formé
    avec l'origine et l'aire du segment circulaire, `(r²/2)(θ − sin θ)`.
    """
    chord = math.dist((x0, y0), (x1, y1))
    triangle = 0.5 * (x0 * y1 - x1 * y0)
    if bulge == 0.0 or chord == 0.0:
        return triangle
    theta = 4.0 * math.atan(bulge)
    radius = chord / (2.0 * math.sin(theta / 2.0))
    return triangle + 0.5 * radius * radius * (theta - math.sin(theta))


def polyline_area(entity) -> float:
    vertices = list(entity.vertices)
    total = 0.0
    for index, vertex in enumerate(vertices):
        following = vertices[(index + 1) % len(vertices)]
        total += segment_area(
            vertex.dxf.location.x, vertex.dxf.location.y,
            following.dxf.location.x, following.dxf.location.y,
            vertex.dxf.bulge,
        )
    return total


def check(directory: Path) -> int:
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    print(f"{'profilé':30s} {'entités':7s} {'fermées':7s} {'aire DXF':>12s} "
          f"{'écart':>10s} {'audit':6s}")
    failures = 0
    for entry in manifest["profiles"]:
        path = directory / entry["files"]["dxf"]
        document = ezdxf.readfile(path)
        auditor = document.audit()
        entities = list(document.modelspace())
        closed = all(entity.is_closed for entity in entities)
        area = abs(sum(polyline_area(entity) for entity in entities))
        expected = entry["area_mm2"]
        error = abs(area - expected) / expected
        ok = closed and not auditor.has_errors and error < 1e-9
        if not ok:
            failures += 1
        print(f"{entry['profile_id']:30s} {len(entities):<7d} {str(closed):7s} "
              f"{area:12.4f} {error:10.2e} {str(not auditor.has_errors):6s} "
              f"{'OK' if ok else 'ERR'}")
    print()
    print(f"{len(manifest['profiles'])} fichiers, {failures} en échec")
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    directory = Path(argv[1]) if len(argv) > 1 else Path("exports")
    return check(directory)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
