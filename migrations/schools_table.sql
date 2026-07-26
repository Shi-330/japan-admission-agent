-- Migration: move SCHOOL_CATALOG from hardcoded Python to Supabase
-- Run this in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS schools (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    majors TEXT[] DEFAULT '{}',
    degree TEXT DEFAULT '修士',
    jlpt TEXT DEFAULT '',
    english TEXT DEFAULT '',
    exam TEXT DEFAULT '',
    deadlines JSONB DEFAULT '{}',
    notes TEXT DEFAULT '',
    tags TEXT[] DEFAULT '{}',
    website TEXT DEFAULT '',
    source TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Enable RLS but allow public read
ALTER TABLE schools ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Anyone can read schools" ON schools
    FOR SELECT USING (true);

-- Enable API access
COMMENT ON TABLE schools IS 'Reference catalog of Japanese graduate schools';
