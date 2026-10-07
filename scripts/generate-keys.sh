#!/usr/bin/env bash
# Generates the local-only ES256 key pair used by the dockerised CloudParse backend.
# The backend signs user tokens with keys/private.pem; the mini-app backend
# verifies them with keys/public.pem. Never reuse these keys anywhere else.
set -euo pipefail

KEYS_DIR="$(cd "$(dirname "$0")/.." && pwd)/keys"

if [[ -f "$KEYS_DIR/private.pem" ]]; then
  echo "Keys already exist in keys/, nothing to do."
  exit 0
fi

mkdir -p "$KEYS_DIR"
openssl ecparam -name prime256v1 -genkey -noout -out "$KEYS_DIR/private.pem"
openssl ec -in "$KEYS_DIR/private.pem" -pubout -out "$KEYS_DIR/public.pem" 2>/dev/null
# World-readable on purpose (local-only keys): the container runs as a different
# non-root user and must be able to read the bind mount.
chmod 644 "$KEYS_DIR/private.pem" "$KEYS_DIR/public.pem"
echo "Generated keys/private.pem and keys/public.pem."
