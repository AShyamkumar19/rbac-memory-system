CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

SET timezone = 'UTC';

CREATE TYPE access_scope_type AS ENUM ('own', 'project', 'department', 'organization', 'session');
CREATE TYPE classification_type AS ENUM ('public', 'internal', 'confidential', 'secret');
CREATE TYPE memory_tier_type AS ENUM ('short_term', 'long_term', 'mid-term');
CREATE TYPE project_status AS ENUM ('planning', 'active', 'completed', 'on-hold', 'cancelled');

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Function to generate unique codes
CREATE OR REPLACE FUNCTION generate_unique_code(prefix TEXT, length INTEGER DEFAULT 6)
RETURNS TEXT AS $$
DECLARE
    chars TEXT := 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    result TEXT := prefix;
    i INTEGER := 0;
BEGIN
    FOR i IN 1..length LOOP
        result := result || substr(chars, floor(random() * length(chars) + 1)::integer, 1);
    END LOOP;
    RETURN result;
END;
$$ language 'plpgsql';

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'Database initialized successfully at %', CURRENT_TIMESTAMP;
END $$;