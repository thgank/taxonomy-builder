#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
K6_BASE_URL="${K6_BASE_URL:-}"
API_KEY="${API_KEY:-dev-api-key-change-me}"
K6_IMAGE="${K6_IMAGE:-grafana/k6}"
PERF_ENV="${PERF_ENV:-local}"
INFLUXDB_URL="${INFLUXDB_URL:-http://localhost:8086}"
K6_INFLUXDB_URL="${K6_INFLUXDB_URL:-}"
INFLUXDB_DB="${INFLUXDB_DB:-k6}"
RESULTS_ROOT="${RESULTS_ROOT:-qa/k6-results}"
RUN_LABEL="${RUN_LABEL:-$(date +%Y%m%d-%H%M%S)}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-taxonomy-postgres-dev}"
POSTGRES_DB="${POSTGRES_DB:-taxonomy}"
POSTGRES_USER="${POSTGRES_USER:-taxonomy}"
JOB_ID="${JOB_ID:-}"
TAXONOMY_ID="${TAXONOMY_ID:-}"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/run_k6_perf.sh

Environment overrides:
  BASE_URL=http://localhost:8080
  K6_BASE_URL=http://host.docker.internal:8080
  API_KEY=dev-api-key-change-me
  PERF_ENV=local
  INFLUXDB_URL=http://localhost:8086
  K6_INFLUXDB_URL=http://host.docker.internal:8086
  INFLUXDB_DB=k6
  RESULTS_ROOT=qa/k6-results
  RUN_LABEL=20260408-153000
  POSTGRES_CONTAINER=taxonomy-postgres-dev
  POSTGRES_DB=taxonomy
  POSTGRES_USER=taxonomy
  JOB_ID=<uuid>
  TAXONOMY_ID=<uuid>

The script resolves JOB_ID and TAXONOMY_ID from Docker PostgreSQL automatically
when they are not provided.
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required" >&2
  exit 1
fi

resolve_k6_base_url() {
  if [ -n "$K6_BASE_URL" ]; then
    return
  fi

  case "$BASE_URL" in
    http://localhost*)
      K6_BASE_URL="http://host.docker.internal${BASE_URL#http://localhost}"
      ;;
    https://localhost*)
      K6_BASE_URL="https://host.docker.internal${BASE_URL#https://localhost}"
      ;;
    http://127.0.0.1*)
      K6_BASE_URL="http://host.docker.internal${BASE_URL#http://127.0.0.1}"
      ;;
    https://127.0.0.1*)
      K6_BASE_URL="https://host.docker.internal${BASE_URL#https://127.0.0.1}"
      ;;
    *)
      K6_BASE_URL="$BASE_URL"
      ;;
  esac
}

resolve_k6_influxdb_url() {
  if [ -n "$K6_INFLUXDB_URL" ]; then
    return
  fi

  case "$INFLUXDB_URL" in
    http://localhost*)
      K6_INFLUXDB_URL="http://host.docker.internal${INFLUXDB_URL#http://localhost}"
      ;;
    https://localhost*)
      K6_INFLUXDB_URL="https://host.docker.internal${INFLUXDB_URL#https://localhost}"
      ;;
    http://127.0.0.1*)
      K6_INFLUXDB_URL="http://host.docker.internal${INFLUXDB_URL#http://127.0.0.1}"
      ;;
    https://127.0.0.1*)
      K6_INFLUXDB_URL="https://host.docker.internal${INFLUXDB_URL#https://127.0.0.1}"
      ;;
    *)
      K6_INFLUXDB_URL="$INFLUXDB_URL"
      ;;
  esac
}

resolve_k6_base_url
resolve_k6_influxdb_url

if ! curl -fsS "${BASE_URL}/actuator/health" >/dev/null 2>&1; then
  echo "API is not reachable at ${BASE_URL}. Start api-service first." >&2
  exit 1
fi

if ! curl -fsS "${INFLUXDB_URL}/ping" >/dev/null 2>&1; then
  echo "InfluxDB is not reachable at ${INFLUXDB_URL}. Start docker compose -f docker-compose.perf.yml up -d first." >&2
  exit 1
fi

