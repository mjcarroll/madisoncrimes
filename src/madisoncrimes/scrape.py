"""Scrape incident/arrest report PDFs from the City of Madison archive."""

import subprocess

import requests
from lxml import html

from .data import DataDir

ARCHIVE_URL = "https://www.madisonal.gov/Archive.aspx"
INCIDENT_AMID = 67
ARREST_AMID = 68
USER_AGENT = "madisoncrimes/2.0 (+https://github.com/mjcarroll/madisoncrimes)"


def list_reports(amid: int, session: requests.Session | None = None) -> list[str]:
    """Return the archive document IDs currently listed for the given archive module."""
    session = session or requests.Session()
    page = session.get(
        ARCHIVE_URL,
        params={"AMID": amid, "Type": "", "ADID": ""},
        headers={"User-Agent": USER_AGENT},
        timeout=60,
    )
    page.raise_for_status()
    tree = html.fromstring(page.text)
    ids = []
    for link in tree.xpath('//span[@class="archive"]/a'):
        parts = link.attrib.get("href", "").split("=")
        if len(parts) >= 2 and parts[1].isdigit():
            ids.append(parts[1])
    return ids


def download_report(adid: str, dest, session: requests.Session | None = None) -> None:
    session = session or requests.Session()
    page = session.get(
        ARCHIVE_URL,
        params={"ADID": adid},
        headers={"User-Agent": USER_AGENT},
        timeout=120,
    )
    page.raise_for_status()
    if not page.content.startswith(b"%PDF"):
        raise ValueError(f"ADID {adid} did not return a PDF")
    (dest / adid).write_bytes(page.content)


def pdf_to_text(pdf_path, txt_path) -> None:
    txt = subprocess.check_output(["pdftotext", "-nopgbrk", "-layout", str(pdf_path), "-"])
    txt_path.write_bytes(txt)


def sync(data: DataDir, dry_run: bool = False) -> dict:
    """Download any reports listed online that we don't have, then convert new PDFs to text.

    Returns a summary of what was (or would be) fetched.
    """
    data.ensure()
    session = requests.Session()
    summary = {}
    for kind, amid, pdf_dir, txt_dir in (
        ("incidents", INCIDENT_AMID, data.incidents, data.incidents_txt),
        ("arrests", ARREST_AMID, data.arrests, data.arrests_txt),
    ):
        online = set(list_reports(amid, session))
        cached = {p.name for p in pdf_dir.iterdir() if p.is_file()}
        new = sorted(online - cached, key=int)
        if not dry_run:
            for adid in new:
                download_report(adid, pdf_dir, session)
            for pdf in pdf_dir.iterdir():
                txt = txt_dir / pdf.name
                if pdf.is_file() and not txt.exists():
                    pdf_to_text(pdf, txt)
        summary[kind] = {"online": len(online), "cached": len(cached), "new": len(new)}
    return summary
