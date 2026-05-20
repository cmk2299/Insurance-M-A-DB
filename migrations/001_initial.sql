-- insurance-intel — Sprint 1 schema
-- Author: CMK Digital
-- Date: 2026-05-19
--
-- Design notes:
--   * event_date and transaction_value_eur stay TEXT, not DATE/NUMERIC.
--     Trade press delivers "undisclosed", "Q4 2025", "2025-11-03" as
--     real data points. Value fabrication via default casts is forbidden
--     (Hardline #2 in CMK Insurance Platform DIRECTIVE.md).
--   * content_hash is the dedupe key. Hash is over normalized markdown
--     (lowercased, whitespace-collapsed) of the extracted article.
--   * raw_llm_output retains the full structured response for forensic
--     review if downstream signal classification ever needs auditing.

CREATE TABLE IF NOT EXISTS loop_runs (
    id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('running','succeeded','failed','partial')),
    events_added INT NOT NULL DEFAULT 0,
    events_skipped_dupe INT NOT NULL DEFAULT 0,
    sources_attempted INT NOT NULL DEFAULT 0,
    sources_failed INT NOT NULL DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS trade_press_hits (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES loop_runs(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    snippet TEXT,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    content_hash TEXT NOT NULL,
    raw_markdown TEXT,
    CONSTRAINT trade_press_hits_content_hash_uniq UNIQUE (content_hash)
);
CREATE INDEX IF NOT EXISTS idx_tph_run ON trade_press_hits(run_id);
CREATE INDEX IF NOT EXISTS idx_tph_source ON trade_press_hits(source);
CREATE INDEX IF NOT EXISTS idx_tph_fetched ON trade_press_hits(fetched_at);

CREATE TABLE IF NOT EXISTS ma_events (
    id BIGSERIAL PRIMARY KEY,
    hit_id BIGINT NOT NULL REFERENCES trade_press_hits(id) ON DELETE CASCADE,
    event_date TEXT,
    buyer_name TEXT,
    buyer_consolidator_id TEXT,
    seller_name TEXT,
    deal_type TEXT,
    transaction_value_eur TEXT,
    segment TEXT,
    region TEXT,
    source_url TEXT NOT NULL,
    source_publication TEXT NOT NULL,
    data_quality TEXT NOT NULL CHECK (data_quality IN ('verified-public','aggregate-reference','hypothesis-pending-review')),
    signal_priority INT NOT NULL CHECK (signal_priority BETWEEN 1 AND 5),
    llm_confidence REAL CHECK (llm_confidence BETWEEN 0.0 AND 1.0),
    raw_llm_output JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ma_hit ON ma_events(hit_id);
CREATE INDEX IF NOT EXISTS idx_ma_date ON ma_events(event_date);
CREATE INDEX IF NOT EXISTS idx_ma_buyer ON ma_events(buyer_name);
CREATE INDEX IF NOT EXISTS idx_ma_consolidator ON ma_events(buyer_consolidator_id);
CREATE INDEX IF NOT EXISTS idx_ma_priority ON ma_events(signal_priority);

-- Convenience view: most recent run's events with full provenance
CREATE OR REPLACE VIEW latest_run_events AS
SELECT
    e.id,
    e.event_date,
    e.buyer_name,
    e.buyer_consolidator_id,
    e.seller_name,
    e.deal_type,
    e.transaction_value_eur,
    e.segment,
    e.region,
    e.signal_priority,
    e.data_quality,
    e.llm_confidence,
    h.url AS source_url,
    h.source AS source_publication,
    e.created_at
FROM ma_events e
JOIN trade_press_hits h ON h.id = e.hit_id
JOIN loop_runs r ON r.id = h.run_id
WHERE r.id = (SELECT max(id) FROM loop_runs WHERE status IN ('succeeded','partial'));
