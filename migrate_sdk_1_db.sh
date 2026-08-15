#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sdk_dir="${project_dir}/../kafkaQueueSdk"
migration="${sdk_dir}/migrations/1.0.0/001_sessions_external_id.sql"

if [[ ! -f "${migration}" ]]; then
  echo "SDK 1.0 migration not found at ${migration}" >&2
  exit 1
fi

if ! KAFKA_QUEUE_AUTH_PASSWORD="${KAFKA_QUEUE_AUTH_PASSWORD:-migration-not-used}" \
  docker-compose -f "${project_dir}/docker-compose.yaml" ps --status running postgres_db | grep -q postgres_db; then
  echo "Start PostgreSQL first: docker-compose up -d postgres_db" >&2
  exit 1
fi

# Run only for an existing pre-1.0 schema. A database first created by SDK 1.0
# already has the NOT NULL/unique contract and needs no upgrade SQL.
KAFKA_QUEUE_AUTH_PASSWORD="${KAFKA_QUEUE_AUTH_PASSWORD:-migration-not-used}" \
  docker-compose -f "${project_dir}/docker-compose.yaml" exec -T postgres_db \
  sh -c 'exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < "${migration}"
