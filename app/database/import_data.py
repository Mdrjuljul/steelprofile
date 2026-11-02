"""Import du catalogue Phase 1 depuis `Steel Section Database` vers SQLite.

Usage :
    python app/database/import_data.py [--repo <chemin>] [--db <chemin>] [--stats <chemin>]

Le script ne fait *aucune* supposition géométrique : il recopie les valeurs
primaires publiées, résout les rayons d'angle des profilés creux par la règle
explicite de la série (EN 10210-2 / EN 10219-2), recalcule les contrôles de
faisabilité documentés, et écrit les anomalies détectées dans `catalog_issue`.

Sortie :
    data/profiles.db          base SQLite
    data/catalogue_stats.json comptages et anomalies, base du rapport
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sqlite3
import sys
import tomllib
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPO = ROOT / "data" / "sources" / "Steel_Section_Database-main"
DEFAULT_DB = ROOT / "data" / "profiles.db"
DEFAULT_STATS = ROOT / "data" / "catalogue_stats.json"
STAGING = ROOT / "data" / "staging"
SCHEMA = Path(__file__).resolve().parent / "schema.sql"
TODAY = date.today().isoformat()

# ---------------------------------------------------------------------------
# Référentiels (valeurs fixes, documentées)
# ---------------------------------------------------------------------------

FAMILIES = [
    ("I", "Profilés en I", "3.1", 1, 10),
    ("H", "Profilés en H", "3.2", 1, 20),
    ("U", "Profilés en U", "3.3", 1, 30),
    ("L", "Cornières", "3.4", 1, 40),
    ("T", "Profilés en T", "3.5", 1, 50),
    ("HOLLOW", "Tubes et profilés creux", "3.6", 1, 60),
    ("SOLID", "Profilés pleins", "3.7", 1, 70),
]

SHAPES = {
    "I":         ("Profilé I/H à semelles parallèles", 1, "geometry/i_sections.py"),
    "I_TAPERED": ("Profilé I à semelles inclinées (IPN)", 1, "geometry/i_sections.py"),
    "U":         ("Profilé U à semelles parallèles (UPE)", 0, "geometry/u_sections.py"),
    "U_TAPERED": ("Profilé U à semelles inclinées (UPN)", 0, "geometry/u_sections.py"),
    "SHS":       ("Tube carré", 1, "geometry/hollow_sections.py"),
    "RHS":       ("Tube rectangulaire", 1, "geometry/hollow_sections.py"),
    "CHS":       ("Tube circulaire", 1, "geometry/hollow_sections.py"),
    "L_EQ":      ("Cornière à ailes égales", 0, "geometry/l_sections.py"),
    "L":         ("Cornière à ailes inégales", 0, "geometry/l_sections.py"),
    "FLAT":      ("Plat", 1, "geometry/solid_sections.py"),
    "ROUND":     ("Rond plein", 1, "geometry/solid_sections.py"),
    "SQUARE":    ("Carré plein", 1, "geometry/solid_sections.py"),
    # Forme provisoire : le modèle de EN 10055 (semelles inclinées + âme inclinée)
    # doit être confirmé sur la norme avant toute reconstruction. Aucune donnée
    # n'est importée dans cette forme à ce jour.
    "T_TAPERED": ("Profilé T à semelles inclinées (EN 10055)", 1, "geometry/t_sections.py"),
}

PARAMS = {
    "I":         [("h", 1), ("b", 1), ("tw", 1), ("tf", 1), ("r", 1)],
    "I_TAPERED": [("h", 1), ("b", 1), ("tw", 1), ("tf", 1), ("r1", 1), ("r2", 1),
                  ("slope_pct", 1), ("x_tf", 1)],
    "U":         [("h", 1), ("b", 1), ("tw", 1), ("tf", 1), ("r", 1)],
    "U_TAPERED": [("h", 1), ("b", 1), ("tw", 1), ("tf", 1), ("r1", 1), ("r2", 1),
                  ("slope_pct", 1), ("x_tf", 1)],
    "SHS":       [("b", 1), ("t", 1), ("ro", 1), ("ri", 1)],
    "RHS":       [("h", 1), ("b", 1), ("t", 1), ("ro", 1), ("ri", 1)],
    "CHS":       [("D", 1), ("t", 1)],
    "L_EQ":      [("b", 1), ("t", 1), ("r1", 1), ("r2", 1)],
    "L":         [("h", 1), ("b", 1), ("t", 1), ("r1", 1), ("r2", 1)],
    "FLAT":      [("b", 1), ("t", 1)],
    "ROUND":     [("D", 1)],
    "SQUARE":    [("a", 1)],
    "T_TAPERED": [("h", 1), ("b", 1), ("tw", 1), ("tf", 1), ("r1", 1), ("r2", 1),
                  ("slope_pct", 1), ("x_tf", 1)],
}

PARAM_LABELS = {
    "h": "hauteur", "b": "largeur", "tw": "épaisseur d'âme", "tf": "épaisseur de semelle",
    "t": "épaisseur", "r": "rayon de congé", "r1": "rayon de congé racine",
    "r2": "rayon de congé d'extrémité", "ro": "rayon d'angle extérieur",
    "ri": "rayon d'angle intérieur", "D": "diamètre extérieur",
    "a": "côté du carré",
    "slope_pct": "inclinaison des semelles (%)", "x_tf": "abscisse de mesure de tf",
}

# Règles de rayon d'angle (EN 10210-2:2006 A.3 / EN 10219-2:2006 B.3).
RADIUS_RULES = [
    ("EN10210-2", "hot_finished", None, None, 1.5, 1.0, "EN 10210-2:2006 §A.3",
     "ro = 1,5·t ; ri = 1,0·t (congé non concentrique : paroi plus épaisse dans l'angle)"),
    ("EN10219-2", "cold_formed", None, 6.0, 2.0, 1.0, "EN 10219-2:2006 §B.3",
     "t ≤ 6 mm : ro = 2,0·t ; ri = 1,0·t"),
    ("EN10219-2", "cold_formed", 6.0, 10.0, 2.5, 1.5, "EN 10219-2:2006 §B.3",
     "6 < t ≤ 10 mm : ro = 2,5·t ; ri = 1,5·t"),
    ("EN10219-2", "cold_formed", 10.0, None, 3.0, 2.0, "EN 10219-2:2006 §B.3",
     "t > 10 mm : ro = 3,0·t ; ri = 2,0·t"),
]

SOURCES = [
    dict(
        source_id="ssdb-github",
        name="Steel Section Database (Adam Koudelka, ulmewix) — branche main",
        kind="repository",
        url="https://github.com/ulmewix/Steel_Section_Database",
        retrieved_on=TODAY,
        version="main @ 2026-09-28 (archive ZIP, 155 fichiers)",
        license="MIT",
        license_url="https://github.com/ulmewix/Steel_Section_Database/blob/main/LICENSE",
        redistribution="allowed",
        usage="data_source",
        notes=(
            "Licence MIT explicite (Copyright (c) 2026 Adam Koudelka) couvrant le dépôt. "
            "Les fichiers de données ne portent aucune mention de source primaire distincte : "
            "la licence MIT est réputée s'appliquer à l'ensemble. Données non contrôlées ligne à "
            "ligne contre les normes (déclaré par le dépôt lui-même)."
        ),
    ),
    dict(
        source_id="constructalia",
        name="ArcelorMittal Constructalia",
        kind="website",
        url="https://constructalia.arcelormittal.com/",
        retrieved_on=TODAY,
        version="—",
        license="Propriétaire — tous droits réservés",
        license_url="https://constructalia.arcelormittal.com/en/links/terms-of-use",
        redistribution="restricted",
        usage="reference_only",
        notes=(
            "Conditions d'utilisation : le contenu « may not be sold, distributed, transmitted, "
            "copied, modified, or decompiled, in any way, without the prior written consent of "
            "ArcelorMittal » ; téléchargement/impression d'une copie autorisés pour usage privé "
            "non commercial. Utilisable uniquement pour vérifier une valeur à la lecture, jamais "
            "pour alimenter la base ni pour redistribuer des tables ou fichiers CAO."
        ),
    ),
    dict(
        source_id="ahanassa",
        name="Ahan Assa (آهن آسا)",
        kind="website",
        url="https://www.ahanassa.com/",
        retrieved_on=TODAY,
        version="—",
        license="Non déclarée — droits réservés par défaut",
        license_url=None,
        redistribution="restricted",
        usage="rejected",
        notes=(
            "Négociant iranien : pages produit et prix, aucune table dimensionnelle normalisée "
            "téléchargeable, aucune licence ni mention de réutilisation. Désignations locales "
            "(tirant, nabshi, ghoti) non alignées sur les séries EN. Écarté comme source de "
            "données ; sans intérêt pour une géométrie EN."
        ),
    ),
    dict(
        source_id="cadxchange",
        name="CADXChange",
        kind="website",
        url="https://www.cadxchange.com/",
        retrieved_on=TODAY,
        version="—",
        license="Non vérifiable (site injoignable)",
        license_url=None,
        redistribution="unknown",
        usage="rejected",
        notes=(
            "Deux tentatives de connexion depuis cet environnement : délai dépassé puis "
            "connexion réinitialisée par l'hôte (207.148.248.143). Conditions de réutilisation "
            "des DXF non consultables ; les fichiers de constructeurs qui y circulent sont "
            "généralement sous licence propre. Non retenu : aucune donnée n'a pu être examinée."
        ),
    ),
    dict(
        source_id="en-standards",
        name="Normes EN (CEN) — EN 10365, EN 10056-1, EN 10210-2, EN 10219-2, EN 10058/59/60, EN 10055",
        kind="standard",
        url="https://standards.cencenelec.eu/",
        retrieved_on=TODAY,
        version="Éditions citées série par série",
        license="Propriétaire — texte normatif non redistribuable",
        license_url=None,
        redistribution="restricted",
        usage="reference_only",
        notes=(
            "Les normes EN sont protégées par le droit d'auteur du CEN et de ses membres "
            "nationaux ; l'achat d'une copie n'autorise pas la redistribution des tableaux. "
            "Les valeurs nominales sont utilisées comme des faits dimensionnels, avec citation "
            "de la norme et de l'édition, sans reproduction du texte normatif."
        ),
    ),
]

STANDARDS = [
    # id, code, edition, titre, statut, remplacée par, vérifié
    ("EN 10365:2017", "EN 10365", "2017", "Profilés I et H laminés à chaud — dimensions et masses",
     "superseded", None, 0),
    ("EN 10365:2026", "EN 10365", "2026", "Profilés I et H laminés à chaud — dimensions et masses",
     "current", None, 0),
    ("EN 10056-1:1998", "EN 10056-1", "1998", "Cornières à ailes égales et inégales — dimensions",
     "superseded", None, 0),
    ("EN 10056-1:2017", "EN 10056-1", "2017", "Cornières à ailes égales et inégales — dimensions",
     "current", None, 0),
    ("EN 10210-2:2006", "EN 10210-2", "2006", "Profils creux de construction finis à chaud — tolérances, dimensions, caractéristiques",
     "current", None, 0),
    ("EN 10219-2:2006", "EN 10219-2", "2006", "Profils creux de construction formés à froid — tolérances, dimensions, caractéristiques",
     "current", None, 0),
    ("EN 10024:1995", "EN 10024", "1995", "Profilés I à semelles inclinées laminés à chaud — tolérances de forme et de dimensions",
     "current", None, 0),
    ("DIN 1025-1:2009", "DIN 1025-1", "2009", "Profilés I — série à semelles inclinées (IPN)",
     "current", None, 0),
    ("DIN 1026-1:2009", "DIN 1026-1", "2009", "Profilés U — série à semelles inclinées (UPN)",
     "current", None, 0),
    ("DIN 1026-2:2002", "DIN 1026-2", "2002", "Profilés U — série à semelles parallèles (UPE)",
     "current", None, 0),
    ("EN 10058:2018", "EN 10058", "2018", "Plats en acier laminés à chaud — dimensions et tolérances",
     "assumed", None, 0),
    ("EN 10055:1995", "EN 10055", "1995", "Profilés T en acier laminés à chaud — dimensions et tolérances",
     "current", None, 0),
    ("EN 10059:2003", "EN 10059", "2003", "Carrés en acier laminés à chaud — dimensions et tolérances",
     "current", None, 0),
    ("EN 10060:2003", "EN 10060", "2003", "Ronds en acier laminés à chaud — dimensions et tolérances",
     "current", None, 0),
]

# Désignations explicitement écartées par la source (géométrie infaisable avec la règle).
EXCLUDED_INFEASIBLE = {"RHS-HF": ["RHS 80x40x11", "RHS 80x40x12.5"]}

DERIVED_UNITS = {
    "mm": "mm", "cm": "cm", "cm2": "cm2", "cm3": "cm3", "cm4": "cm4", "cm6": "cm6",
    "kg_m": "kg/m", "m2_m": "m2/m", "deg": "deg",
}
# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------


def dec(value: str) -> Decimal | None:
    txt = (value or "").strip()
    if txt == "":
        return None
    return Decimal(txt)


def f(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def designation_key(text: str) -> str:
    return "".join(ch for ch in text.upper().replace("×", "X") if ch.isalnum() or ch in ".+-/").replace(" ", "")


def read_csv(path: Path) -> list[dict[str, str]]:
    with io.open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


class LocalDataError(Exception):
    """Série locale invalide : l'import doit s'arrêter sans rien conserver."""


# Connexion en cours de construction : permet de la fermer si une série locale
# est refusée en cours d'import (sinon le fichier reste verrouillé sous Windows).
_ACTIVE_CON: sqlite3.Connection | None = None


def read_toml(path: Path) -> dict:
    # Lecture binaire puis décodage : tolère un BOM UTF-8 (fichier réenregistré
    # par un éditeur Windows), que tomllib refuse en mode binaire.
    with io.open(path, "rb") as fh:
        raw = fh.read()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return tomllib.loads(raw.decode("utf-8"))


def toml_comments(path: Path) -> str:
    """Conserve les commentaires du fichier de métadonnées (provenance, réserves)."""
    lines = []
    for line in io.open(path, encoding="utf-8"):
        stripped = line.strip()
        if stripped.startswith("#"):
            text = stripped.lstrip("#").strip()
            if text:
                lines.append(text)
    return " / ".join(lines)


# ---------------------------------------------------------------------------
# Règles de rayon d'angle
# ---------------------------------------------------------------------------


def resolve_hollow_radii(rule_id: str, t: Decimal) -> tuple[Decimal, Decimal]:
    for rid, _process, lo, hi, ro_f, ri_f, _ref, _note in RADIUS_RULES:
        if rid != rule_id:
            continue
        if lo is not None and not (t > Decimal(str(lo))):
            continue
        if hi is not None and not (t <= Decimal(str(hi))):
            continue
        factor_ro = Decimal(str(ro_f))
        factor_ri = Decimal(str(ri_f))
        return t * factor_ro, t * factor_ri
    raise ValueError(f"aucune règle de rayon {rule_id} pour t = {t}")


# ---------------------------------------------------------------------------
# Faisabilité (contrôles documentés dans docs/DATA_MODEL.md de la source)
# ---------------------------------------------------------------------------


def feasibility(shape: str, g: dict[str, Decimal | None]) -> list[str]:
    errors: list[str] = []
    gt = {k: v for k, v in g.items() if v is not None}

    if shape in ("I", "U"):
        for p in ("h", "b", "tw", "tf"):
            if gt.get(p, 0) <= 0:
                errors.append(f"{p} doit être > 0")
        r = gt.get("r", Decimal(0))
        if (gt["b"] - gt["tw"]) / 2 - r <= 0:
            errors.append("semelle plane (b − tw)/2 − r doit être > 0")
        if gt["h"] - 2 * gt["tf"] - 2 * r <= 0:
            errors.append("âme plane h − 2·tf − 2·r doit être > 0")

    elif shape in ("I_TAPERED", "U_TAPERED"):
        for p in ("h", "b", "tw", "tf"):
            if gt.get(p, 0) <= 0:
                errors.append(f"{p} doit être > 0")
        for p in ("r1", "r2", "slope_pct"):
            if gt.get(p, Decimal(0)) < 0:
                errors.append(f"{p} doit être ≥ 0")
        outstand = (gt["b"] - gt["tw"]) / 2 if shape == "I_TAPERED" else gt["b"] - gt["tw"]
        if outstand <= 0:
            errors.append("porte-à-faux de semelle doit être > 0")
        x_tf = gt.get("x_tf", Decimal(0))
        if not (0 < x_tf < outstand):
            errors.append("x_tf doit vérifier 0 < x_tf < porte-à-faux")

    elif shape in ("SHS", "RHS"):
        for p in ("b", "t"):
            if gt.get(p, 0) <= 0:
                errors.append(f"{p} doit être > 0")
        if shape == "RHS" and gt.get("h", 0) <= 0:
            errors.append("h doit être > 0")
        h = gt.get("h", gt.get("b"))
        b = gt["b"]
        t = gt["t"]
        ro, ri = gt.get("ro"), gt.get("ri")
        if ro is None or ri is None:
            errors.append("rayons d'angle non résolus")
            return errors
        if shape == "RHS" and h < b:
            errors.append("h ≥ b exigé (y-y = axe fort)")
        if b - 2 * t <= 0 or h - 2 * t <= 0:
            errors.append("trou intérieur b − 2·t et h − 2·t doivent être > 0")
        if b - 2 * ro < 0 or h - 2 * ro < 0:
            errors.append("plats extérieurs b − 2·ro et h − 2·ro doivent être ≥ 0")
        if b - 2 * t - 2 * ri < 0 or h - 2 * t - 2 * ri < 0:
            errors.append("plats intérieurs b − 2·t − 2·ri et h − 2·t − 2·ri doivent être ≥ 0")
        d = ro - ri
        if d > t and not (d * d > 2 * (d - t) * (d - t)):
            errors.append("épaisseur de paroi non positive dans l'angle")

    elif shape == "CHS":
        if gt.get("D", 0) <= 0 or gt.get("t", 0) <= 0:
            errors.append("D et t doivent être > 0")
        elif gt["D"] - 2 * gt["t"] <= 0:
            errors.append("D − 2·t doit être > 0")

    elif shape in ("L_EQ", "L"):
        for p in ("h", "b", "t") if shape == "L" else ("b", "t"):
            if gt.get(p, 0) <= 0:
                errors.append(f"{p} doit être > 0")
        h = gt.get("h", gt.get("b"))
        b, t = gt["b"], gt["t"]
        r1, r2 = gt.get("r1", Decimal(0)), gt.get("r2", Decimal(0))
        if shape == "L" and h < b:
            errors.append("h ≥ b exigé")
        if h <= t or b <= t:
            errors.append("chaque aile doit être plus longue que t")
        if h - t - r1 - r2 < 0 or b - t - r1 - r2 < 0:
            errors.append("faces intérieures droites négatives")
        if t - r2 < 0:
            errors.append("extrémité d'aile t − r2 négative")

    elif shape == "FLAT":
        if gt.get("b", 0) <= 0 or gt.get("t", 0) <= 0:
            errors.append("b et t doivent être > 0")

    elif shape == "ROUND":
        if gt.get("D", 0) <= 0:
            errors.append("D doit être > 0")

    elif shape == "SQUARE":
        if gt.get("a", 0) <= 0:
            errors.append("a doit être > 0")

    elif shape == "T_TAPERED":
        # Modèle provisoire : à confirmer sur EN 10055 avant reconstruction.
        for p in ("h", "b", "tw", "tf"):
            if gt.get(p, 0) <= 0:
                errors.append(f"{p} doit être > 0")
        for p in ("r1", "r2", "slope_pct"):
            if gt.get(p, Decimal(0)) < 0:
                errors.append(f"{p} doit être ≥ 0")
        outstand = (gt["b"] - gt["tw"]) / 2
        if outstand <= 0:
            errors.append("porte-à-faux de semelle doit être > 0")
        if outstand - gt.get("r1", Decimal(0)) - gt.get("r2", Decimal(0)) < 0:
            errors.append("semelle droite (b − tw)/2 − r1 − r2 négative")
        if gt["h"] - gt["tf"] - gt.get("r1", Decimal(0)) < 0:
            errors.append("âme droite h − tf − r1 négative")
        x_tf = gt.get("x_tf", Decimal(0))
        if not (0 < x_tf < outstand):
            errors.append("x_tf doit vérifier 0 < x_tf < porte-à-faux")

    return errors


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


def register_staging_source(cur: sqlite3.Cursor, meta: dict) -> None:
    """Déclare dans `source` la provenance d'une série locale (`data/staging`)."""
    source_id = meta["source_id"]
    if cur.execute("SELECT 1 FROM source WHERE source_id = ?", (source_id,)).fetchone():
        return
    redistribution = meta.get("redistribution", "restricted")
    if redistribution not in ("allowed", "restricted", "unknown", "not_applicable"):
        sys.exit(f"{source_id} : `redistribution` invalide ({redistribution!r})")
    kind = meta.get("source_kind", "dataset")
    if kind not in ("repository", "website", "standard", "manufacturer", "dataset"):
        sys.exit(f"{source_id} : `source_kind` invalide ({kind!r})")
    cur.execute(
        "INSERT INTO source VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            source_id,
            meta.get("source_name", source_id),
            kind,
            meta.get("source_url"),
            TODAY,
            meta.get("source_version"),
            meta.get("source_license"),
            meta.get("source_license_url"),
            redistribution,
            "local_only",
            meta.get("source_note", "Données fournies localement ; non destinées à la redistribution."),
        ),
    )


