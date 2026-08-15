#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Alembic safely creates an empty schema or adopts/upgrades a supported existing
# schema. The command is idempotent and never clears application tables.
KAFKA_QUEUE_AUTH_PASSWORD="${KAFKA_QUEUE_AUTH_PASSWORD:-migration-not-used}" \
  docker-compose -f "${project_dir}/docker-compose.yaml" run --rm --build db-migrate
