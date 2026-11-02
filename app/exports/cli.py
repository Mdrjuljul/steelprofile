"""Ligne de commande d'export.

Exemples :

    python -m app.exports --profile "IPE/IPE 200" --out exports
    python -m app.exports --series IPE --format step dxf --out exports/IPE
    python -m app.exports --profile "CHS-CF/CHS 168.3x6" --format stl glb --tolerance 0.02

Chaque format est écrit dans `--out` sous un nom dérivé de la désignation. Un
profilé incomplet est refusé (aucune géométrie inventée) et n'empêche pas les
autres exports ; le code de sortie vaut 1 si au moins un profilé a échoué.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.exports.dxf import write_dxf
from app.exports.glb import write_glb
from app.exports.mesh import build_mesh, write_obj, write_stl
from app.exports.step import write_step
from app.geometry.build import connect, iter_profile_ids, load_profile
from app.geometry.contour import GeometryError
from app.geometry.properties import section_properties
from app.geometry.shapes import build_section

FORMATS = ("dxf", "step", "stl", "obj", "glb")
DEFAULT_LENGTH = 1000.0
DEFAULT_TOLERANCE = 0.05


def safe_name(text: str) -> str:
    """Nom de fichier ASCII stable : accents retirés, séparateurs normalisés."""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = decomposed.encode("ascii", "ignore").decode("ascii")
    cleaned = []
    for char in ascii_text:
        if char.isalnum() or char in "._-":
            cleaned.append(char)
        elif char in " /\\":
            cleaned.append("-")
    name = "".join(cleaned)
    while "--" in name:
        name = name.replace("--", "-")
    return name.strip("-._") or "profile"


def export_profile(*, profile_id: str, section, out_dir: Path, formats: tuple[str, ...],
                   length: float, tolerance: float, binary_stl: bool = True) -> dict:
    """Écrit les formats demandés pour une section ; renvoie les chemins produits."""
    base = safe_name(profile_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}
    for fmt in formats:
        path = out_dir / f"{base}.{fmt}"
        if fmt == "dxf":
            write_dxf(section, path, name=profile_id)
        elif fmt == "step":
            write_step(section, path, length, name=profile_id)
        elif fmt == "stl":
            write_stl(build_mesh(section, length, tolerance), path, name=profile_id,
                      binary=binary_stl)
        elif fmt == "obj":
            write_obj(build_mesh(section, length, tolerance), path, name=profile_id)
        elif fmt == "glb":
            write_glb(build_mesh(section, length, tolerance), path, name=profile_id)
        else:  # pragma: no cover - argparse restreint déjà les valeurs
            raise ValueError(f"format inconnu : {fmt!r}")
        files[fmt] = str(path)
    return files


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_selection(*, con, profile_ids, out_dir: Path, formats: tuple[str, ...],
                     length: float, tolerance: float, binary_stl: bool = True,
                     progress=None) -> tuple[list[dict], list[tuple[str, str]]]:
    """Exporte une liste de profilés et renvoie (entrées du manifeste, refus).

    Un profilé inconnu ou incomplet est refusé et consigné, sans interrompre les
    autres : la même règle que la ligne de commande s'applique à toute interface.
    `progress(index, total, profile_id)` est appelé avant chaque export.
    """
    entries: list[dict] = []
    failures: list[tuple[str, str]] = []
    total = len(profile_ids)
    for index, profile_id in enumerate(profile_ids, start=1):
        if progress is not None:
            progress(index, total, profile_id)
        try:
            profile = load_profile(con, profile_id)
            section = build_section(profile.shape_id, profile.params)
        except GeometryError as exc:
            failures.append((profile_id, str(exc)))
            continue
        properties = section_properties(section)
        files = export_profile(
            profile_id=profile_id, section=section, out_dir=out_dir,
            formats=formats, length=length, tolerance=tolerance,
            binary_stl=binary_stl,
        )
        entries.append({
            "profile_id": profile_id,
            "series_id": profile.series_id,
            "designation": profile.designation,
            "category": profile.category,
            "verified": False,
            "length_mm": length,
            "tolerance_mm": tolerance,
            "area_mm2": properties.A,
            "files": {fmt: Path(path).name for fmt, path in files.items()},
            "sha256": {fmt: _sha256(Path(path)) for fmt, path in files.items()},
        })
    return entries, failures


def build_manifest(*, formats, length: float, tolerance: float,
                   entries: list[dict], failures: list[tuple[str, str]]) -> dict:
    """Manifeste d'export : paramètres, fichiers produits et empreintes."""
    return {
        "tool": "SteelProfile",
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "length_mm": length,
        "tolerance_mm": tolerance,
        "formats": list(formats),
        "profiles": entries,
        "failures": [{"profile_id": pid, "error": message}
                     for pid, message in failures],
    }


