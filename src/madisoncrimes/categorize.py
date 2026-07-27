"""Map raw incident/charge strings to a small set of categories plus an offense degree.

The exact-match table in resources/categories.json was hand-curated during the original
hackhuntsville effort; rule-based fallbacks below cover strings that appeared later
(mostly arrest charges: drugs, DUI, failure-to-appear).
"""

import json
import re
from functools import cache
from importlib import resources

WORD_DEGREES = {"FIRST": 1, "SECOND": 2, "THIRD": 3, "FOURTH": 4}

# (pattern, category) — first match wins; checked before the generic degree-strip fallback.
RULES = [
    (r"^DV\b|^DOMESTIC VIOLENCE", "DOMESTIC VIOLENCE"),
    (r"MARIJUANA|CONTROLLED SUBSTANCE|DRUG PARAPHERNALIA|AMPHETAMINE|METHAMPHETAMINE"
     r"|COCAINE|HEROIN|OPIUM|NARCOTIC|PRESCRIPTION DRUG|OVERDOSE|DRUG", "DRUGS"),
    (r"DRIVING UNDER (THE )?INFLUENCE|^DUI\b", "DRIVING UNDER INFLUENCE"),
    (r"FAILURE TO APPEAR", "FAILURE TO APPEAR"),
    (r"FORGED INSTRUMENT", "POSS. FORGED INSTRUMENT"),
    (r"^FORGERY", "FORGERY"),
    (r"^THEFT OF LOST PROPERTY", "THEFT OF LOST PROPERTY"),
    (r"^THEFT OF SERVICES", "THEFT OF SERVICES"),
    (r"^THEFT|SHOPLIFTING", "THEFT"),
    (r"^BURGLARY", "BURGLARY"),
    (r"^ROBBERY", "ROBBERY"),
    (r"^ASSAULT", "ASSAULT"),
    (r"RECEIVING STOLEN PROPERTY", "RECEIVING STOLEN PROPERTY"),
    (r"BAIL JUMPING", "BAIL JUMPING"),
    (r"^CRIMINAL TRESPASS", "CRIMINAL TRESPASS"),
    (r"BREAKING AND ENTERING", "BREAKING AND ENTERING A VEHICLE"),
    (r"^HARASS", "HARASSMENT"),
    (r"^CRIMINAL MISCHIEF", "CRIMINAL MISCHIEF"),
    (r"IDENTITY THEFT", "IDENTITY THEFT"),
    (r"CREDIT CARD|DEBIT CARD", "ILLEGAL POSS/USE CREDIT CARD"),
    (r"PISTOL|FIREARM|WEAPON|GUN\b", "WEAPON"),
    (r"PUBLIC INTOX|DISORDERLY", "PUBLIC ORDER"),
    (r"RESISTING ARREST|OBSTRUCT", "OBSTRUCTION"),
]
_RULES = [(re.compile(p), cat) for p, cat in RULES]


@cache
def curated() -> dict[str, tuple[str, int | None]]:
    raw = resources.files("madisoncrimes.resources").joinpath("categories.json").read_text()
    return {k: (v[0], v[1]) for k, v in json.loads(raw).items()}


def split_degree(incident: str) -> tuple[str, int | None]:
    """Strip a trailing offense degree ('THEFT 4 DEGREE' -> ('THEFT', 4))."""
    m = re.search(r"\s+(\d)(?:\s+DEGREE)?$", incident)
    if m:
        return incident[: m.start()].strip(), int(m.group(1))
    m = re.search(r"\s+(FIRST|SECOND|THIRD|FOURTH)\s+DEGREE$", incident)
    if m:
        return incident[: m.start()].strip(), WORD_DEGREES[m.group(1)]
    return incident, None


def categorize(incident: str) -> tuple[str, int | None]:
    """Return (category, degree) for a normalized incident/charge string."""
    if incident in curated():
        return curated()[incident]
    base, degree = split_degree(incident)
    for pattern, cat in _RULES:
        if pattern.search(incident):
            return cat, degree
    return base or incident, degree
