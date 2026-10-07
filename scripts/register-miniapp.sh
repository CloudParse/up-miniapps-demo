#!/usr/bin/env bash
# Registers this mini-app on the LOCAL CloudParse backend (the Hub) and writes
# the credentials it returns to up-miniapps-template-python-backend/.env.
#
#   scripts/register-miniapp.sh            # app name "My Mini-App"
#   APP_NAME="Weather" scripts/register-miniapp.sh
#   FORCE=1 scripts/register-miniapp.sh   # overwrite an existing up-miniapps-template-python-backend/.env
#
# Local development only: it relies on the dev sign-in bypass that docker-compose.yml
# enables (any phone number, OTP code 999999). In production an admin registers
# the app from the back office instead.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HUB_URL="${HUB_URL:-http://localhost:21509/api/v1}"
APP_NAME="${APP_NAME:-My Mini-App}"
BACKEND_URL="${BACKEND_URL:-http://localhost:21514/api/v1}"
ENV_FILE="$ROOT/up-miniapps-template-python-backend/.env"

if [[ -f "$ENV_FILE" && "${FORCE:-0}" != "1" ]]; then
  echo "up-miniapps-template-python-backend/.env already exists. Re-run with FORCE=1 to overwrite it." >&2
  exit 1
fi

# Local-only throwaway admin account: it only exists in your local database.
ADMIN_COUNTRY_CODE="+33"
ADMIN_LOCAL_NUMBER="612345678"
ADMIN_PASSWORD="password123"

post_json() { # <path> <json> [bearer-token]
  curl -fsS -X POST "$HUB_URL$1" -H 'Content-Type: application/json' \
    ${3:+-H "Authorization: Bearer $3"} -d "$2"
}

require() { command -v "$1" >/dev/null || { echo "Missing dependency: $1" >&2; exit 1; }; }
require curl
require jq
require docker

create_admin_user() {
  local phone="$ADMIN_COUNTRY_CODE$ADMIN_LOCAL_NUMBER" request_id verification_token
  request_id=$(post_json /auth/send-otp "{\"phone\":\"$phone\"}" | jq -r .requestId)
  verification_token=$(post_json /auth/verify-otp \
    "{\"requestId\":\"$request_id\",\"code\":\"999999\"}" | jq -r .verificationToken)
  post_json /auth/register "$(jq -n --arg vt "$verification_token" --arg phone "$phone" \
    --arg pw "$ADMIN_PASSWORD" \
    '{verificationToken:$vt, phone:$phone, password:$pw, firstName:"Dev", lastName:"Admin", username:"devadmin"}')" \
    >/dev/null
}

promote_to_admin() {
  docker compose -f "$ROOT/docker-compose.yml" exec -T postgres \
    psql -U "${POSTGRES_USER:-postgres}" -q \
    -c "UPDATE users SET admin = true WHERE country_code = '$ADMIN_COUNTRY_CODE' AND local_number = '$ADMIN_LOCAL_NUMBER';"
}

login_admin() {
  post_json /auth/login "$(jq -n --arg cc "$ADMIN_COUNTRY_CODE" --arg ln "$ADMIN_LOCAL_NUMBER" \
    --arg pw "$ADMIN_PASSWORD" '{countryCode:$cc, localNumber:$ln, password:$pw}')" | jq -r .token
}

echo "1/4 Preparing a local admin user..."
if ! admin_error=$(create_admin_user 2>&1); then
  # Registering again is expected to fail once the admin exists; anything else
  # (Hub down, bypass disabled) surfaces at the login below.
  echo "    (admin user not created: assuming it already exists)"
  echo "    $admin_error" | head -n 1 >&2
fi
promote_to_admin
admin_token=$(login_admin)

echo "2/4 Registering \"$APP_NAME\" on the Hub..."
origin="$(echo "$BACKEND_URL" | sed -E 's#^(https?://[^/]+).*#\1#')"
if ! application=$(post_json /admin/applications "$(jq -n --arg name "$APP_NAME" \
  --arg url "$BACKEND_URL" --arg origin "$origin" \
  '{name:$name, description:"Registered by scripts/register-miniapp.sh", httpBackendUrl:$url, allowedOrigins:[$origin], isDarkTheme:true}')" \
  "$admin_token"); then
  echo "Registration failed. Is \"$APP_NAME\" already registered? Pick another APP_NAME." >&2
  exit 1
fi
app_uuid=$(echo "$application" | jq -r .application.uuid)
client_secret=$(echo "$application" | jq -r .clientSecret)

echo "3/4 Verifying the machine-to-machine credentials..."
post_json /partner/auth/login \
  "$(jq -n --arg id "$app_uuid" --arg secret "$client_secret" '{appUuid:$id, clientSecret:$secret}')" \
  | jq -e .token >/dev/null

echo "4/4 Writing up-miniapps-template-python-backend/.env..."
umask 077
printf 'HUB_APP_UUID=%s\nHUB_CLIENT_SECRET=%s\n' "$app_uuid" "$client_secret" > "$ENV_FILE"

echo "Done. Mini-app UUID: $app_uuid"
echo "The client secret is only shown once: it now lives in up-miniapps-template-python-backend/.env (gitignored)."
