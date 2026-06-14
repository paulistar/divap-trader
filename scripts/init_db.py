#!/usr/bin/env python3
"""Initialize TimescaleDB schema for DIVAP trader."""

import os
import sys

from src.data.schema_init import apply_schema


def main() -> int:
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://divap:divap@localhost:5432/divap",
    )
    print("Connecting to database...")
    try:
        apply_schema(database_url)
        print("Database schema initialized successfully.")
        return 0
    except Exception as exc:
        print(f"Error initializing database: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
