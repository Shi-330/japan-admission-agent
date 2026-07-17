-- schools_v2.sql
-- Schema migration: add new structured columns to schools table.
-- Run this in Supabase SQL Editor BEFORE running migrate_schools_v2.py.
--
-- Does NOT drop old columns (jlpt, english) — they are kept for one release cycle
-- then cleaned up manually after migration is verified.

ALTER TABLE schools ADD COLUMN IF NOT EXISTS jlpt_min text DEFAULT '';
ALTER TABLE schools ADD COLUMN IF NOT EXISTS gpa_min float8 DEFAULT 0.0;
ALTER TABLE schools ADD COLUMN IF NOT EXISTS english_req jsonb DEFAULT '{"required": false}'::jsonb;
ALTER TABLE schools ADD COLUMN IF NOT EXISTS source text DEFAULT 'manual';
ALTER TABLE schools ADD COLUMN IF NOT EXISTS verified bool DEFAULT false;
ALTER TABLE schools ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();
-- 结构化 deadlines 走新列：老 deadlines dict 列原样保留，生产老代码不受影响
ALTER TABLE schools ADD COLUMN IF NOT EXISTS deadlines_v2 jsonb DEFAULT NULL;
