"""Export STEP AP214 en B-REP exact (surfaces planes et cylindriques).

Le solide est l'extrusion de la section sur `length` mm selon +Z. Aucun
facettage : les faces latérales issues d'un segment sont des plans, celles
issues d'un arc sont des cylindres de rayon exact, et les arêtes sont des
droites ou des cercles. Les chapeaux sont des plans dont les boucles sont
constituées des mêmes arêtes : chaque arête est partagée par exactement deux
faces, avec des orientations opposées (coque fermée).

Topologie produite, pour chaque tronçon `i` d'un contour de `n` tronçons :

- arête basse `Eb_i` (`J_i → J_{i+1}`, z = 0) et haute `Et_i` (z = length) ;
- arête verticale `Ev_i` (`J_i` bas → `J_i` haut) ;
- face latérale : `Eb_i` + `Ev_{i+1}` + `Et_i` inversée + `Ev_i` inversée ;
- chapeau bas : boucles inversées (normale −Z) ; chapeau haut : boucles directes.

Repère : `X = y`, `Y = z` du repère de section, extrusion selon +Z, unités mm.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.geometry.contour import GeometryError, Section

from app.exports.curve import Segment, contour_segments

SCHEMA = "AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }"


def _number(value: float) -> str:
    if value == 0.0:
        return "0."
    text = f"{value:.12g}"
    if "e" in text or "E" in text:
        mantissa, exponent = text.lower().split("e")
        text = f"{mantissa}E{int(exponent)}"
    if "." not in text and "E" not in text:
        text += "."
    return text


def _string(value: str) -> str:
    """Chaîne STEP : apostrophes doublées, Unicode échappé en \\X2\\…\\X0\\."""
    out: list[str] = []
    i = 0
    while i < len(value):
        char = value[i]
        if char == "'":
            out.append("''")
        elif ord(char) < 128:
            out.append(char)
        else:
            run = []
            while i < len(value) and ord(value[i]) >= 128:
                run.append(f"{ord(value[i]):04X}")
                i += 1
            out.append("\\X2\\" + "".join(run) + "\\X0\\")
            continue
        i += 1
    return "".join(out)


class _Step:
    """Accumulateur d'entités STEP numérotées."""

    def __init__(self) -> None:
        self.entities: list[str] = []

    def add(self, body: str) -> int:
        self.entities.append(body)
        return len(self.entities)

    # --- géométrie de base ------------------------------------------------
    def point(self, x: float, y: float, z: float) -> int:
        return self.add(f"CARTESIAN_POINT('',({_number(x)},{_number(y)},{_number(z)}))")

    def direction(self, x: float, y: float, z: float) -> int:
        norm = math.sqrt(x * x + y * y + z * z)
        if norm == 0.0:
            raise GeometryError("direction nulle")
        return self.add(
            f"DIRECTION('',({_number(x / norm)},{_number(y / norm)},{_number(z / norm)}))")

    def axis2(self, origin: int, axis: int, ref: int) -> int:
        return self.add(f"AXIS2_PLACEMENT_3D('',#{origin},#{axis},#{ref})")

    def vertex(self, x: float, y: float, z: float) -> int:
        return self.add(f"VERTEX_POINT('',#{self.point(x, y, z)})")

    def line(self, start: tuple[float, float], end: tuple[float, float],
             z: float) -> int:
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length == 0.0:
            raise GeometryError("arête de longueur nulle")
        origin = self.point(start[0], start[1], z)
        vector = self.add(
            f"VECTOR('',#{self.direction(dx, dy, 0.0)},{_number(length)})")
        return self.add(f"LINE('',#{origin},#{vector})")

    def vertical(self, start: tuple[float, float], height: float) -> int:
        origin = self.point(start[0], start[1], 0.0)
        vector = self.add(f"VECTOR('',#{self.direction(0.0, 0.0, 1.0)},{_number(height)})")
        return self.add(f"LINE('',#{origin},#{vector})")

    def circle(self, center: tuple[float, float], radius: float, z: float) -> int:
        origin = self.point(center[0], center[1], z)
        axis = self.direction(0.0, 0.0, 1.0)
        ref = self.direction(1.0, 0.0, 0.0)
        return self.add(
            f"CIRCLE('',#{self.axis2(origin, axis, ref)},{_number(radius)})")

    def edge(self, v1: int, v2: int, curve: int, same_sense: bool) -> int:
        flag = ".T." if same_sense else ".F."
        return self.add(f"EDGE_CURVE('',#{v1},#{v2},#{curve},{flag})")

    def oriented_edge(self, edge: int, forward: bool) -> int:
        flag = ".T." if forward else ".F."
        return self.add(f"ORIENTED_EDGE('',*,*,#{edge},{flag})")

    def loop(self, edges: list[int]) -> int:
        refs = ",".join(f"#{edge}" for edge in edges)
        return self.add(f"EDGE_LOOP('',({refs}))")

    def bound(self, loop: int, *, outer: bool) -> int:
        kind = "FACE_OUTER_BOUND" if outer else "FACE_BOUND"
        return self.add(f"{kind}('',#{loop},.T.)")

    def plane(self, origin: tuple[float, float, float],
              axis: tuple[float, float, float], ref: tuple[float, float, float]) -> int:
        return self.add(f"PLANE('',#{self.axis2(self.point(*origin),
                                              self.direction(*axis),
                                              self.direction(*ref))})")

    def cylinder(self, center: tuple[float, float], radius: float) -> int:
        placement = self.axis2(self.point(center[0], center[1], 0.0),
                               self.direction(0.0, 0.0, 1.0),
                               self.direction(1.0, 0.0, 0.0))
        return self.add(f"CYLINDRICAL_SURFACE('',#{placement},{_number(radius)})")

    def face(self, bounds: list[int], surface: int, same_sense: bool = True) -> int:
        flag = ".T." if same_sense else ".F."
        refs = ",".join(f"#{bound}" for bound in bounds)
        return self.add(f"ADVANCED_FACE('',({refs}),#{surface},{flag})")

    def shell(self, faces: list[int]) -> int:
        refs = ",".join(f"#{face}" for face in faces)
        return self.add(f"CLOSED_SHELL('',({refs}))")

    def solid(self, shell: int) -> int:
        return self.add(f"MANIFOLD_SOLID_BREP('',#{shell})")


