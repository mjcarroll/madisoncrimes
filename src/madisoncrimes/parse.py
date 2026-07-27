"""Extract structured records from pdftotext output of MPD incident/arrest reports."""

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from .data import DataDir

REJECT_LINES = {
    "",
    "Incident Report",
    "Arrest Report",
    "Madison Police Department",
    "Date",
    "Arrest Information",
    "Arrest",
    "Report Designed by the Law Enforcement Technology Coordinator",
}

ROMAN_SHIFTS = {"I": 1, "II": 2, "III": 3, "IV": 4}


@dataclass
class IncidentRecord:
    case: str
    when: datetime
    shift: int | None
    location: str
    incidents: list[str]
    source: str = ""


@dataclass
class ArrestRecord:
    case: str
    when: date
    name: str
    residence: str
    location: str
    charges: list[str]
    source: str = ""


@dataclass
class ParseErrors:
    """Records that could not be parsed, kept for diagnostics."""

    errors: list[tuple[str, str]] = field(default_factory=list)

    def add(self, source: str, message: str) -> None:
        self.errors.append((source, message))


def clean_lines(text: str) -> list[str]:
    """Drop headers, footers, and boilerplate; return stripped content lines."""
    keep = []
    for line in text.splitlines():
        line = line.strip()
        if line in REJECT_LINES:
            continue
        if re.match(r"Page \d+ of \d+", line):
            continue
        if re.match(r"\((.*) To (.*)\)", line):
            continue
        keep.append(line)
    return keep


def split_fields(lines: list[str]) -> list[str]:
    """pdftotext -layout puts several fields on one line; split them apart."""
    out = []
    for line in lines:
        for marker in ("Time:", "Shift:", "Location:"):
            idx = line.find(marker)
            if idx > 0:
                out.append(line[:idx].strip())
                line = line[idx:]
        out.append(line.strip())
    return [line for line in out if line]


def normalize_incident(inc: str) -> str:
    """Normalize an incident/charge string the same way the original pipeline did."""
    inc = inc.replace("-", " ")
    inc = re.sub(r"\s+", " ", inc)
    for word, digit in (("1st", "1"), ("2nd", "2"), ("3rd", "3"), ("4th", "4")):
        inc = inc.replace(word, digit).replace(word.upper(), digit)
    return inc.strip().strip(".")


def parse_shift(shift: str) -> int | None:
    return ROMAN_SHIFTS.get(shift.strip().upper())


def extract_incidents(
    lines: list[str], source: str = "", errors: ParseErrors | None = None
) -> list[IncidentRecord]:
    """Parse an incident report: blocks of Case No. / Time / Shift / Date / Location / Incident."""
    fields = {
        "case": "Case No.: ",
        "time": "Time: ",
        "shift": "Shift: ",
        "date": "Date Reported: ",
        "location": "Location: ",
        "incident": "Incident: ",
    }
    found: dict[str, dict[int, str]] = {name: {} for name in fields}
    for ii, line in enumerate(lines):
        for name, marker in fields.items():
            idx = line.find(marker)
            if idx >= 0:
                found[name][ii] = line[idx + len(marker) :].strip()

    def between(name: str, start: int, end: int) -> list[str]:
        return [v for k, v in sorted(found[name].items()) if start < k < end]

    records = []
    case_keys = sorted(found["case"])
    for start, end in zip(case_keys, case_keys[1:] + [len(lines)], strict=False):
        try:
            when = datetime.strptime(
                f"{between('time', start, end)[0]} {between('date', start, end)[0]}",
                "%I:%M %p %B %d, %Y",
            )
        except (IndexError, ValueError) as e:
            if errors:
                errors.add(source, f"case {found['case'][start]}: {e}")
            continue

        shifts = between("shift", start, end)
        locations = between("location", start, end)
        records.append(
            IncidentRecord(
                case=found["case"][start],
                when=when,
                shift=parse_shift(shifts[0]) if shifts else None,
                location=locations[0] if locations else "",
                incidents=[normalize_incident(i) for i in between("incident", start, end)],
                source=source,
            )
        )
    return records


ARREST_RE = re.compile(r"([^,]+), (.*?) was arrested at (.*) on the charge\(s\) of:")


