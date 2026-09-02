"""Verify schema.sql and queries.sql against the CSV data using SQLite."""
import csv, sqlite3
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data" / "leads.csv"
rows = list(csv.DictReader(open(_DATA, encoding="utf-8")))
conn = sqlite3.connect(":memory:")
cur = conn.cursor()

cur.execute("""
CREATE TABLE leads (
    lead_id TEXT PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    source TEXT NOT NULL,
    city TEXT, area TEXT, property_type TEXT,
    budget_pkr_lac REAL, bedrooms INTEGER,
    first_response_minutes REAL,
    calls_made INTEGER DEFAULT 0,
    total_call_seconds REAL DEFAULT 0,
    whatsapp_replies INTEGER DEFAULT 0,
    site_visits INTEGER DEFAULT 0,
    agent_experience_years REAL,
    is_overseas INTEGER DEFAULT 0,
    referred_by_existing_client INTEGER DEFAULT 0,
    has_financing_approved INTEGER DEFAULT 0,
    token_amount_received_pkr REAL DEFAULT 0,
    crm_record_hash TEXT NOT NULL,
    converted INTEGER DEFAULT 0
)
""")

for r in rows:
    cur.execute(
        "INSERT INTO leads VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            r["lead_id"], r["created_at"], r["source"], r["city"], r["area"],
            r["property_type"],
            float(r["budget_pkr_lac"]) if r["budget_pkr_lac"] else None,
            int(float(r["bedrooms"])) if r["bedrooms"] else None,
            float(r["first_response_minutes"]) if r["first_response_minutes"] else None,
            int(float(r["calls_made"])),
            float(r["total_call_seconds"]),
            int(float(r["whatsapp_replies"])),
            int(float(r["site_visits"])),
            float(r["agent_experience_years"]) if r["agent_experience_years"] else None,
            int(float(r["is_overseas"])),
            int(float(r["referred_by_existing_client"])),
            int(float(r["has_financing_approved"])),
            float(r["token_amount_received_pkr"]),
            r["crm_record_hash"],
            int(float(r["converted"])),
        ),
    )
conn.commit()
print(f"Loaded {len(rows)} rows.\n")

# --- Q1 ---
print("=== Q1: Conversion rate by source (200+ leads) ===")
for row in cur.execute("""
    SELECT source, COUNT(*) as total_leads,
           SUM(CASE WHEN converted THEN 1 ELSE 0 END) as converted,
           ROUND(SUM(CASE WHEN converted THEN 1 ELSE 0 END)*100.0/COUNT(*),2)
    FROM leads GROUP BY source HAVING COUNT(*) >= 200 ORDER BY 4 DESC
"""):
    print(f"  {row[0]:20s}  {row[1]:5d} leads  {row[2]:4d} converted  {row[3]:5.2f}%")

# --- Q2 ---
print("\n=== Q2: Duplicate leads ===")
dups = cur.execute("""
    SELECT crm_record_hash, COUNT(*) as entries,
           MIN(created_at), MAX(created_at)
    FROM leads GROUP BY crm_record_hash HAVING COUNT(*) > 1 ORDER BY entries DESC
""").fetchall()
print(f"  Hashes with >1 entry: {len(dups)}")
print(f"  Total duplicate rows: {sum(d[1] for d in dups)}")
for h, c, first, last in dups[:5]:
    print(f"  Hash {h}: {c} entries ({first} -> {last})")

conn.close()
