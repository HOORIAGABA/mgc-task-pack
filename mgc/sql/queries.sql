-- ============================================================
-- Query 1: Conversion rate by lead source (best first),
--          only for sources with 200+ leads.
-- ============================================================

SELECT
    source,
    COUNT(*)                                          AS total_leads,
    SUM(CASE WHEN converted THEN 1 ELSE 0 END)       AS converted,
    ROUND(
        SUM(CASE WHEN converted THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    )                                                 AS conversion_pct
FROM leads
GROUP BY source
HAVING COUNT(*) >= 200
ORDER BY conversion_pct DESC;


-- ============================================================
-- Query 2: Find duplicate leads — same person entered twice
--          by different agents.
--
-- crm_record_hash is a deterministic hash of identifying info
-- (phone, CNIC, or both). Any hash appearing more than once
-- means the same lead was entered into the CRM multiple times.
--
-- To prevent this at the schema level: a UNIQUE constraint on
-- crm_record_hash (already in schema.sql) causes the second
-- INSERT to fail. At the application layer you'd instead do
-- an UPSERT — match on hash, update the existing row's agent
-- metadata and created_at if the new entry is fresher, rather
-- than rejecting the insert outright.
-- ============================================================

SELECT
    crm_record_hash,
    COUNT(*)                                         AS entries,
    MIN(created_at)                                  AS first_entered,
    MAX(created_at)                                  AS last_entered,
    GROUP_CONCAT(DISTINCT lead_id ORDER BY created_at) AS lead_ids   -- SQLite
    -- STRING_AGG(DISTINCT lead_id, ', ' ORDER BY created_at) AS lead_ids  -- PostgreSQL
FROM leads
GROUP BY crm_record_hash
HAVING COUNT(*) > 1
ORDER BY entries DESC, first_entered;