def build(db_path: Path, repo: Path, stats_path: Path, staging: Path = STAGING) -> dict:
    if not (repo / "data").is_dir():
        sys.exit(f"Dépôt introuvable : {repo}")

    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(db_path)
    global _ACTIVE_CON
    _ACTIVE_CON = con
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    cur = con.cursor()

    # --- référentiels -----------------------------------------------------
    cur.executemany(
        "INSERT INTO source VALUES (:source_id,:name,:kind,:url,:retrieved_on,:version,"
        ":license,:license_url,:redistribution,:usage,:notes)", SOURCES)

    cur.executemany(
        "INSERT INTO standard (standard_id,code,edition,title,status,verified,notes) "
        "VALUES (?,?,?,?,?,?,?)",
        [(sid, code, ed, title, status, verified, None)
         for sid, code, ed, title, status, _sup, verified in STANDARDS])
    cur.execute("UPDATE standard SET superseded_by='EN 10365:2026' WHERE standard_id='EN 10365:2017'")

    cur.executemany("INSERT INTO family VALUES (?,?,?,?,?)", FAMILIES)

    for shape_id, (label, sym, gen) in SHAPES.items():
        cur.execute("INSERT INTO shape VALUES (?,?,?,?,NULL)", (shape_id, label, sym, gen))
        for order, (param, required) in enumerate(PARAMS[shape_id], start=1):
            cur.execute(
                "INSERT INTO param_def VALUES (?,?,?,?,?,?)",
                (shape_id, param, "mm" if param != "slope_pct" else "%", required,
                 PARAM_LABELS.get(param, param), order))

    for rid, process, _lo, _hi, _ro_f, _ri_f, ref, note in RADIUS_RULES:
        cur.execute("INSERT OR IGNORE INTO corner_radius_rule VALUES (?,?,?,?)",
                    (rid, process, ref, note))
    for rid, _process, lo, hi, ro_f, ri_f, _ref, note in RADIUS_RULES:
        cur.execute(
            "INSERT INTO corner_radius_band (rule_id,t_min,t_max,ro_factor,ri_factor,note) "
            "VALUES (?,?,?,?,?,?)", (rid, lo, hi, ro_f, ri_f, note))

    issues: list[tuple] = []

    def issue(scope, ref, severity, code, message):
        issues.append((scope, ref, severity, code, message))

    # --- séries -----------------------------------------------------------
    # Chaque travail = (fichier TOML, source_id, répertoire de référence).
    jobs: list[tuple[Path, str, Path]] = [
        (p, "ssdb-github", repo) for p in sorted((repo / "data").glob("*/*.toml"))
    ]

    # Dépôt local optionnel : tables fournies par l'utilisateur (norme achetée,
    # jeu de données autorisé). Jamais livré avec le projet et jamais inclus
    # dans l'export redistribuable. Un TOML = une série ; `source_id` obligatoire.
    if staging.is_dir():
        for p in sorted(staging.glob("*.toml")):
            meta = read_toml(p)
            if not meta.get("source_id"):
                sys.exit(f"{p.name} : le champ `source_id` est obligatoire "
                         f"pour une série locale (data/staging).")
            register_staging_source(cur, meta)
            jobs.append((p, meta["source_id"], staging))

    imported_series = []
    total_profiles = 0
    seen_series: set[str] = set()

    for toml_path, source_id, base in jobs:
        meta = read_toml(toml_path)
        series_id = meta["id"]
        if series_id in seen_series:
            sys.exit(f"série en double : {series_id} (id présent deux fois)")
        seen_series.add(series_id)
        shape_id = meta["shape"]
        if shape_id not in SHAPES:
            sys.exit(f"{series_id} : forme inconnue {shape_id!r} — "
                     f"formes gérées : {', '.join(SHAPES)}")
        family_id = family_of(series_id, shape_id)
        csv_path = toml_path.with_suffix(".csv")
        rows = read_csv(csv_path)
        rule_id = meta.get("corner_radii")

        policy = match_standard(meta.get("standard"))

        # §3.7 : une dimension commerciale vit dans une catégorie distincte et
        # ne doit jamais être confondue avec une référence normalisée.
        category = meta.get("category", "standard")
        if category not in ("standard", "commercial"):
            sys.exit(f"{series_id} : `category` invalide ({category!r}) — "
                     f"valeurs admises : 'standard', 'commercial'.")
        commercial_ref = meta.get("commercial_ref")
        if category == "commercial":
            if policy:
                sys.exit(f"{series_id} : une série commerciale ne peut pas déclarer la norme "
                         f"{meta.get('standard')!r}. Décrivez le programme dans `commercial_ref` : "
                         f"une dimension commerciale n'est pas une référence normalisée (§3.7).")
            if not commercial_ref:
                sys.exit(f"{series_id} : `commercial_ref` est obligatoire pour une série "
                         f"commerciale (programme, fabricant, édition).")
        elif commercial_ref:
            sys.exit(f"{series_id} : `commercial_ref` n'a de sens qu'avec `category = \"commercial\"`.")

        # Paramètres que la source ne publie pas : déclarés explicitement dans le
        # TOML (`[missing]`). Leur absence est alors un fait de la source, pas une
        # faute de saisie ; la référence est importée `incomplete` et bloquée.
        declared_missing = meta.get("missing", {})
        known_params = {p for p, _r in PARAMS[shape_id]}
        unknown_missing = sorted(set(declared_missing) - known_params)
        if unknown_missing:
            sys.exit(f"{series_id} : `[missing]` déclare des paramètres inconnus pour la forme "
                     f"{shape_id} : {', '.join(unknown_missing)} — paramètres de la forme : "
                     f"{', '.join(sorted(known_params))}.")

        cur.execute(
            "INSERT INTO series (series_id,family_id,label,shape_id,standard_id,process,"
            "corner_radii_rule,source_id,source_ref,alias_patterns,notes,category,commercial_ref) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (series_id, family_id, meta.get("title", series_id), shape_id, policy, meta.get("process"),
             rule_id, source_id, str(csv_path.relative_to(base)).replace("\\", "/"),
             json.dumps(meta.get("designation", {}).get("aliases", []), ensure_ascii=False),
             toml_comments(toml_path), category, commercial_ref))

        imported_series.append(series_id)

        # --- profils ------------------------------------------------------
        for row_index, row in enumerate(rows, start=2):  # ligne 1 = en-tête
            designation = row["designation"].strip()
            note = (row.get("note") or "").strip() or None
            profile_id = f"{series_id}/{designation}"
            geom: dict[str, Decimal | None] = {}
            origins: dict[str, str] = {}

            for param, _required in PARAMS[shape_id]:
                value = dec(row.get(param, ""))
                geom[param] = value
                if value is not None:
                    origins[param] = "table"

            if shape_id in ("SHS", "RHS"):
                t = geom.get("t")
                if rule_id and t is not None and (geom.get("ro") is None or geom.get("ri") is None):
                    ro, ri = resolve_hollow_radii(rule_id, t)
                    if geom.get("ro") is None:
                        geom["ro"], origins["ro"] = ro, "series_rule"
                    if geom.get("ri") is None:
                        geom["ri"], origins["ri"] = ri, "series_rule"

            missing = [p for p, req in PARAMS[shape_id] if req and geom.get(p) is None]
            undeclared = [p for p in missing if p not in declared_missing]
            errors = feasibility(shape_id, geom) if not missing else []

            # Une série locale est saisie à la main : une ligne incomplète ou
            # infaisable est une faute de saisie, pas une donnée de la source.
            # On refuse l'import plutôt que de créer une référence bancale —
            # sauf pour un paramètre explicitement déclaré absent de la source
            # (`[missing]`), qui donne une référence `incomplete` et bloquée.
            if source_id != "ssdb-github" and (undeclared or errors):
                detail = []
                if undeclared:
                    detail.append("paramètres manquants : " + ", ".join(undeclared))
                if errors:
                    detail.append("faisabilité : " + " ; ".join(errors))
                raise LocalDataError(f"{profile_id} (ligne {row_index}) — " + " | ".join(detail))

            if missing:
                status = "incomplete"
            elif errors:
                status = "infeasible"
            else:
                status = "complete"

            source_kind = "table+rule" if "series_rule" in origins.values() else "table"
            sort_value = geom.get("h") or geom.get("b") or geom.get("D") or geom.get("a")

            cur.execute(
                "INSERT INTO profile (profile_id,series_id,designation,designation_key,sort_key,"
                "geometry_status,geometry_source,verified,verified_on,source_row,notes) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (profile_id, series_id, designation, designation_key(designation), f(sort_value),
                 status, source_kind, 0, None, str(row_index), note))

            for param, _required in PARAMS[shape_id]:
                value = geom.get(param)
                cur.execute(
                    "INSERT INTO profile_param (profile_id,param,value,unit,origin,note) VALUES (?,?,?,?,?,?)",
                    (profile_id, param, f(value), "%" if param == "slope_pct" else "mm",
                     origins.get(param, "table"),
                     None if value is not None
                     else declared_missing.get(param, "absent de la source")))

            if missing:
                detail = "; ".join(
                    f"{p} ({declared_missing[p]})" if p in declared_missing else p
                    for p in missing)
                issue("profile", profile_id, "blocking", "MISSING_PARAMETER",
                      "paramètres absents : " + detail)
            if errors:
                issue("profile", profile_id, "blocking", "INFEASIBLE_GEOMETRY",
                      "contrôle de faisabilité en échec : " + " ; ".join(errors))

            # alias issus des motifs déclarés par la série
            aliases = expand_aliases(meta.get("designation", {}).get("aliases", []), designation)
            seen_keys: set[str] = set()
            for alias in aliases:
                key = designation_key(alias)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                cur.execute("INSERT OR IGNORE INTO profile_alias VALUES (?,?,?)",
                            (profile_id, alias, key))

            # propriétés dérivées (recopiées, non indépendantes)
            total_profiles += 1

        # propriétés dérivées : un fichier par série
        props_path = base / "generated" / "properties" / f"{series_id}.csv"
        if props_path.is_file():
            conventions = meta.get("conventions", {})
            primary = {p for p, _r in PARAMS[shape_id]}
            prop_cur = con.cursor()
            for row in read_csv(props_path):
                designation = row["designation"].strip()
                profile_id = f"{series_id}/{designation}"
                for column, raw in row.items():
                    if column == "designation":
                        continue
                    param, unit = split_derived_column(column)
                    if param is None or param in primary:
                        # la géométrie primaire ne se duplique pas ici
                        continue
                    value = None if raw.strip() in ("", "unsupported", "n/a") else float(raw)
                    status = "supported" if value is not None else "unsupported"
                    conv = conventions.get(param)
                    method = conv.get("method") if isinstance(conv, dict) else None
                    prop_cur.execute(
                        "INSERT OR REPLACE INTO derived_property VALUES (?,?,?,?,?,?,?)",
                        (profile_id, param, value, unit, status, method, 0))

        # --- réserves par série -------------------------------------------
        origin_label = "d'un dépôt tiers" if source_id == "ssdb-github" else f"de la source locale « {source_id} »"
        issue("series", series_id, "warning", "NOT_VERIFIED_AGAINST_STANDARD",
              f"Dimensions issues {origin_label} ; elles n'ont pas été contrôlées ligne à ligne "
              f"contre une copie licite de la norme. Statut de validation : non vérifié.")
        if source_id != "ssdb-github":
            issue("series", series_id, "warning", "LOCAL_ONLY_DATA",
                  f"Série locale (source « {source_id} ») : exclue de l'export redistribuable. "
                  f"Ne peut être livrée avec le projet.")
        if category == "commercial":
            issue("series", series_id, "warning", "COMMERCIAL_DATA",
                  f"Dimensions commerciales ({commercial_ref}) : catégorie distincte au sens du §3.7. "
                  f"Ce ne sont pas des références normalisées et elles ne doivent pas être présentées "
                  f"comme telles.")
        if policy == "EN 10365:2017":
            issue("series", series_id, "info", "STANDARD_EDITION_SUPERSEDED",
                  "La série cite EN 10365:2017, remplacée par EN 10365:2026 (écart non évalué).")
        if policy == "EN 10056-1:1998":
            issue("series", series_id, "info", "STANDARD_EDITION_SUPERSEDED",
                  "EN 10056-1:1998 est remplacée par EN 10056-1:2017 ; les rayons de certaines "
                  "lignes viennent de DIN 1028/1029 ou de catalogues fabricants.")
        if series_id == "FLAT":
            issue("series", series_id, "warning", "STANDARD_ASSUMED",
                  "Aucune norme ne définit ces 62 largeurs/épaisseurs dans la source : "
                  "l'appartenance à l'EN 10058 est une hypothèse, non vérifiée.")
        if series_id in ("L-EQ", "L"):
            issue("series", series_id, "warning", "MIXED_RANGE",
                  "Gamme mixte : une partie seulement des tailles figure dans EN 10056-1 ; "
                  "les autres viennent de DIN 1028/1029 ou de fabricants.")
        if rule_id:
            issue("series", series_id, "info", "RADIUS_FROM_RULE",
                  f"Rayons d'angle non tabulés : ro/ri déduits de la règle {rule_id} "
                  f"(facteurs de t). Aucune valeur n'est inventée, mais ce sont des rayons de "
                  f"calcul et non des rayons mesurés.")
        if series_id in EXCLUDED_INFEASIBLE:
            for ref in EXCLUDED_INFEASIBLE[series_id]:
                issue("series", series_id, "info", "EXCLUDED_BY_SOURCE",
                      f"{ref} absent de la source : contour intérieur inexistant avec la règle "
                      f"de rayon ; à traiter avec un ri explicite documenté.")

    # --- anomalies ciblées -------------------------------------------------
    issue("profile", "L/L 75x50x7", "warning", "RADII_UNRESOLVED",
          "Rayons 7 / 3,5 non tranchés : une table de stockiste donne 6,5 / 3,5 (A = 8,30 cm²). "
          "Une table DIN 1029 primaire est nécessaire.")
    issue("profile", "IPN/IPN 600", "warning", "OUTSIDE_RADIUS_SOURCE",
          "IPN 600 n'est pas dans DIN 1025-1:2009 (qui s'arrête à 550) : r1/r2 proviennent d'une "
          "autre source, non explicitée par le dépôt.")

    # --- manques de périmètre ---------------------------------------------
    fam_counts = {
        r[0]: (r[1] or 0, r[2] or 0)
        for r in cur.execute("""
            SELECT f.family_id, COUNT(p.profile_id),
                   SUM(CASE WHEN s.category = 'commercial' THEN 1 ELSE 0 END)
            FROM family f
            LEFT JOIN series s USING (family_id)
            LEFT JOIN profile p ON p.series_id = s.series_id
            GROUP BY f.family_id""")
    }
    t_total, t_commercial = fam_counts.get("T", (0, 0))
    solid_total, solid_commercial = fam_counts.get("SOLID", (0, 0))
    if t_commercial:
        issue("family", "T", "blocking", "FAMILY_COMMERCIAL_ONLY",
              f"Famille T couverte seulement par des dimensions commerciales "
              f"({t_commercial} référence(s) sur {t_total}) : aucune série normalisée. Les "
              f"dimensions publiées par le fabricant ne suffisent pas à reconstruire la section "
              f"(pente de semelle et position de mesure de tf non publiées) : toutes les "
              f"références sont `incomplete` et bloquées.")
    else:
        issue("family", "T", "blocking", "FAMILY_NOT_COVERED",
              "Aucune série T dans la source : les profilés T (EN 10055) restent à constituer "
              "(0 référence).")
    if solid_commercial:
        issue("family", "SOLID", "warning", "FAMILY_PARTLY_COMMERCIAL",
              f"{solid_total} référence(s) pleines, dont {solid_commercial} commerciales. Les "
              f"barres pleines normalisées restent absentes de la source MIT (seuls les plats y "
              f"figurent) ; carrés et ronds pleins ne sont couverts que par le programme "
              f"commercial du fabricant (catégorie distincte, §3.7).")
    else:
        issue("family", "SOLID", "blocking", "FAMILY_PARTIAL",
              "Seuls les plats sont couverts. Carrés pleins (EN 10059) et ronds pleins (EN 10060) "
              "sont absents : 0 référence.")
    issue("family", "I", "warning", "SERIES_MISSING",
          "IPE couvert (18). IPN couvert (21). Séries IPE A / AA / O / V non couvertes : 0 référence.")
    issue("family", "H", "warning", "SERIES_MISSING",
          "HEA, HEB, HEM couvertes (72). Série HE C absente, dont la section 320 × 305 "
          "improprement appelée « HEM 320/305 ».")
    issue("family", "HOLLOW", "info", "DUPLICATE_DESIGNATIONS",
          "Les désignations des séries HF et CF se recouvrent : mêmes libellés, rayons d'angle "
          "différents (le procédé fait partie de l'identité). Voir data/catalogue_stats.json.")

    con.executemany(
        "INSERT INTO catalog_issue (scope,ref,severity,code,message) VALUES (?,?,?,?,?)", issues)

    # --- export lisible du catalogue ---------------------------------------
    write_inventory(con, stats_path.parent / "catalogue_inventory.csv")
    local_only = cur.execute(
        "SELECT COUNT(*) FROM series s JOIN source sr ON sr.source_id = s.source_id "
        "WHERE sr.redistribution <> 'allowed'").fetchone()[0]
    if local_only:
        write_inventory(con, stats_path.parent / "catalogue_inventory_redistributable.csv",
                        redistributable_only=True)

    con.commit()

    # --- statistiques ------------------------------------------------------
    stats = collect_stats(con)
    stats["source_repo"] = str(repo)
    stats["imported_on"] = TODAY
    stats["series"] = imported_series
    stats["profiles_imported"] = total_profiles
    stats["local_only_series"] = local_only
    stats["duplicate_designations_hf_cf"] = hf_cf_overlap(con)
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    con.close()
    _ACTIVE_CON = None
    return stats


