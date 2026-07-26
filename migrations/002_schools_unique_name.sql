-- Add unique constraint on schools.name so upsert works
ALTER TABLE schools ADD UNIQUE (name);
