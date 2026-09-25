#!/usr/bin/env python3
"""
Extreu el menú de cada dia a partir de la imatge (o PDF) del menú mensual.

L'algoritme no llegeix el menú "a ull": detecta la graella per OCR, en
tres passades.
  1. Una passada d'OCR sobre tota la imatge localitza la capçalera amb els
     noms dels dies de la setmana -> defineix els límits de les 5 columnes
     (Dilluns..Divendres), a més del mes/any del títol i el peu de pàgina.
  2. Una passada d'OCR per columna (retalls alts i estrets) hi busca
     números solts (1-31): són candidats a ser el "dia del mes" imprès a la
     cantonada de cada cel·la. Com que en un calendari setmanal la data =
     offset + fila*7 + columna, s'ajusta aquest "offset" per vot majoritari
     entre tots els candidats trobats a qualsevol columna/fila. Això
     permet recuperar la data correcta de cel·les on el número de dia no
     s'ha pogut llegir bé (o gens), sempre que n'hi hagi prou als altres
     dies de la mateixa setmana o de columnes veïnes per fer l'ajust. Amb
     els candidats ja agrupats per fila (per proximitat vertical) es
     calculen els límits Y de cada fila.
  3. Coneixent ja els límits de fila i columna, cada cel·la es retalla
     individualment i es torna a passar per OCR (un retall petit i homogeni
     dona resultats molt més fiables que un de gran i decorat, on tesseract
     tendeix a saltar-se línies senceres). El número de dia es filtra del
     text i la resta es recompon en ordre de lectura com el menú del dia.

Ús:
    python ocr_menu.py menu.jpg
    python ocr_menu.py menu.pdf --json sortida.json
    python ocr_menu.py menu.jpg --lang cat --debug

Depèn del binari `tesseract` (amb les dades d'idioma corresponents, p. ex.
`tesseract-ocr-cat`) instal·lat al sistema, a més dels paquets de
requirements.txt (pytesseract, opencv-python-headless, numpy, Pillow,
pdf2image).

Limitacions conegudes: aquestes imatges de menú solen tenir fons
decoratius (patrons, dibuixos) que degraden l'OCR. El resultat és un bon
punt de partida per revisar/corregir, no una transcripció garantida al
100%.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

import cv2
import numpy as np
import pytesseract

WEEKDAYS_CA = ["DILLUNS", "DIMARTS", "DIMECRES", "DIJOUS", "DIVENDRES"]
MONTHS_CA = {
    "GENER": 1, "FEBRER": 2, "MARC": 3, "ABRIL": 4, "MAIG": 5, "JUNY": 6,
    "JULIOL": 7, "AGOST": 8, "SETEMBRE": 9, "OCTUBRE": 10, "NOVEMBRE": 11,
    "DESEMBRE": 12,
}
FOOTER_KEYWORDS = ["ALLERGENS", "ALLERGEN", "ALERGENOS", "ALERGIA"]
HOLIDAY_KEYWORDS = ["FESTA", "FESTIU", "TANCAT", "VACANCES"]

MIN_BADGE_CONF = 35
ROW_GAP_FRACTION = 0.45   # fraction of median row spacing used to split row clusters
ROW_TOP_MARGIN_FRACTION = 0.15  # how far above its badge a row's top boundary sits


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


def load_image(path: str) -> np.ndarray:
    """Load an image or the first page of a PDF as a BGR OpenCV array."""
    if path.lower().endswith(".pdf"):
        from pdf2image import convert_from_path
        pages = convert_from_path(path, dpi=300, first_page=1, last_page=1)
        if not pages:
            raise ValueError(f"No s'ha pogut convertir el PDF: {path}")
        pil_img = pages[0].convert("RGB")
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    img = cv2.imread(path)
    if img is None:
        raise ValueError(f"No s'ha pogut llegir la imatge: {path}")
    return img


def upscale_if_small(img: np.ndarray, min_width: int = 1600) -> tuple[np.ndarray, float]:
    h, w = img.shape[:2]
    if w >= min_width:
        return img, 1.0
    scale = min_width / w
    resized = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return resized, scale


def ocr_words(img: np.ndarray, lang: str, psm: int = 3) -> list[Word]:
    data = pytesseract.image_to_data(
        img, lang=lang, config=f"--psm {psm}", output_type=pytesseract.Output.DICT
    )
    words = []
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        conf = float(data["conf"][i])
        if not text or conf < 0:
            continue
        line_id = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        words.append(Word(text, data["left"][i], data["top"][i],
                           data["width"][i], data["height"][i], conf, line_id))
    return words


def find_weekday_header(words: list[Word]) -> dict[str, Word]:
    """Best match per weekday name among OCR words (accent/case insensitive)."""
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


def crop_column(img: np.ndarray, x0: int, x1: int, y0: int, y1: int, scale: int = 2) -> np.ndarray:
    strip = img[max(y0, 0):y1, max(x0, 0):x1]
    return cv2.resize(strip, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)


def ocr_cell(img: np.ndarray, x0: int, x1: int, y0: int, y1: int,
             lang: str, pad: int = 6, scale: int = 3) -> list["Word"]:
    """OCR a single grid cell in isolation. Tesseract's page-segmentation gets
    confused (and silently drops whole lines) on the tall, decorated
    per-column strips used for row/column detection; cropping down to one
    cell at a time is far more reliable for the actual dish text."""
    h_img, w_img = img.shape[:2]
    x0p, x1p = max(int(x0) - pad, 0), min(int(x1) + pad, w_img)
    y0p, y1p = max(int(y0) - pad, 0), min(int(y1) + pad, h_img)
    if x1p <= x0p or y1p <= y0p:
        return []
    crop = img[y0p:y1p, x0p:x1p]
    scaled = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    raw_words = ocr_words(scaled, lang=lang, psm=6)
    return [
        Word(w.text, w.left // scale + x0p, w.top // scale + y0p,
             w.width // scale, w.height // scale, w.conf, w.line_id)
        for w in raw_words
    ]


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
    """Rebuild reading-order text using tesseract's own line grouping
    (far more reliable than re-deriving lines from raw pixel gaps, which
    breaks whenever an accented glyph makes a word's bounding box taller)."""
    lines: dict[tuple, list[Word]] = {}
    for w in words:
        lines.setdefault(w.line_id, []).append(w)

    ordered_lines = sorted(lines.values(), key=lambda line: min(w.top for w in line))
    out = []
    for line in ordered_lines:
        line_sorted = sorted(line, key=lambda w: w.left)
        out.append(" ".join(w.text for w in line_sorted))
    return " ".join(out)


def extract_menu(image_path: str, lang: str = "cat", debug: bool = False) -> dict:
    img = load_image(image_path)
    img, _scale = upscale_if_small(img)
    h, w = img.shape[:2]

    full_words = ocr_words(img, lang=lang, psm=3)
    header = find_weekday_header(full_words)
    if len(header) < 5:
        raise ValueError(
            f"Només s'han trobat {len(header)}/5 capçaleres de dia de la setmana; "
            "no es pot determinar la graella."
        )

    month_name, month_num, year = find_month_year(full_words)
    header_bottom = max(header[wd].bottom for wd in WEEKDAYS_CA)
    footer_top = find_footer_top(full_words, h)
    col_bounds = compute_column_bounds(header, w)

    # --- Per-column OCR pass, used only to find day-number badges and thus
    # the row boundaries (the actual dish text is re-OCR'd per cell below,
    # since tesseract handles small homogeneous crops far better than these
    # tall decorated strips). ---
    badge_candidates: list[tuple[int, int, float]] = []  # (col, value, top_in_full_image)
    for col in range(5):
        x0, x1 = int(col_bounds[col]), int(col_bounds[col + 1])
        crop_scale = 2
        strip = crop_column(img, x0, x1, int(header_bottom), int(footer_top), scale=crop_scale)
        strip_words_raw = ocr_words(strip, lang=lang, psm=4)
        for sw in strip_words_raw:
            val = is_bare_day_number(sw.text)
            if val is not None and sw.conf >= MIN_BADGE_CONF:
                top = sw.top // crop_scale + int(header_bottom)
                badge_candidates.append((col, val, top))

    if not badge_candidates:
        raise ValueError("No s'ha detectat cap número de dia a la graella.")

    # --- Row clustering across all columns' badge candidates ---
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

    if debug:
        print(f"[debug] columns bounds: {col_bounds}", file=sys.stderr)
        print(f"[debug] header_bottom={header_bottom} footer_top={footer_top}", file=sys.stderr)
        print(f"[debug] {len(badge_candidates)} badge candidates, {n_rows} row clusters, "
              f"median_gap={median_gap:.0f}", file=sys.stderr)
        print(f"[debug] date offset={offset} confidence={confidence:.2f}", file=sys.stderr)

    # --- Row Y boundaries: row_top[i] = anchor[i] - margin, clamped to header/footer ---
    row_margin = median_gap * ROW_TOP_MARGIN_FRACTION
    row_top = [max(header_bottom, row_anchor_top[i] - row_margin) for i in range(n_rows)]
    row_bounds = row_top + [footer_top]

    # last day of month, to drop out-of-range (row, col) combinations (e.g. padding cells)
    last_day = _days_in_month(month_num, year)

    days: list[DayCell] = []
    for row_idx in range(n_rows):
        y0, y1 = row_bounds[row_idx], row_bounds[row_idx + 1]
        for col in range(5):
            date = offset + row_idx * 7 + col
            if last_day is not None and not (1 <= date <= last_day):
                continue

            cell_words = ocr_cell(img, col_bounds[col], col_bounds[col + 1], y0, y1, lang=lang)

            # The day-number badge sits near the top-right corner of the cell
            # and is often misread: either as digits merged onto the same
            # tesseract line as the first dish words ("25" glued to "AMB."),
            # or as a short garbled "word" standing alone on its own line
            # ("28" -> "Va.)"). Drop both shapes rather than only a
            # successfully-read bare number: (a) any bare 1-2 digit token in
            # the top ~25% of the cell, wherever it sits on its line, and
            # (b) the sole word of a line up there positioned in the right
            # ~35% of the column (real dish lines start flush left and
            # normally have several words, so an isolated right-aligned
            # word can only be the badge).
            badge_zone = y0 + (y1 - y0) * 0.25
            col_x0, col_x1 = col_bounds[col], col_bounds[col + 1]
            lines_by_id: dict[tuple, list[Word]] = {}
            for wd in cell_words:
                lines_by_id.setdefault(wd.line_id, []).append(wd)

            def is_badge_word(wd: Word) -> bool:
                if wd.top > badge_zone:
                    return False
                # An exact match to the date already derived for this cell is
                # unambiguous, regardless of where it sits. Any other bare
                # number (e.g. the "4" in "ALS 4 FORMATGES") is real dish
                # text, even if it happens to fall in the top-right area.
                if is_bare_day_number(wd.text) == date:
                    return True
                # Otherwise, only a badge misread as a garbled non-numeric
                # "word" (e.g. "28" -> "Va.)") can still be caught: the sole
                # word on its line, positioned in the right ~35% of the
                # column (real dish lines start flush left and normally
                # have several words).
                line_words = lines_by_id[wd.line_id]
                if len(line_words) == 1:
                    rel_x = (wd.cx - col_x0) / (col_x1 - col_x0)
                    return rel_x > 0.65
                return False

            cell_words = [wd for wd in cell_words if not is_badge_word(wd)]
            if not cell_words:
                continue

            raw_text = clean_join(cell_words)
            avg_conf = sum(wd.conf for wd in cell_words) / len(cell_words)
            # Cells with no real menu (a blank pre-month/holiday square) still get
            # OCR'd, since decorative background lines can be misread as a
            # stray letter or two; require enough text at high enough confidence
            # before treating it as real content.
            if not raw_text.strip() or (len(raw_text.replace(" ", "")) < 4 and avg_conf < 70):
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

    days.sort(key=lambda d: (d.date if d.date is not None else 0))

    return {
        "month": month_name,
        "month_number": month_num,
        "year": year,
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


def _days_in_month(month_num: int | None, year: int | None) -> int | None:
    if not month_num:
        return None
    import calendar
    return calendar.monthrange(year or 2024, month_num)[1]


def main():
    parser = argparse.ArgumentParser(description="Extreu el menú diari d'una imatge/PDF per OCR.")
    parser.add_argument("image", help="Ruta a la imatge (jpg/png) o PDF del menú")
    parser.add_argument("--lang", default="cat", help="Idioma de tesseract (per defecte: cat)")
    parser.add_argument("--json", dest="json_path", help="Fitxer de sortida JSON (per defecte: stdout)")
    parser.add_argument("--debug", action="store_true", help="Mostra informació de diagnòstic")
    args = parser.parse_args()

    result = extract_menu(args.image, lang=args.lang, debug=args.debug)
    output = json.dumps(result, ensure_ascii=False, indent=2)

    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Menú extret: {len(result['days'])} dies -> {args.json_path}")
    else:
        print(output)


if __name__ == "__main__":
    main()
