"""Delete e2e-seed-* rows from Neon email_processing."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def main() -> None:
    eng = create_engine(os.environ["DATABASE_URL"])
    with eng.begin() as conn:
        result = conn.execute(
            text("DELETE FROM email_processing WHERE message_id LIKE :pat"),
            {"pat": "e2e-seed-%"},
        )
        print(f"deleted {result.rowcount} e2e-seed rows")


if __name__ == "__main__":
    main()
