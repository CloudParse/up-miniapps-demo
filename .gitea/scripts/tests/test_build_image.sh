#!/usr/bin/env bash
# Tests build-image.sh with a fake Kaniko executor that records its arguments and the registry config.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
script="$here/../build-image.sh"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/api"
touch "$work/api/Dockerfile"
cat >"$work/fake-kaniko" <<'FAKE'
#!/usr/bin/env bash
printf '%s\n' "$@" >"$FAKE_ARGS"
cp "$DOCKER_CONFIG/config.json" "$FAKE_CONFIG"
FAKE
chmod +x "$work/fake-kaniko"

run() {
  (cd "$work" && FAKE_ARGS="$work/args" FAKE_CONFIG="$work/config" KANIKO_EXECUTOR="$work/fake-kaniko" \
    IMAGE=git.demo.example/demo/demo-atlas-5b51 VERSION=1.0.3 API_DIR=api API_PORT=8000 \
    REGISTRY_USER=ci REGISTRY_TOKEN=tok "$@" "$script")
}
fail() { echo "FAIL: $1" >&2; exit 1; }

run env >/dev/null
grep -qx -- '--destination' "$work/args" || fail "no destination"
grep -qx 'git.demo.example/demo/demo-atlas-5b51:1.0.3' "$work/args" || fail "wrong destination"
grep -qx 'API_PORT=8000' "$work/args" || fail "no port build arg"
grep -q 'dir://.*/api$' "$work/args" || fail "wrong context"
! grep -q -- '--insecure' "$work/args" || fail "insecure without opt-in"
grep -q '"git.demo.example"' "$work/config" || fail "registry host missing in auth config"
! grep -q 'tok' "$work/args" || fail "token leaked into arguments"

run env REGISTRY_INSECURE=true >/dev/null
grep -qx -- '--insecure' "$work/args" || fail "insecure not set"

if run env VERSION=latest >/dev/null 2>&1; then fail "non-semver version accepted"; fi
if run env API_DIR=nowhere >/dev/null 2>&1; then fail "missing Dockerfile accepted"; fi
if run env -u REGISTRY_TOKEN >/dev/null 2>&1; then fail "missing token accepted"; fi
echo "build-image.sh: ok"
