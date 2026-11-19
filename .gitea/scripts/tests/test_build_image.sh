#!/usr/bin/env bash
# Tests build-image.sh with a fake Kaniko executor that records its arguments and the registry login.
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
    KANIKO_DOCKER_CONFIG="$work/docker" REGISTRY_HOST=git.demo.example REPOSITORY=Demo/Demo-Atlas-5b51 VERSION=1.0.3 \
    API_DIR=api API_PORT=8000 REGISTRY_USER=ci REGISTRY_TOKEN=tok "$@" "$script")
}
fail() { echo "FAIL: $1" >&2; exit 1; }
refuses() {
  local label="$1"
  shift
  if run "$@" >/dev/null 2>&1; then fail "accepted: $label"; fi
}

run env >/dev/null
grep -qx -- '--destination' "$work/args" || fail "no destination"
grep -qx 'git.demo.example/demo/demo-atlas-5b51:1.0.3' "$work/args" || fail "wrong destination"
grep -qx 'API_PORT=8000' "$work/args" || fail "no port build arg"
grep -q 'dir://.*/api$' "$work/args" || fail "wrong context"
! grep -q -- '--insecure' "$work/args" || fail "insecure without opt-in"
grep -q '"git.demo.example"' "$work/config" || fail "registry host missing in the login file"
! grep -q 'tok' "$work/args" || fail "token leaked into arguments"
[[ ! -e "$work/docker/config.json" ]] || fail "the login file was left behind"

run env REGISTRY_INSECURE=true >/dev/null
grep -qx -- '--insecure' "$work/args" || fail "insecure not set"

refuses "non-semver" VERSION=latest
refuses "semver with a suffix" VERSION=1.0.3-rc1
refuses "missing Dockerfile" API_DIR=nowhere
refuses "missing token" -u REGISTRY_TOKEN
refuses "missing registry host" -u REGISTRY_HOST
refuses "registry host with a path" REGISTRY_HOST=evil.example/x
refuses "registry host with a space" "REGISTRY_HOST=evil.example x"
refuses "repository without owner" REPOSITORY=atlas
refuses "repository with injection" 'REPOSITORY=a/b";c'
refuses "privileged port" API_PORT=80
refuses "port out of range" API_PORT=70000
refuses "port not a number" API_PORT=80a0
refuses "absolute API_DIR" API_DIR=/etc
refuses "API_DIR with .." API_DIR=../x
refuses "insecure value" REGISTRY_INSECURE=yes

ln -s /etc/hostname "$work/api2-Dockerfile"
mkdir -p "$work/api2"
ln -s /etc/hostname "$work/api2/Dockerfile"
refuses "Dockerfile symlink" API_DIR=api2
echo "build-image.sh: ok"
