"""Maillage triangulaire d'une section extrudée, et écritures STL / OBJ.

Le maillage est construit sur les boucles tessellées à une tolérance de corde
déclarée. Les chapeaux (bas et haut) sont triangulés par **tranches
horizontales** : entre deux cotes de sommets consécutives, aucune arête ne
commence ni ne finit, les intersections sont donc des segments droits que l'on
apparie par la règle pair-impair. Cette méthode traite les trous sans pont ni
découpe d'oreille, et reste stable sur les formes à congés multiples.

Trois précautions rendent la triangulation **conforme** :

- les cotes séparées de moins de `_LEVEL_TOL` (1e-7 mm) sont regroupées, sans
  quoi deux contours tessellés indépendamment créeraient des tranches
  d'épaisseur quasi nulle ;
- une arête horizontale mitoyenne de deux tranches est découpée aux **mêmes**
  abscisses des deux côtés, sinon une fissure en T apparaît au milieu du
  chapeau ;
- les arêtes de découpe sont arrondies avant comparaison, pour ne pas dupliquer
  un sommet déjà présent et produire un triangle dégénéré.

Les parois sont découpées aux mêmes cotes que les chapeaux, de sorte que chaque
arête du maillage soit partagée par exactement deux triangles : le volume est
fermé au sens topologique, pas seulement visuellement.

Convention : la section est dans le plan (X, Y) avec `X = y`, `Y = z` du repère
de section ; l'extrusion va de `Z = 0` à `Z = length`.
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from pathlib import Path

from app.geometry.contour import GeometryError, Section

from app.exports.curve import ascii_text, section_loops

Point3 = tuple[float, float, float]
Triangle = tuple[int, int, int]

_DECIMALS = 9
_LEVEL_TOL = 1.0e-7
"""Écart maximal entre deux cotes considérées comme identiques (mm)."""


def _key(y: float, z: float, level: int) -> tuple[float, float, int]:
    return (round(y, _DECIMALS), round(z, _DECIMALS), level)


def _cross(origin: Point3, a: Point3, b: Point3) -> Point3:
    ux, uy, uz = a[0] - origin[0], a[1] - origin[1], a[2] - origin[2]
    vx, vy, vz = b[0] - origin[0], b[1] - origin[1], b[2] - origin[2]
    return (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)


@dataclass
class Mesh:
    """Maillage triangulaire fermé, indices dans `vertices`."""

    vertices: list[Point3] = field(default_factory=list)
    triangles: list[Triangle] = field(default_factory=list)

    def add_vertex(self, point: Point3) -> int:
        self.vertices.append(point)
        return len(self.vertices) - 1

    def volume(self) -> float:
        """Volume signé (positif pour des normales sortantes)."""
        total = 0.0
        for i, j, k in self.triangles:
            a, b, c = self.vertices[i], self.vertices[j], self.vertices[k]
            total += (a[0] * (b[1] * c[2] - b[2] * c[1])
                      - a[1] * (b[0] * c[2] - b[2] * c[0])
                      + a[2] * (b[0] * c[1] - b[1] * c[0]))
        return total / 6.0

    def area(self) -> float:
        return math.fsum(0.5 * math.sqrt(sum(c * c for c in _cross(
            self.vertices[i], self.vertices[j], self.vertices[k])))
            for i, j, k in self.triangles)

    def bounds(self) -> tuple[Point3, Point3]:
        xs = [v[0] for v in self.vertices]
        ys = [v[1] for v in self.vertices]
        zs = [v[2] for v in self.vertices]
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def edge_use(self) -> dict[tuple[int, int], int]:
        """Nombre d'utilisations de chaque arête non orientée (2 = étanche)."""
        use: dict[tuple[int, int], int] = {}
        for triangle in self.triangles:
            for a, b in ((triangle[0], triangle[1]), (triangle[1], triangle[2]),
                         (triangle[2], triangle[0])):
                key = (a, b) if a < b else (b, a)
                use[key] = use.get(key, 0) + 1
        return use


def _at_z(p: tuple[float, float], q: tuple[float, float], z: float) -> float:
    """Abscisse du point d'abscisse curviligne connue en cote `z` sur [p, q]."""
    if p[1] == q[1]:
        raise ValueError("arête horizontale")
    return p[0] + (q[0] - p[0]) * (z - p[1]) / (q[1] - p[1])


def _spanning_edges(loops, z0: float, z1: float) -> list[tuple[float, tuple, tuple]]:
    """Arêtes traversant toute la tranche `[z0, z1]`, triées par abscisse médiane.

    Une arête qui commence ou finit à l'intérieur de la tranche ne peut pas
    exister : les cotes des sommets sont toutes des bornes de tranche.
    """
    middle = 0.5 * (z0 + z1)
    spanning = []
    for loop in loops:
        n = len(loop)
        for i in range(n):
            p, q = loop[i], loop[(i + 1) % n]
            if p[1] == q[1]:
                continue
            low, high = (p[1], q[1]) if p[1] < q[1] else (q[1], p[1])
            if low <= z0 and high >= z1:
                spanning.append((_at_z(p, q, middle), p, q))
    spanning.sort(key=lambda item: item[0])
    return spanning


