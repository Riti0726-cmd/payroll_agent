"""
Interactive DB Shell for email_processing (Neon PostgreSQL)
-----------------------------------------------------------
Type any SQL query and press Enter to run it.
Shortcuts:
  \l          -> last 10 rows (by ingestion_time)
  \c          -> row count
  \cols       -> show all column names
  \q or exit  -> quit
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_FgnL6WNsJ4Ud"
    "@ep-withered-math-az5cs1xt-pooler.c-3.ap-southeast-1.aws.neon.tech"
    "/neondb?sslmode=require&channel_binding=require",
)

SHORTCUTS = {
    r"\l": "SELECT message_id, sender_email, name, subject, is_categorized, is_drafted, is_processed, ingestion_time FROM email_processing ORDER BY ingestion_time DESC LIMIT 10",
    r"\c": "SELECT COUNT(*) AS total_rows FROM email_processing",
    r"\cols": "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'email_processing' ORDER BY ordinal_position",
}

def print_results(cur):
    rows = cur.fetchall()
    if not rows:
        print("  (no rows returned)")
        return
    cols = [desc[0] for desc in cur.description]
    # Calculate column widths
    widths = [len(c) for c in cols]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val) if val is not None else "NULL"))
    # Cap width at 40 chars
    widths = [min(w, 40) for w in widths]
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    def fmt_row(values):
        parts = []
        for i, v in enumerate(values):
            s = str(v) if v is not None else "NULL"
            if len(s) > widths[i]:
                s = s[:widths[i] - 1] + "~"
            parts.append(f" {s:<{widths[i]}} ")
        return "|" + "|".join(parts) + "|"
    print(sep)
    print(fmt_row(cols))
    print(sep)
    for row in rows:
        print(fmt_row([row[c] for c in cols]))
    print(sep)
    print(f"  {len(rows)} row(s)")

def main():
    print("=" * 60)
    print("  Payroll DB Shell  —  Neon PostgreSQL")
    print("=" * 60)
    print("  Shortcuts: \\l (last 10)  \\c (count)  \\cols (columns)")
    print("  Type SQL or \\q to quit")
    print("=" * 60)

    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        conn.autocommit = True
        print("  Connected to Neon DB\n")
    except Exception as e:
        print(f"  Connection failed: {e}")
        return

    buffer = []
    while True:
        try:
            prompt = "db> " if not buffer else "... "
            line = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Bye!")
            break

        if not line:
            continue

        if line.lower() in (r"\q", "exit", "quit"):
            print("  Bye!")
            break

        # Expand shortcuts
        expanded = SHORTCUTS.get(line, line)
        if expanded != line:
            buffer = [expanded]
        else:
            buffer.append(line)

        # Execute when query ends with semicolon OR is a shortcut
        full_query = " ".join(buffer)
        if full_query.rstrip().endswith(";") or expanded != line:
            try:
                cur = conn.cursor()
                cur.execute(full_query)
                if cur.description:
                    print_results(cur)
                else:
                    print(f"  OK — {cur.rowcount} row(s) affected")
                cur.close()
            except Exception as e:
                print(f"  ERROR: {e}")
            buffer = []

    conn.close()

if __name__ == "__main__":
    main()