def write_manifest(out_dir: Path, manifest: dict) -> Path:
    """Écrit `manifest.json` dans `out_dir` (UTF-8, sans BOM) et renvoie son chemin."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Exporte des profilés en DXF, STEP, STL, OBJ ou GLB.")
    parser.add_argument("--db", type=Path, default=None, help="base SQLite (défaut : data/profiles.db)")
    parser.add_argument("--profile", action="append", default=[], help="identifiant exact (répétable)")
    parser.add_argument("--series", help="limiter à une série (ex. IPE)")
    parser.add_argument("--category", choices=("standard", "commercial"), help="limiter à une catégorie")
    parser.add_argument("--limit", type=int, help="nombre maximal de profilés")
    parser.add_argument("--format", nargs="+", choices=FORMATS + ("all",), default=["all"],
                        help="formats à écrire (défaut : all)")
    parser.add_argument("--length", type=float, default=DEFAULT_LENGTH,
                        help=f"longueur d'extrusion en mm (défaut {DEFAULT_LENGTH:g})")
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE,
                        help=f"flèche de corde maximale en mm (défaut {DEFAULT_TOLERANCE:g})")
    parser.add_argument("--ascii-stl", action="store_true", help="STL ASCII au lieu du binaire")
    parser.add_argument("--out", type=Path, default=Path("exports"), help="répertoire de sortie")
    parser.add_argument("--no-manifest", action="store_true", help="ne pas écrire manifest.json")
    args = parser.parse_args(argv)

    formats: tuple[str, ...] = FORMATS if "all" in args.format else tuple(
        dict.fromkeys(args.format))
    if args.length <= 0.0:
        parser.error("--length doit être > 0")
    if args.tolerance <= 0.0:
        parser.error("--tolerance doit être > 0")

    con = connect(args.db) if args.db else connect()
    try:
        if args.profile:
            profile_ids = list(dict.fromkeys(args.profile))
        else:
            profile_ids = list(iter_profile_ids(con, category=args.category,
                                                series_id=args.series))
            if args.limit:
                profile_ids = profile_ids[:args.limit]
        if not profile_ids:
            print("aucun profilé à exporter", file=sys.stderr)
            return 2

        entries, failures = export_selection(
            con=con, profile_ids=profile_ids, out_dir=args.out, formats=formats,
            length=args.length, tolerance=args.tolerance,
            binary_stl=not args.ascii_stl,
        )
        for entry in entries:
            print(f"{entry['profile_id']} -> {', '.join(entry['files'].values())}")

        if not args.no_manifest:
            manifest = build_manifest(
                formats=formats, length=args.length, tolerance=args.tolerance,
                entries=entries, failures=failures)
            manifest_path = write_manifest(args.out, manifest)
            print(f"manifeste : {manifest_path}")
    finally:
        con.close()

    if failures:
        print(f"\n{len(failures)} profilé(s) refusé(s) :", file=sys.stderr)
        for profile_id, message in failures:
            print(f"  {profile_id}: {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
