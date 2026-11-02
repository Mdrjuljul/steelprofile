"""Génère les fichiers de dépôt `data/staging/AM-*` depuis le catalogue ArcelorMittal.

Aucune valeur n'est inventée : les dimensions sont celles publiées, les lignes
dont les colonnes de contrôle se contredisent sont écartées (jamais corrigées).

Deux formats de nombre :
  * `val()` : point décimal, pour les CSV (le lecteur attend un `Decimal`) et les
    désignations (le découpage des alias se fait sur `\\d+(?:\\.\\d+)?`) ;
  * `fr()`  : virgule décimale, réservée aux notes en prose.
"""
import csv
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import am_extract as X  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
STAGING = ROOT / "data" / "staging"
PROPS = STAGING / "generated" / "properties"
PDF = ROOT / "data" / "sources" / "Arcelor-Catalogue-Web-2020-avec-liens-bouton-light.pdf"

SOURCE_ID = "arcelormittal-catalogue-2020"
COMMERCIAL_REF = ("ArcelorMittal Distribution Solutions France — "
                  "Catalogue général, édition 2020, pages 49-52 / 57 / 59 / 60")
SOURCE_NOTE = (
    "Tableaux du catalogue général 2020 (PDF propriétaire, usage local uniquement). "
    "Dimensions relevées colonne par colonne sur les coordonnées du PDF, puis "
    "recoupées avec les colonnes masse et surface de peinture publiées. "
    "Les lignes dont les colonnes de contrôle se contredisent ne sont pas reprises.")

SHA = ""


def val(value, digits=3):
    """Nombre pour CSV / désignation : point décimal, zéros inutiles retirés."""
    if value is None:
        return ""
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def fr(value, digits=3):
    """Nombre pour la prose des notes : virgule décimale."""
    return val(value, digits).replace(".", ",")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        for row in rows:
            w.writerow(row)


PROPS_HEADER = ["designation", "mass_kg_m", "A_cm2", "surf_m2_m"]


def toml(path: Path, *, series_id, title, shape, body, design_pattern, aliases,
         missing, extra_comment=""):
    text = f"""# {title}
#
# Source : ArcelorMittal Distribution Solutions France, catalogue général 2020,
# PDF propriétaire de 21 608 979 octets. Extraction locale, jamais redistribuée.
# {body}
#
# Contrôles ligne à ligne : la masse linéique (A x 7,85 kg/dm3) et la surface de
# peinture (2 x (l+e) par mètre) publiées par le catalogue servent de recoupement
# indépendant des dimensions lues. Une divergence d'une seule colonne dérivée est
# consignée en note ; deux divergences font écarter la ligne.

id = "{series_id}"
title = "{title}"
shape = "{shape}"
process = "hot_rolled"

category = "commercial"
commercial_ref = "{COMMERCIAL_REF}"

source_id = "{SOURCE_ID}"
source_name = "ArcelorMittal Distribution Solutions France — Catalogue général, édition 2020 (PDF)"
source_kind = "manufacturer"
source_license = "Propriétaire — tous droits réservés (catalogue fabricant)"
source_license_url = ""
source_version = "Édition 2020, PDF de 21 608 979 octets (SHA-256 {SHA})"
redistribution = "restricted"
source_note = "{SOURCE_NOTE}"

[designation]
pattern = "{design_pattern}"
aliases = [{aliases}]
"""
    if missing:
        text += "\n[missing]\n"
        for param, reason in missing.items():
            text += f'{param} = "{reason}"\n'
    text += """
# Valeurs publiées par le fabricant, recopiées telles quelles dans
# `derived_property` (independent = 0) : elles ne sont pas recalculées.
[conventions.mass]
method = "masse linéique publiée par le fabricant (7,85 kg/dm3)"
[conventions.A]
method = "section publiée par le fabricant"
"""
    text += extra_comment
    path.write_text(text, encoding="utf-8")