def family_of(series_id: str, shape_id: str | None = None) -> str:
    # Familles déterminées par la forme : sans ambiguïté, y compris pour les
    # séries locales dont l'identifiant ne suit pas la nomenclature du dépôt.
    if shape_id in ("ROUND", "SQUARE", "FLAT"):
        return "SOLID"
    if shape_id == "T_TAPERED":
        return "T"
    if series_id in ("IPE", "IPN") or series_id.startswith("IPE"):
        return "I"
    if series_id in ("HEA", "HEB", "HEM", "HEC"):
        return "H"
    if series_id in ("UPN", "UPE"):
        return "U"
    if series_id in ("L-EQ", "L"):
        return "L"
    if series_id.startswith("T"):
        return "T"
    if series_id.split("-")[0] in ("SHS", "RHS", "CHS"):
        return "HOLLOW"
    return "SOLID"


def match_standard(raw: str | None) -> str | None:
    if not raw:
        return None
    for sid, code, edition, *_ in STANDARDS:
        if raw == sid:
            return sid
    if raw.startswith("Mixed range"):
        return "EN 10056-1:1998"
    if raw.startswith("Assumed"):
        return "EN 10058:2018"
    return None


def split_derived_column(column: str) -> tuple[str | None, str | None]:
    if column == "corner_radii":
        return None, None
    for suffix in ("_kg_m", "_m2_m", "_cm6", "_cm4", "_cm3", "_cm2", "_mm", "_cm", "_deg"):
        if column.endswith(suffix):
            return column[: -len(suffix)], DERIVED_UNITS[suffix[1:]]
    return column, None


