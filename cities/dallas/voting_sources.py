"""Readers for the vote-center lists the counties publish as PDFs, shared by fetch_voting.py (in Actions).
Each returns rows {code, name, room, address, city, zip}; columns are read by their x position on the page."""
import re
from collections import defaultdict

import pdfplumber


def _lines(path):
    """Words grouped into printed lines, page by page, each word with its x position."""
    for pg in pdfplumber.open(path).pages:
        lines = defaultdict(list)
        for w in pg.extract_words(keep_blank_chars=False):
            lines[round(w['top'] / 4)].append(w)
        for k in sorted(lines):
            yield sorted(lines[k], key=lambda w: w['x0'])


def _cells(ws, cols):
    out = [''] * len(cols)
    for w in ws:
        i = max(j for j, c in enumerate(cols) if w['x0'] >= c - 2)
        out[i] = (out[i] + ' ' + w['text']).strip()
    return out


def dallas(path):
    """Dallas County's lists: code (V0003 / E0004), location, voting area (room), address, city, ZIP."""
    rows = []
    for ws in _lines(path):
        c = _cells(ws, [0, 60, 250, 395, 575, 700])
        if re.fullmatch(r'[VE]\d{4}', c[0]):
            rows.append(dict(zip(['code', 'name', 'room', 'address', 'city', 'zip'], c)))
        elif rows and not c[0] and any(c) and not re.search(r'Poll|Edificio|Địa|DALLAS COUNTY|List of|2026|November|Page', ' '.join(c)):
            r = rows[-1]   # a location or room that wraps onto a second line
            for k, v in zip(['code', 'name', 'room', 'address', 'city', 'zip'], c):
                if v: r[k] = (r[k] + ' ' + v).strip()
    return rows


def tarrant_ed(path):
    """Tarrant County's Election Day list: location, voting area, address, "City, TX ZIP" (no codes)."""
    rows, pending = [], ''
    for ws in _lines(path):
        c = _cells(ws, [0, 305, 605, 805])
        m = re.fullmatch(r'(.+?),\s*TX\s+(\d{5})', c[3])
        if m and re.match(r'\d', c[2]):
            name = (pending + ' ' + c[0]).strip() if pending or not c[0] else c[0]
            rows.append({'code': '', 'name': name, 'room': c[1], 'address': c[2], 'city': m.group(1), 'zip': m.group(2)})
            pending = ''
        elif c[0] and not any(c[1:]) and not re.search(r'(?i)election|elecciones|bầu|polling place|lugar|địa|page \d', c[0]):
            pending = (pending + ' ' + c[0]).strip()   # a long location name printed on the line above
    return rows


def tarrant_ev(path):
    """Tarrant County's early voting list: number, location, address, city, ZIP. A long name sits on the line above
    its number; a room printed below is left out."""
    rows, pending = [], ''
    for ws in _lines(path):
        c = _cells(ws, [0, 120, 345, 540, 655])
        if re.fullmatch(r'\d{1,3}', c[0]) and re.match(r'\d', c[2]) and re.fullmatch(r'\d{5}', c[4]):
            rows.append({'code': 'EV' + c[0], 'name': c[1] or pending, 'room': '', 'address': c[2], 'city': c[3], 'zip': c[4]})
            pending = ''
        elif c[1] and not c[0] and not any(c[2:]):
            pending = c[1]
        else:
            pending = ''
    return rows