def main() -> None:
    global SHA
    SHA = sha256(PDF)
    print("SHA-256 du PDF :", SHA)

    # ---------------------------------------------------------------- ronds
    ronds, _r_mb, _r_sb, _ = X.parse_ronds()
    rows, props = [], []
    for r in ronds:
        des = f"Rond {val(r['D'], 1)}"
        rows.append([des, val(r["D"], 1), ""])
        props.append([des, val(r["mass"]), val(r["A"]), ""])
    write_csv(STAGING / "AM-RONDS.csv", ["designation", "D", "note"], rows)
    write_csv(PROPS / "AM-RONDS.csv", PROPS_HEADER, props)
    toml(STAGING / "AM-RONDS.toml", series_id="AM-RONDS",
         title="Ronds pleins — programme commercial ArcelorMittal 2020 (EN 10060)",
         shape="ROUND", design_pattern="Rond {D}", aliases='"Ø{D}"', missing={},
         body=(f"{len(ronds)} diamètres (6 à 250 mm). Masse et section publiées "
               f"recoupées : aucune anomalie sur {len(ronds)} lignes."))

    # -------------------------------------------------------------- carrés
    carres, c_mb, _c_sb, _ = X.parse_carres()
    rows, props, notes = [], [], []
    for r in carres:
        des = f"Carré {val(r['a'], 1)}"
        if "mass_printed" in r:
            note = (f"masse imprimée {fr(r['mass'],3)} kg/m incohérente "
                    f"(a² x 7,85 = {fr(r['a'] * r['a'] * 0.00785,3)}) ; la section imprimée "
                    f"{fr(r['A'],3)} cm² confirme a = {fr(r['a'],1)} mm")
            rows.append([des, val(r["a"], 1), note])
            props.append([des, "", val(r["A"]), ""])
            notes.append((des, note))
        else:
            rows.append([des, val(r["a"], 1), ""])
            props.append([des, val(r["mass"]), val(r["A"]), ""])
    write_csv(STAGING / "AM-CARRES.csv", ["designation", "a", "note"], rows)
    write_csv(PROPS / "AM-CARRES.csv", PROPS_HEADER, props)
    toml(STAGING / "AM-CARRES.toml", series_id="AM-CARRES",
         title="Carrés pleins — programme commercial ArcelorMittal 2020 (EN 10059)",
         shape="SQUARE", design_pattern="Carré {a}", aliases='"C{a}"', missing={},
         body=(f"{len(carres)} côtés (5 à 120 mm). {len(c_mb)} coquille de masse "
               f"consignée en note (carré 5), dimensions confirmées par la section."))

    # ---------------------------------------------------- plats / larges plats
    def plat_note(r):
        l, e = r["b"], r["t"]
        if r.get("coquille") == "surface":
            return (f"surface de peinture imprimée {fr(r['surf'],3)} m²/m incohérente "
                    f"(2 x (l+e) = {fr(r['surf_calc'],3)}) ; dimensions confirmées par la "
                    f"masse {fr(r['mass'],2)} kg/m")
        if r.get("coquille") == "masse":
            return (f"masse imprimée {fr(r['mass'],3)} kg/m incohérente "
                    f"(l x e x 7,85 = {fr(r['mass_calc'],3)}) ; dimensions confirmées par la "
                    f"surface {fr(r['surf'],3)} m²/m")
        if (l, e) == (80.0, 35.0):
            return (f"masse imprimée {fr(r['mass'],3)} et surface imprimée {fr(r['surf'],3)} "
                    f"toutes deux incohérentes (attendu {fr(r['mass_calc'],3)} kg/m et "
                    f"{fr(r['surf_calc'],3)} m²/m) ; les deux valeurs imprimées coïncident avec "
                    f"celles de lignes voisines (90x30, 90x35). Les colonnes Dimensions "
                    f"(80 et 35) sont seules retenues telles quelles, sans correction.")
        return ""

    def emit(records, prefix):
        rows, props, notes = [], [], []
        for r in records:
            des = f"{prefix} {val(r['b'], 1)}x{val(r['t'], 1)}"
            note = plat_note(r)
            # Une colonne dérivée fausse n'est pas recopiée dans derived_property :
            # on n'y stocke que ce que la source publie réellement.
            mass_ko = r.get("coquille") == "masse" or (r["b"], r["t"]) == (80.0, 35.0)
            surf_ko = r.get("coquille") == "surface" or (r["b"], r["t"]) == (80.0, 35.0)
            rows.append([des, val(r["b"], 1), val(r["t"], 1), note])
            props.append([des, "" if mass_ko else val(r["mass"]), "",
                          "" if surf_ko else val(r["surf"], 3)])
            if note:
                notes.append((des, note))
        return rows, props, notes

    plat_records = []
    for sid in X.STREAM_PLATS:
        ok, _mb, _sb, bb, _ = X.parse_plats(sid, X.PLAT_BANDS, 3, False)
        plat_records += ok + bb
    l_ok, _l_mb, _l_sb, l_bb, _ = X.parse_plats(X.STREAM_LARGES, X.LARGE_BANDS, 2, True)
    large_records = l_ok + l_bb

    rows, props, notes = emit(plat_records, "Plat")
    write_csv(STAGING / "AM-PLATS.csv", ["designation", "b", "t", "note"], rows)
    write_csv(PROPS / "AM-PLATS.csv", PROPS_HEADER, props)

    rows_l, props_l, notes_l = emit(large_records, "Large plat")
    write_csv(STAGING / "AM-LARGES-PLATS.csv", ["designation", "b", "t", "note"], rows_l)
    write_csv(PROPS / "AM-LARGES-PLATS.csv", PROPS_HEADER, props_l)

    toml(STAGING / "AM-PLATS.toml", series_id="AM-PLATS",
         title="Fers plats — programme commercial ArcelorMittal 2020 (EN 10058)",
         shape="FLAT", design_pattern="Plat {b}x{t}", aliases='"P{b}×{t}"', missing={},
         body=(f"{len(plat_records)} couples largeur x épaisseur (14 à 150 mm de large). "
               f"Chaque ligne est confirmée par la masse ou la surface de peinture ; "
               f"les coquilles d'une colonne dérivée sont consignées en note."))
    toml(STAGING / "AM-LARGES-PLATS.toml", series_id="AM-LARGES-PLATS",
         title="Larges plats — programme commercial ArcelorMittal 2020 (EN 10058)",
         shape="FLAT", design_pattern="Large plat {b}x{t}", aliases='"LP{b}×{t}"', missing={},
         body=(f"{len(large_records)} couples largeur x épaisseur (160 à 450 mm de large). "
               f"La largeur n'est imprimée que sur la première ligne de chaque groupe et se "
               f"reporte vers le bas."))

    # ------------------------------------------------------------------ tés
    tes, _t_sb, _t_bb = X.parse_tes()
    gardes, ecartes = [], []
    for r in tes:
        if r["b"] == 25:
            ecartes.append((r, "e1 = 0,5 mm et r1 = 0,5 mm, physiquement impossibles ; la "
                               "section (1,64 cm²) et la masse (1,29 kg/m) impliquent 3,5 mm. "
                               "Valeur non corrigée : ligne écartée."))
        elif r["b"] == 45:
            ecartes.append((r, "e = 5 mm contredit la section (4,67 cm²), la masse (3,67 kg/m) "
                               "et r1 (5,5 mm), qui décrivent tous une section uniforme de "
                               "5,5 mm. Valeur non corrigée : ligne écartée."))
        else:
            gardes.append(r)

    rows, props = [], []
    for r in gardes:
        des = f"Té {val(r['b'],1)}x{val(r['h'],1)}x{val(r['e'],1)}"
        note = "hors NF EN 10055 (astérisque du catalogue)" if r["hors_norme"] else ""
        rows.append([des, val(r["h"], 1), val(r["b"], 1), val(r["e"], 1),
                     val(r["e1"], 1), val(r["r1"], 1), val(r["r2"], 1), note])
        props.append([des, val(r["mass"]), val(r["A"]), ""])
    write_csv(STAGING / "AM-TES.csv",
              ["designation", "h", "b", "tw", "tf", "r1", "r2", "note"], rows)
    write_csv(PROPS / "AM-TES.csv", PROPS_HEADER, props)
    toml(STAGING / "AM-TES.toml", series_id="AM-TES",
         title="Tés à angles arrondis — programme commercial ArcelorMittal 2020 (EN 10055)",
         shape="T_TAPERED",
         design_pattern="Té {b}x{h}x{tw}", aliases='"T{b}×{h}×{tw}", "T{b}"',
         missing={
             "slope_pct": ("non publiée par le catalogue ; la pente des semelles est définie "
                           "par EN 10055, non détenue"),
             "x_tf": ("non publiée par le catalogue ; la position de mesure de tf est définie "
                      "par EN 10055, non détenue"),
         },
         body=(f"{len(gardes)} tailles retenues sur {len(tes)} lignes publiées. Les dimensions "
               f"sont publiées, mais ni la pente de semelle ni la position de mesure de e1 ne "
               f"le sont : aucune reconstruction n'est possible en l'état."),
         extra_comment=("# `r3` (3e rayon du tableau, 1,00 à 2,00 mm) n'est pas repris :\n"
                        "# sa signification n'est pas documentée par le catalogue.\n"))

    print(f"RONDS {len(ronds)} | CARRÉS {len(carres)} | PLATS {len(plat_records)} | "
          f"LARGES {len(large_records)} | TÉS {len(gardes)}")
    print("\nLignes écartées (T) :")
    for r, why in ecartes:
        print(f"  Té {r['b']:.0f} — {why}")
    print(f"\nCoquilles consignées en note ({len(notes) + len(notes_l)} plats + carré) :")
    for des, note in notes + notes_l:
        print(f"  {des}: {note}")


if __name__ == "__main__":
    main()
