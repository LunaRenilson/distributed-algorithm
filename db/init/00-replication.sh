#!/bin/bash
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'EOSQL'
    DO $do$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'replicator') THEN
            CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD 'replicator_dev';
        END IF;
    END
    $do$;
EOSQL

{
    echo "host replication replicator all scram-sha-256"
} >> "$PGDATA/pg_hba.conf"
