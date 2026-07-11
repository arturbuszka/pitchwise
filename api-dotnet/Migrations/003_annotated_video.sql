-- Dev migration: annotated (boxes burned-in) playback.
-- EnsureCreated() does NOT alter existing tables, so run this once against a DB that
-- predates the feature. Fresh databases get the column from EnsureCreated. Matches the
-- EF mapping in AppDbContext and the ALTER in Program.cs.

-- Persistent annotated MP4 (whole video, detection boxes drawn in), for seekable playback.
ALTER TABLE video ADD COLUMN IF NOT EXISTS annotated_filename TEXT NULL;
