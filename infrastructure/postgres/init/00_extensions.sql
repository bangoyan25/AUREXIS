-- AUREXIS PostgreSQL initialization
-- This file runs on first DB creation inside Docker.
-- Schema is managed entirely by Alembic migrations (run separately).
-- Do NOT add schema DDL here — use alembic revision instead.

-- Extension: uuid-ossp for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- Extension: pgcrypto for server-side encryption helpers
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
