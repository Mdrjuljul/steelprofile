"""Extraction contrôlée du catalogue ArcelorMittal 2020 (pages 49-52, 57, 59, 60).

Chaque ligne est confrontée à DEUX colonnes indépendantes publiées par le
catalogue :

  * la masse linéique (kg/m = A[mm2] x 0,00785) ;
  * la surface de peinture (m2/m = 2 x (perimetre utile) / 1000).

Une divergence de surface invalide la lecture des dimensions (on rejette).
Une divergence de masse seule est une coquille de la colonne « masse » : les
dimensions restent utilisables et la coquille est consignée en note.
"""
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from am_parse import num, row_runs  # noqa: E402

STREAM_PLATS = (193, 196, 198)
STREAM_LARGES = 201
STREAM_TES = 216
STREAM_RONDS = 222
STREAM_CARRES = 225

YMIN, YMAX = 60, 440


def cells(items, bands):
    """Assigne chaque valeur numérique à la colonne la plus proche."""
    got = {}
    for x, text in items:
        v = num(text)
        if v is None:
            continue
        name = min(bands, key=lambda b: abs(x - b[1]))[0]
        got.setdefault(name, []).append(v)
    return {k: v[0] for k, v in got.items() if len(v) == 1}, {
        k: v for k, v in got.items() if len(v) > 1}


# --------------------------------------------------------------- RONDS (p.59)
ROND_BANDS = [("d1", 82.7), ("m1", 111.7), ("s1", 142.9),
              ("d2", 196.3), ("m2", 230.3), ("s2", 261.5),
              ("d3", 312.8), ("m3", 346.7), ("s3", 377.9)]


def parse_ronds():
    ok, mass_bad, surf_bad, empty = [], [], [], []
    for y, items in row_runs(STREAM_RONDS):
        if not (YMIN <= y <= YMAX):
            continue
        got, _dup = cells(items, ROND_BANDS)
        for i in (1, 2, 3):
            d = got.get(f"d{i}")
            if d is None:
                continue
            m, A = got.get(f"m{i}"), got.get(f"s{i}")
            A_calc = math.pi * d * d / 4 / 100
            m_calc = A_calc * 0.785
            if A is None or m is None:
                empty.append((d, m, A))
                continue
            if abs(A - A_calc) > max(0.01, 0.02 * A_calc) or abs(m - m_calc) > max(0.01, 0.02 * m_calc):
                surf_bad.append((d, m, A, round(m_calc, 3), round(A_calc, 3)))
            else:
                ok.append({"D": d, "mass": m, "A": A})
    return ok, mass_bad, surf_bad, empty


# -------------------------------------------------------------- CARRÉS (p.60)
CARRE_BANDS = [("a1", 85.0), ("m1", 132.2), ("A1", 188.0),
               ("a2", 267.0), ("m2", 315.0), ("A2", 372.0)]


def parse_carres():
    ok, mass_bad, surf_bad, empty = [], [], [], []
    for y, items in row_runs(STREAM_CARRES):
        if not (YMIN <= y <= YMAX):
            continue
        got, _dup = cells(items, CARRE_BANDS)
        for i in (1, 2):
            a = got.get(f"a{i}")
            if a is None:
                continue
            m, A = got.get(f"m{i}"), got.get(f"A{i}")
            A_calc = a * a / 100
            m_calc = A_calc * 0.785
            if A is None or m is None:
                empty.append((a, m, A))
                continue
            surf_ok = abs(A - A_calc) <= max(0.01, 0.02 * A_calc)
            mass_ok = abs(m - m_calc) <= max(0.01, 0.02 * m_calc)
            if not surf_ok:
                surf_bad.append((a, m, A, round(m_calc, 3), round(A_calc, 3)))
            elif not mass_ok:
                mass_bad.append((a, m, A, round(m_calc, 3)))
                ok.append({"a": a, "mass": m, "A": A, "mass_printed": m})
            else:
                ok.append({"a": a, "mass": m, "A": A})
    return ok, mass_bad, surf_bad, empty


