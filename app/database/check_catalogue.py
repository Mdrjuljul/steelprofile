"""Contrôle de cohérence du catalogue et des chiffres annoncés dans les docs.

Usage :
    python app/database/check_catalogue.py            # base de travail (avec data/staging)
    python app/database/check_catalogue.py --publish  # catalogue publiable (sans série locale)

Le mode `--publish` vérifie l'état destiné à la distribution : aucune série
locale, aucune série commerciale, aucun export restreint. Le mode par défaut
vérifie la base de travail, dans laquelle les séries commerciales locales
(`data/staging/AM-*`) sont légitimement présentes : les comptes de référence
sont alors augmentés de ceux de ces séries, sans jamais les confondre avec les
séries normalisées (§3.7).

Code de sortie 0 si tout est cohérent, 1 sinon.
"""

import csv
import io
import json
import os
import sqlite3
import sys
from pathlib import Path

ARGS = sys.argv[1:]
PUBLISH = "--publish" in ARGS
DB = Path(ARGS[ARGS.index("--db") + 1]) if "--db" in ARGS else Path("data/profiles.db")
DATA = DB.parent

# Séries commerciales locales : (profils, paramètres par profil, alias par profil).
COMMERCIAL = {
    "AM-RONDS": (69, 1, 1),
    "AM-CARRES": (28, 1, 1),
    "AM-PLATS": (288, 2, 1),
    "AM-LARGES-PLATS": (54, 2, 1),
    "AM-TES": (7, 8, 2),
}

con = sqlite3.connect(DB)
cur = con.cursor()
failures: list[str] = []


def check(label: str, got, exp) -> None:
    good = got == exp
    if not good:
        failures.append(f"{label}: {got!r} != {exp!r}")
    print(f"{'OK ' if good else 'ERR'} {label:<46} {got!r}")


commercial = dict(cur.execute(
    "SELECT s.series_id, COUNT(p.profile_id) FROM series s "
    "JOIN profile p USING (series_id) WHERE s.category = 'commercial' "
    "GROUP BY s.series_id"))
expected_commercial = {} if PUBLISH else dict((k, v[0]) for k, v in COMMERCIAL.items())
extra_profiles = sum(expected_commercial.values())
extra_params = sum(COMMERCIAL[k][0] * COMMERCIAL[k][1] for k in expected_commercial)
extra_alias = sum(COMMERCIAL[k][0] * COMMERCIAL[k][2] for k in expected_commercial)
extra_derived = 3 * extra_profiles
extra_series_issues = 3 * len(expected_commercial)
incomplete_t = sum(1 for _ in cur.execute(
    "SELECT 1 FROM profile WHERE series_id = 'AM-TES' AND geometry_status <> 'complete'")) \
    if expected_commercial else 0

print(f"== comptages ({'catalogue publiable' if PUBLISH else 'base de travail'}) ==")
check("profils", cur.execute("SELECT COUNT(*) FROM profile").fetchone()[0], 1792 + extra_profiles)
check("séries", cur.execute("SELECT COUNT(*) FROM series").fetchone()[0], 16 + len(expected_commercial))
check("paramètres", cur.execute("SELECT COUNT(*) FROM profile_param").fetchone()[0], 7411 + extra_params)
check("alias", cur.execute("SELECT COUNT(*) FROM profile_alias").fetchone()[0], 2147 + extra_alias)
check("propriétés dérivées", cur.execute("SELECT COUNT(*) FROM derived_property").fetchone()[0],
      53760 + extra_derived)
# La famille SOLID passe de « manque » (blocking) à « partiellement commerciale »
# (warning) dès qu'une série commerciale la couvre ; la famille T reste bloquante.
solid_commercial = bool(expected_commercial)
blocking_exp = 2 - (1 if solid_commercial else 0) + incomplete_t
warning_exp = 23 + (1 if solid_commercial else 0) + extra_series_issues
check("anomalies", cur.execute("SELECT COUNT(*) FROM catalog_issue").fetchone()[0],
      blocking_exp + warning_exp + 16)
for sev, exp in (("blocking", blocking_exp), ("warning", warning_exp), ("info", 16)):
    check(f"anomalies {sev}", cur.execute(
        "SELECT COUNT(*) FROM catalog_issue WHERE severity=?", (sev,)).fetchone()[0], exp)
