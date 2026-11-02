"""Générateurs de sections exactes, famille par famille.

Chaque fonction reçoit les dimensions en millimètres et renvoie une `Section`
composée de segments et d'arcs de cercle **exacts**. Les conventions de repère
sont celles de la base et du moteur de référence (SSDB) :

- I/H et plats : origine au centre, y horizontal vers la droite, z vers le haut ;
- U : dos de l'âme en y = 0, ailes vers +y, z = 0 à mi-hauteur ;
- cornières : talon à l'origine, aile h selon +z, aile b selon +y, semelles
  extérieures sur les axes ;
- tubes : origine au centre ; ronds et carrés pleins : origine au centre.

Les paramètres sont validés avant construction : une géométrie impossible est
refusée, jamais corrigée. Un rayon nul est un angle vif (pas d'arc).
"""
from __future__ import annotations

import math
from typing import Callable, Mapping

from app.geometry.contour import ContourBuilder, GeometryError, Section

CLOSURE_TOLERANCE_FACTOR = 1e-9


def _tolerance(*dims: float) -> float:
    return CLOSURE_TOLERANCE_FACTOR * max(dims)


def _require_positive(**values: float) -> None:
    errors = [f"{name} doit être > 0 (reçu {value:g})" for name, value in values.items() if not value > 0.0]
    if errors:
        raise GeometryError("; ".join(errors))


def _require_non_negative(**values: float) -> None:
    errors = [f"{name} doit être >= 0 (reçu {value:g})" for name, value in values.items() if not value >= 0.0]
    if errors:
        raise GeometryError("; ".join(errors))


# --------------------------------------------------------------------------- #
# I / H à semelles parallèles
# --------------------------------------------------------------------------- #

def i_section(h: float, b: float, tw: float, tf: float, r: float) -> Section:
    """Profilé I ou H : semelles parallèles, quatre congés de racine, bouts vifs."""
    _require_positive(h=h, b=b, tw=tw, tf=tf)
    _require_non_negative(r=r)
    flange_flat = (b - tw) / 2.0 - r
    web_flat = h - 2.0 * tf - 2.0 * r
    if not flange_flat > 0.0:
        raise GeometryError(f"partie droite de semelle (b - tw)/2 - r = {flange_flat:g} doit être > 0")
    if not web_flat > 0.0:
        raise GeometryError(f"partie droite d'âme h - 2 tf - 2 r = {web_flat:g} doit être > 0")
    contour = (
        ContourBuilder(start=(-b / 2.0, -h / 2.0), heading_deg=0.0)
        .line(b, 0.0)                     # dessous de la semelle inférieure
        .line(tf, 90.0)
        .line(flange_flat, 180.0)         # dessus de la semelle, débord droit
        .arc(-90.0, r)
        .line(web_flat, 90.0)             # face droite de l'âme
        .arc(-90.0, r)
        .line(flange_flat, 0.0)           # dessous de la semelle supérieure, débord droit
        .line(tf, 90.0)
        .line(b, 180.0)                   # dessus de la semelle supérieure
        .line(tf, 270.0)
        .line(flange_flat, 0.0)           # dessous de la semelle supérieure, débord gauche
        .arc(-90.0, r)
        .line(web_flat, 270.0)            # face gauche de l'âme
        .arc(-90.0, r)
        .line(flange_flat, 180.0)         # dessus de la semelle inférieure, débord gauche
        .line(tf, 270.0)
        .close(tolerance=_tolerance(h, b))
    )
    return Section(outer=(contour,))


# --------------------------------------------------------------------------- #
# Semelles inclinées : débord commun aux U et I
# --------------------------------------------------------------------------- #

