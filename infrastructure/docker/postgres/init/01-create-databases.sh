#!/bin/bash
set -e

echo "Initializing Agentic AI Lab databases..."

psql \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --set ON_ERROR_STOP=1 \
    --set agentlab_db="$AGENTLAB_DB_NAME" \
    --set agentlab_user="$AGENTLAB_DB_USER" \
    --set agentlab_password="$AGENTLAB_DB_PASSWORD" \
    --set langfuse_db="$LANGFUSE_DB_NAME" \
    --set langfuse_user="$LANGFUSE_DB_USER" \
    --set langfuse_password="$LANGFUSE_DB_PASSWORD" <<'EOSQL'

CREATE ROLE :"agentlab_user" LOGIN PASSWORD :'agentlab_password';
CREATE DATABASE :"agentlab_db" OWNER :"agentlab_user";

CREATE ROLE :"langfuse_user" LOGIN PASSWORD :'langfuse_password';
CREATE DATABASE :"langfuse_db" OWNER :"langfuse_user";

EOSQL

echo "Database initialization completed successfully."