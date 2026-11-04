"""Extraction de texte d'un PDF avec la bibliothèque standard (zlib + parseur minimal).

Usage : python extract_pdf.py <pdf> <sortie.txt>
Produit un fichier texte où chaque flux est précédé d'un marqueur <<<STREAM n>>>.
Aucune dépendance externe, aucun réseau.
"""

import re
import sys
import zlib

TOKEN_RE = re.compile(
    rb"""
    (?P<str>\((?:\\.|[^\\()])*\))
  | (?P<hex><[0-9A-Fa-f\s]*>)
  | (?P<name>/[^\s/<>\[\]()%{}]*)
  | (?P<num>[-+]?\d*\.?\d+)
  | (?P<arr>[\[\]])
  | (?P<op>[A-Za-z'"*][A-Za-z0-9'"*]*)
  | (?P<ws>\s+)
  | (?P<other>.)
    """,
    re.X | re.S,
)

ESC = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f",
       b"(": b"(", b")": b")", b"\\": b"\\"}


def decode_pdf_string(raw: bytes) -> str:
    """Résout les échappements PDF puis décode en cp1252 (polices non incorporées)."""
    out = bytearray()
    i = 0
    while i < len(raw):
        c = raw[i:i + 1]
        if c != b"\\":
            out += c
            i += 1
            continue
        i += 1
        if i >= len(raw):
            break
        c = raw[i:i + 1]
        if c in ESC:
            out += ESC[c]
            i += 1
        if c in b"01234567":
            j = i
            while j < len(raw) and j < i + 3 and raw[j:j + 1] in b"01234567":
                j += 1
            out.append(int(raw[i:j], 8) & 0xFF)
            i = j
        elif c == b"\n":
            i += 1
        elif c == b"\r":
            i += 2 if raw[i + 1:i + 2] == b"\n" else 1
        else:
            out += c
            i += 1
    return out.decode("cp1252", "replace")


def decode_hex(raw: bytes) -> str:
    digits = re.sub(rb"\s", b"", raw[1:-1])
    if len(digits) % 2:
        digits += b"0"
    data = bytes.fromhex(digits.decode("ascii"))
    # CID/UTF-16BE fréquent : on garde le cas ASCII simple
    try:
        return data.decode("utf-16-be") if b"\x00" in data else data.decode("cp1252", "replace")
    except Exception:
        return data.decode("latin-1", "replace")


def extract_stream_text(content: bytes) -> list[tuple[float, float, float, str]]:
    """Retourne [(x, y, taille, texte)] pour un flux de contenu."""
    runs: list[tuple[float, float, float, str]] = []
    stack: list = []
    font_size = 10.0
    leading = 12.0
    tm = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    tlm = tm[:]
    pending_line = False

    def show(text: str) -> None:
        if text:
            runs.append((tm[4], tm[5], font_size, text))

    for m in TOKEN_RE.finditer(content):
        kind = m.lastgroup
        tok = m.group()
        if kind == "ws":
            continue
        if kind == "num":
            stack.append(float(tok))
        elif kind == "name":
            stack.append(tok)
        elif kind == "str":
            stack.append(("s", decode_pdf_string(tok[1:-1])))
        elif kind == "hex":
            stack.append(("s", decode_hex(tok)))
        elif kind == "arr":
            stack.append(tok)
        elif kind == "op":
            op = tok
            if op == b"BT":
                tm = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
                tlm = tm[:]
            elif op == b"Tf" and len(stack) >= 2:
                font_size = stack[-1] if isinstance(stack[-1], float) else font_size
            elif op == b"TL" and stack:
                leading = stack[-1] if isinstance(stack[-1], float) else leading
            elif op == b"Tm" and len(stack) >= 6:
                vals = [v for v in stack[-6:] if isinstance(v, float)]
                if len(vals) == 6:
                    tm = vals[:]
                    tlm = vals[:]
            elif op in (b"Td", b"TD"):
                vals = [v for v in stack[-2:] if isinstance(v, float)]
                if len(vals) != 2:
                    stack.clear()
                    continue
                tx, ty = vals
                if op == b"TD":
                    leading = -ty
                tlm = [tlm[0], tlm[1], tlm[2], tlm[3],
                       tlm[4] + tx * tlm[0] + ty * tlm[2],
                       tlm[5] + tx * tlm[1] + ty * tlm[3]]
                tm = tlm[:]
            elif op == b"T*":
                tlm = [tlm[0], tlm[1], tlm[2], tlm[3],
                       tlm[4] - leading * tlm[2], tlm[5] - leading * tlm[3]]
                tm = tlm[:]
            elif op == b"Tj" and stack and isinstance(stack[-1], tuple):
                show(stack[-1][1])
            elif op == b"'" and stack and isinstance(stack[-1], tuple):
                tlm = [tlm[0], tlm[1], tlm[2], tlm[3],
                       tlm[4] - leading * tlm[2], tlm[5] - leading * tlm[3]]
                tm = tlm[:]
                show(stack[-1][1])
            elif op == b'"' and stack and isinstance(stack[-1], tuple):
                show(stack[-1][1])
            elif op == b"TJ" and stack:
                # dernier élément = tableau éventuel
                parts = []
                for item in reversed(stack):
                    if isinstance(item, tuple):
                        parts.append(item[1])
                    elif item == b"]":
                        continue
                    elif item == b"[":
                        break
                if parts:
                    show("".join(reversed(parts)))
            if op not in (b"[",):
                stack.clear()
    return runs


def layout(runs, y_tol=1.2):
    """Regroupe les fragments par ligne (y décroissant) et les trie par x."""
    lines = []
    for x, y, size, text in runs:
        placed = False
        for line in lines:
            if abs(line["y"] - y) <= y_tol:
                line["items"].append((x, text))
                placed = True
                break
        if not placed:
            lines.append({"y": y, "items": [(x, text)]})
    lines.sort(key=lambda l: -l["y"])
    out = []
    for line in lines:
        items = sorted(line["items"], key=lambda t: t[0])
        buf = ""
        prev_end = None
        for x, text in items:
            if prev_end is not None and x - prev_end > 1.5 and not buf.endswith(" "):
                buf += " "
            buf += text
            prev_end = x + 0.5 * len(text)
        out.append(buf.rstrip())
    return out


def main() -> None:
    pdf, out = sys.argv[1], sys.argv[2]
    data = open(pdf, "rb").read()
    streams = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S)
    written = kept = 0
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        for idx, raw in enumerate(streams):
            try:
                content = zlib.decompress(raw)
            except Exception:
                try:
                    content = zlib.decompress(raw, -15)
                except Exception:
                    continue
            if b"Tj" not in content and b"TJ" not in content:
                continue
            runs = extract_stream_text(content)
            if not runs:
                continue
            kept += 1
            fh.write(f"\n<<<STREAM {idx}>>>\n")
            for line in layout(runs):
                if line.strip():
                    fh.write(line + "\n")
                    written += 1
    print(f"flux texte conservés : {kept} ; lignes : {written}")


if __name__ == "__main__":
    main()
