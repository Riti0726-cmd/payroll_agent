"""Print the last N rows from email_processing."""
import psycopg2

DATABASE_URL = (
    "postgresql://neondb_owner:npg_FgnL6WNsJ4Ud"
    "@ep-withered-math-az5cs1xt-pooler.c-3.ap-southeast-1.aws.neon.tech"
    "/neondb?sslmode=require&channel_binding=require"
)

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("""
    SELECT message_id, sender_email, name, subject,
           is_categorized, is_drafted, is_processed,
           ingestion_time
    FROM email_processing
    ORDER BY ingestion_time DESC
    LIMIT 10;
""")

rows = cur.fetchall()
cur.close()
conn.close()

sep = "-" * 130
header = "{:<32} {:<30} {:<18} {:<33} {:<5} {:<6} {:<5}".format(
    "message_id", "sender_email", "name", "subject", "cat", "draft", "proc"
)
print(sep)
print(header)
print(sep)
for r in rows:
    msg_id   = str(r[0])[:31]
    sender   = str(r[1])[:29]
    name     = str(r[2])[:17]
    subject  = str(r[3])[:32]
    is_cat   = str(r[4])
    is_draft = str(r[5])
    is_proc  = str(r[6])
    print("{:<32} {:<30} {:<18} {:<33} {:<5} {:<6} {:<5}".format(
        msg_id, sender, name, subject, is_cat, is_draft, is_proc
    ))
print(sep)
print("Showing {} rows — ordered by ingestion_time DESC".format(len(rows)))