check("familles", cur.execute("SELECT COUNT(*) FROM family").fetchone()[0], 7)
check("formes", cur.execute("SELECT COUNT(*) FROM shape").fetchone()[0], 13)
check("param_def", cur.execute("SELECT COUNT(*) FROM param_def").fetchone()[0], 58)
check("normes", cur.execute("SELECT COUNT(*) FROM standard").fetchone()[0], 14)
check("sources", cur.execute("SELECT COUNT(*) FROM source").fetchone()[0],
      5 + (1 if expected_commercial else 0))
check("règles rayon", cur.execute("SELECT COUNT(*) FROM corner_radius_rule").fetchone()[0], 2)
check("bandes rayon", cur.execute("SELECT COUNT(*) FROM corner_radius_band").fetchone()[0], 4)

print("\n== familles ==")
fam = {r[0]: (r[1], r[2]) for r in cur.execute(
    "SELECT family_id, profile_count, profile_complete FROM v_family_stats")}
t_refs = expected_commercial.get("AM-TES", 0)
solid_refs = sum(expected_commercial.get(k, 0) for k in ("AM-RONDS", "AM-CARRES", "AM-PLATS",
                                                        "AM-LARGES-PLATS"))
for code, exp, exp_complete in (("I", 39, 39), ("H", 72, 72), ("U", 32, 32), ("L", 81, 81),
                                ("T", t_refs, 0),
                                ("HOLLOW", 1506, 1506),
                                ("SOLID", 62 + solid_refs, 62 + solid_refs)):
    total, complete = fam[code]
    check(f"famille {code} total", total, exp)
    check(f"famille {code} complètes", complete, exp_complete)

print("\n== séries ==")
series = dict(cur.execute("SELECT series_id, profile_count FROM v_series_stats").fetchall())
for sid, exp in (("IPE", 18), ("IPN", 21), ("HEA", 24), ("HEB", 24), ("HEM", 24),
                 ("UPN", 18), ("UPE", 14), ("L-EQ", 42), ("L", 39), ("SHS-HF", 243),
                 ("SHS-CF", 163), ("RHS-HF", 496), ("RHS-CF", 260), ("CHS-HF", 114),
                 ("CHS-CF", 230), ("FLAT", 62)):
    check(f"série {sid}", series.get(sid), exp)
for sid, (n, _p, _a) in COMMERCIAL.items():
    if not PUBLISH:
        check(f"série commerciale {sid}", series.get(sid), n)

print("\n== statuts ==")
complete_exp = 1792 + extra_profiles - incomplete_t
check("complètes", cur.execute(
    "SELECT COUNT(*) FROM profile WHERE geometry_status='complete'").fetchone()[0], complete_exp)
check("rayons tabulés", cur.execute(
    "SELECT COUNT(*) FROM profile WHERE geometry_source='table'").fetchone()[0], 630 + extra_profiles)
check("rayons par règle", cur.execute(
    "SELECT COUNT(*) FROM profile WHERE geometry_source='table+rule'").fetchone()[0], 1162)
check("vérifiés", cur.execute("SELECT COUNT(*) FROM profile WHERE verified=1").fetchone()[0], 0)
check("paramètre requis NULL", cur.execute("""
    SELECT COUNT(*) FROM profile p
    JOIN profile_param pp ON pp.profile_id = p.profile_id
    JOIN param_def d ON d.shape_id = (SELECT shape_id FROM series s WHERE s.series_id = p.series_id)
                    AND d.param = pp.param
    WHERE d.required = 1 AND pp.value IS NULL""").fetchone()[0], 2 * incomplete_t)
check("paramètres non requis", cur.execute(
    "SELECT COUNT(*) FROM profile_param pp JOIN profile p USING(profile_id) "
    "JOIN series s USING(series_id) JOIN param_def d ON d.shape_id=s.shape_id "
    "AND d.param=pp.param WHERE d.required=0").fetchone()[0], 0)
check("doublons (série, désignation)", cur.execute(
    "SELECT COUNT(*) - COUNT(DISTINCT series_id || '|' || designation) FROM profile").fetchone()[0], 0)
check("alias en double dans une série", cur.execute("""
    SELECT COUNT(*) FROM (SELECT p.series_id, a.alias_key, COUNT(*) n
    FROM profile_alias a JOIN profile p USING(profile_id)
    GROUP BY p.series_id, a.alias_key HAVING n > 1)""").fetchone()[0], 0)

print("\n== valeurs extrêmes ==")
check("rayons > 0", cur.execute(
    "SELECT MIN(value) FROM profile_param "
    "WHERE param IN ('r','r1','r2','ro','ri')").fetchone()[0] > 0, True)
