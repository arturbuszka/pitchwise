-- Dev migration: adds the `highlight` table to an existing database.
-- .NET uses EnsureCreated() (all-or-nothing), so a new table is NOT auto-added to a
-- DB that already exists. Run this once against such a DB. Matches the EF mapping in
-- AppDbContext (snake_case columns, text status, timestamptz timestamps).
CREATE TABLE IF NOT EXISTS highlight (
    id               SERIAL PRIMARY KEY,
    analysis_id      INTEGER NOT NULL,
    name             TEXT NOT NULL,
    event_ids        TEXT NOT NULL,
    status           TEXT NOT NULL,
    progress         DOUBLE PRECISION NOT NULL DEFAULT 0,
    filename         TEXT,
    error            TEXT,
    share_token      TEXT,
    share_expires_at TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_highlight_analysis_id ON highlight (analysis_id);
CREATE INDEX IF NOT EXISTS ix_highlight_share_token ON highlight (share_token);
