-- V2.2 Migration: Add missing columns to user_profiles
-- Run this in Supabase SQL Editor
ALTER TABLE user_profiles
ADD COLUMN IF NOT EXISTS target_degree text DEFAULT '修士',
ADD COLUMN IF NOT EXISTS research_area text DEFAULT '',
ADD COLUMN IF NOT EXISTS gpa_score float DEFAULT 0.0,
ADD COLUMN IF NOT EXISTS gpa_scale float DEFAULT 4.0,
ADD COLUMN IF NOT EXISTS facts jsonb DEFAULT '{}',
ADD COLUMN IF NOT EXISTS events jsonb DEFAULT '[]',
ADD COLUMN IF NOT EXISTS applications jsonb DEFAULT '[]',
ADD COLUMN IF NOT EXISTS target_professors jsonb DEFAULT '[]',
ADD COLUMN IF NOT EXISTS application_stage text DEFAULT '',
ADD COLUMN IF NOT EXISTS field_sources jsonb DEFAULT '{}';
