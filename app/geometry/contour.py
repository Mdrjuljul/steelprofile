"""Contours exacts : segments, arcs, et intégrales de section en forme close.

Une section est un ensemble de contours fermés : contours extérieurs orientés dans
le sens trigonométrique (aire positive), trous orientés dans le sens horaire (aire
négative). Les primitives sont des segments et des arcs de cercle **exacts** : un
arc n'est jamais remplacé par une corde.

Les moments (aire, moments statiques, moments quadratiques, produit d'inertie)
sont obtenus par intégration de Green le long de la frontière, en forme close.
Toutes les formules sont exprimées dans le repère local (y horizontal vers la
droite, z vertical vers le haut), en millimètres.

Aucune valeur n'est approchée : seules les opérations flottantes de la
bibliothèque standard interviennent, et les formules sont exactes à l'arrondi
machine près.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

TAU = 2.0 * math.pi


def _int_sin_cos(p: int, q: int, t0: float, t1: float) -> float:
    """Intégrale exacte de sin^p(t)·cos^q(t) entre t0 et t1 (récurrence).

    Aucune quadrature : seuls des sinus et cosinus évalués aux bornes
    interviennent. Les cas de base sont p=q=0, (0,1), (1,0) et (1,1).
    """
    if p < 0 or q < 0:
        raise ValueError(f"exposants négatifs : ({p}, {q})")
    if q >= 2:
        edge = (math.sin(t1) ** (p + 1) * math.cos(t1) ** (q - 1)
                - math.sin(t0) ** (p + 1) * math.cos(t0) ** (q - 1))
        return (edge + (q - 1) * _int_sin_cos(p, q - 2, t0, t1)) / (p + q)
    if p >= 2:
        edge = (math.sin(t1) ** (p - 1) * math.cos(t1) ** (q + 1)
                - math.sin(t0) ** (p - 1) * math.cos(t0) ** (q + 1))
        return ((p - 1) * _int_sin_cos(p - 2, q, t0, t1) - edge) / (p + q)
    if p == 0 and q == 0:
        return t1 - t0
    if p == 0 and q == 1:
        return math.sin(t1) - math.sin(t0)
    if p == 1 and q == 0:
        return math.cos(t0) - math.cos(t1)
    # p == 1 and q == 1
    return 0.5 * (math.sin(t1) ** 2 - math.sin(t0) ** 2)


@dataclass(frozen=True)
class Moments:
    """Moments d'une frontière par rapport à l'origine du repère local.

    `Qy = ∫ z dA` et `Qz = ∫ y dA` (moments statiques, comme la base SSDB),
    `Iy = ∫ z² dA`, `Iz = ∫ y² dA`, `Iyz = ∫ y z dA` (moments d'ordre 2 à
    l'origine). Les valeurs au centre de gravité s'en déduisent par transport
    (voir `properties.py`).
    """

    A: float = 0.0
    Qy: float = 0.0
    Qz: float = 0.0
    Iy: float = 0.0
    Iz: float = 0.0
    Iyz: float = 0.0

    def __add__(self, other: "Moments") -> "Moments":
        return Moments(self.A + other.A, self.Qy + other.Qy, self.Qz + other.Qz,
                       self.Iy + other.Iy, self.Iz + other.Iz, self.Iyz + other.Iyz)


def _total(parts) -> Moments:
    """Somme stable (fsum) d'une suite de moments."""
    parts = list(parts)
    return Moments(
        A=math.fsum(p.A for p in parts),
        Qy=math.fsum(p.Qy for p in parts),
        Qz=math.fsum(p.Qz for p in parts),
        Iy=math.fsum(p.Iy for p in parts),
        Iz=math.fsum(p.Iz for p in parts),
        Iyz=math.fsum(p.Iyz for p in parts),
    )


@dataclass(frozen=True)
class Line:
    """Segment de droite exact, de `p0` à `p1`, dans le sens de parcours."""

    p0: tuple[float, float]
    p1: tuple[float, float]

    @property
    def start(self) -> tuple[float, float]:
        return self.p0

    @property
    def end(self) -> tuple[float, float]:
        return self.p1

    def length(self) -> float:
        return math.dist(self.p0, self.p1)

    def moments(self) -> Moments:
        (y0, z0), (y1, z1) = self.p0, self.p1
        u, v = y1 - y0, z1 - z0
        poly_y2z = z0 * (y0 * y0 + y0 * u + u * u / 3.0) + v * (
            y0 * y0 / 2.0 + 2.0 * y0 * u / 3.0 + u * u / 4.0)
        poly_yz2 = y0 * (z0 * z0 + z0 * v + v * v / 3.0) + u * (
            z0 * z0 / 2.0 + 2.0 * z0 * v / 3.0 + v * v / 4.0)
        return Moments(
            A=0.5 * (y0 * v - z0 * u),
            Qy=-0.5 * u * (z0 * z0 + z0 * v + v * v / 3.0),
            Qz=0.5 * v * (y0 * y0 + y0 * u + u * u / 3.0),
            Iy=v * poly_yz2,
            Iz=-u * poly_y2z,
            Iyz=0.25 * (v * poly_y2z - u * poly_yz2),
        )

    def corners(self) -> tuple[tuple[float, float], ...]:
        return (self.p0, self.p1)


@dataclass(frozen=True)
class Arc:
    """Arc de cercle exact.

    `center` : centre ; `radius` : rayon ; `theta0` : angle polaire du point de
    départ (radians) ; `sweep` : ouverture signée (positif = sens trigonométrique).
    """

    center: tuple[float, float]
    radius: float
    theta0: float
    sweep: float

    @property
    def start(self) -> tuple[float, float]:
        cy, cz = self.center
        return (cy + self.radius * math.cos(self.theta0),
                cz + self.radius * math.sin(self.theta0))

    @property
    def end(self) -> tuple[float, float]:
        t = self.theta0 + self.sweep
        cy, cz = self.center
        return (cy + self.radius * math.cos(t), cz + self.radius * math.sin(t))

    def length(self) -> float:
        return abs(self.sweep) * self.radius

    def contains_angle(self, angle: float) -> bool:
        """Vrai si l'angle polaire `angle` appartient à l'arc parcouru."""
        d = (angle - self.theta0) % TAU
        if self.sweep >= 0.0:
            return d <= self.sweep or math.isclose(d, TAU, abs_tol=1e-12)
        return (TAU - d) % TAU <= -self.sweep or math.isclose(d, 0.0, abs_tol=1e-12)

    def moments(self) -> Moments:
        """Intégrales de frontière de l'arc, en forme close.

        Les intégrandes sont des polynômes en sin t et cos t ; chaque monôme est
        intégré exactement par `_int_sin_cos` (récurrence), sans développement
        numérique ni discrétisation.
        """
        a, b = self.center
        R = self.radius
        t0, t1 = self.theta0, self.theta0 + self.sweep

        def J(p: int, q: int) -> float:
            return _int_sin_cos(p, q, t0, t1)

        J01, J02, J03 = J(0, 1), J(0, 2), J(0, 3)
        J10, J11, J12, J13 = J(1, 0), J(1, 1), J(1, 2), J(1, 3)
        J20, J21, J22 = J(2, 0), J(2, 1), J(2, 2)
        J30, J31 = J(3, 0), J(3, 1)

        # I1 = ∫ y dz, I2 = ∫ z dy, I4 = ∫ z² dy,
        # I5 = ∫ z² y dz, I6 = ∫ y² z dy, I7 = ∫ y² z dz, I8 = ∫ y z² dy.
        # Qy = ∫ z dA = −½∮z² dy ; Qz = ∫ y dA = ½∮y² dz.
        I1 = a * R * J01 + R * R * J02
        I2 = -b * R * J10 - R * R * J20
        I4 = -R * (b * b * J10 + 2.0 * b * R * J20 + R * R * J30)
        I5 = R * (a * b * b * J01 + b * b * R * J02 + 2.0 * a * b * R * J11
                  + 2.0 * b * R * R * J12 + a * R * R * J21 + R ** 3 * J22)
        I6 = -R * (a * a * b * J10 + a * a * R * J20 + 2.0 * a * b * R * J11
                   + 2.0 * a * R * R * J21 + b * R * R * J12 + R ** 3 * J22)
        I7 = R * (a * a * b * J01 + a * a * R * J11 + 2.0 * a * b * R * J02
                  + 2.0 * a * R * R * J12 + b * R * R * J03 + R ** 3 * J13)
        I8 = -R * (a * b * b * J10 + 2.0 * a * b * R * J20 + a * R * R * J30
                   + b * b * R * J11 + 2.0 * b * R * R * J21 + R ** 3 * J31)
        y2dz = R * (a * a * J01 + 2.0 * a * R * J02 + R * R * J03)

        return Moments(
            A=0.5 * (I1 - I2),
            Qy=-0.5 * I4,
            Qz=0.5 * y2dz,
            Iy=I5,
            Iz=-I6,
            Iyz=0.25 * (I7 - I8),
        )

    def corners(self) -> tuple[tuple[float, float], ...]:
        """Points où l'arc atteint un extremum en y ou en z (bornes exactes)."""
        pts = [self.start, self.end]
        for angle in (0.0, math.pi / 2.0, math.pi, 3.0 * math.pi / 2.0):
            if self.contains_angle(angle):
                pts.append((self.center[0] + self.radius * math.cos(angle),
                            self.center[1] + self.radius * math.sin(angle)))
        return tuple(pts)


Primitive = Line | Arc


@dataclass(frozen=True)
class Contour:
    """Chaîne fermée de primitives, chacune commençant où la précédente finit."""

    primitives: tuple[Primitive, ...]

    def moments(self) -> Moments:
        return _total(p.moments() for p in self.primitives)

    def signed_area(self) -> float:
        return self.moments().A

    def perimeter(self) -> float:
        return math.fsum(p.length() for p in self.primitives)

    def bounds(self) -> tuple[float, float, float, float]:
        pts = [pt for p in self.primitives for pt in p.corners()]
        ys = [p[0] for p in pts]
        zs = [p[1] for p in pts]
        return min(ys), max(ys), min(zs), max(zs)


@dataclass(frozen=True)
class Section:
    """Région bornée par des contours extérieurs (sens trigo) et des trous (sens horaire)."""

    outer: tuple[Contour, ...]
    holes: tuple[Contour, ...] = ()

    def __post_init__(self) -> None:
        if not self.outer:
            raise GeometryError("une section doit avoir au moins un contour extérieur")
        for contour in self.outer:
            if not contour.signed_area() > 0.0:
                raise GeometryError("un contour extérieur doit être orienté dans le sens trigonométrique")
        for contour in self.holes:
            if not contour.signed_area() < 0.0:
                raise GeometryError("un trou doit être orienté dans le sens horaire")

    @property
    def contours(self) -> tuple[Contour, ...]:
        return self.outer + self.holes

    def moments(self) -> Moments:
        return _total(p.moments() for c in self.contours for p in c.primitives)

    def perimeter(self) -> float:
        """Périmètre extérieur (m²/m de surface = ce périmètre / 1000)."""
        return math.fsum(c.perimeter() for c in self.outer)

    def bounds(self) -> tuple[float, float, float, float]:
        boxes = [c.bounds() for c in self.outer]
        return (min(b[0] for b in boxes), max(b[1] for b in boxes),
                min(b[2] for b in boxes), max(b[3] for b in boxes))


class GeometryError(ValueError):
    """Contour ou section non constructible."""


class ContourBuilder:
    """Trace un contour fermé avec un stylo portant une position et une direction.

    `line(longueur, cap)` trace un segment ; avec `cap`, le stylo tourne d'abord
    (angle droit). `arc(ouverture, rayon)` trace un arc tangent à la direction
    courante ; `ouverture` positive tourne à gauche. `close()` vérifie la fermeture.
    """

    def __init__(self, start: tuple[float, float], heading_deg: float = 0.0) -> None:
        self._start = start
        self._point = start
        self._heading = heading_deg
        self._pieces: list[Primitive] = []

    def _turn_to(self, heading_deg: float) -> None:
        self._heading = heading_deg

    def line(self, length: float, heading_deg: float | None = None) -> "ContourBuilder":
        if heading_deg is not None:
            self._turn_to(heading_deg)
        if length < 0.0:
            raise GeometryError(f"longueur de segment négative : {length}")
        if length == 0.0:
            return self
        a = math.radians(self._heading)
        y, z = self._point
        end = (y + length * math.cos(a), z + length * math.sin(a))
        self._pieces.append(Line(self._point, end))
        self._point = end
        return self

    def arc(self, sweep_deg: float, radius: float) -> "ContourBuilder":
        if radius < 0.0:
            raise GeometryError(f"rayon d'arc négatif : {radius}")
        if radius == 0.0 or sweep_deg == 0.0:
            self._heading += sweep_deg
            return self
        polar = self._heading - math.copysign(90.0, sweep_deg)
        p = math.radians(polar)
        y, z = self._point
        center = (y - radius * math.cos(p), z - radius * math.sin(p))
        arc = Arc(center, radius, p, math.radians(sweep_deg))
        self._pieces.append(arc)
        self._point = arc.end
        self._heading += sweep_deg
        return self

    def close(self, tolerance: float = 1e-7) -> Contour:
        if not self._pieces:
            raise GeometryError("contour vide")
        gap = math.dist(self._point, self._start)
        if gap > tolerance:
            raise GeometryError(f"contour non fermé : écart {gap:.3e} mm > {tolerance:.3e} mm")
        pieces = list(self._pieces)
        last = pieces[-1]
        if isinstance(last, Line) and last.p1 != self._start:
            pieces[-1] = Line(last.p0, self._start)
        return Contour(tuple(pieces))