# ---------------------------------------------------- PLATS / LARGES PLATS
PLAT_BANDS = [("l1", 72.0), ("e1", 99.0), ("m1", 120.0), ("s1", 146.5),
              ("l2", 187.0), ("e2", 214.0), ("m2", 235.5), ("s2", 262.0),
              ("l3", 303.0), ("e3", 330.5), ("m3", 353.5), ("s3", 380.0)]
LARGE_BANDS = [("l1", 78.0), ("e1", 118.5), ("m1", 155.0), ("s1", 197.5),
               ("l2", 250.5), ("e2", 293.0), ("m2", 330.5), ("s2", 372.5)]


def parse_plats(sid, bands, ncol, carry_width, ymin=YMIN, ymax=YMAX):
    """`carry_width` : la largeur n'est imprimée que sur la première ligne du
    groupe et se reporte vers le bas (pages « LARGES PLATS »).

    Les deux colonnes dérivées (masse, surface de peinture) servent de contrôle
    croisé indépendant des dimensions lues :
      - les deux confirment  -> ligne validée ;
      - une seule confirme   -> dimensions validées, coquille consignée ;
      - aucune ne confirme   -> ligne à arbitrer (jamais importée en silence).
    """
    ok, mass_bad, surf_bad, both_bad, empty = [], [], [], [], []
    last_l = {}
    for y, items in row_runs(sid):
        if not (ymin <= y <= ymax):
            continue
        got, _dup = cells(items, bands)
        for i in range(1, ncol + 1):
            l, e = got.get(f"l{i}"), got.get(f"e{i}")
            if l is not None:
                last_l[i] = l
            elif carry_width:
                l = last_l.get(i)
            if l is None or e is None:
                if e is not None:
                    empty.append((l, e, got.get(f"m{i}"), got.get(f"s{i}")))
                continue
            m, s = got.get(f"m{i}"), got.get(f"s{i}")
            m_calc = l * e * 0.00785
            s_calc = 2 * (l + e) / 1000
            mass_ok = m is not None and abs(m - m_calc) <= max(0.02, 0.03 * m_calc)
            surf_ok = s is not None and abs(s - s_calc) <= 0.0015
            rec = {"b": l, "t": e, "mass": m, "surf": s,
                   "mass_calc": round(m_calc, 3), "surf_calc": round(s_calc, 4)}
            if mass_ok and surf_ok:
                ok.append(rec)
            elif mass_ok:
                surf_bad.append(rec)
                ok.append(dict(rec, coquille="surface"))
            elif surf_ok:
                mass_bad.append(rec)
                ok.append(dict(rec, coquille="masse"))
            else:
                both_bad.append(rec)
    return ok, mass_bad, surf_bad, both_bad, empty


# ----------------------------------------------------------------- TÉS (p.57)
TES_BANDS = [("b", 74.5), ("h", 99.5), ("e", 124.0), ("e1", 149.5),
             ("r1", 175.5), ("r2", 199.5), ("r3", 223.5), ("mass", 250.5),
             ("A", 283.0), ("surf", 315.5), ("m2t", 345.0), ("x", 376.0)]


