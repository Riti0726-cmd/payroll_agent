"""Helper script to inspect database schema and query data."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]

# If invoked with global/system python instead of the project venv, re-exec using .venv
_venv_python = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / ("python.exe" if sys.platform == "win32" else "python")
if _venv_python.exists() and Path(sys.executable).resolve() != _venv_python.resolve():
    import subprocess
    sys.exit(subprocess.call([str(_venv_python)] + sys.argv))

PKG = ROOT / "src" / "payroll_specialist"
sys.path.insert(0, str(PKG))
os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from sqlalchemy import inspect, text
from db.database import get_engine


def print_schema() -> None:
    engine = get_engine()
    inspector = inspect(engine)

    tables = inspector.get_table_names()
    print("========================================")
    print("         DATABASE TABLES                ")
    print("========================================")
    for t in tables:
        print(f"  • {t}")

    for table in tables:
        print(f"\n========================================")
        print(f"  TABLE SCHEMA: {table}")
        print("========================================")
        pk = inspector.get_pk_constraint(table)
        print(f"Primary Key: {pk.get('constrained_columns')}")

        cols = inspector.get_columns(table)
        print("\nColumns:")
        print(f"  {'Column Name':<28} {'Data Type':<22} {'Nullable':<10} {'Default'}")
        print(f"  {'-'*26} {'-'*20} {'-'*8} {'-'*15}")
        for c in cols:
            name = c["name"]
            col_type = str(c["type"])
            nullable = "YES" if c["nullable"] else "NO"
            default = str(c.get("default") or "")
            print(f"  {name:<28} {col_type:<22} {nullable:<10} {default}")

        indexes = inspector.get_indexes(table)
        if indexes:
            print("\nIndexes:")
            for idx in indexes:
                cols_str = ", ".join(idx["column_names"])
                unique_str = " (UNIQUE)" if idx.get("unique") else ""
                print(f"  • {idx['name']}: [{cols_str}]{unique_str}")


def print_data(limit: int = 10, full: bool = False, message_id: str | None = None, all_columns: bool = False) -> None:
    engine = get_engine()
    with engine.connect() as conn:
        if message_id:
            query = text("SELECT * FROM email_processing WHERE message_id = :mid OR internet_message_id = :mid")
            params = {"mid": message_id}
            title = f"DATA FOR MESSAGE ID: {message_id}"
        else:
            query = text("SELECT * FROM email_processing ORDER BY ingestion_time DESC LIMIT :lim")
            params = {"lim": limit}
            title = f"DATA IN email_processing (Latest {limit} row(s))"

        result = conn.execute(query, params)
        rows = result.mappings().all()

        print(f"\n========================================")
        print(f"  {title}")
        print("========================================")
        if not rows:
            print("No matching records found in email_processing.")
            return

        for i, row in enumerate(rows, start=1):
            if all_columns:
                print(f"\n" + "=" * 30 + f" [ ROW {i}: ALL 26 COLUMNS ] " + "=" * 30)
                max_k = max(len(k) for k in row.keys())
                for k, v in row.items():
                    val_str = "<NULL>" if v is None else str(v)
                    if "\n" in val_str:
                        print(f"  {k:<{max_k}} :")
                        for line in val_str.split("\n"):
                            print(f"    {line}")
                    else:
                        print(f"  {k:<{max_k}} : {val_str}")
                print("=" * 76)
                continue

            print(f"\n--- [Row {i}] Message ID: {row['message_id']} ---")
            print(f"  Internet Msg ID: {row['internet_message_id']}")
            print(f"  Sender:          {row['sender_email']}")
            print(f"  Specialist:      {row['payroll_specialist_email']}")
            print(f"  Subject:         {row['subject']}")
            print(f"  Category:        {row['category']}")
            print(f"  Priority:        {row['priority_rate']}")
            print(f"  HITL Status:     {row['hitl_status']}")
            print(f"  Categorized:     {row['is_categorized']} | Drafted: {row['is_drafted']} | Processed: {row['is_processed']}")
            print(f"  Received:        {row['email_received_dttm']}")
            print(f"  Ingested:        {row['ingestion_time']}")

            if full:
                print(f"\n  [Full Email Body]:\n{row['content']}\n")
                print(f"  [Draft Content]:\n{row['draft_content']}\n")
                if row.get('sub_content'):
                    print(f"  [Extracts (sub_content)]:\n{row['sub_content']}\n")
                if row.get('qa_response'):
                    print(f"  [QA Response]:\n{row['qa_response']}\n")
                if row.get('changelist_response'):
                    print(f"  [Changelist Response]:\n{row['changelist_response']}\n")
            else:
                content_preview = (row['content'] or '')[:140].replace('\n', ' ')
                print(f"  Content Preview: {content_preview}...")
                draft_preview = (row['draft_content'] or '')[:140].replace('\n', ' ')
                if draft_preview:
                    print(f"  Draft Preview:   {draft_preview}...")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Neon DB schema and data")
    parser.add_argument("--schema", action="store_true", help="Print table schema")
    parser.add_argument("--data", action="store_true", help="Print table rows")
    parser.add_argument("--all", action="store_true", help="Print ALL 26 columns for each row")
    parser.add_argument("--full", action="store_true", help="Print full text columns")
    parser.add_argument("--limit", type=int, default=10, help="Row limit (e.g. --limit 1)")
    parser.add_argument("--id", type=str, default=None, help="Retrieve single row by message_id")
    args = parser.parse_args()

    if args.id:
        print_data(message_id=args.id, full=args.full, all_columns=args.all)
    elif not args.schema and not args.data:
        print_schema()
        print_data(limit=args.limit, full=args.full, all_columns=args.all)
    else:
        if args.schema:
            print_schema()
        if args.data:
            print_data(limit=args.limit, full=args.full, all_columns=args.all)


if __name__ == "__main__":
    main()
