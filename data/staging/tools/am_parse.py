"""Utilitaires de lecture des flux du catalogue ArcelorMittal 2020.

Expose uniquement le socle partagé par `am_extract.py` :
`PDF`, `DATA`, `STREAMS`, `row_runs()` et `num()`.

Le PDF n'est pas livré avec le projet. Pour rejouer l'extraction, le placer dans
`data/sources/Arcelor-Catalogue-Web-2020-avec-liens-bouton-light.pdf` et vérifier
son empreinte SHA-256 (voir `docs/sources.md` §12).
"""
import re
import zlib
from pathlib import Path

from extract_pdf import extract_stream_text

ROOT = Path(__file__).resolve().parents[3]
PDF = ROOT / "data" / "sources" / "Arcelor-Catalogue-Web-2020-avec-liens-bouton-light.pdf"
DATA = PDF.read_bytes()
STREAMS = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", DATA, re.S)


def row_runs(sid):
    """Regroupe les fragments de texte d'un flux par ligne (ordonnée arrondie)."""
    content = zlib.decompress(STREAMS[sid])
    runs = extract_stream_text(content)
    rows = {}
    for x, y, size, text in runs:
        rows.setdefault(round(y * 2), []).append((x, text.strip()))
    out = []
    for key in sorted(rows, reverse=True):
        out.append((key / 2, sorted(rows[key])))
    return out


def num(text):
    """Convertit un fragment numérique du PDF ; `None` si ce n'est pas un nombre."""
    t = text.replace(" ", "").replace("\u2212", "-")
    if re.fullmatch(r"-?\d+(?:[.,]\d+)?", t):
        return float(t.replace(",", "."))
    return None