def expand_aliases(patterns: list[str], designation: str) -> list[str]:
    """Remplace les jetons {…} par les valeurs numériques de la désignation, dans l'ordre."""
    numbers = re.findall(r"\d+(?:\.\d+)?", designation)
    out: list[str] = []
    for pattern in patterns:
        candidate = tokens_to_alias(pattern, numbers)
        if candidate and candidate not in out and candidate != designation:
            out.append(candidate)
    return out


def tokens_to_alias(pattern: str, numbers: list[str]) -> str | None:
    result = pattern
    for number in numbers:
        if "{" in result:
            start = result.index("{")
            end = result.index("}", start)
            result = result[:start] + number + result[end + 1:]
    return None if "{" in result else result


def collect_stats(con: sqlite3.Connection) -> dict:
    cur = con.cursor()
    families = []
    for row in cur.execute("""
        SELECT f.family_id, f.label_fr, f.spec_section, f.expected,
               COUNT(DISTINCT se.series_id),
               COUNT(p.profile_id),
               SUM(CASE WHEN p.geometry_status='complete' THEN 1 ELSE 0 END),
               SUM(CASE WHEN p.geometry_source='table+rule' THEN 1 ELSE 0 END),
               SUM(CASE WHEN p.geometry_status='incomplete' THEN 1 ELSE 0 END),
               SUM(CASE WHEN p.geometry_status='infeasible' THEN 1 ELSE 0 END)
        FROM family f
        LEFT JOIN series se ON se.family_id = f.family_id
        LEFT JOIN profile p ON p.series_id = se.series_id
        GROUP BY f.family_id ORDER BY f.sort_order"""):
        families.append(dict(
            family=row[0], label=row[1], spec_section=row[2], expected=bool(row[3]),
            series=row[4], profiles=row[5], complete=row[6], rule_radii=row[7],
            incomplete=row[8], infeasible=row[9]))

    series = []
    for row in cur.execute("""
        SELECT se.series_id, se.family_id, se.shape_id, se.process, st.standard_id,
               COUNT(p.profile_id),
               SUM(CASE WHEN p.geometry_status='complete' THEN 1 ELSE 0 END),
               SUM(CASE WHEN p.geometry_source='table+rule' THEN 1 ELSE 0 END),
               MIN(p.sort_key), MAX(p.sort_key)
        FROM series se
        LEFT JOIN standard st ON st.standard_id = se.standard_id
        LEFT JOIN profile p ON p.series_id = se.series_id
        GROUP BY se.series_id ORDER BY se.family_id, se.series_id"""):
        series.append(dict(
            series=row[0], family=row[1], shape=row[2], process=row[3], standard=row[4],
            profiles=row[5], complete=row[6], rule_radii=row[7],
            min_size=row[8], max_size=row[9]))

    params = []
    for row in cur.execute("""
        SELECT se.series_id, pp.param, COUNT(*) AS n,
               SUM(CASE WHEN pp.value IS NULL THEN 1 ELSE 0 END),
               MIN(pp.value), MAX(pp.value),
               MAX(CASE WHEN pp.origin='series_rule' THEN 1 ELSE 0 END)
        FROM profile p
        JOIN series se ON se.series_id = p.series_id
        JOIN profile_param pp ON pp.profile_id = p.profile_id
        GROUP BY se.series_id, pp.param
        ORDER BY se.series_id, pp.param"""):
        params.append(dict(series=row[0], param=row[1], rows=row[2], missing=row[3],
                           min=row[4], max=row[5], from_rule=bool(row[6])))

    issues = [dict(scope=r[0], ref=r[1], severity=r[2], code=r[3], message=r[4])
              for r in cur.execute(
                  "SELECT scope,ref,severity,code,message FROM catalog_issue ORDER BY severity,scope,ref")]

    derived = cur.execute("SELECT COUNT(*) FROM derived_property").fetchone()[0]
    aliases = cur.execute("SELECT COUNT(*) FROM profile_alias").fetchone()[0]

    return dict(families=families, series=series, params=params, issues=issues,
                derived_properties=derived, aliases=aliases)


