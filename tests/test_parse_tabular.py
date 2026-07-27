from datetime import datetime

from madisoncrimes.parse_tabular import extract_incidents_tabular

HEADER = ["level", "page_num", "par_num", "block_num", "line_num", "word_num",
          "left", "top", "width", "height", "conf", "text"]


def tsv(words: list[tuple[float, float, str]]) -> str:
    """Build pdftotext -tsv output from (left, top, text) triples."""
    rows = ["\t".join(HEADER)]
    for left, top, text in words:
        rows.append(f"5\t1\t0\t0\t0\t0\t{left}\t{top}\t10\t10\t100\t{text}")
    return "\n".join(rows)


def test_extract_incidents_tabular():
    # Mirrors the real layout: header row, then a record whose incident text
    # wraps and whose time carries AM on the wrapped line.
    doc = tsv([
        (55.9, 104.9, "Date/Time"), (139.1, 104.9, "Case"), (165.8, 104.9, "No."),
        (212.0, 104.9, "Incident"), (356.8, 104.9, "Location"),
        # squeezed row: date and time share the first line
        (55.9, 123.6, "7/17/2026"), (100.0, 123.6, "8:25:00"), (139.2, 123.6, "26M003376"),
        (212.0, 123.6, "HARASSING"), (356.8, 123.6, "5000"), (376.0, 123.6, "Block"),
        (400.0, 123.6, "of"), (410.0, 123.6, "WALL"), (440.0, 123.6, "TRIANA"),
        (55.9, 136.9, "AM"), (212.0, 136.9, "COMMUNICATIONS"),
        # second record, same case number continues a multi-incident case
        (55.9, 154.2, "7/17/2026"), (139.2, 154.2, "26M003379"),
        (212.0, 154.2, "POSSESSION"), (240.0, 154.2, "OF"), (255.0, 154.2, "DRUG"),
        (356.9, 154.2, "100"), (376.0, 154.2, "Block"),
        (55.9, 167.5, "3:26:58"), (89.9, 167.5, "PM"), (212.0, 167.5, "PARAPHERNALIA"),
        (55.9, 184.9, "7/17/2026"), (139.2, 184.9, "26M003379"),
        (212.0, 184.9, "POSSESSION"), (240.0, 184.9, "OF"), (260.0, 184.9, "MARIJUANA"),
        (330.0, 184.9, "2ND"), (356.9, 184.9, "100"), (376.0, 184.9, "Block"),
        (55.9, 198.2, "3:26:58"), (89.9, 198.2, "PM"),
    ])
    records = extract_incidents_tabular(doc)
    assert len(records) == 2
    assert records[0].case == "26M003376"
    assert records[0].when == datetime(2026, 7, 17, 8, 25)
    assert records[0].incidents == ["HARASSING COMMUNICATIONS"]
    assert records[0].location == "5000 Block of WALL TRIANA"
    assert records[1].case == "26M003379"
    assert records[1].when == datetime(2026, 7, 17, 15, 26, 58)
    assert records[1].incidents == ["POSSESSION OF DRUG PARAPHERNALIA",
                                    "POSSESSION OF MARIJUANA 2"]
    assert records[1].location == "100 Block"
