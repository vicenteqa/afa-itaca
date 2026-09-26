#!/usr/bin/env python3
"""
Extreu el menú de cada dia a partir del PDF del menú mensual.

Llegeix directament la capa de text del PDF (exportat des d'una eina de
disseny, no un escaneig): no hi ha cap OCR ni conjectura de píxels.

  1. Es localitza la capçalera amb els noms dels dies de la setmana ->
     defineix els límits de les 5 columnes (Dilluns..Divendres), a més del
     mes/any del títol i el peu de pàgina.
  2. Es busquen números solts (1-31) al text del PDF: són candidats a ser
     el "dia del mes" imprès a la cantonada de cada cel·la. Com que en un
     calendari setmanal la data = offset + fila*7 + columna, s'ajusta
     aquest "offset" per vot majoritari entre tots els candidats trobats.
     Amb els candidats ja agrupats per fila (per proximitat vertical) es
     calculen els límits Y de cada fila.
  3. Coneixent ja els límits de fila i columna, es filtra el número de dia
     del text de cada cel·la i la resta es recompon en ordre de lectura
     com el menú del dia.

Ús:
    python ocr_menu.py menu.pdf
    python ocr_menu.py menu.pdf --json sortida.json
    python ocr_menu.py menu.pdf --debug

Depèn només dels paquets de requirements.txt (pdfplumber, numpy).

Limitacions conegudes: si el PDF no té una capa de text (per exemple, és
un escaneig aplanat a imatge), no es pot extreure el menú.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

import numpy as np
import pdfplumber

WEEKDAYS_CA = ["DILLUNS", "DIMARTS", "DIMECRES", "DIJOUS", "DIVENDRES"]
MONTHS_CA = {
    "GENER": 1, "FEBRER": 2, "MARC": 3, "ABRIL": 4, "MAIG": 5, "JUNY": 6,
    "JULIOL": 7, "AGOST": 8, "SETEMBRE": 9, "OCTUBRE": 10, "NOVEMBRE": 11,
    "DESEMBRE": 12,
}
FOOTER_KEYWORDS = ["ALLERGENS", "ALLERGEN", "ALERGENOS", "ALERGIA"]
HOLIDAY_KEYWORDS = ["FESTA", "FESTIU", "TANCAT", "VACANCES"]

ROW_GAP_FRACTION = 0.45   # fraction of median row spacing used to split row clusters
ROW_TOP_MARGIN_FRACTION = 0.15  # how far above its badge a row's top boundary sits

MIN_PDF_TEXT_WORDS = 30  # below this, treat the PDF as image-only (no usable text layer)


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]", "", s.upper())


@dataclass
class Word:
    text: str
    left: int
    top: int
    width: int
    height: int
    conf: float
    line_id: tuple = (0, 0, 0)

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def cx(self) -> float:
        return self.left + self.width / 2

    @property
    def cy(self) -> float:
        return self.top + self.height / 2


@dataclass
class DayCell:
    date: int | None
    weekday: str
    col: int
    row: int
    holiday: bool = False
    items: list[str] = field(default_factory=list)
    allergens: list[int] = field(default_factory=list)
    raw_text: str = ""


def find_weekday_header(words: list[Word]) -> dict[str, Word]:
    """Best match per weekday name among the PDF's words (accent/case insensitive)."""
    hits: dict[str, Word] = {}
    for w in words:
        nt = normalize(w.text)
        if len(nt) < 5:
            continue
        for wd in WEEKDAYS_CA:
            nwd = normalize(wd)
            if nt == nwd or nwd.startswith(nt) or nt.startswith(nwd[:6]):
                if wd not in hits or w.conf > hits[wd].conf:
                    hits[wd] = w
    return hits


def find_month_year(words: list[Word]) -> tuple[str | None, int | None, int | None]:
    month_name = None
    month_num = None
    year = None
    for w in words:
        nt = normalize(w.text)
        if nt in MONTHS_CA:
            month_name = w.text.strip().capitalize()
            month_num = MONTHS_CA[nt]
        m = re.fullmatch(r"(19|20)\d{2}", w.text.strip())
        if m:
            year = int(m.group(0))
    return month_name, month_num, year


def compute_column_bounds(header: dict[str, Word], img_width: int) -> list[float]:
    centers = [header[wd].cx for wd in WEEKDAYS_CA]
    bounds = [0.0]
    for i in range(4):
        bounds.append((centers[i] + centers[i + 1]) / 2)
    bounds.append(float(img_width))
    return bounds


def find_footer_top(words: list[Word], img_height: int) -> float:
    tops = [w.top for w in words if any(k in normalize(w.text) for k in FOOTER_KEYWORDS)]
    if tops:
        return float(min(tops))
    return img_height * 0.90