def _subdivide(a: tuple[float, float], b: tuple[float, float],
               cuts: list[float]) -> list[tuple[float, float]]:
    """Chaîne `a → b` enrichie des abscisses de `cuts` strictement intermédiaires.

    Les extrémités sont arrondies avant comparaison : un point de découpe égal à
    une extrémité au-delà de la précision de stockage serait sinon dupliqué et
    produirait des triangles dégénérés.
    """
    a = (round(a[0], _DECIMALS), a[1])
    b = (round(b[0], _DECIMALS), b[1])
    if a[0] > b[0]:
        a, b = b, a
    chain = [a]
    for x in cuts:
        if a[0] < x < b[0] and x != chain[-1][0]:
            chain.append((x, a[1]))
    chain.append(b)
    return chain


def _zipper(bottom: list[tuple[float, float]], top: list[tuple[float, float]]) -> list[
        tuple[tuple[float, float], tuple[float, float], tuple[float, float]]]:
    """Triangles d'un quadrilatère à chaînes horizontales (bas et haut, gauche→droite).

    La couture suit l'abscisse : chaque triangle relie le point le plus à gauche
    disponible en bas ou en haut. Les deux chaînes peuvent avoir des découpages
    différents, ce qui garantit que les arêtes horizontales partagées entre deux
    tranches voisines portent exactement les mêmes sommets.
    """
    triangles = []
    i = j = 0
    while i < len(bottom) - 1 or j < len(top) - 1:
        if j == len(top) - 1 or (i < len(bottom) - 1 and bottom[i + 1][0] <= top[j + 1][0]):
            triangles.append((bottom[i], bottom[i + 1], top[j]))
            i += 1
        else:
            triangles.append((bottom[i], top[j + 1], top[j]))
            j += 1
    return triangles


def _cap_triangles(loops: list[list[tuple[float, float]]], upward: bool) -> list[
        tuple[tuple[float, float], tuple[float, float], tuple[float, float]]]:
    """Triangles d'un chapeau, par tranches entre cotes de sommets.

    Chaque tranche est remplie par la règle pair-impair (balayage horizontal),
    ce qui traite les trous sans pont. Les arêtes horizontales mitoyennes de
    deux tranches sont découpées aux **mêmes** abscisses : la triangulation est
    donc conforme et le maillage reste étanche, sans fissure en T.
    """
    z_values = sorted({round(p[1], _DECIMALS) for loop in loops for p in loop})
    quads = []
    for z0, z1 in zip(z_values, z_values[1:]):
        if z1 == z0:
            continue
        spanning = _spanning_edges(loops, z0, z1)
        if len(spanning) % 2:
            raise GeometryError(
                f"triangulation impossible : {len(spanning)} intersections à la cote "
                f"{z0:g}–{z1:g} (section non simple)")
        for k in range(0, len(spanning), 2):
            (_, pa, qa), (_, pb, qb) = spanning[k], spanning[k + 1]
            quads.append((
                (_at_z(pa, qa, z0), z0),
                (_at_z(pb, qb, z0), z0),
                (_at_z(pb, qb, z1), z1),
                (_at_z(pa, qa, z1), z1),
            ))

    level_x: dict[float, list[float]] = {}
    for quad in quads:
        for x, z in quad:
            bucket = level_x.setdefault(z, [])
            value = round(x, _DECIMALS)
            if value not in bucket:
                bucket.append(value)
    for bucket in level_x.values():
        bucket.sort()

    triangles = []
    for a0, b0, b1, a1 in quads:
        bottom = _subdivide(a0, b0, level_x[a0[1]])
        top = _subdivide(a1, b1, level_x[a1[1]])
        for tri in _zipper(bottom, top):
            area2 = ((tri[1][0] - tri[0][0]) * (tri[2][1] - tri[0][1])
                     - (tri[2][0] - tri[0][0]) * (tri[1][1] - tri[0][1]))
            if abs(area2) <= 1e-18:
                continue
            if (area2 > 0.0) != upward:
                tri = (tri[0], tri[2], tri[1])
            triangles.append(tri)
    return triangles


def _snap_levels(loops: list[list[tuple[float, float]]]) -> list[float]:
    """Cotes de la section, regroupées à `_LEVEL_TOL` près.

    Deux contours tessellés indépendamment (cercle extérieur et intérieur, par
    exemple) peuvent produire des cotes séparées de quelques 1e-9 mm. Sans
    regroupement, la tranche correspondante serait un sliver d'épaisseur nulle
    que le chapeau écarte mais que la paroi conserve : le maillage ne serait plus
    étanche. Le regroupement déplace les sommets de moins de `_LEVEL_TOL`, très
    en dessous de la tolérance de corde.
    """
    values = sorted({p[1] for loop in loops for p in loop})
    clusters: list[list[float]] = []
    for value in values:
        if clusters and value - clusters[-1][-1] <= _LEVEL_TOL:
            clusters[-1].append(value)
        else:
            clusters.append([value])
    mapping = {value: group[0] for group in clusters for value in group}
    for loop in loops:
        for i, (x, z) in enumerate(loop):
            loop[i] = (x, mapping[z])
    return [group[0] for group in clusters]