def write_inventory(con: sqlite3.Connection, path: Path, redistributable_only: bool = False) -> None:
    """Vue dénormalisée, une ligne par référence : le catalogue tel qu'il sera lu.

    `redistributable_only` exclut les séries dont la source n'autorise pas la
    redistribution (données locales de `data/staging`).
    """
    cur = con.cursor()
    params = ["h", "b", "tw", "tf", "t", "r", "r1", "r2", "ro", "ri", "D", "a",
              "slope_pct", "x_tf"]
    header = ["profile_id", "series_id", "family_id", "shape_id", "process", "standard",
              "category", "commercial_ref",
              "designation", "aliases", "geometry_status", "geometry_source", "verified",
              "radius_origin", *params, "source_ref"]
    rows = []
    fetched = cur.execute("""
        SELECT p.profile_id, p.series_id, s.family_id, s.shape_id, s.process, st.standard_id,
               s.category, s.commercial_ref,
               p.designation, p.geometry_status, p.geometry_source, p.verified, s.source_ref,
               g.h, g.b, g.tw, g.tf, g.t, g.r, g.r1, g.r2, g.ro, g.ri, g."D", g.a,
               g.slope_pct, g.x_tf
        FROM profile p
        JOIN series s ON s.series_id = p.series_id
        JOIN source sr ON sr.source_id = s.source_id
        LEFT JOIN standard st ON st.standard_id = s.standard_id
        LEFT JOIN v_profile_geometry g ON g.profile_id = p.profile_id
        WHERE (? = 0 OR sr.redistribution = 'allowed')
        ORDER BY s.family_id, p.series_id, p.sort_key, p.designation""",
        (1 if redistributable_only else 0,)).fetchall()
    alias_cur = con.cursor()
    for r in fetched:
        profile_id = r[0]
        aliases = [a[0] for a in alias_cur.execute(
            "SELECT alias FROM profile_alias WHERE profile_id = ? ORDER BY alias", (profile_id,))]
        origin = alias_cur.execute("""
            SELECT group_concat(param) FROM profile_param
            WHERE profile_id = ? AND origin = 'series_rule'""", (profile_id,)).fetchone()[0]
        rows.append([
            profile_id, r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], "|".join(aliases),
            r[9], r[10], r[11], "series_rule:" + origin if origin else "table",
            *[fmt_num(v) for v in r[13:]], r[12],
        ])
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def fmt_num(value) -> str:
    if value is None:
        return ""
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text


