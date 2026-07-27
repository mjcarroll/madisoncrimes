"""Parser for the tabular report format the city switched to (~2020s).

These reports are column-based (Date/Time | Case No. | Incident | Location for
incidents; Date | First | Middle | Last | City | State | Address | Case for
arrests) with values wrapping inside their columns. `pdftotext -layout` output
misaligns squeezed rows, so records are extracted from `pdftotext -tsv` word
coordinates instead.

Column x-positions come from each page's header row. Words are assigned to the
column whose x-start they sit in (with a small tolerance, since rows render a
few points off the header). Date, time, and case number are recognized
lexically wherever they land, because some layout variants let them overflow
their columns.
"""

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime

from .parse import ArrestRecord, IncidentRecord, ParseErrors, normalize_incident

DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
TIME_RE = re.compile(r"^\d{1,2}:\d{2}:\d{2}$")
CASE_RE = re.compile(r"^\d{2}[A-Z]\d+$")
MERIDIEM = {"AM", "PM"}
TOLERANCE = 6.0


@dataclass
class Word:
    page: int
    left: float
    top: float
    text: str


def pdf_to_tsv(pdf_path, tsv_path) -> None:
    tsv = subprocess.check_output(["pdftotext", "-tsv", str(pdf_path), "-"])
    tsv_path.write_bytes(tsv)


def tsv_words(tsv_text: str) -> list[Word]:
    words = []
    for line in tsv_text.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) == 12 and parts[0] == "5":
            words.append(Word(int(parts[1]), float(parts[6]), float(parts[7]), parts[11]))
    return words


def tsv_lines(tsv_text: str, tol: float = 3.0) -> list[list[Word]]:
    """Group words into visual lines by page and y-position."""
    words = sorted(tsv_words(tsv_text), key=lambda w: (w.page, w.top, w.left))
    lines: list[list[Word]] = []
    for word in words:
        if lines and lines[-1][0].page == word.page and abs(lines[-1][0].top - word.top) <= tol:
            lines[-1].append(word)
        else:
            lines.append([word])
    return [sorted(line, key=lambda w: w.left) for line in lines]


def header_lefts(header: list[Word], names: list[str]) -> list[float] | None:
    """x-positions of the named header columns, or None if any is missing/misordered."""
    lefts = []
    for name in names:
        match = next((w for w in header if w.text == name), None)
        if match is None:
            return None
        lefts.append(match.left)
    return lefts if lefts == sorted(lefts) else None


def in_column(line: list[Word], start: float, end: float | None = None) -> str:
    """Text of the words whose x-start falls within [start-tol, end-tol)."""
    return " ".join(
        w.text
        for w in line
        if w.left >= start - TOLERANCE and (end is None or w.left < end - TOLERANCE)
    )


def _pick_time(tokens: list[str]) -> tuple[str | None, str | None]:
    time = next((t for t in tokens if TIME_RE.match(t)), None)
    meridiem = next((t for t in tokens if t in MERIDIEM), None)
    return time, meridiem


def extract_incidents_tabular(
    tsv_text: str, source: str = "", errors: ParseErrors | None = None
) -> list[IncidentRecord]:
    rows: list[dict] = []
    bounds = None  # (incident column x, location column x)
    for line in tsv_lines(tsv_text):
        texts = [w.text for w in line]
        if "Date/Time" in texts and "Location" in texts:
            lefts = header_lefts(line, ["Incident", "Location"])
            if lefts:
                bounds = lefts
            continue
        if bounds is None:
            continue
        inc_left, loc_left = bounds
        meta = [w.text for w in line if w.left < inc_left - TOLERANCE]
        incident = in_column(line, inc_left, loc_left)
        location = in_column(line, loc_left)

        if meta and DATE_RE.match(meta[0]):
            time, meridiem = _pick_time(meta[1:])
            rows.append({
                "date": meta[0],
                "time": time,
                "meridiem": meridiem,
                "case": next((t for t in meta[1:] if CASE_RE.match(t)), None),
                "incident": [incident],
                "location": [location],
            })
        elif rows:
            row = rows[-1]
            time, meridiem = _pick_time(meta)
            row["time"] = row["time"] or time
            row["meridiem"] = row["meridiem"] or meridiem
            row["case"] = row["case"] or next((t for t in meta if CASE_RE.match(t)), None)
            if incident:
                row["incident"].append(incident)
            if location:
                row["location"].append(location)

    # Consecutive rows with the same case number are one record with several incidents.
    records: list[IncidentRecord] = []
    for row in rows:
        try:
            when = datetime.strptime(
                f"{row['date']} {row['time']} {row['meridiem']}", "%m/%d/%Y %I:%M:%S %p"
            )
        except (TypeError, ValueError) as e:
            if errors:
                errors.add(source, f"case {row['case']}: {e}")
            continue
        if not row["case"]:
            if errors:
                errors.add(source, f"row at {row['date']} {row['time']}: no case number")
            continue
        incident = normalize_incident(" ".join(" ".join(row["incident"]).split()))
        location = " ".join(" ".join(row["location"]).split())
        if records and records[-1].case == row["case"]:
            records[-1].incidents.append(incident)
        else:
            records.append(
                IncidentRecord(case=row["case"], when=when, shift=None,
                               location=location, incidents=[incident], source=source)
            )
    return records


ARREST_COLUMNS = ["Date", "First", "Middle", "Last", "City", "State", "Address", "Case"]


def extract_arrests_tabular(
    tsv_text: str, source: str = "", errors: ParseErrors | None = None
) -> list[ArrestRecord]:
    lefts = None
    rows: list[dict] = []
    in_charges = False
    for line in tsv_lines(tsv_text):
        texts = [w.text for w in line]
        if texts[:3] == ["Date", "First", "Middle"]:
            found = header_lefts(line, ARREST_COLUMNS)
            if found:
                lefts = found
            continue
        if lefts is None or texts == ["Number"]:
            continue
        if texts[0] == "Charge":
            if rows:
                rows[-1]["charges"].append(" ".join(texts[1:]))
                in_charges = True
            continue

        date_l, first_l, middle_l, last_l, city_l, state_l, addr_l, case_l = lefts
        name = in_column(line, first_l, city_l)
        city = in_column(line, city_l, state_l)
        address = in_column(line, addr_l, case_l)
        if DATE_RE.match(texts[0]):
            rows.append({
                "date": texts[0],
                "name": [name],
                "city": [city],
                "state": in_column(line, state_l, addr_l),
                "address": [address],
                "case": next((t for t in texts if CASE_RE.match(t)), None),
                "charges": [],
            })
            in_charges = False
        elif rows:
            if in_charges:
                rows[-1]["charges"][-1] += " " + " ".join(texts)
                continue
            for target, value in (("name", name), ("city", city), ("address", address)):
                if value:
                    rows[-1][target].append(value)

    records = []
    for row in rows:
        try:
            when = datetime.strptime(row["date"], "%m/%d/%Y").date()
        except ValueError as e:
            if errors:
                errors.add(source, f"case {row['case']}: {e}")
            continue
        if not row["case"]:
            if errors:
                errors.add(source, f"arrest on {row['date']}: no case number")
            continue
        city = " ".join(" ".join(row["city"]).split())
        address = " ".join(" ".join(row["address"]).split())
        location = ", ".join(filter(None, (address, city, row["state"] or "AL")))
        charges = [normalize_incident(c) for text in row["charges"] for c in text.split(" / ")]
        records.append(
            ArrestRecord(
                case=row["case"], when=when,
                name=" ".join(" ".join(row["name"]).split()),
                residence=city, location=location, charges=charges, source=source,
            )
        )
    return records
