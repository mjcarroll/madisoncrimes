"""Paths and database access for the madisoncrimes-data working directory."""

import os
import sqlite3
from pathlib import Path

DEFAULT_DATA_DIR = Path(os.environ.get("MADISONCRIMES_DATA", "madisoncrimes-data"))


class DataDir:
    """Layout of the data repo: PDF caches, text caches, and the SQLite store."""

    def __init__(self, root: Path | str = DEFAULT_DATA_DIR):
        self.root = Path(root)
        self.incidents = self.root / "incidents"
        self.arrests = self.root / "arrests"
        self.incidents_txt = self.root / "incidents_txt"
        self.arrests_txt = self.root / "arrests_txt"
        self.incidents_tsv = self.root / "incidents_tsv"
        self.arrests_tsv = self.root / "arrests_tsv"
        self.db_path = self.root / "parsed_data.db"

    def ensure(self) -> None:
        for d in (
            self.incidents,
            self.arrests,
            self.incidents_txt,
            self.arrests_txt,
            self.incidents_tsv,
            self.arrests_tsv,
        ):
            d.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS location (
                id INTEGER PRIMARY KEY,
                location VARCHAR(250) NOT NULL UNIQUE,
                needs_moderation BOOLEAN NOT NULL DEFAULT 1,
                latitude FLOAT,
                longitude FLOAT,
                address VARCHAR(500),
                raw VARCHAR(10000)
            )
            """
        )
        return conn
