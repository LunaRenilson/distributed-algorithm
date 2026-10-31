#!/bin/bash
set -euo pipefail

PRIMARY_HOST="${POSTGRES_PRIMARY_HOST:-postgres-primary}"
REPL_USER="${POSTGRES_REPLICATION_USER:-replicator}"
REPL_PASSWORD="${POSTGRES_REPLICATION_PASSWORD:-replicator_dev}"

if [ ! -s "${PGDATA}/PG_VERSION" ]; then
    echo "Waiting for primary (${PRIMARY_HOST})..."
    until pg_isready -h "${PRIMARY_HOST}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"; do
        sleep 2
    done

    echo "Cloning standby from ${PRIMARY_HOST}..."
    export PGPASSWORD="${REPL_PASSWORD}"
    pg_basebackup \
        -h "${PRIMARY_HOST}" \
        -p 5432 \
        -U "${REPL_USER}" \
        -D "${PGDATA}" \
        -Fp -Xs -P -R
    unset PGPASSWORD

    chown -R postgres:postgres "${PGDATA}"
    chmod 700 "${PGDATA}"
fi

exec /usr/local/bin/docker-entrypoint.sh postgres