def hf_cf_overlap(con: sqlite3.Connection) -> dict:
    cur = con.cursor()
    out = {}
    for base in ("SHS", "RHS", "CHS"):
        hf = {r[0] for r in cur.execute(
            "SELECT designation FROM profile WHERE series_id = ?", (f"{base}-HF",))}
        cf = {r[0] for r in cur.execute(
            "SELECT designation FROM profile WHERE series_id = ?", (f"{base}-CF",))}
        out[base] = dict(hf=len(hf), cf=len(cf), common=len(hf & cf),
                         hf_only=len(hf - cf), cf_only=len(cf - hf))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--stats", type=Path, default=DEFAULT_STATS)
    parser.add_argument("--staging", type=Path, default=STAGING,
                        help="dépôt local de séries sous licence (défaut : data/staging)")
    args = parser.parse_args()
    try:
        stats = build(args.db, args.repo, args.stats, args.staging)
    except LocalDataError as exc:
        # La base vient d'être recréée par cette exécution : on la retire pour
        # ne pas laisser un catalogue partiel derrière un import refusé.
        if _ACTIVE_CON is not None:
            _ACTIVE_CON.close()
        if args.db.exists():
            args.db.unlink()
        for extra in (args.stats.parent / "catalogue_inventory.csv",
                      args.stats.parent / "catalogue_inventory_redistributable.csv"):
            if extra.exists():
                extra.unlink()
        sys.exit(f"série locale invalide : {exc}\n"
                 f"Aucune base n'a été écrite. Corrigez la ligne indiquée.")
    print(f"base    : {args.db}")
    print(f"stats   : {args.stats}")
    print(f"profils : {stats['profiles_imported']}")
    for fam in stats["families"]:
        print(f"  {fam['family']:<7} {fam['profiles']:>5} références "
              f"({fam['complete']} complètes, {fam['rule_radii']} avec rayons par règle)")


if __name__ == "__main__":
    main()
