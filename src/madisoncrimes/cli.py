"""Command-line interface: madisoncrimes {status,sync,geocode,build}."""

import argparse
from pathlib import Path

from .data import DEFAULT_DATA_DIR, DataDir


def main() -> None:
    parser = argparse.ArgumentParser(prog="madisoncrimes")
    parser.add_argument(
        "--data", type=Path, default=DEFAULT_DATA_DIR,
        help="path to the madisoncrimes-data checkout (default: %(default)s)",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="show scrape/parse/geocode coverage")
    sync_p = sub.add_parser("sync", help="download new reports and convert to text")
    sync_p.add_argument("--dry-run", action="store_true")
    geo_p = sub.add_parser("geocode", help="geocode locations missing from the cache")
    geo_p.add_argument("--limit", type=int, default=None)
    geo_p.add_argument(
        "--retry-flagged", action="store_true",
        help="retry previously flagged locations (after improving to_query)",
    )
    build_p = sub.add_parser("build", help="write site/data/records.json")
    build_p.add_argument("--site", type=Path, default=Path("site"))
    args = parser.parse_args()

    data = DataDir(args.data)

    if args.command == "sync":
        from .scrape import sync

        for kind, s in sync(data, dry_run=args.dry_run).items():
            print(f"{kind}: {s['online']} online, {s['cached']} cached, {s['new']} new")

    elif args.command == "geocode":
        from .geocode import geocode_missing
        from .parse import parse_all

        incidents, arrests = parse_all(data)
        locations = {r.location for r in incidents + arrests if r.location}
        stats = geocode_missing(
            data.connect(), locations, limit=args.limit, retry_flagged=args.retry_flagged
        )
        print(
            f"{stats['new']} new locations: {stats['resolved']} resolved, "
            f"{stats['flagged']} flagged for moderation, {stats['errors']} errors"
        )

    elif args.command == "build":
        from .build import build_site_data

        stats = build_site_data(data, args.site)
        print(
            f"wrote {args.site}/data/records.json: {stats['incident_reports']} incidents, "
            f"{stats['arrest_reports']} arrests, {stats['geocoded']} geocoded"
        )

    elif args.command == "status":
        from .geocode import coordinates
        from .parse import ParseErrors, parse_all
        from .scrape import sync

        for kind, s in sync(data, dry_run=True).items():
            print(f"{kind}: {s['online']} online, {s['cached']} cached, {s['new']} to fetch")
        errors = ParseErrors()
        incidents, arrests = parse_all(data, errors)
        print(f"parsed: {len(incidents)} incident records, {len(arrests)} arrest records, "
              f"{len(errors.errors)} parse errors")
        coords = coordinates(data.connect())
        n = sum(1 for r in incidents + arrests if r.location in coords)
        total = len(incidents) + len(arrests)
        print(f"geocoded: {n}/{total} records ({100 * n / total:.1f}%)")
