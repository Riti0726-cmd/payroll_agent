"""Run any SQL file against the configured DATABASE_URL (Neon / PostgreSQL).

Usage (from repo root):
  .\.venv\Scripts\python.exe scripts\run_sql_file.py sql/seed_snowflake_employees.sql
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG  = ROOT / "src" / "payroll_specialist"
sys.path.insert(0, str(PKG))
sys.path.insert(0, str(ROOT))

import os
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from db.database import get_engine


def run_sql_file(sql_path: Path) -> None:
    sql = sql_path.read_text(encoding="utf-8")

    engine = get_engine()
    # Use raw psycopg2 connection so multi-statement SQL blocks execute cleanly
    raw_conn = engine.raw_connection()
    try:
        cursor = raw_conn.cursor()
        cursor.execute(sql)
        raw_conn.commit()
        cursor.close()
    finally:
        raw_conn.close()

    print(f"[OK] Executed: {sql_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_sql_file.py <path/to/file.sql>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.is_absolute():
        path = ROOT / path

    if not path.exists():
        print(f"[ERROR] File not found: {path}")
        sys.exit(1)

    run_sql_file(path)
