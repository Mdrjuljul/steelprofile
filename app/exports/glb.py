"""Export GLB (glTF 2.0 binaire) d'un maillage triangulaire.

Un seul maillage, non indexé : chaque triangle porte ses trois sommets et sa
normale, ce qui donne un rendu à facettes net et évite les coutures de lissage
sur les arêtes vives. Les coordonnées sont en millimètres, comme le reste de
l'outil ; l'unité est déclarée dans `extras`.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

from app.exports.mesh import Mesh, normal

_JSON_CHUNK = 0x4E4F534A
_BIN_CHUNK = 0x004E4942


def glb_bytes(mesh: Mesh, *, name: str = "SteelProfile") -> bytes:
    """Contenu binaire d'un GLB pour `mesh`."""
    positions: list[tuple[float, float, float]] = []
    normals: list[tuple[float, float, float]] = []
    for i, j, k in mesh.triangles:
        a, b, c = mesh.vertices[i], mesh.vertices[j], mesh.vertices[k]
        n = normal(a, b, c)
        for vertex in (a, b, c):
            positions.append(vertex)
            normals.append(n)

    position_data = b"".join(struct.pack("<3f", *p) for p in positions)
    normal_data = b"".join(struct.pack("<3f", *n) for n in normals)

    # Bornes calculées sur les valeurs réellement stockées (float32) : le
    # validateur glTF compare `accessor.min/max` au contenu binaire.
    stored = struct.unpack(f"<{3 * len(positions)}f", position_data)
    xs = [stored[i] for i in range(0, len(stored), 3)]
    ys = [stored[i + 1] for i in range(0, len(stored), 3)]
    zs = [stored[i + 2] for i in range(0, len(stored), 3)]
    count = len(positions)

    document = {
        "asset": {"version": "2.0", "generator": "SteelProfile"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": name}],
        "meshes": [{
            "name": name,
            "primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1}, "mode": 4}],
        }],
        "buffers": [{"byteLength": len(position_data) + len(normal_data)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(position_data), "target": 34962},
            {"buffer": 0, "byteOffset": len(position_data), "byteLength": len(normal_data),
             "target": 34962},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": count, "type": "VEC3",
             "min": [min(xs), min(ys), min(zs)], "max": [max(xs), max(ys), max(zs)]},
            {"bufferView": 1, "componentType": 5126, "count": count, "type": "VEC3"},
        ],
        "extras": {"units": "mm", "triangles": len(mesh.triangles)},
    }

    json_data = json.dumps(document, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    json_data += b" " * (-len(json_data) % 4)
    bin_data = position_data + normal_data
    bin_data += b"\x00" * (-len(bin_data) % 4)

    total = 12 + 8 + len(json_data) + 8 + len(bin_data)
    chunks = [
        struct.pack("<II", len(json_data), _JSON_CHUNK),
        json_data,
        struct.pack("<II", len(bin_data), _BIN_CHUNK),
        bin_data,
    ]
    return struct.pack("<4sII", b"glTF", 2, total) + b"".join(chunks)


def write_glb(mesh: Mesh, path: str | Path, *, name: str = "SteelProfile") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(glb_bytes(mesh, name=name))
    return path
