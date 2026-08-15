#!/usr/bin/env bash
set -u

: "${KAFKA_QUEUE_AUTH_PASSWORD:?export KAFKA_QUEUE_AUTH_PASSWORD before running this test}"

auth_user="${KAFKA_QUEUE_AUTH_USER:-admin}"
auth_password="${KAFKA_QUEUE_AUTH_PASSWORD}"
failures=0

status_without_auth() {
  local method="${2:-GET}"
  curl --silent --show-error --max-time 15 --output /dev/null \
    --write-out '%{http_code}' --request "${method}" "$1"
}

status_with_auth() {
  local method="${2:-GET}"
  curl --silent --show-error --max-time 15 --output /dev/null \
    --write-out '%{http_code}' --request "${method}" \
    --user "${auth_user}:${auth_password}" "$1"
}

check_public() {
  local name="$1"
  local url="$2"
  local status
  status="$(status_without_auth "${url}" || true)"
  if [[ "${status}" == "200" ]]; then
    printf 'PASS public    %-24s %s\n' "${name}" "${status}"
  else
    printf 'FAIL public    %-24s expected 200, got %s\n' "${name}" "${status:-curl-error}"
    failures=$((failures + 1))
  fi
}

check_protected() {
  local name="$1"
  local url="$2"
  local allowed_with_auth="$3"
  local method="${4:-GET}"
  local anonymous_status authenticated_status
  anonymous_status="$(status_without_auth "${url}" "${method}" || true)"
  authenticated_status="$(status_with_auth "${url}" "${method}" || true)"

  if [[ "${anonymous_status}" != "401" ]]; then
    printf 'FAIL protected %-24s anonymous expected 401, got %s\n' \
      "${name}" "${anonymous_status:-curl-error}"
    failures=$((failures + 1))
    return
  fi

  if [[ " ${allowed_with_auth} " == *" ${authenticated_status} "* ]]; then
    printf 'PASS protected %-24s 401 -> %s\n' "${name}" "${authenticated_status}"
  else
    printf 'FAIL protected %-24s authenticated expected [%s], got %s\n' \
      "${name}" "${allowed_with_auth}" "${authenticated_status:-curl-error}"
    failures=$((failures + 1))
  fi
}

check_public "in health" "http://localhost:7091/in/healthcheck"
check_protected "in send" "http://localhost:7091/in/send" "400 415" "POST"

check_public "out health" "http://localhost:7092/out/healthcheck"
check_protected "out sessions" "http://localhost:7092/out/list_sessions" "200"

check_public "storage health" "http://localhost:7093/files/healthcheck"
check_protected "storage files" "http://localhost:7093/files/list_files/" "200"

check_public "logic auth status" "http://localhost:7096/auth/status"
check_protected "logic requests" "http://localhost:7096/requests" "200"

check_public "hold auth status" "http://localhost:7097/hold_admin_panel/auth/status"
check_protected "hold messages" "http://localhost:7097/hold_admin_panel/held_messages" "200"

check_public "hold 2 auth status" "http://localhost:7099/hold_admin_panel_2/auth/status"
check_protected "hold 2 messages" "http://localhost:7099/hold_admin_panel_2/held_messages" "200"

check_public "queue auth status" "http://localhost:7094/auth/status"
check_protected "queue info" "http://localhost:7094/admin/queue_info" "200"
check_protected "queue proxy" "http://localhost:7094/admin/services/logic/requests" "200"

if (( failures > 0 )); then
  printf '\nAuthentication smoke test failed: %d check(s).\n' "${failures}" >&2
  exit 1
fi

printf '\nAuthentication smoke test passed.\n'