@dataclass(frozen=True)
class _Loop:
    bottom: int
    top: int
    is_hole: bool


def _same_sense(segment: Segment) -> bool:
    return segment.sweep > 0.0


def step_text(section: Section, length: float, *, name: str = "SteelProfile",
              timestamp: str | None = None) -> str:
    """Texte STEP AP214 du solide extrudé (B-REP exact)."""
    if length <= 0.0:
        raise ValueError(f"longueur d'extrusion > 0 requise (reçue {length})")
    if len(section.outer) != 1:
        raise GeometryError(
            "l'export STEP suppose un seul contour extérieur "
            f"(reçu {len(section.outer)})")

    step = _Step()
    faces: list[int] = []
    loops: list[_Loop] = []

    for contour, is_hole in ([(c, False) for c in section.outer]
                             + [(c, True) for c in section.holes]):
        segments = contour_segments(contour)
        n = len(segments)
        joints = [segment.start for segment in segments]

        bottom_vertices = [step.vertex(x, y, 0.0) for x, y in joints]
        top_vertices = [step.vertex(x, y, length) for x, y in joints]
        bottom_edges: list[int] = []
        top_edges: list[int] = []
        for i, segment in enumerate(segments):
            j = (i + 1) % n
            if segment.is_arc:
                curve_bottom = step.circle(segment.center, segment.radius, 0.0)
                curve_top = step.circle(segment.center, segment.radius, length)
            else:
                curve_bottom = step.line(segment.start, segment.end, 0.0)
                curve_top = step.line(segment.start, segment.end, length)
            bottom_edges.append(step.edge(bottom_vertices[i], bottom_vertices[j],
                                          curve_bottom, _same_sense(segment)))
            top_edges.append(step.edge(top_vertices[i], top_vertices[j],
                                       curve_top, _same_sense(segment)))
        vertical = [step.edge(bottom_vertices[i], top_vertices[i],
                              step.vertical(joints[i], length), True) for i in range(n)]

        loops.append(_Loop(
            bottom=step.loop([step.oriented_edge(bottom_edges[i], False)
                              for i in reversed(range(n))]),
            top=step.loop([step.oriented_edge(top_edges[i], True) for i in range(n)]),
            is_hole=is_hole,
        ))

        for i, segment in enumerate(segments):
            j = (i + 1) % n
            face_loop = step.loop([
                step.oriented_edge(bottom_edges[i], True),
                step.oriented_edge(vertical[j], True),
                step.oriented_edge(top_edges[i], False),
                step.oriented_edge(vertical[i], False),
            ])
            if segment.is_arc:
                surface = step.cylinder(segment.center, segment.radius)
                same_sense = segment.sweep > 0.0
            else:
                dx = segment.end[0] - segment.start[0]
                dy = segment.end[1] - segment.start[1]
                surface = step.plane(
                    (segment.start[0], segment.start[1], 0.0),
                    (dy, -dx, 0.0),
                    (dx, dy, 0.0),
                )
                same_sense = True
            faces.append(step.face([step.bound(face_loop, outer=True)], surface, same_sense))

    for soup in ("bottom", "top"):
        bounds = [
            step.bound(getattr(item, soup), outer=not item.is_hole)
            for item in loops
        ]
        if soup == "bottom":
            surface = step.plane((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
            faces.append(step.face(bounds, surface, same_sense=False))
        else:
            surface = step.plane((0.0, 0.0, length), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
            faces.append(step.face(bounds, surface, same_sense=True))

    shell = step.shell(faces)
    solid = step.solid(shell)

    # --- structure produit et unités -------------------------------------
    context = step.add("APPLICATION_CONTEXT('core data for automotive mechanical design processes')")
    step.add(f"APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',"
             f"2000,#{context})")
    product_context = step.add(f"PRODUCT_CONTEXT('',#{context},'mechanical')")
    product = step.add(f"PRODUCT('{_string(name)}','{_string(name)}','',(#{product_context}))")
    formation = step.add(f"PRODUCT_DEFINITION_FORMATION('','',#{product})")
    definition_context = step.add(f"PRODUCT_DEFINITION_CONTEXT('part definition',#{context},"
                                  f"'design')")
    definition = step.add(f"PRODUCT_DEFINITION('design','',#{formation},#{definition_context})")
    shape = step.add(f"PRODUCT_DEFINITION_SHAPE('','',#{definition})")
    length_unit = step.add("(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.))")
    angle_unit = step.add("(NAMED_UNIT(*)PLANE_ANGLE_UNIT()SI_UNIT($,.RADIAN.))")
    solid_angle_unit = step.add("(NAMED_UNIT(*)SI_UNIT($,.STERADIAN.)SOLID_ANGLE_UNIT())")
    uncertainty = step.add(
        f"UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-6),#{length_unit},"
        f"'distance_accuracy_value','confusion accuracy')")
    rep_context = step.add(
        f"(GEOMETRIC_REPRESENTATION_CONTEXT(3)"
        f"GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#{uncertainty}))"
        f"GLOBAL_UNIT_ASSIGNED_CONTEXT((#{length_unit},#{angle_unit},#{solid_angle_unit}))"
        f"REPRESENTATION_CONTEXT('',''))")
    placement = step.add(
        f"AXIS2_PLACEMENT_3D('',#{step.point(0.0, 0.0, 0.0)},"
        f"#{step.direction(0.0, 0.0, 1.0)},#{step.direction(1.0, 0.0, 0.0)})")
    representation = step.add(
        f"ADVANCED_BREP_SHAPE_REPRESENTATION('{_string(name)}',(#{solid},#{placement}),"
        f"#{rep_context})")
    step.add(f"SHAPE_DEFINITION_REPRESENTATION(#{shape},#{representation})")

    if timestamp is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    header = (
        "ISO-10303-21;\n"
        "HEADER;\n"
        "FILE_DESCRIPTION(('SteelProfile exact B-REP'),'2;1');\n"
        f"FILE_NAME('{_string(name)}.step','{timestamp}',('SteelProfile'),(''),"
        f"'SteelProfile 0.1','SteelProfile','');\n"
        f"FILE_SCHEMA(('{SCHEMA}'));\n"
        "ENDSEC;\n"
        "DATA;\n"
    )
    body = "".join(f"#{i}={entity};\n" for i, entity in enumerate(step.entities, start=1))
    return header + body + "ENDSEC;\nEND-ISO-10303-21;\n"


def write_step(section: Section, path: str | Path, length: float, *,
               name: str = "SteelProfile", timestamp: str | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(step_text(section, length, name=name, timestamp=timestamp),
                    encoding="ascii", newline="\n")
    return path
