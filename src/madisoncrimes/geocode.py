"""Geocode report locations.

Coordinates are cached in the `location` table of parsed_data.db — including ~4,300
entries carried over from the original Google-geocoded dataset. New locations are
resolved with the free US Census Bureau geocoder (no API key). Results outside a
sanity bounding box around Madison, AL are flagged for moderation instead of stored.
"""

import json
import re
import sqlite3

import requests

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"

# Generous bounding box around Madison, AL (from the original notebook's sanity filter).
LAT_MIN, LAT_MAX = 34.484434, 34.8950
LON_MIN, LON_MAX = -86.984023, -86.4159


def in_bounds(lat: float, lon: float) -> bool:
    return LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX


# Trailing city abbreviations used by the newer tabular reports.
CITY_HINTS = {
    "MAD": "Madison",
    "MADISON": "Madison",
    "HSV": "Huntsville",
    "HUNTSVILLE": "Huntsville",
    "LIME": "Madison",  # Limestone County side of the city
    "LIMESTONE": "Madison",
}


def to_query(location: str) -> str | None:
    """Turn a report location string into a geocodable one-line address.

    Returns None for strings the Census geocoder can't handle (intersections, mile
    markers) — those stay flagged for manual moderation.
    """
    loc = location.strip()
    if (
        "/" in loc
        or "&" in loc
        or re.search(r"\bI ?565\b|MILE MARKER|\bMM\b|EXIT|#ERROR", loc, re.IGNORECASE)
    ):
        return None
    # "Business Name, 123 Street Rd" -> keep the street part
    if "," in loc and re.match(r"^\D", loc):
        parts = [p.strip() for p in loc.split(",")]
        street = next((p for p in parts if re.match(r"^\d+ ", p)), None)
        if street:
            loc = street
    city = "Madison"
    tokens = loc.split()
    while tokens and tokens[-1].upper() in CITY_HINTS:
        city = CITY_HINTS[tokens[-1].upper()]
        tokens = tokens[:-1]
    loc = " ".join(tokens)
    loc = re.sub(r"(?i)^(\d+) Block of ", r"\1 ", loc)
    loc = re.sub(r"^area of ", "", loc, flags=re.IGNORECASE)
    loc = re.sub(r"(?i)\s+(Apt|Ste|Suite|Unit)\.?\s*#?[\w-]+$", "", loc)
    loc = re.sub(r"(?i)\bAv\b\.?", "Ave", loc)
    loc = re.sub(r"(?i)\bHwy\b\.?", "Highway", loc)
    if not loc:
        return None
    if not re.search(r"(?i)\b(al|alabama)\b", loc):
        loc += f", {city}, AL"
    return loc


def census_geocode(query: str, session: requests.Session | None = None) -> dict | None:
    session = session or requests.Session()
    resp = session.get(
        CENSUS_URL,
        params={"address": query, "benchmark": "Public_AR_Current", "format": "json"},
        timeout=60,
    )
    resp.raise_for_status()
    matches = resp.json().get("result", {}).get("addressMatches", [])
    if not matches:
        return None
    best = matches[0]
    return {
        "latitude": best["coordinates"]["y"],
        "longitude": best["coordinates"]["x"],
        "address": best["matchedAddress"],
        "raw": json.dumps(best),
    }


def geocode_missing(
    conn: sqlite3.Connection,
    locations: set[str],
    limit: int | None = None,
    retry_flagged: bool = False,
) -> dict:
    """Geocode locations not yet in the cache table. Returns a summary of the run.

    With retry_flagged, previously flagged coordinate-less locations are retried
    (useful after improving to_query) instead of geocoding new ones.
    """
    if retry_flagged:
        todo = sorted(
            row["location"]
            for row in conn.execute(
                "SELECT location FROM location WHERE needs_moderation = 1 AND latitude IS NULL"
            )
            if row["location"] in locations
        )
        conn.executemany(
            "DELETE FROM location WHERE location = ? AND needs_moderation = 1"
            " AND latitude IS NULL",
            [(loc,) for loc in todo],
        )
        known: set[str] = set()
    else:
        known = {row["location"] for row in conn.execute("SELECT location FROM location")}
        todo = sorted(locations - known)
    if limit is not None:
        todo = todo[:limit]

    session = requests.Session()
    stats = {"cached": len(known), "new": len(todo), "resolved": 0, "flagged": 0, "errors": 0}
    consecutive_errors = 0
    for loc in todo:
        query = to_query(loc)
        try:
            result = census_geocode(query, session) if query else None
        except requests.RequestException:
            # Transient API failure: leave the location out of the cache entirely so a
            # later run retries it, and give up if the API looks down.
            stats["errors"] += 1
            consecutive_errors += 1
            if consecutive_errors >= 5:
                break
            continue
        consecutive_errors = 0
        if result and in_bounds(result["latitude"], result["longitude"]):
            conn.execute(
                "INSERT INTO location (location, needs_moderation, latitude, longitude,"
                " address, raw) VALUES (?, 0, ?, ?, ?, ?)",
                (loc, result["latitude"], result["longitude"], result["address"], result["raw"]),
            )
            stats["resolved"] += 1
        else:
            conn.execute(
                "INSERT INTO location (location, needs_moderation) VALUES (?, 1)", (loc,)
            )
            stats["flagged"] += 1
        conn.commit()
    return stats


def coordinates(conn: sqlite3.Connection) -> dict[str, tuple[float, float]]:
    """All usable cached coordinates, keyed by raw location string."""
    return {
        row["location"]: (row["latitude"], row["longitude"])
        for row in conn.execute(
            "SELECT location, latitude, longitude FROM location"
            " WHERE needs_moderation = 0 AND latitude IS NOT NULL"
        )
        if in_bounds(row["latitude"], row["longitude"])
    }
