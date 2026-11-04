"""Découpage des contours exacts en segments exploitables par les exports.

Le noyau de géométrie décrit une frontière avec des arcs de rayon quelconque,
jusqu'au cercle complet. Les formats d'export ont chacun leurs contraintes :

- DXF exprime un arc par un *bulge* `tan(θ/4)`, infini à 360° et numériquement
  fragile au-delà de 90° ;
- STEP représente un cercle complet par une arête périodique dont les deux
  extrémités coïncident, topologie mal acceptée par certains noyaux.

On découpe donc chaque arc en tronçons d'au plus 90°, **sans changer la
géométrie** : chaque tronçon reste un arc du même cercle, de même centre et de
même rayon. Les extrémités sont chaînées pour que deux segments consécutifs
partagent exactement le même point, condition d'une topologie STEP étanche.

Repère d'export : la section est dans le plan (X, Y) avec `X = y` et `Y = z`
du repère de section ; l'extrusion se fait selon +Z (axe du profilé).
"""
from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass, replace

from app.geometry.contour import Arc, Contour, GeometryError, Line

MAX_SWEEP = math.pi / 2.0
"""Ouverture maximale d'un tronçon d'arc exporté (90°)."""


def ascii_text(text: str) -> str:
    """Texte ASCII stable pour les formats qui n'acceptent pas l'Unicode."""
    for dash in ("\u2014", "\u2013", "\u2212"):
        text = text.replace(dash, "-")
    decomposed = unicodedata.normalize("NFKD", text)
    return decomposed.encode("ascii", "ignore").decode("ascii")


@dataclass(frozen=True)
class Segment:
    """Tronçon de frontière : segment de droite ou arc de cercle exact.

    `center`, `radius`, `theta0` et `sweep` ne sont renseignés que pour un arc.
    `start` et `end` sont chaînés avec les tronçons voisins : le point de
    jonction est partagé, pas recalculé.
    """

    start: tuple[float, float]
    end: tuple[float, float]
    center: tuple[float, float] | None = None
    radius: float = 0.0
    theta0: float = 0.0
    sweep: float = 0.0

    @property
    def is_arc(self) -> bool:
        return self.center is not None

    def bulge(self) -> float:
        """Bulge DXF : `tan(sweep/4)`, positif dans le sens trigonométrique."""
        if not self.is_arc:
            return 0.0
        return math.tan(self.sweep / 4.0)

    def length(self) -> float:
        if self.is_arc:
            return abs(self.sweep) * self.radius
        return math.dist(self.start, self.end)

    def chamfer_error(self, segments: int) -> float:
        """Flèche maximale entre l'arc et la corde pour `segments` tronçons."""
        if not self.is_arc or segments <= 0:
            return 0.0
        half = abs(self.sweep) / (2.0 * segments)
        return self.radius * (1.0 - math.cos(half))


def _split_primitive(primitive: Line | Arc, max_sweep: float) -> list[Segment]:
    if isinstance(primitive, Line):
        return [Segment(start=primitive.p0, end=primitive.p1)]

    count = max(1, math.ceil(abs(primitive.sweep) / max_sweep - 1e-12))
    cy, cz = primitive.center
    r = primitive.radius
    parts: list[Segment] = []
    for k in range(count):
        t0 = primitive.theta0 + primitive.sweep * k / count
        t1 = primitive.theta0 + primitive.sweep * (k + 1) / count
        parts.append(Segment(
            start=(cy + r * math.cos(t0), cz + r * math.sin(t0)),
            end=(cy + r * math.cos(t1), cz + r * math.sin(t1)),
            center=primitive.center,
            radius=r,
            theta0=t0,
            sweep=t1 - t0,
        ))
    return parts


def contour_segments(contour: Contour, *, max_sweep: float = MAX_SWEEP) -> list[Segment]:
    """Tronçons d'un contour fermé, chaînés de bout en bout.

    Les points de jonction entre primitives sont alignés sur le tronçon
    précédent : deux tronçons voisins partagent exactement leurs extrémités,
    même si le calcul trigonométrique d'un arc diffère de `1e-16` mm.
    """
    if max_sweep <= 0.0:
        raise ValueError(f"max_sweep doit être > 0 (reçu {max_sweep})")
    parts: list[Segment] = []
    for primitive in contour.primitives:
        parts.extend(_split_primitive(primitive, max_sweep))

    for i in range(len(parts) - 1):
        if parts[i].end != parts[i + 1].start:
            parts[i + 1] = replace(parts[i + 1], start=parts[i].end)
    if parts[-1].end != parts[0].start:
        parts[-1] = replace(parts[-1], end=parts[0].start)
    return parts


def tessellate_contour(contour: Contour, tolerance: float,
                       *, max_sweep: float = MAX_SWEEP) -> list[tuple[float, float]]:
    """Polyligne fermée approchant le contour à `tolerance` mm près.

    La flèche de chaque arc est bornée par `tolerance` : le nombre de cordes est
    calculé par `R·(1 − cos(θ/2n)) ≤ tolerance`. Une tolérance nulle est refusée
    (un arc ne peut pas être représenté exactement par des cordes).
    """
    if tolerance <= 0.0:
        raise ValueError(f"la tolérance de corde doit être > 0 (reçue {tolerance})")
    points: list[tuple[float, float]] = []
    for segment in contour_segments(contour, max_sweep=max_sweep):
        points.append(segment.start)
        if not segment.is_arc:
            continue
        if tolerance >= segment.radius:
            count = 1
        else:
            step = 2.0 * math.acos(1.0 - tolerance / segment.radius)
            count = max(1, math.ceil(abs(segment.sweep) / step))
        cx, cz = segment.center  # type: ignore[misc]
        for k in range(1, count):
            t = segment.theta0 + segment.sweep * k / count
            points.append((cx + segment.radius * math.cos(t),
                           cz + segment.radius * math.sin(t)))

    # Fermeture implicite : le dernier segment rejoint le premier point ; son
    # extrémité a été chaînée sur `points[0]` par `contour_segments`.
    if len(points) < 3:
        raise GeometryError("contour dégénéré : moins de trois points après tessellation")
    return points


def section_loops(section, tolerance: float) -> list[list[tuple[float, float]]]:
    """Boucles tessellées de la section : extérieurs puis trous, orientations conservées."""
    return [tessellate_contour(contour, tolerance) for contour in section.contours]
