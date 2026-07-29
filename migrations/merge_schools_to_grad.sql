-- Migration: merge schools enrichment data into graduate_schools
-- Goal: universities → graduate_schools (single source of truth, inherits all op data)
-- After migration, the schools table can be dropped.

BEGIN;

-- 1. Add enrichment columns to graduate_schools
ALTER TABLE graduate_schools
  ADD COLUMN IF NOT EXISTS majors           TEXT[]        DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS tags             TEXT[]        DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS degree           TEXT          DEFAULT '修士',
  ADD COLUMN IF NOT EXISTS deadlines        JSONB         DEFAULT '[]',
  ADD COLUMN IF NOT EXISTS english_req      JSONB         DEFAULT '{"required": false}',
  ADD COLUMN IF NOT EXISTS jlpt_min         TEXT          DEFAULT '',
  ADD COLUMN IF NOT EXISTS gpa_min          FLOAT         DEFAULT 0.0,
  ADD COLUMN IF NOT EXISTS pdf_url          TEXT          DEFAULT '',
  ADD COLUMN IF NOT EXISTS enrichment_status TEXT        DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS source           TEXT          DEFAULT 'catalog',
  ADD COLUMN IF NOT EXISTS verified         BOOLEAN       DEFAULT false;

-- 2. Comment existing overlap columns for clarity
COMMENT ON COLUMN graduate_schools.exam_type IS '入試形式（schools.exam を移行）';
COMMENT ON COLUMN graduate_schools.jlpt     IS '日本語要件記述テキスト';
COMMENT ON COLUMN graduate_schools.english  IS '英語要件記述テキスト（構造化は english_req で）';
COMMENT ON COLUMN graduate_schools.notes    IS '内部備考・ノウハウ';

COMMIT;