def _outstand(h: float, y_web: float, y_tip: float, tf: float, x_tf: float,
              slope_pct: float, r1: float, r2: float) -> tuple[float, float, float]:
    """(web_half, run, tip_flat) d'un débord de semelle inclinée (conventions SSDB).

    La face intérieure est `z = c0 + s·y`, avec `s = slope_pct/100` et
    `c0 = h/2 − tf − s·(y_tip − x_tf)`. Le congé de racine r1 et l'arc de bout
    r2 sont tangents aux deux droites qu'ils joignent et tournent de 90° − α,
    avec `k = √(1+s²)`.
    """
    s = slope_pct / 100.0
    k = math.sqrt(1.0 + s * s)
    c0 = h / 2.0 - tf - s * (y_tip - x_tf)
    web_half = c0 + s * (y_web + r1) - r1 * k
    toe_z = c0 + s * (y_tip - r2) + r2 * k
    run = (y_tip - r2 + r2 * s / k) - (y_web + r1 - r1 * s / k)
    tip_flat = h / 2.0 - toe_z
    return web_half, run, tip_flat


def _check_outstand(h: float, b: float, tw: float, tf: float, r1: float, r2: float,
                    slope_pct: float, x_tf: float, *, y_web: float, y_tip: float,
                    web_label: str) -> None:
    _require_positive(h=h, b=b, tw=tw, tf=tf)
    _require_non_negative(r1=r1, r2=r2, slope_pct=slope_pct)
    width = y_tip - y_web
    if not width > 0.0:
        raise GeometryError(f"débord de semelle {web_label} = {width:g} doit être > 0")
    if slope_pct != 0.0 and not 0.0 < x_tf < width:
        raise GeometryError(f"x_tf = {x_tf:g} doit être sur le débord (0 < x_tf < {width:g})")
    web_half, run, tip_flat = _outstand(h, y_web, y_tip, tf, x_tf, slope_pct, r1, r2)
    if not web_half > 0.0:
        raise GeometryError(f"partie droite d'âme entre congés = {2.0 * web_half:g} doit être > 0")
    if not run > 0.0:
        raise GeometryError(f"partie droite de semelle entre congé et bout = {run:g} doit être > 0")
    if not tip_flat > 0.0:
        raise GeometryError(f"partie droite de bout de semelle = {tip_flat:g} doit être > 0")


def channel(h: float, b: float, tw: float, tf: float, r1: float, r2: float,
            slope_pct: float, x_tf: float) -> Section:
    """Profilé U : semelles parallèles (slope_pct = 0, r2 = 0) ou inclinées (UPN)."""
    _check_outstand(h, b, tw, tf, r1, r2, slope_pct, x_tf,
                    y_web=tw, y_tip=b, web_label="b - tw")
    web_half, run, tip_flat = _outstand(h, tw, b, tf, x_tf, slope_pct, r1, r2)
    alpha = math.degrees(math.atan(slope_pct / 100.0))
    turn = 90.0 - alpha
    face = run * math.sqrt(1.0 + (slope_pct / 100.0) ** 2)
    contour = (
        ContourBuilder(start=(0.0, -h / 2.0), heading_deg=0.0)
        .line(b, 0.0)                     # face extérieure de la semelle inférieure
        .line(tip_flat, 90.0)             # bout de la semelle inférieure
        .arc(turn, r2)                    # arc de bout
        .line(face, 180.0 - alpha)        # face intérieure, vers l'âme
        .arc(-turn, r1)                   # congé de racine
        .line(2.0 * web_half, 90.0)       # face intérieure de l'âme
        .arc(-turn, r1)                   # congé de racine
        .line(face, alpha)                # face intérieure, vers le bout
        .arc(turn, r2)                    # arc de bout
        .line(tip_flat, 90.0)             # bout de la semelle supérieure
        .line(b, 180.0)                   # face extérieure de la semelle supérieure
        .line(h, 270.0)                   # dos de l'âme
        .close(tolerance=_tolerance(h, b))
    )
    return Section(outer=(contour,))