def is_bare_day_number(text: str) -> int | None:
    t = text.strip().strip(".:,")
    if re.fullmatch(r"\d{1,2}", t):
        val = int(t)
        if 1 <= val <= 31:
            return val
    return None


def cluster_rows(anchors_y: list[float], min_gap: float) -> list[list[int]]:
    """Group indices of a sorted-by-y list of anchors into row clusters."""
    order = sorted(range(len(anchors_y)), key=lambda i: anchors_y[i])
    clusters: list[list[int]] = []
    cur: list[int] = []
    last_y = None
    for i in order:
        y = anchors_y[i]
        if last_y is not None and y - last_y > min_gap:
            clusters.append(cur)
            cur = []
        cur.append(i)
        last_y = y
    if cur:
        clusters.append(cur)
    return clusters


def fit_date_offset(candidates: list[tuple[int, int, int]]) -> tuple[int, float]:
    """candidates: list of (row_idx, col_idx, value). Returns (offset, confidence)."""
    votes = Counter(value - row * 7 - col for row, col, value in candidates)
    offset, support = votes.most_common(1)[0]
    confidence = support / len(candidates) if candidates else 0.0
    return offset, confidence


def fit_grid(badge_candidates: list[tuple[int, int, float]], header_bottom: float,
             footer_top: float) -> tuple[list[float], int, float]:
    """Turn (col, value, top) day-badge candidates into row Y-boundaries plus
    the fitted date/offset confidence. Returns (row_bounds, offset, confidence)
    where row_bounds has n_rows+1 entries and date(row, col) = offset + row*7 + col."""
    if not badge_candidates:
        raise ValueError("No s'ha detectat cap número de dia a la graella.")

    tops_sorted = sorted(t for _, _, t in badge_candidates)
    diffs = [b - a for a, b in zip(tops_sorted, tops_sorted[1:]) if b - a > 5]
    median_gap = float(np.median(diffs)) if diffs else 200.0
    min_gap = max(median_gap * ROW_GAP_FRACTION, 40.0)

    anchors_y = [t for _, _, t in badge_candidates]
    clusters = cluster_rows(anchors_y, min_gap)
    n_rows = len(clusters)

    row_of_candidate = [-1] * len(badge_candidates)
    row_anchor_top = [0.0] * n_rows
    for row_idx, members in enumerate(clusters):
        row_anchor_top[row_idx] = float(np.median([anchors_y[i] for i in members]))
        for i in members:
            row_of_candidate[i] = row_idx

    fit_input = [
        (row_of_candidate[i], badge_candidates[i][0], badge_candidates[i][1])
        for i in range(len(badge_candidates))
    ]
    offset, confidence = fit_date_offset(fit_input)

    row_margin = median_gap * ROW_TOP_MARGIN_FRACTION
    row_top = [max(header_bottom, row_anchor_top[i] - row_margin) for i in range(n_rows)]
    row_bounds = row_top + [footer_top]
    return row_bounds, offset, confidence


def build_output(days: list[DayCell], month_name: str | None, month_num: int | None,
                  year: int | None, confidence: float, source: str) -> dict:
    days = sorted(days, key=lambda d: (d.date if d.date is not None else 0))
    return {
        "month": month_name,
        "month_number": month_num,
        "year": year,
        "source": source,
        "date_offset_confidence": round(confidence, 2),
        "days": [
            {
                "date": d.date,
                "weekday": d.weekday,
                "holiday": d.holiday,
                "items": d.items,
                "allergens": d.allergens,
                "raw_text": d.raw_text,
            }
            for d in days
        ],
    }


def extract_allergens(text: str) -> list[int]:
    codes: set[int] = set()
    for match in re.finditer(r"\(([\d,\s]+)\)", text):
        for part in match.group(1).split(","):
            part = part.strip()
            if part.isdigit():
                codes.add(int(part))
    return sorted(codes)


def split_items(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!])\s+|\n+", text)
    items = []
    for p in parts:
        p = re.sub(r"\s+", " ", p).strip(" .")
        if p:
            items.append(p)
    return items


def clean_join(words: list[Word]) -> str:
    """Rebuild reading-order text by grouping words into lines (by rounded
    top position) and each line left-to-right."""
    lines: dict[tuple, list[Word]] = {}
    for w in words:
        lines.setdefault(w.line_id, []).append(w)

    ordered_lines = sorted(lines.values(), key=lambda line: min(w.top for w in line))
    out = []
    for line in ordered_lines:
        line_sorted = sorted(line, key=lambda w: w.left)
        out.append(" ".join(w.text for w in line_sorted))
    return " ".join(out)


