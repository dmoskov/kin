-- One-time bootstrap for RDS IAM authentication (no database password).
--
-- Run ONCE as the RDS master user against the familytree database:
--
--   psql "$MASTER_DATABASE_URL" -v ON_ERROR_STOP=1 -f deploy/db-iam-setup.sql
--
-- Afterwards set DATABASE_URL to a passwordless DSN in .env:
--   DATABASE_URL=postgresql://familytree_app@<host>:5432/familytree?sslmode=require
-- and grant the EC2 instance role rds-db:connect on that dbuser (README →
-- "Production deployment" → "Database authentication").
--
-- Idempotent: safe to re-run. It never drops anything.

-- Audit logging: the parameter group preloads pgaudit (pgaudit.log = ddl,role),
-- but the extension must be created once, by the master user, per database.
CREATE EXTENSION IF NOT EXISTS pgaudit;

-- App role: LOGIN, no password. rds_iam makes Postgres accept an RDS IAM
-- token (minted by src/database/connection.py) in place of a password.
SELECT 'CREATE ROLE familytree_app LOGIN'
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'familytree_app')\gexec
GRANT rds_iam TO familytree_app;

-- Hand every existing table/sequence/etc in this database to the app role so
-- schema migrations (ALTER TABLE …) keep working without the master user.
-- The master user is a member of the app role afterwards, so it can still
-- administer everything.
GRANT familytree_app TO CURRENT_USER;
REASSIGN OWNED BY CURRENT_USER TO familytree_app;
GRANT ALL ON SCHEMA public TO familytree_app;