def i_tapered(h: float, b: float, tw: float, tf: float, r1: float, r2: float,
              slope_pct: float, x_tf: float) -> Section:
    """Profilé I à semelles inclinées (IPN) : quatre débords identiques."""
    _check_outstand(h, b, tw, tf, r1, r2, slope_pct, x_tf,
                    y_web=tw / 2.0, y_tip=b / 2.0, web_label="(b - tw)/2")
    web_half, run, tip_flat = _outstand(h, tw / 2.0, b / 2.0, tf, x_tf, slope_pct, r1, r2)
    alpha = math.degrees(math.atan(slope_pct / 100.0))
    turn = 90.0 - alpha
    face = run * math.sqrt(1.0 + (slope_pct / 100.0) ** 2)
    web = 2.0 * web_half
    contour = (
        ContourBuilder(start=(-b / 2.0, -h / 2.0), heading_deg=0.0)
        .line(b, 0.0)
        .line(tip_flat, 90.0)
        .arc(turn, r2)
        .line(face, 180.0 - alpha)
        .arc(-turn, r1)
        .line(web, 90.0)
        .arc(-turn, r1)
        .line(face, alpha)
        .arc(turn, r2)
        .line(tip_flat, 90.0)
        .line(b, 180.0)
        .line(tip_flat, 270.0)
        .arc(turn, r2)
        .line(face, 360.0 - alpha)
        .arc(-turn, r1)
        .line(web, 270.0)
        .arc(-turn, r1)
        .line(face, 180.0 + alpha)
        .arc(turn, r2)
        .line(tip_flat, 270.0)
        .close(tolerance=_tolerance(h, b))
    )
    return Section(outer=(contour,))


# --------------------------------------------------------------------------- #
# Cornières
# --------------------------------------------------------------------------- #

def angle(h: float, b: float, t: float, r1: float, r2: float) -> Section:
    """Cornière à ailes inégales (h ≠ b) ou égales (h = b), talon à l'origine."""
    _require_positive(h=h, b=b, t=t)
    _require_non_negative(r1=r1, r2=r2)
    tolerance = _tolerance(h, b)
    for name, leg in (("h", h), ("b", b)):
        inner = leg - t - r1 - r2
        if not leg > t:
            raise GeometryError(f"aile {name} = {leg:g} doit être > t = {t:g}")
        if inner < -tolerance:
            raise GeometryError(f"partie droite intérieure de l'aile {name} = {inner:g} doit être >= 0")
    if t - r2 < -tolerance:
        raise GeometryError(f"bout d'aile t - r2 = {t - r2:g} doit être >= 0")
    inner_b = 0.0 if b - t - r1 - r2 <= tolerance else b - t - r1 - r2
    inner_h = 0.0 if h - t - r1 - r2 <= tolerance else h - t - r1 - r2
    leg_end = 0.0 if t - r2 <= tolerance else t - r2
    contour = (
        ContourBuilder(start=(0.0, 0.0), heading_deg=0.0)
        .line(b, 0.0)                     # face extérieure de l'aile b
        .line(leg_end, 90.0)              # bout de l'aile b
        .arc(90.0, r2)                    # arc de bout
        .line(inner_b, 180.0)             # face intérieure de l'aile b
        .arc(-90.0, r1)                   # congé de racine
        .line(inner_h, 90.0)              # face intérieure de l'aile h
        .arc(90.0, r2)                    # arc de bout
        .line(leg_end, 180.0)             # bout de l'aile h
        .line(h, 270.0)                   # face extérieure de l'aile h, retour au talon
        .close(tolerance=tolerance)
    )
    return Section(outer=(contour,))


# --------------------------------------------------------------------------- #
# Tubes
# --------------------------------------------------------------------------- #

