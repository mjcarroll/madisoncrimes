"""Join parsed records, geocodes, and categories into the static site's data file.

Output schema (site/data/records.json):
    categories: list of category names; records reference them by index
    locations:  list of raw location strings; records reference them by index
    records:    [lat, lon, "YYYY-MM-DD", hour|null, shift|null, type, [catIdx...], locIdx|null]
                lat/lon are null when the location isn't geocoded; type 0=incident 1=arrest
    case_gaps:  [[year, published, span], ...] — how many sequential case numbers
                the year's published reports cover vs. the span they imply exists

Arrestee names and residences are deliberately never exported.
"""

import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

from .categorize import categorize
from .data import DataDir
from .geocode import coordinates
from .parse import parse_all

TYPE_INCIDENT = 0
TYPE_ARREST = 1

# "B11-000726" / "18-000057" / "26M003276" -> (series, year, sequence number)
CASE_RE = re.compile(r"^([A-Z]?)(\d{2})([A-Z]?)0*(\d+)$")


def case_key(case: str) -> tuple[str, int, int] | None:
    m = CASE_RE.match(case.replace("-", ""))
    if not m:
        return None
    series = m.group(1) or m.group(3) or "#"
    return series, 2000 + int(m.group(2)), int(m.group(4))


def case_gaps(records) -> list[list[int]]:
    """Per year: how many distinct case numbers were published vs. the sequence
    span they cover. Case numbers are sequential, so the span approximates every
    case the department opened in that window — published or not."""
    seen: dict[tuple[int, str], set[int]] = defaultdict(set)
    for r in records:
        key = case_key(r.case)
        if key:
            series, year, seq = key
            seen[(year, series)].add(seq)
    years: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for (year, _series), seqs in seen.items():
        if len(seqs) < 30:  # ignore noise series (typos, misfiled reports)
            continue
        # trim 0.5% off both ends so a typo'd case number (B13-009999) can't inflate the span
        ordered = sorted(seqs)
        lo = ordered[int(len(ordered) * 0.005)]
        hi = ordered[min(int(len(ordered) * 0.995), len(ordered) - 1)]
        years[year][0] += len(seqs)
        years[year][1] += hi - lo + 1
    return [[year, published, span] for year, (published, span) in sorted(years.items())]


def canon_location(location: str) -> str:
    """Identity key for a location: eras differ in casing and trailing city hints
    ("100 Block of Hughes Rd Madison" vs "100 Block of HUGHES RD MAD")."""
    tokens = location.split()
    while tokens and tokens[-1].upper().strip(",") in ("MAD", "MADISON", "AL"):
        tokens.pop()
    return " ".join(tokens).upper()


def display_location(location: str) -> str:
    tokens = location.split()
    while tokens and tokens[-1].upper().strip(",") in ("MAD", "MADISON", "AL"):
        tokens.pop()
    # de-shout the new-format strings, keeping short directionals (NW, W) as-is
    tokens = [t.title() if t.isupper() and len(t) > 2 else t for t in tokens]
    return " ".join(tokens).replace(" Of ", " of ")


def build_site_data(data: DataDir, site_dir: Path) -> dict:
    incidents, arrests = parse_all(data)
    coords = coordinates(data.connect())

    cat_index: dict[str, int] = {}
    loc_index: dict[str, int] = {}

    def cats(strings: list[str]) -> list[int]:
        out = []
        for s in strings:
            cat, _deg = categorize(s)
            if cat not in cat_index:
                cat_index[cat] = len(cat_index)
            idx = cat_index[cat]
            if idx not in out:
                out.append(idx)
        return out

    loc_names: list[str] = []

    def loc(location: str) -> int | None:
        key = canon_location(location)
        if not key:
            return None
        if key not in loc_index:
            loc_index[key] = len(loc_index)
            loc_names.append(display_location(location))
        return loc_index[key]

    records = []
    for r in incidents:
        lat, lon = coords.get(r.location, (None, None))
        records.append(
            [lat, lon, r.when.strftime("%Y-%m-%d"), r.when.hour, r.shift,
             TYPE_INCIDENT, cats(r.incidents), loc(r.location)]
        )
    for r in arrests:
        lat, lon = coords.get(r.location, (None, None))
        records.append(
            [lat, lon, r.when.strftime("%Y-%m-%d"), None, None,
             TYPE_ARREST, cats(r.charges), loc(r.location)]
        )
    records.sort(key=lambda rec: rec[2])

    out = {
        "generated": date.today().isoformat(),
        "generated_from": {
            "incident_reports": len(incidents),
            "arrest_reports": len(arrests),
            "geocoded": sum(1 for rec in records if rec[0] is not None),
        },
        "categories": [name for name, _ in sorted(cat_index.items(), key=lambda kv: kv[1])],
        "locations": loc_names,
        "case_gaps": case_gaps(incidents + arrests),
        "records": records,
    }
    dest = site_dir / "data"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "records.json").write_text(json.dumps(out, separators=(",", ":")))
    return out["generated_from"]