resolve_job_context() {
  local row

  if [ -n "$JOB_ID" ]; then
    return
  fi

  if ! docker ps --format '{{.Names}}' | grep -qx "$POSTGRES_CONTAINER"; then
    echo "PostgreSQL container ${POSTGRES_CONTAINER} is not running and JOB_ID was not provided." >&2
    exit 1
  fi

  row="$(docker exec "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F '|' -c "SELECT id, COALESCE(taxonomy_version_id::text, '') FROM jobs WHERE taxonomy_version_id IS NOT NULL ORDER BY created_at DESC LIMIT 1;")"
  if [ -n "$row" ]; then
    JOB_ID="${row%%|*}"
    TAXONOMY_ID="${row#*|}"
    return
  fi

  row="$(docker exec "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F '|' -c "SELECT id FROM jobs ORDER BY created_at DESC LIMIT 1;")"
  if [ -z "$row" ]; then
    echo "No jobs found in PostgreSQL and JOB_ID was not provided." >&2
    exit 1
  fi

  JOB_ID="$row"
}

resolve_job_context

RESULTS_DIR="${RESULTS_ROOT}/${RUN_LABEL}"
mkdir -p "$RESULTS_DIR"

K6_DOCKER_ARGS=(--rm -i -v "$PWD:/work" -v "$PWD/${RESULTS_DIR}:/results" -w /work)
if [ "$(uname -s)" = "Linux" ]; then
  K6_DOCKER_ARGS+=(--add-host host.docker.internal:host-gateway)
fi

run_case() {
  local script_path="$1"
  local script_name="$2"
  local p95_target="$3"
  local failure_target="$4"
  shift 4
  local -a env_args=("$@")

  echo "==> ${script_name}"
  docker run "${K6_DOCKER_ARGS[@]}" "$K6_IMAGE" run \
    --tag "service=taxonomy" \
    --tag "env=${PERF_ENV}" \
    --tag "script=${script_name}" \
    --tag "run_id=${RUN_LABEL}" \
    --tag "p95_target=${p95_target}" \
    --tag "failure_target=${failure_target}" \
    --out "influxdb=${K6_INFLUXDB_URL}/${INFLUXDB_DB}" \
    --summary-export "/results/${script_name}-summary.json" \
    "${env_args[@]}" \
    "$script_path"
}

run_case \
  "qa/k6/core-api-smoke.js" \
  "core-api-smoke" \
  "smoke" \
  "smoke" \
  -e "BASE_URL=${K6_BASE_URL}" \
  -e "API_KEY=${API_KEY}" \
  -e "RUN_JOB=true"

run_case \
  "qa/k6/auth-negative-smoke.js" \
  "auth-negative-smoke" \
  "smoke" \
  "smoke" \
  -e "BASE_URL=${K6_BASE_URL}"

run_case \
  "qa/k6/collections-browse-load.js" \
  "collections-browse-load" \
  "1200" \
  "0.03" \
  -e "BASE_URL=${K6_BASE_URL}" \
  -e "API_KEY=${API_KEY}" \
  -e "VUS=10" \
  -e "DURATION=60s" \
  -e "SLEEP_SECONDS=0.5" \
  -e "MAX_FAILED_RATE=0.03" \
  -e "P95_MS=1200"

run_case \
  "qa/k6/job-status-load.js" \
  "job-status-load" \
  "1000" \
  "0.03" \
  -e "BASE_URL=${K6_BASE_URL}" \
  -e "API_KEY=${API_KEY}" \
  -e "JOB_ID=${JOB_ID}" \
  -e "TAXONOMY_ID=${TAXONOMY_ID}" \
  -e "VUS=12" \
  -e "DURATION=90s" \
  -e "SLEEP_SECONDS=0.25" \
  -e "MAX_FAILED_RATE=0.03" \
  -e "P95_MS=1000"

run_case \
  "qa/k6/job-create-burst.js" \
  "job-create-burst" \
  "1800" \
  "0.15" \
  -e "BASE_URL=${K6_BASE_URL}" \
  -e "API_KEY=${API_KEY}" \
  -e "VUS=5" \
  -e "ITERATIONS=6" \
  -e "MAX_DURATION=90s" \
  -e "SLEEP_SECONDS=0.25" \
  -e "MAX_FAILED_RATE=0.15" \
  -e "P95_MS=1800"

run_case \
  "qa/k6/mixed-workflow-load.js" \
  "mixed-workflow-load" \
  "1800" \
  "0.08" \
  -e "BASE_URL=${K6_BASE_URL}" \
  -e "API_KEY=${API_KEY}" \
  -e "JOB_ID=${JOB_ID}" \
  -e "TAXONOMY_ID=${TAXONOMY_ID}" \
  -e "VUS=14" \
  -e "DURATION=90s" \
  -e "SLEEP_SECONDS=0.25" \
  -e "MAX_FAILED_RATE=0.08" \
  -e "P95_MS=1800"

echo "k6 summaries saved to ${RESULTS_DIR}"
echo "Grafana: http://localhost:3000 (admin/admin)"