def extract_arrests(
    lines: list[str], source: str = "", errors: ParseErrors | None = None
) -> list[ArrestRecord]:
    """Parse an arrest report: date line, prose sentence, case number line, charge lines."""
    date_lines: dict[int, str] = {}
    case_lines: dict[int, str] = {}
    other_lines: dict[int, str] = {}
    for ii, line in enumerate(lines):
        if re.match(r"\d+/\d+/\d+$", line):
            date_lines[ii] = line
        elif re.match(r"\d\d-\d+$", line):
            case_lines[ii] = line
        else:
            other_lines[ii] = line

    records = []
    date_keys = sorted(date_lines)
    for start, end in zip(date_keys, date_keys[1:] + [len(lines)], strict=False):
        cases = [k for k in sorted(case_lines) if start < k < end]
        if not cases:
            continue
        prose = [(k, other_lines[k]) for k in sorted(other_lines) if start < k < end]
        joined = " ".join(text for _, text in prose)
        match = ARREST_RE.match(joined)
        if not match:
            if errors:
                errors.add(source, f"case {case_lines[cases[0]]}: no arrest sentence")
            continue

        # Charges are the lines after the one where the prose sentence ends.
        offset = match.end()
        charges_from = len(prose)
        for ii, (_, text) in enumerate(prose):
            if offset >= len(text):
                offset -= len(text) + 1
            else:
                charges_from = ii
                break

        try:
            when = datetime.strptime(date_lines[start], "%m/%d/%y").date()
        except ValueError as e:
            if errors:
                errors.add(source, f"case {case_lines[cases[0]]}: {e}")
            continue

        records.append(
            ArrestRecord(
                case=case_lines[cases[0]],
                when=when,
                name=match.group(1).strip(),
                residence=match.group(2).strip(),
                location=match.group(3).strip(),
                charges=[normalize_incident(text) for _, text in prose[charges_from:]],
                source=source,
            )
        )
    return records


def _tsv(data: DataDir, pdf_dir, tsv_dir, name: str) -> str:
    """Read the cached pdftotext -tsv output for a report, generating it if needed."""
    from .parse_tabular import pdf_to_tsv

    tsv_path = tsv_dir / name
    if not tsv_path.exists():
        data.ensure()
        pdf_to_tsv(pdf_dir / name, tsv_path)
    return tsv_path.read_text(errors="replace")


def parse_all(
    data: DataDir, errors: ParseErrors | None = None
) -> tuple[list[IncidentRecord], list[ArrestRecord]]:
    """Parse every cached report, dispatching on the report format.

    Reports up to ~2019 are prose/field based and parse from the cached text;
    later ones are tabular and parse from pdftotext -tsv word coordinates.
    Dispatch is by content, not archive: the city occasionally files a report
    under the wrong archive type.
    """
    from .parse_tabular import extract_arrests_tabular, extract_incidents_tabular

    incidents: list[IncidentRecord] = []
    arrests: list[ArrestRecord] = []
    for pdf_dir, txt_dir, tsv_dir in (
        (data.incidents, data.incidents_txt, data.incidents_tsv),
        (data.arrests, data.arrests_txt, data.arrests_tsv),
    ):
        for path in sorted(txt_dir.iterdir(), key=lambda p: int(p.name)):
            text = path.read_text(errors="replace")
            if "Case No.:" in text:
                lines = split_fields(clean_lines(text))
                incidents.extend(extract_incidents(lines, source=path.name, errors=errors))
            elif "was arrested at" in text:
                arrests.extend(
                    extract_arrests(clean_lines(text), source=path.name, errors=errors)
                )
            elif "Date/Time" in text:
                tsv = _tsv(data, pdf_dir, tsv_dir, path.name)
                incidents.extend(
                    extract_incidents_tabular(tsv, source=path.name, errors=errors)
                )
            elif "First" in text and "Middle" in text:
                tsv = _tsv(data, pdf_dir, tsv_dir, path.name)
                arrests.extend(extract_arrests_tabular(tsv, source=path.name, errors=errors))
            elif errors:
                errors.add(path.name, "unrecognized report format")
    return incidents, arrests
