# madisoncrimes

Scrapes incident and arrest report PDFs published by the [City of Madison, AL
Police Department](https://www.madisonal.gov/Archive.aspx), extracts structured
records, geocodes them, and publishes a static site with an interactive crime
heatmap.

Extracted data lives in a separate repo:
[mjcarroll/madisoncrimes-data](https://github.com/mjcarroll/madisoncrimes-data)
(PDF/text caches plus `parsed_data.db` with the geocode cache).

## Setup

```sh
uv sync
git clone https://github.com/mjcarroll/madisoncrimes-data
```

`pdftotext` (poppler-utils) is required for converting newly downloaded PDFs.

## Pipeline

```sh
uv run madisoncrimes status    # what's online vs cached, parse + geocode coverage
uv run madisoncrimes sync      # download new PDFs from the city archive, convert to text
uv run madisoncrimes geocode   # geocode new locations (US Census geocoder, cached in sqlite)
uv run madisoncrimes build     # emit site/data/*.json for the static site
```

The site in `site/` is fully static — serve it with any file server:

```sh
python3 -m http.server -d site
```

## Automation

`.github/workflows/update.yml` runs the whole pipeline weekly (and on demand):
sync → geocode → build, commits new PDFs and geocodes back to the data repo,
and deploys `site/` to GitHub Pages. It needs:

- GitHub Pages enabled for the repo (Settings → Pages → GitHub Actions source)
- a `DATA_REPO_TOKEN` repo secret: a fine-grained PAT with contents write
  access to `madisoncrimes-data`, so the workflow can push new data

## How it works

- **scrape** — lists the city archive pages (AMID 67 incidents / 68 arrests),
  downloads new ADIDs, converts PDF → text with `pdftotext -layout`.
- **parse** — extracts case number, timestamp, shift, location, and incident
  strings from the text; arrest reports also yield charges. Names from arrest
  reports are never exported to the site.
- **categorize** — maps ~490 raw incident strings to ~40 categories + offense
  degree, using the hand-curated mapping from the original hackhuntsville
  effort plus rule-based fallbacks.
- **geocode** — coordinates come from the cached geocode table (4,300+ entries
  from the original dataset); new locations are resolved with the free US
  Census geocoder and sanity-checked against a Madison bounding box.
- **build** — joins everything into compact JSON consumed by the Leaflet
  heatmap in `site/`.