def parse_tes():
    ok, surf_bad, both_bad = [], [], []
    for y, items in row_runs(STREAM_TES):
        if not (YMIN <= y <= YMAX):
            continue
        got, _dup = cells(items, TES_BANDS)
        b = got.get("b")
        if b is None:
            # la colonne b porte un astérisque (« hors NF EN 10055 »)
            raw = [t for x, t in items if abs(x - 74.5) < 8]
            for t in raw:
                if t.endswith("*") and num(t[:-1]) is not None:
                    b = num(t[:-1])
                    break
        if b is None or got.get("h") is None or got.get("e") is None or got.get("e1") is None:
            continue
        h, e, e1 = got["h"], got["e"], got["e1"]
        A_calc = (b * e1 + (h - e1) * e) / 100
        m_calc = A_calc * 0.785
        s_calc = 2 * (b + h) / 1000
        s = got.get("surf")
        rec = {"b": b, "h": h, "e": e, "e1": e1,
               "r1": got.get("r1"), "r2": got.get("r2"), "r3": got.get("r3"),
               "mass": got.get("mass"), "A": got.get("A"),
               "A_calc": round(A_calc, 3), "m_calc": round(m_calc, 3),
               "surf": s, "surf_calc": round(s_calc, 4),
               "hors_norme": any(t.endswith("*") for x, t in items if abs(x - 74.5) < 8)}
        A_ok = got.get("A") is not None and abs(got["A"] - A_calc) <= max(0.03, 0.02 * A_calc)
        m_ok = got.get("mass") is not None and abs(got["mass"] - m_calc) <= max(0.02, 0.03 * m_calc)
        s_ok = s is not None and abs(s - s_calc) <= 0.06
        rec["A_ok"], rec["m_ok"], rec["s_ok"] = A_ok, m_ok, s_ok
        if s_ok:
            ok.append(rec)
        else:
            both_bad.append(rec)
    return ok, surf_bad, both_bad


def rapport():
    ronds, r_mb, r_sb, r_e = parse_ronds()
    carres, c_mb, c_sb, c_e = parse_carres()
    print(f"RONDS   : {len(ronds)} lues | rejets {len(r_sb)} | vides {len(r_e)}")
    for r in r_sb:
        print("   REJET", r)
    print(f"CARRÉS  : {len(carres)} lues | coquilles masse {len(c_mb)} | rejets {len(c_sb)}")
    for r in c_mb:
        print("   masse fausse", r)
    for r in c_sb:
        print("   REJET", r)

    total_plats = 0
    for sid in STREAM_PLATS:
        ok, mb, sb, bb, em = parse_plats(sid, PLAT_BANDS, 3, False)
        total_plats += len(ok)
        print(f"PLATS p.{sid}: {len(ok)} retenues | coquille masse {len(mb)} | coquille surface {len(sb)} | à arbitrer {len(bb)} | vides {len(em)}")
        for r in bb:
            print("   ARBITRER", r)
        for r in mb:
            print("   masse fausse", r)
        for r in sb:
            print("   surface fausse", r)
    print("PLATS total retenu:", total_plats)

    ok, mb, sb, bb, em = parse_plats(STREAM_LARGES, LARGE_BANDS, 2, True)
    print(f"LARGES PLATS: {len(ok)} retenues | coquille masse {len(mb)} | coquille surface {len(sb)} | à arbitrer {len(bb)} | vides {len(em)}")
    for r in bb:
        print("   ARBITRER", r)
    for r in mb:
        print("   masse fausse", r)
    for r in sb:
        print("   surface fausse", r)

    tes, t_sb, t_bb = parse_tes()
    print(f"TÉS     : {len(tes)} lues")
    for r in tes:
        print(f"   {r['b']:>4.0f}x{r['h']:<4.0f} e={r['e']:<4} e1={r['e1']:<4} r1={r['r1']:<4} r2={r['r2']:<3} r3={r['r3']:<5} "
              f"A={r['A']} (calc {r['A_calc']}) m={r['mass']} (calc {r['m_calc']}) surf={r['surf']} (calc {r['surf_calc']}) "
              f"A_ok={r['A_ok']} m_ok={r['m_ok']} s_ok={r['s_ok']} *={r['hors_norme']}")
    for r in t_sb:
        print("   REJET", r)
    for r in t_bb:
        print("   ARBITRER", r)

    for label, keyset in (("RONDS", [r["D"] for r in ronds]),
                          ("CARRÉS", [r["a"] for r in carres]),
                          ("TÉS", [(r["b"], r["h"], r["e"]) for r in tes])):
        dup = {k for k in keyset if keyset.count(k) > 1}
        print(f"doublons {label}: {sorted(dup) if dup else 'aucun'}")


if __name__ == "__main__":
    rapport()
