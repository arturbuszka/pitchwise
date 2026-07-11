-- Dev migration: whole-match aggregate statistics (possession, passing, time-on-pitch).
-- EnsureCreated() builds this table for fresh databases from the AppDbContext mapping; run this
-- once against a DB that predates the feature. Matches the CREATE in Program.cs.

CREATE TABLE IF NOT EXISTS matchstats (
    id SERIAL PRIMARY KEY,
    video_id INTEGER NOT NULL UNIQUE,
    analysis_id INTEGER NOT NULL,
    possession_pct_a DOUBLE PRECISION NOT NULL DEFAULT 0,
    possession_pct_b DOUBLE PRECISION NOT NULL DEFAULT 0,
    controlled_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
    loose_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
    passes_a INTEGER NOT NULL DEFAULT 0,
    passes_b INTEGER NOT NULL DEFAULT 0,
    turnovers_a INTEGER NOT NULL DEFAULT 0,
    turnovers_b INTEGER NOT NULL DEFAULT 0,
    pass_accuracy_pct_a DOUBLE PRECISION NOT NULL DEFAULT 0,
    pass_accuracy_pct_b DOUBLE PRECISION NOT NULL DEFAULT 0,
    time_on_pitch_json TEXT NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
