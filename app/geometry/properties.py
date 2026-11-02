"""Propriétés de section calculées à partir d'un contour exact.

Toutes les grandeurs sont calculées en unités SI de la géométrie : millimètres
pour les longueurs, mm² pour l'aire, mm⁴ pour les moments, mm³ pour les modules.
La conversion vers les unités de catalogue (cm², cm⁴, cm³, cm, kg/m, m²/m) est
faite explicitement par `catalogue_values()`, afin qu'aucune confusion d'unité
ne s'introduise dans le moteur.

Les formules sont celles du moteur de référence SSDB (docs/CONVENTIONS.md) :

    y_c = Qz / A,  z_c = Qy / A
    Iy  = ∫ z² dA − A·z_c²      (axe y passant par le centre de gravité)
    Iz  = ∫ y² dA − A·y_c²
    Iyz = ∫ y z dA − A·y_c·z_c
    Wel_y = Iy / max(z_top, z_bottom), etc.

`ys` et `zs` sont les coordonnées du centre de gravité mesurées depuis les bords
du rectangle englobant (convention des catalogues et de la base), et non depuis
l'origine du repère local.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.geometry.contour import GeometryError, Section

RHO_STEEL_KG_M3 = 7850.0
MM2_TO_M2 = 1e-6
ISOTROPY_TOLERANCE = 1e-9


@dataclass(frozen=True)
class SectionProperties:
    """Propriétés élastiques exactes, en unités géométriques (mm, mm², mm⁴, mm³)."""

    A: float
    y_c: float
    z_c: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float
    Iy: float
    Iz: float
    Iyz: float
    I_u: float
    I_v: float
    alpha_deg: float
    Wel_y_top: float
    Wel_y_bottom: float
    Wel_z_right: float
    Wel_z_left: float
    Wel_y: float
    Wel_z: float
    i_y: float
    i_z: float
    perimeter: float
    mass: float

    @property
    def i_u(self) -> float:
        return math.sqrt(self.I_u / self.A)

    @property
    def i_v(self) -> float:
        return math.sqrt(self.I_v / self.A)

    @property
    def ys(self) -> float:
        """Abscisse du centre de gravité depuis le bord gauche du rectangle englobant."""
        return self.y_c - self.y_min

    @property
    def zs(self) -> float:
        """Cote du centre de gravité depuis le bord inférieur du rectangle englobant."""
        return self.z_c - self.z_min

    @property
    def surface(self) -> float:
        """Surface développée par mètre de longueur [m²/m] = périmètre extérieur / 1000."""
        return self.perimeter / 1000.0

    def catalogue_values(self) -> dict[str, float]:
        """Valeurs dans les unités de `derived_property` (cm², cm⁴, cm³, cm, kg/m, m²/m)."""
        return {
            "A": self.A / 100.0,
            "Iy": self.Iy / 1e4,
            "Iz": self.Iz / 1e4,
            "Iyz": self.Iyz / 1e4,
            "Iu": self.I_u / 1e4,
            "Iv": self.I_v / 1e4,
            "alpha": self.alpha_deg,
            "i_y": self.i_y / 10.0,
            "i_z": self.i_z / 10.0,
            "i_u": self.i_u / 10.0,
            "i_v": self.i_v / 10.0,
            "Wel_y": self.Wel_y / 1e3,
            "Wel_y_top": self.Wel_y_top / 1e3,
            "Wel_y_bottom": self.Wel_y_bottom / 1e3,
            "Wel_z": self.Wel_z / 1e3,
            "Wel_z_left": self.Wel_z_left / 1e3,
            "Wel_z_right": self.Wel_z_right / 1e3,
            "mass": self.mass,
            "surface": self.surface,
            "ys": self.ys / 10.0,
            "zs": self.zs / 10.0,
        }


def principal_axes(Iy: float, Iz: float, Iyz: float) -> tuple[float, float, float]:
    """(I_u, I_v, alpha_deg) des moments principaux, axe u à l'angle alpha de +y.

    `I(a) = Iy·cos²a + Iz·sin²a − 2·Iyz·sin a·cos a`, maximum en
    `alpha = ½·atan2(−2·Iyz, Iy − Iz)` ramené dans ]−90°, 90°]. Si les deux
    moments principaux sont égaux (section isotrope), alpha = 0 par convention.
    """
    mean = (Iy + Iz) / 2.0
    radius = math.hypot((Iy - Iz) / 2.0, Iyz)
    if radius <= ISOTROPY_TOLERANCE * abs(mean):
        return mean + radius, mean - radius, 0.0
    alpha = 0.5 * math.degrees(math.atan2(-2.0 * Iyz, Iy - Iz))
    if alpha <= -90.0:
        alpha += 180.0
    return mean + radius, mean - radius, alpha + 0.0


def section_properties(section: Section) -> SectionProperties:
    """Propriétés élastiques exactes d'une section (contours fermés, arcs exacts)."""
    m = section.moments()
    if not m.A > 0.0:
        raise GeometryError("l'aire de la section doit être positive")
    y_c = m.Qz / m.A
    z_c = m.Qy / m.A
    Iy = m.Iy - m.A * z_c * z_c
    Iz = m.Iz - m.A * y_c * y_c
    Iyz = m.Iyz - m.A * y_c * z_c
    I_u, I_v, alpha = principal_axes(Iy, Iz, Iyz)

    y_min, y_max, z_min, z_max = section.bounds()
    z_top, z_bottom = z_max - z_c, z_c - z_min
    y_right, y_left = y_max - y_c, y_c - y_min
    if not (z_top > 0.0 and z_bottom > 0.0 and y_right > 0.0 and y_left > 0.0):
        raise GeometryError("le centre de gravité doit être intérieur au rectangle englobant")

    return SectionProperties(
        A=m.A,
        y_c=y_c,
        z_c=z_c,
        y_min=y_min,
        y_max=y_max,
        z_min=z_min,
        z_max=z_max,
        Iy=Iy,
        Iz=Iz,
        Iyz=Iyz,
        I_u=I_u,
        I_v=I_v,
        alpha_deg=alpha,
        Wel_y_top=Iy / z_top,
        Wel_y_bottom=Iy / z_bottom,
        Wel_z_right=Iz / y_right,
        Wel_z_left=Iz / y_left,
        Wel_y=Iy / max(z_top, z_bottom),
        Wel_z=Iz / max(y_right, y_left),
        i_y=math.sqrt(Iy / m.A),
        i_z=math.sqrt(Iz / m.A),
        perimeter=section.perimeter(),
        mass=m.A * MM2_TO_M2 * RHO_STEEL_KG_M3,
    )