def build_mesh(section: Section, length: float, tolerance: float) -> Mesh:
    """Maillage fermé de la section extrudée sur `length` mm."""
    if length <= 0.0:
        raise ValueError(f"longueur d'extrusion > 0 requise (reçue {length})")
    loops = [[(round(x, _DECIMALS), round(y, _DECIMALS)) for x, y in loop]
             for loop in section_loops(section, tolerance)]
    z_values = _snap_levels(loops)

    mesh = Mesh()
    index: dict[tuple[float, float, int], int] = {}

    def vertex(y: float, z: float, level: int) -> int:
        key = _key(y, z, level)
        try:
            return index[key]
        except KeyError:
            idx = mesh.add_vertex((key[0], key[1], 0.0 if level == 0 else length))
            index[key] = idx
            return idx

    for upward, level in ((False, 0), (True, 1)):
        for tri in _cap_triangles(loops, upward):
            mesh.triangles.append(tuple(vertex(p[0], p[1], level) for p in tri))

    for loop in loops:
        n = len(loop)
        for i in range(n):
            p, q = loop[i], loop[(i + 1) % n]
            if p[1] == q[1]:
                spans = [(p[1], q[1])]
            else:
                low, high = sorted((p[1], q[1]))
                cuts = [low] + [z for z in z_values if low < z < high] + [high]
                if p[1] > q[1]:
                    cuts.reverse()
                spans = list(zip(cuts, cuts[1:]))
            for za, zb in spans:
                if za == zb:
                    xa, xb = p[0], q[0]
                else:
                    xa, xb = _at_z(p, q, za), _at_z(p, q, zb)
                p0 = vertex(xa, za, 0)
                q0 = vertex(xb, zb, 0)
                q1 = vertex(xb, zb, 1)
                p1 = vertex(xa, za, 1)
                for triangle in ((p0, q0, q1), (p0, q1, p1)):
                    if len(set(triangle)) == 3:
                        mesh.triangles.append(triangle)

    if mesh.volume() < 0.0:
        mesh.triangles = [(a, c, b) for a, b, c in mesh.triangles]
    return mesh


def normal(a: Point3, b: Point3, c: Point3) -> Point3:
    n = _cross(a, b, c)
    norm = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2])
    if norm == 0.0:
        return (0.0, 0.0, 0.0)
    return (n[0] / norm, n[1] / norm, n[2] / norm)


def write_stl(mesh: Mesh, path: str | Path, *, name: str = "", binary: bool = True) -> Path:
    """Écrit le maillage en STL binaire (défaut) ou ASCII."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if binary:
        header = ascii_text(name or "SteelProfile").encode("ascii", "replace")[:80].ljust(80, b" ")
        with open(path, "wb") as fh:
            fh.write(header)
            fh.write(struct.pack("<I", len(mesh.triangles)))
            for i, j, k in mesh.triangles:
                a, b, c = mesh.vertices[i], mesh.vertices[j], mesh.vertices[k]
                fh.write(struct.pack("<3f", *normal(a, b, c)))
                fh.write(struct.pack("<9f", *a, *b, *c))
                fh.write(struct.pack("<H", 0))
        return path

    with open(path, "w", encoding="ascii", newline="\n") as fh:
        label = ascii_text(name or "SteelProfile")
        fh.write(f"solid {label}\n")
        for i, j, k in mesh.triangles:
            a, b, c = mesh.vertices[i], mesh.vertices[j], mesh.vertices[k]
            fh.write("  facet normal %.9e %.9e %.9e\n" % normal(a, b, c))
            fh.write("    outer loop\n")
            for vertex in (a, b, c):
                fh.write("      vertex %.9e %.9e %.9e\n" % vertex)
            fh.write("    endloop\n  endfacet\n")
        fh.write(f"endsolid {label}\n")
    return path


def write_obj(mesh: Mesh, path: str | Path, *, name: str = "SteelProfile") -> Path:
    """Écrit le maillage en OBJ (sommets partagés, normales par facette)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="ascii", newline="\n") as fh:
        label = ascii_text(name or "SteelProfile")
        fh.write("# SteelProfile - maillage triangulaire, unites mm\n")
        fh.write(f"o {label}\n")
        for x, y, z in mesh.vertices:
            fh.write(f"v {x:.9f} {y:.9f} {z:.9f}\n")
        normals = []
        for i, j, k in mesh.triangles:
            normals.append(normal(mesh.vertices[i], mesh.vertices[j], mesh.vertices[k]))
        for nx, ny, nz in normals:
            fh.write(f"vn {nx:.9f} {ny:.9f} {nz:.9f}\n")
        for t, (i, j, k) in enumerate(mesh.triangles, start=1):
            fh.write(f"f {i + 1}//{t} {j + 1}//{t} {k + 1}//{t}\n")
    return path
