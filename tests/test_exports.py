"""Tests des exports : découpage, étanchéité des maillages, structure des fichiers.

Les tests d'export utilisent des sections synthétiques construites directement
par `app.geometry.shapes`, sauf ceux de la ligne de commande qui ont besoin de la
base (`data/profiles.db`) et sont ignorés si elle est absente.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.exports.curve import ascii_text, contour_segments, tessellate_contour  # noqa: E402
from app.exports.dxf import write_dxf  # noqa: E402
from app.exports.glb import glb_bytes  # noqa: E402
from app.exports.mesh import build_mesh, write_obj, write_stl  # noqa: E402
from app.exports.step import step_text, write_step  # noqa: E402
from app.geometry.build import DEFAULT_DB  # noqa: E402
from app.geometry.contour import GeometryError  # noqa: E402
from app.geometry.properties import section_properties  # noqa: E402
from app.geometry.shapes import (  # noqa: E402
    angle,
    channel,
    chs,
    flat,
    i_section,
    rect_hollow,
    round_bar,
    square_bar,
)

LENGTH = 1000.0
TOLERANCE = 0.05


def sections() -> dict:
    """Une section représentative de chaque famille constructible."""
    return {
        "i": i_section(200.0, 100.0, 10.0, 10.0, 12.0),
        "h": i_section(300.0, 300.0, 12.0, 19.0, 27.0),
        "u": channel(200.0, 75.0, 8.5, 11.5, 7.5, 3.0, 0.0, 0.0),
        "l": angle(100.0, 50.0, 8.0, 10.0, 5.0),
        "rhs": rect_hollow(50.0, 100.0, 4.0, 7.5, 4.0),
        "shs": rect_hollow(100.0, 100.0, 5.0, 7.5, 5.0),
        "chs": chs(168.3, 6.0),
        "flat": flat(160.0, 10.0),
        "round": round_bar(60.0),
        "square": square_bar(40.0),
    }


def dxf_entities(text: str) -> list[tuple[int, str]]:
    lines = text.splitlines()
    assert len(lines) % 2 == 0, "DXF : nombre impair de lignes"
    return [(int(lines[i]), lines[i + 1]) for i in range(0, len(lines), 2)]


def step_entities(text: str) -> dict[int, str]:
    body = text.split("DATA;", 1)[1].split("ENDSEC;", 1)[0]
    entities = {}
    for match in re.finditer(r"#(\d+)=(.+?);\n", body):
        entities[int(match.group(1))] = match.group(2)
    return entities


class CurveTests(unittest.TestCase):
    def test_sweeps_are_bounded(self) -> None:
        for contour in chs(168.3, 6.0).contours:
            for segment in contour_segments(contour):
                self.assertLessEqual(abs(segment.sweep), math.pi / 2.0 + 1e-12)
                if segment.is_arc:
                    self.assertLessEqual(abs(segment.bulge()), math.tan(math.pi / 8.0) + 1e-12)

    def test_full_circle_is_split(self) -> None:
        outer = contour_segments(chs(100.0, 5.0).contours[0])
        total = sum(segment.sweep for segment in outer)
        self.assertAlmostEqual(total, 2.0 * math.pi, places=12)
        self.assertGreaterEqual(len(outer), 4)

    def test_segments_are_chained(self) -> None:
        for contour in chs(168.3, 6.0).contours:
            segments = contour_segments(contour)
            for previous, following in zip(segments, segments[1:]):
                self.assertEqual(previous.end, following.start)
            self.assertEqual(segments[-1].end, segments[0].start)

    def test_tessellation_stays_on_the_circles(self) -> None:
        section = chs(100.0, 5.0)
        loops = [tessellate_contour(contour, TOLERANCE) for contour in section.contours]
        radii = (50.0, 45.0)
        for loop, radius in zip(loops, radii):
            for x, y in loop:
                self.assertAlmostEqual(math.hypot(x, y), radius, places=9)

    def test_tessellation_chord_error(self) -> None:
        section = chs(100.0, 5.0)
        loop = tessellate_contour(section.contours[0], TOLERANCE)
        for start, end in zip(loop, loop[1:]):
            chord = math.dist(start, end)
            sagitta = 50.0 - math.sqrt(50.0**2 - (chord / 2.0) ** 2)
            self.assertLessEqual(sagitta, TOLERANCE + 1e-12)

    def test_zero_tolerance_refused(self) -> None:
        with self.assertRaises(ValueError):
            tessellate_contour(chs(100.0, 5.0).contours[0], 0.0)

    def test_ascii_text(self) -> None:
        self.assertEqual(ascii_text("Carré — Té"), "Carre - Te")
        self.assertTrue(ascii_text("Profilé 100x50").isascii())


class MeshTests(unittest.TestCase):
    def test_watertight(self) -> None:
        for name, section in sections().items():
            with self.subTest(name=name):
                mesh = build_mesh(section, LENGTH, TOLERANCE)
                odd = {edge: uses for edge, uses in mesh.edge_use().items() if uses != 2}
                self.assertEqual(odd, {})

    def test_watertight_at_fine_tolerance(self) -> None:
        for name in ("i", "rhs", "chs", "l"):
            with self.subTest(name=name):
                mesh = build_mesh(sections()[name], LENGTH, 0.01)
                self.assertTrue(all(uses == 2 for uses in mesh.edge_use().values()))

    def test_volume_matches_area(self) -> None:
        for name, section in sections().items():
            with self.subTest(name=name):
                volume = build_mesh(section, LENGTH, TOLERANCE).volume()
                expected = section_properties(section).A * LENGTH
                self.assertGreater(volume, 0.0)
                self.assertLess(abs(volume - expected) / expected, 5e-3)

    def test_sharp_shape_volume_is_exact(self) -> None:
        section = flat(160.0, 10.0)
        volume = build_mesh(section, LENGTH, TOLERANCE).volume()
        expected = 160.0 * 10.0 * LENGTH
        self.assertAlmostEqual(volume / expected, 1.0, places=12)

    def test_finer_tolerance_improves_volume(self) -> None:
        section = chs(168.3, 6.0)
        expected = section_properties(section).A * LENGTH
        coarse = abs(build_mesh(section, LENGTH, 0.05).volume() - expected)
        fine = abs(build_mesh(section, LENGTH, 0.01).volume() - expected)
        self.assertLess(fine, coarse)

    def test_bounds(self) -> None:
        section = flat(160.0, 10.0)
        mesh = build_mesh(section, LENGTH, TOLERANCE)
        low, high = mesh.bounds()
        y_min, y_max, z_min, z_max = section.bounds()
        self.assertAlmostEqual(low[0], y_min, places=9)
        self.assertAlmostEqual(low[1], z_min, places=9)
        self.assertAlmostEqual(high[0], y_max, places=9)
        self.assertAlmostEqual(high[1], z_max, places=9)
        self.assertEqual(low[2], 0.0)
        self.assertEqual(high[2], LENGTH)

    def test_no_degenerate_triangles(self) -> None:
        for name, section in sections().items():
            mesh = build_mesh(section, LENGTH, TOLERANCE)
            for i, j, k in mesh.triangles:
                self.assertEqual(len({i, j, k}), 3, name)
                a, b, c = mesh.vertices[i], mesh.vertices[j], mesh.vertices[k]
                u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]]
                v = [c[0] - a[0], c[1] - a[1], c[2] - a[2]]
                cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
                         u[0] * v[1] - u[1] * v[0])
                self.assertGreater(math.sqrt(sum(c * c for c in cross)), 1e-12)

    def test_bad_length_refused(self) -> None:
        with self.assertRaises(ValueError):
            build_mesh(flat(10.0, 10.0), 0.0, TOLERANCE)


class StlObjTests(unittest.TestCase):
    def test_binary_size_and_count(self) -> None:
        section = sections()["i"]
        mesh = build_mesh(section, LENGTH, TOLERANCE)
        with tempfile.TemporaryDirectory() as tmp:
            path = write_stl(mesh, Path(tmp) / "i.stl", name="IPE 200", binary=True)
            data = path.read_bytes()
            count = struct.unpack("<I", data[80:84])[0]
            self.assertEqual(count, len(mesh.triangles))
            self.assertEqual(len(data), 84 + 50 * count)
            self.assertEqual(data[:6], b"IPE 20")
            self.assertEqual(data[80:], struct.pack("<I", count) + data[84:])

    def test_ascii(self) -> None:
        mesh = build_mesh(sections()["l"], LENGTH, TOLERANCE)
        with tempfile.TemporaryDirectory() as tmp:
            path = write_stl(mesh, Path(tmp) / "l.stl", name="L 100x50x8", binary=False)
            text = path.read_text(encoding="ascii")
            self.assertTrue(text.startswith("solid L 100x50x8\n"))
            self.assertEqual(text.count("facet normal"), len(mesh.triangles))
            self.assertTrue(text.endswith("endsolid L 100x50x8\n"))

    def test_obj(self) -> None:
        mesh = build_mesh(sections()["u"], LENGTH, TOLERANCE)
        with tempfile.TemporaryDirectory() as tmp:
            path = write_obj(mesh, Path(tmp) / "u.obj", name="UPN 200")
            lines = path.read_text(encoding="ascii").splitlines()
            vertices = [line for line in lines if line.startswith("v ")]
            faces = [line for line in lines if line.startswith("f ")]
            self.assertEqual(len(vertices), len(mesh.vertices))
            self.assertEqual(len(faces), len(mesh.triangles))
            for line in faces:
                for token in line.split()[1:]:
                    index = int(token.split("//")[0])
                    self.assertGreaterEqual(index, 1)
                    self.assertLessEqual(index, len(mesh.vertices))


class DxfTests(unittest.TestCase):
    def _write(self, section, name="test"):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = write_dxf(section, Path(tmp.name) / "section.dxf", name=name)
        return path.read_text(encoding="ascii")

    def test_structure(self) -> None:
        text = self._write(sections()["chs"], name="CHS 168.3x6")
        pairs = dxf_entities(text)
        self.assertEqual(pairs[0][0], 999)
        self.assertEqual(pairs[-1], (0, "EOF"))
        types = [value for code, value in pairs if code == 0]
        polylines = types.count("POLYLINE")
        self.assertEqual(polylines, 2)
        self.assertEqual(types.count("VERTEX"), sum(
            len(contour_segments(contour)) for contour in sections()["chs"].contours))
        self.assertEqual(types.count("SEQEND"), polylines)
        self.assertEqual(text.count("ENTITIES"), 1)
        self.assertTrue(text.isascii())
        self.assertIn("$INSUNITS", text)

    def test_bulges(self) -> None:
        text = self._write(sections()["chs"])
        pairs = dxf_entities(text)
        bulges = [float(value) for code, value in pairs if code == 42]
        self.assertTrue(bulges)
        self.assertTrue(all(math.isfinite(value) for value in bulges))
        self.assertTrue(all(abs(value) <= math.tan(math.pi / 8.0) + 1e-12 for value in bulges))
        self.assertTrue(any(abs(value) > 0.1 for value in bulges))

    def test_layers_and_extents(self) -> None:
        section = sections()["rhs"]
        text = self._write(section, name="RHS 100x50x4")
        pairs = dxf_entities(text)
        layers = {value for code, value in pairs if code == 8}
        self.assertEqual(layers, {"PROFILE", "HOLES"})
        self.assertIn("$EXTMIN", text)
        self.assertIn("$EXTMAX", text)
        self.assertIn("$INSBASE", text)
        self.assertIn("mm", text)


class GlbTests(unittest.TestCase):
    def test_header_and_chunks(self) -> None:
        mesh = build_mesh(sections()["shs"], LENGTH, TOLERANCE)
        data = glb_bytes(mesh, name="SHS 100x100x5")
        magic, version, total = struct.unpack("<4sII", data[:12])
        self.assertEqual(magic, b"glTF")
        self.assertEqual(version, 2)
        self.assertEqual(total, len(data))

        json_length, json_type = struct.unpack("<II", data[12:20])
        self.assertEqual(json_type, 0x4E4F534A)
        document = json.loads(data[20:20 + json_length].decode("utf-8"))
        self.assertEqual(document["asset"]["version"], "2.0")
        self.assertEqual(document["extras"]["units"], "mm")
        self.assertEqual(document["extras"]["triangles"], len(mesh.triangles))
        self.assertEqual(document["accessors"][0]["count"], 3 * len(mesh.triangles))

        offset = 20 + json_length
        bin_length, bin_type = struct.unpack("<II", data[offset:offset + 8])
        self.assertEqual(bin_type, 0x004E4942)
        self.assertEqual(offset + 8, total - bin_length)
        self.assertEqual(document["buffers"][0]["byteLength"], bin_length)
        self.assertEqual(bin_length % 4, 0)


class StepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.section = sections()["i"]
        cls.text = step_text(cls.section, LENGTH, name="IPE 200", timestamp="2026-01-01T00:00:00Z")
        cls.entities = step_entities(cls.text)

    def test_header(self) -> None:
        self.assertTrue(self.text.startswith("ISO-10303-21;\nHEADER;\n"))
        self.assertIn("FILE_SCHEMA(('AUTOMOTIVE_DESIGN", self.text)
        self.assertIn("FILE_NAME('IPE 200.step','2026-01-01T00:00:00Z'", self.text)
        self.assertTrue(self.text.rstrip().endswith("END-ISO-10303-21;"))
        self.assertTrue(self.text.isascii())

    def test_product_and_units(self) -> None:
        types = " ".join(self.entities.values())
        self.assertIn("MANIFOLD_SOLID_BREP", types)
        self.assertIn("CLOSED_SHELL", types)
        self.assertIn("ADVANCED_BREP_SHAPE_REPRESENTATION", types)
        self.assertIn("SI_UNIT(.MILLI.,.METRE.)", types)
        self.assertIn("SHAPE_DEFINITION_REPRESENTATION", types)
        self.assertIn("PRODUCT('IPE 200'", types)

    def test_no_bspline(self) -> None:
        self.assertNotIn("B_SPLINE", self.text)
        self.assertNotIn("POLY_LOOP", self.text)

    def test_references_are_defined(self) -> None:
        referenced = {int(value) for value in re.findall(r"#(\d+)", self.text)}
        self.assertEqual(referenced, set(self.entities))

    def test_edges_used_twice_with_opposite_sense(self) -> None:
        oriented = {}
        for number, body in self.entities.items():
            match = re.match(r"ORIENTED_EDGE\('',\*,\*,#(\d+),\.([TF])\.\)$", body)
            if match:
                oriented.setdefault(int(match.group(1)), []).append(match.group(2))
        edges = {number for number, body in self.entities.items()
                 if body.startswith("EDGE_CURVE(")}
        self.assertTrue(edges)
        for edge in edges:
            flags = oriented.get(edge, [])
            self.assertEqual(len(flags), 2, f"arête #{edge} utilisée {len(flags)} fois")
            self.assertEqual(sorted(flags), ["F", "T"], f"arête #{edge} mal orientée")

    def test_face_count(self) -> None:
        segments = sum(len(contour_segments(contour)) for contour in self.section.contours)
        faces = [body for body in self.entities.values() if body.startswith("ADVANCED_FACE(")]
        self.assertEqual(len(faces), segments + 2)

    def test_cylinders_and_planes(self) -> None:
        types = " ".join(self.entities.values())
        self.assertIn("CYLINDRICAL_SURFACE", types)
        self.assertIn("PLANE(", types)
        self.assertIn("CIRCLE(", types)
        self.assertIn("LINE(", types)

    def test_unicode_name_escaped(self) -> None:
        text = step_text(sections()["flat"], LENGTH, name="Té 20x20x3",
                         timestamp="2026-01-01T00:00:00Z")
        self.assertIn("\\X2\\00E9\\X0\\", text)
        self.assertTrue(text.isascii())

    def test_file_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_step(self.section, Path(tmp) / "i.step", LENGTH, name="IPE 200",
                              timestamp="2026-01-01T00:00:00Z")
            self.assertEqual(path.read_text(encoding="ascii"), self.text)

    def test_several_contours_refused(self) -> None:
        section = rect_hollow(100.0, 100.0, 5.0, 7.5, 5.0)
        text = step_text(section, LENGTH, name="SHS", timestamp="2026-01-01T00:00:00Z")
        # Chaque chapeau porte la boucle intérieure comme FACE_BOUND, pas comme
        # bord extérieur : deux chapeaux, deux trous liés.
        self.assertEqual(text.count("FACE_BOUND"), 2)
        self.assertIn("FACE_OUTER_BOUND", text)


@unittest.skipUnless(DEFAULT_DB.exists(), "data/profiles.db absent")
class CliTests(unittest.TestCase):
    def test_export_and_manifest(self) -> None:
        from app.exports.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            code = main(["--profile", "IPE/IPE 200", "--out", str(out)])
            self.assertEqual(code, 0)
            for suffix in ("dxf", "step", "stl", "obj", "glb"):
                path = out / f"IPE-IPE-200.{suffix}"
                self.assertTrue(path.exists(), suffix)
                self.assertGreater(path.stat().st_size, 0)
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["profiles"]), 1)
            entry = manifest["profiles"][0]
            self.assertEqual(entry["profile_id"], "IPE/IPE 200")
            self.assertEqual(entry["length_mm"], 1000.0)
            self.assertFalse(entry["verified"])
            self.assertEqual(set(entry["files"]), {"dxf", "step", "stl", "obj", "glb"})
            for fmt, name in entry["files"].items():
                digest = hashlib.sha256((out / name).read_bytes()).hexdigest()
                self.assertEqual(entry["sha256"][fmt], digest)

    def test_selected_formats(self) -> None:
        from app.exports.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            code = main(["--profile", "L/L 100x50x8", "--format", "dxf", "step",
                         "--length", "500", "--out", str(out)])
            self.assertEqual(code, 0)
            self.assertEqual(sorted(p.name for p in out.iterdir()),
                             ["L-L-100x50x8.dxf", "L-L-100x50x8.step", "manifest.json"])

    def test_incomplete_profile_reported(self) -> None:
        from app.exports.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            code = main(["--profile", "AM-TES/Té 20x20x3", "--out", str(out)])
            self.assertEqual(code, 1)
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["profiles"], [])
            self.assertEqual(len(manifest["failures"]), 1)
            self.assertEqual(manifest["failures"][0]["profile_id"], "AM-TES/Té 20x20x3")

    def test_unknown_profile_reported(self) -> None:
        from app.exports.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            code = main(["--profile", "INCONNU/X", "--no-manifest", "--out", tmp])
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
