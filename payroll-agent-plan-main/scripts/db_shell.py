"""Interactive SQL shell connected to the configured DATABASE_URL."""

from __future__ import annotations

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
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PKG))
sys.path.insert(0, str(SCRIPTS))
os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from sqlalchemy import text
from db.database import get_engine


def run_shell() -> None:
    engine = get_engine()
    print("=" * 65)
    print("  Interactive Database Shell (PostgreSQL / Neon)")
    print("  • Type 'data' (or 'latest') to view the latest row with all 26 columns")
    print("  • Type 'schema' (or '\\d') to view the table schema & indexes")
    print("  • Type any SQL query (e.g. SELECT * FROM email_processing LIMIT 1;)")
    print("  • Type 'exit' / 'quit' to leave")
    print("=" * 65 + "\n")

    while True:
        try:
            query = input("db-sql> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not query:
            continue
        if query.lower() in ("exit", "quit", "q"):
            print("Goodbye!")
            break
        if query.lower() in ("schema", "\\d", "\\dt"):
            try:
                from scripts.db_inspect import print_schema
            except ImportError:
                from db_inspect import print_schema
            print_schema()
            continue

        # Handle 'data', 'latest', or pasted db_inspect invocation directly inside shell
        lower_q = query.lower()
        if (
            lower_q in ("data", "latest", "row", "inspect", "show")
            or "db_inspect" in lower_q
            or lower_q.startswith("data ")
        ):
            try:
                from scripts.db_inspect import print_data
            except ImportError:
                from db_inspect import print_data

            # Check if limit was specified like 'data 3'
            limit = 1
            parts = query.split()
            for p in parts:
                if p.isdigit():
                    limit = int(p)
                    break
            print_data(limit=limit, all_columns=True)
            continue

        # Strip trailing semicolon for execution if present
        exec_query = query.rstrip(";")
        try:
            with engine.connect() as conn:
                res = conn.execute(text(exec_query))
                if res.returns_rows:
                    rows = res.mappings().all()
                    if not rows:
                        print("  (0 rows returned)")
                    else:
                        print(f"\n  Result: {len(rows)} record(s) returned")
                        for i, r in enumerate(rows, 1):
                            row_dict = dict(r)
                            print(f"\n" + "=" * 30 + f" [ RECORD {i} ] " + "=" * 30)
                            max_k = max(len(str(k)) for k in row_dict.keys()) if row_dict else 10
                            for k, v in row_dict.items():
                                val_str = "<NULL>" if v is None else str(v)
                                # If multi-line, indent for clean reading
                                if "\n" in val_str:
                                    print(f"  {k:<{max_k}} :")
                                    for line in val_str.split("\n"):
                                        print(f"    {line}")
                                else:
                                    print(f"  {k:<{max_k}} : {val_str}")
                        print("=" * 74 + "\n")
                else:
                    conn.commit()
                    print(f"  Executed successfully (rowcount: {res.rowcount})\n")
        except Exception as exc:
            print(f"  Error: {exc}\n")


if __name__ == "__main__":
    run_shell()