def rect_hollow(b: float, h: float, t: float, ro: float, ri: float) -> Section:
    """Tube rectangulaire (h ≥ b) ou carré (h = b), paroi constante, angles arrondis."""
    _require_positive(b=b, h=h, t=t)
    _require_non_negative(ro=ro, ri=ri)
    if h < b:
        raise GeometryError(f"h = {h:g} < b = {b:g} : la hauteur doit être >= la largeur")
    for label, value in (("largeur intérieure b - 2t", b - 2.0 * t),
                         ("hauteur intérieure h - 2t", h - 2.0 * t)):
        if not value > 0.0:
            raise GeometryError(f"{label} = {value:g} doit être > 0 (pas de trou)")
    tolerance = _tolerance(h, b)
    for label, value in (("plateau extérieur b - 2ro", b - 2.0 * ro),
                         ("plateau extérieur h - 2ro", h - 2.0 * ro),
                         ("plateau intérieur b - 2t - 2ri", b - 2.0 * t - 2.0 * ri),
                         ("plateau intérieur h - 2t - 2ri", h - 2.0 * t - 2.0 * ri)):
        if value < -tolerance:
            raise GeometryError(f"{label} = {value:g} doit être >= 0")
    d = ro - ri
    if not (d <= t or d * d > 2.0 * (d - t) * (d - t)):
        raise GeometryError("épaisseur de paroi dans l'angle insuffisante (ro trop grand devant ri)")

    ob = max(0.0, b - 2.0 * ro)
    oh = max(0.0, h - 2.0 * ro)
    outer = (
        ContourBuilder(start=(-b / 2.0 + ro, -h / 2.0), heading_deg=0.0)
        .line(ob, 0.0)                    # face inférieure
        .arc(90.0, ro)
        .line(oh, 90.0)                   # face droite
        .arc(90.0, ro)
        .line(ob, 180.0)                  # face supérieure
        .arc(90.0, ro)
        .line(oh, 270.0)                  # face gauche
        .arc(90.0, ro)
        .close(tolerance=tolerance)
    )
    hi, bi = h - 2.0 * t, b - 2.0 * t
    ib = max(0.0, bi - 2.0 * ri)
    ih = max(0.0, hi - 2.0 * ri)
    hole = (
        ContourBuilder(start=(bi / 2.0 - ri, -hi / 2.0), heading_deg=180.0)
        .line(ib, 180.0)                  # face intérieure inférieure, de droite à gauche
        .arc(-90.0, ri)
        .line(ih, 90.0)                   # face intérieure gauche
        .arc(-90.0, ri)
        .line(ib, 0.0)                    # face intérieure supérieure
        .arc(-90.0, ri)
        .line(ih, 270.0)                  # face intérieure droite
        .arc(-90.0, ri)
        .close(tolerance=tolerance)
    )
    return Section(outer=(outer,), holes=(hole,))


def chs(D: float, t: float) -> Section:
    """Tube circulaire : deux cercles exacts (extérieur trigo, trou horaire)."""
    _require_positive(D=D, t=t)
    if not D - 2.0 * t > 0.0:
        raise GeometryError(f"diamètre intérieur D - 2t = {D - 2.0 * t:g} doit être > 0")
    ro, ri = D / 2.0, D / 2.0 - t
    tolerance = _tolerance(D)
    outer = ContourBuilder(start=(0.0, -ro), heading_deg=0.0).arc(360.0, ro).close(tolerance=tolerance)
    hole = ContourBuilder(start=(0.0, -ri), heading_deg=180.0).arc(-360.0, ri).close(tolerance=tolerance)
    return Section(outer=(outer,), holes=(hole,))


# --------------------------------------------------------------------------- #
# Pleins
# --------------------------------------------------------------------------- #

def flat(b: float, t: float) -> Section:
    """Plat sur chant : largeur b selon z, épaisseur t selon y, coins vifs."""
    _require_positive(b=b, t=t)
    contour = (
        ContourBuilder(start=(-t / 2.0, -b / 2.0), heading_deg=0.0)
        .line(t, 0.0)
        .line(b, 90.0)
        .line(t, 180.0)
        .line(b, 270.0)
        .close(tolerance=_tolerance(b, t))
    )
    return Section(outer=(contour,))


def round_bar(D: float) -> Section:
    """Rond plein : disque exact de diamètre D, centré à l'origine."""
    _require_positive(D=D)
    r = D / 2.0
    contour = ContourBuilder(start=(0.0, -r), heading_deg=0.0).arc(360.0, r).close(tolerance=_tolerance(D))
    return Section(outer=(contour,))


def square_bar(a: float) -> Section:
    """Carré plein de côté a, centré à l'origine, coins vifs."""
    _require_positive(a=a)
    contour = (
        ContourBuilder(start=(-a / 2.0, -a / 2.0), heading_deg=0.0)
        .line(a, 0.0)
        .line(a, 90.0)
        .line(a, 180.0)
        .line(a, 270.0)
        .close(tolerance=_tolerance(a))
    )
    return Section(outer=(contour,))