def extract_menu(pdf_path: str, debug: bool = False) -> dict:
    """Extract the menu straight from a PDF's embedded text layer: many of
    these menus are exported from a design tool as real text, not a
    scanned/flattened image, in which case this is exact (no OCR guessing
    at all). Raises ValueError if the PDF has no (or too little) extractable
    text, since there's no image-scanning fallback."""
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        raw_words = page.extract_words()
        if len(raw_words) < MIN_PDF_TEXT_WORDS:
            raise ValueError(
                f"El PDF només té {len(raw_words)} paraules de text; "
                "sembla un escaneig sense capa de text i no es pot extreure el menú."
            )

        page_width, page_height = float(page.width), float(page.height)

    # Group words into lines by rounding their (vector-precise) top position;
    # unlike OCR there's no glyph-ascender noise to worry about.
    words: list[Word] = []
    for rw in raw_words:
        line_id = (0, 0, round(rw["top"]))
        words.append(Word(
            text=rw["text"], left=rw["x0"], top=rw["top"],
            width=rw["x1"] - rw["x0"], height=rw["bottom"] - rw["top"],
            conf=100.0, line_id=line_id,
        ))

    header = find_weekday_header(words)
    if len(header) < 5:
        raise ValueError(
            f"Només s'han trobat {len(header)}/5 capçaleres de dia de la setmana "
            "a la capa de text del PDF; no es pot determinar la graella."
        )

    month_name, month_num, year = find_month_year(words)
    header_bottom = max(header[wd].bottom for wd in WEEKDAYS_CA)
    footer_top = find_footer_top(words, page_height)
    col_bounds = compute_column_bounds(header, page_width)

    badge_candidates: list[tuple[int, int, float]] = []
    for wd in words:
        val = is_bare_day_number(wd.text)
        if val is None or wd.top <= header_bottom:
            continue
        col = next((c for c in range(5) if col_bounds[c] <= wd.cx < col_bounds[c + 1]), None)
        if col is not None:
            badge_candidates.append((col, val, wd.top))

    row_bounds, offset, confidence = fit_grid(badge_candidates, header_bottom, footer_top)
    n_rows = len(row_bounds) - 1

    if debug:
        print(f"[debug] PDF text layer: {len(raw_words)} words, columns {col_bounds}",
              file=sys.stderr)
        print(f"[debug] {len(badge_candidates)} badge candidates, {n_rows} row clusters",
              file=sys.stderr)
        print(f"[debug] date offset={offset} confidence={confidence:.2f}", file=sys.stderr)

    last_day = _days_in_month(month_num, year)

    days: list[DayCell] = []
    for row_idx in range(n_rows):
        y0, y1 = row_bounds[row_idx], row_bounds[row_idx + 1]
        for col in range(5):
            date = offset + row_idx * 7 + col
            if last_day is not None and not (1 <= date <= last_day):
                continue

            col_x0, col_x1 = col_bounds[col], col_bounds[col + 1]
            cell_words = [
                wd for wd in words
                if y0 <= wd.cy < y1 and col_x0 <= wd.cx < col_x1
                and is_bare_day_number(wd.text) != date
            ]
            if not cell_words:
                continue

            raw_text = clean_join(cell_words)
            if not raw_text.strip():
                continue

            is_holiday = any(k in normalize(raw_text) for k in HOLIDAY_KEYWORDS)
            days.append(DayCell(
                date=date,
                weekday=WEEKDAYS_CA[col].capitalize(),
                col=col,
                row=row_idx,
                holiday=is_holiday,
                items=[] if is_holiday else split_items(raw_text),
                allergens=extract_allergens(raw_text),
                raw_text=raw_text,
            ))

    return build_output(days, month_name, month_num, year, confidence, source="pdf_text")


def _days_in_month(month_num: int | None, year: int | None) -> int | None:
    if not month_num:
        return None
    import calendar
    return calendar.monthrange(year or 2024, month_num)[1]


def main():
    parser = argparse.ArgumentParser(description="Extreu el menú diari d'un PDF de la capa de text.")
    parser.add_argument("pdf", help="Ruta al PDF del menú")
    parser.add_argument("--json", dest="json_path", help="Fitxer de sortida JSON (per defecte: stdout)")
    parser.add_argument("--debug", action="store_true", help="Mostra informació de diagnòstic")
    args = parser.parse_args()

    result = extract_menu(args.pdf, debug=args.debug)
    output = json.dumps(result, ensure_ascii=False, indent=2)

    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Menú extret: {len(result['days'])} dies -> {args.json_path}")
    else:
        print(output)


if __name__ == "__main__":
    main()
