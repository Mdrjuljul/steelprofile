"""Validation de développement des STEP avec OpenCASCADE — outil optionnel.

Ce script n'est **pas** une dépendance du projet : `app.exports` n'importe que
la bibliothèque standard. Il sert à relire les fichiers STEP produits avec un
noyau CAO tiers, à vérifier que le B-REP est valide et à comparer le volume au
produit aire × longueur consigné dans `manifest.json`.

Installation dans un environnement jetable :

    python -m venv %TEMP%\\stepcheck
    %TEMP%\\stepcheck\\Scripts\\python -m pip install cadquery-ocp

Utilisation :

    %TEMP%\\stepcheck\\Scripts\\python tools\\validate_step.py exports\\step

Le répertoire doit contenir le `manifest.json` écrit par `app.exports`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SOLID, TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer
except ImportError:  # pragma: no cover - dépend de l'environnement de dev
    raise SystemExit(
        "OCP est absent. Créer un environnement virtuel jetable et installer "
        "cadquery-ocp (voir l'en-tête du script).")


def count(shape, kind) -> int:
    total = 0
    explorer = TopExp_Explorer(shape, kind)
    while explorer.More():
        total += 1
        explorer.Next()
    return total


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path("exports") / "step"
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        print(f"manifeste absent : {manifest_path}", file=sys.stderr)
        return 2
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if "step" not in manifest.get("formats", []):
        print("ce manifeste ne contient pas de STEP", file=sys.stderr)
        return 2

    print(f"{'profilé':30s} {'valide':6s} {'solides':7s} {'faces':6s} {'arêtes':7s} "
          f"{'volume OCC':>15s} {'écart':>10s}")
    failures = 0
    for entry in manifest["profiles"]:
        path = root / entry["files"]["step"]
        reader = STEPControl_Reader()
        status = reader.ReadFile(str(path))
        if status != IFSelect_RetDone:
            print(f"{entry['profile_id']:30s} ECHEC lecture ({status})")
            failures += 1
            continue
        reader.TransferRoots()
        shape = reader.OneShape()
        valid = BRepCheck_Analyzer(shape).IsValid()
        solids = count(shape, TopAbs_SOLID)
        faces = count(shape, TopAbs_FACE)
        edges = count(shape, TopAbs_EDGE)
        vertices = count(shape, TopAbs_VERTEX)
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(shape, props)
        volume = props.Mass()
        expected = entry["area_mm2"] * entry["length_mm"]
        error = abs(volume - expected) / expected
        ok = valid and solids == 1 and error < 1e-9
        if not ok:
            failures += 1
        print(f"{entry['profile_id']:30s} {str(valid):6s} {solids:<7d} {faces:<6d} "
              f"{edges:<7d} {volume:15.4f} {error:10.2e} {'OK' if ok else 'ERR'}"
              f"  (sommets {vertices})")

    print()
    print(f"{len(manifest['profiles'])} fichiers, {failures} en échec")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
