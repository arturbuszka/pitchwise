-- Dev migration: adds hls_ready to the highlight table on an existing database.
-- EnsureCreated() does NOT alter an existing table, so run this once against a DB
-- that predates the HLS feature. Fresh databases get the column from EnsureCreated.
ALTER TABLE highlight ADD COLUMN IF NOT EXISTS hls_ready BOOLEAN NOT NULL DEFAULT false;