# --------------------------------------------------------------------------- #
# Profilés T : géométrie non constructible sans données manquantes
# --------------------------------------------------------------------------- #

def t_tapered(h: float, b: float, tw: float, tf: float, r1: float, r2: float,
              slope_pct: float, x_tf: float) -> Section:
    """Profilé T à semelles inclinées (EN 10055) — non constructible en l'état.

    La base ne contient ni l'inclinaison `slope_pct` ni l'abscisse `x_tf` pour
    la série AM-TES : toute reconstruction serait une hypothèse. Cette fonction
    existe pour que l'appel échoue explicitement au lieu de produire une
    géométrie inventée.
    """
    raise GeometryError(
        "géométrie T non constructible : slope_pct et x_tf ne sont pas documentés "
        "pour la série AM-TES (EN 10055 requis) ; aucune valeur n'est inventée"
    )


# --------------------------------------------------------------------------- #
# Dispatcher
# --------------------------------------------------------------------------- #

def _from_i(p: Mapping[str, float]) -> Section:
    return i_section(p["h"], p["b"], p["tw"], p["tf"], p["r"])


def _from_u(p: Mapping[str, float]) -> Section:
    return channel(p["h"], p["b"], p["tw"], p["tf"], p["r"], 0.0, 0.0, 0.0)


def _from_u_tapered(p: Mapping[str, float]) -> Section:
    return channel(p["h"], p["b"], p["tw"], p["tf"], p["r1"], p["r2"], p["slope_pct"], p["x_tf"])


def _from_i_tapered(p: Mapping[str, float]) -> Section:
    return i_tapered(p["h"], p["b"], p["tw"], p["tf"], p["r1"], p["r2"], p["slope_pct"], p["x_tf"])


def _from_l(p: Mapping[str, float]) -> Section:
    return angle(p["h"], p["b"], p["t"], p["r1"], p["r2"])


def _from_l_eq(p: Mapping[str, float]) -> Section:
    return angle(p["b"], p["b"], p["t"], p["r1"], p["r2"])


def _from_rhs(p: Mapping[str, float]) -> Section:
    return rect_hollow(p["b"], p["h"], p["t"], p["ro"], p["ri"])


def _from_shs(p: Mapping[str, float]) -> Section:
    return rect_hollow(p["b"], p["b"], p["t"], p["ro"], p["ri"])


def _from_chs(p: Mapping[str, float]) -> Section:
    return chs(p["D"], p["t"])


def _from_flat(p: Mapping[str, float]) -> Section:
    return flat(p["b"], p["t"])


def _from_round(p: Mapping[str, float]) -> Section:
    return round_bar(p["D"])


def _from_square(p: Mapping[str, float]) -> Section:
    return square_bar(p["a"])


def _from_t(p: Mapping[str, float]) -> Section:
    return t_tapered(p["h"], p["b"], p["tw"], p["tf"], p["r1"], p["r2"], p["slope_pct"], p["x_tf"])


BUILDERS: dict[str, Callable[[Mapping[str, float]], Section]] = {
    "I": _from_i,
    "U": _from_u,
    "U_TAPERED": _from_u_tapered,
    "I_TAPERED": _from_i_tapered,
    "L": _from_l,
    "L_EQ": _from_l_eq,
    "RHS": _from_rhs,
    "SHS": _from_shs,
    "CHS": _from_chs,
    "FLAT": _from_flat,
    "ROUND": _from_round,
    "SQUARE": _from_square,
    "T_TAPERED": _from_t,
}


def build_section(shape_id: str, params: Mapping[str, float]) -> Section:
    """Construit la section d'un identifiant de forme et d'un dictionnaire de dimensions [mm]."""
    try:
        builder = BUILDERS[shape_id]
    except KeyError:
        raise GeometryError(f"forme inconnue : {shape_id!r}") from None
    return builder(params)