check("aucune dimension <= 0", cur.execute("""
    SELECT COUNT(*) FROM profile_param WHERE param <> 'slope_pct' AND value <= 0""").fetchone()[0], 0)
check("pentes UPN/IPN (5/8/14 %)", sorted(r[0] for r in cur.execute(
    "SELECT DISTINCT value FROM profile_param WHERE param='slope_pct' AND value IS NOT NULL")),
    [5.0, 8.0, 14.0])
check("pentes manquantes (T commercial)", cur.execute(
    "SELECT COUNT(*) FROM profile_param WHERE param='slope_pct' AND value IS NULL").fetchone()[0],
    8 * 0 + incomplete_t)
check("x_tf manquants (T commercial)", cur.execute(
    "SELECT COUNT(*) FROM profile_param WHERE param='x_tf' AND value IS NULL").fetchone()[0],
    incomplete_t)

print("\n== inventaire CSV ==")
with io.open(DATA / "catalogue_inventory.csv", encoding="utf-8") as fh:
    rows = list(csv.reader(fh))
check("lignes CSV", len(rows) - 1, 1792 + extra_profiles)
check("colonnes CSV", len(rows[0]), 29)
check("CSV complet", sum(1 for r in rows[1:] if r[rows[0].index("geometry_status")] == "complete"),
      complete_exp)

print("\n== stats JSON ==")
with io.open(DATA / "catalogue_stats.json", encoding="utf-8") as fh:
    stats = json.load(fh)
check("stats profils", stats["profiles_imported"], 1792 + extra_profiles)
check("stats séries", len(stats["series"]), 16 + len(expected_commercial))
check("stats anomalies", len(stats["issues"]), blocking_exp + warning_exp + 16)
check("stats séries locales", stats["local_only_series"], len(expected_commercial))

print("\n== séries locales et commerciales ==")
check("séries hors redistribution", cur.execute(
    "SELECT COUNT(*) FROM series s JOIN source sr ON sr.source_id = s.source_id "
    "WHERE sr.redistribution <> 'allowed'").fetchone()[0], len(expected_commercial))
check("sources local_only", cur.execute(
    "SELECT COUNT(*) FROM source WHERE usage = 'local_only'").fetchone()[0],
    1 if expected_commercial else 0)
check("séries commerciales", commercial, expected_commercial)
check("séries commerciales par catégorie", sorted(commercial), sorted(expected_commercial))
check("commerciales sans norme déclarée", cur.execute(
    "SELECT COUNT(*) FROM series WHERE category='commercial' AND standard_id IS NOT NULL"
).fetchone()[0], 0)
check("commerciales sans programme", cur.execute(
    "SELECT COUNT(*) FROM series WHERE category='commercial' "
    "AND (commercial_ref IS NULL OR commercial_ref = '')").fetchone()[0], 0)
check("anomalie COMMERCIAL_DATA par série commerciale", cur.execute(
    "SELECT COUNT(*) FROM catalog_issue WHERE code='COMMERCIAL_DATA'").fetchone()[0],
    len(expected_commercial))
check("anomalie LOCAL_ONLY_DATA par série locale", cur.execute(
    "SELECT COUNT(*) FROM catalog_issue WHERE code='LOCAL_ONLY_DATA'").fetchone()[0],
    len(expected_commercial))
check("T commercial incomplet bloqué", cur.execute(
    "SELECT COUNT(*) FROM catalog_issue WHERE code='MISSING_PARAMETER'").fetchone()[0],
    incomplete_t)
check("export redistribuable présent", os.path.exists(DATA / "catalogue_inventory_redistributable.csv"),
      bool(expected_commercial))
if expected_commercial:
    with io.open(DATA / "catalogue_inventory_redistributable.csv", encoding="utf-8") as fh:
        pub = list(csv.reader(fh))
    check("lignes export redistribuable", len(pub) - 1, 1792)
    check("aucune ligne commerciale exportée",
          sum(1 for r in pub[1:] if r[pub[0].index("category")] != "standard"), 0)
elif not PUBLISH:
    check("export redistribuable absent", True, True)

print("\n== intégrité ==")
check("integrity_check", cur.execute("PRAGMA integrity_check").fetchone()[0], "ok")
check("foreign_key_check", cur.execute("PRAGMA foreign_key_check").fetchall(), [])

if failures:
    print("\nRESULTAT : incohérences détectées")
    for line in failures:
        print("  -", line)
    sys.exit(1)

print("\nRESULTAT : tout est cohérent")
