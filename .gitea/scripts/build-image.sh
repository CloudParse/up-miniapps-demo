#!/usr/bin/env bash
# Build the API image with Kaniko (no Docker daemon) and push it to the Gitea container registry. Pushes only: the
# platform deletes the old images, and this account never deletes.
#
# Environment (never arguments):
#   REGISTRY_HOST    registry host the nodes pull from (runner env CI_REGISTRY_HOST, required: no fallback)
#   REPOSITORY       <owner>/<repository> of the project; the image is <REGISTRY_HOST>/<REPOSITORY> in lower case
#   VERSION          semver of this deployment, becomes the image tag
#   API_DIR          folder of the API (build context, holds the Dockerfile)
#   API_PORT         port the container listens on (build argument), 1024 or more
#   REGISTRY_USER, REGISTRY_TOKEN   account that pushes (write:package)
#   REGISTRY_INSECURE=true          registry with a local-CA certificate or plain HTTP (runner env CI_REGISTRY_INSECURE;
#                                   local clusters only, false when unset)
#   KANIKO_EXECUTOR                 path of the executor (default /kaniko/executor)
#   KANIKO_DOCKER_CONFIG            folder of the registry login (default /kaniko/.docker, the place Kaniko keeps while it
#                                   replaces the file system of the build; tests override it)
#
# Limit, documented in docs/deploy.md: the Dockerfile's RUN steps run as root inside the build and can read that login file.
set -euo pipefail

: "${REGISTRY_HOST:?REGISTRY_HOST is required (CI_REGISTRY_HOST of the runner)}" "${REPOSITORY:?REPOSITORY is required}"
: "${VERSION:?VERSION is required}" "${API_DIR:?API_DIR is required}" "${API_PORT:?API_PORT is required}"
: "${REGISTRY_USER:?REGISTRY_USER is required}" "${REGISTRY_TOKEN:?REGISTRY_TOKEN is required}"

fail() {
  echo "build-image: $1" >&2
  exit 1
}
[[ "$VERSION" =~ ^(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})$ ]] || fail "VERSION must be a plain semver such as 1.2.3"
[[ "$REGISTRY_HOST" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?(:[0-9]{1,5})?$ ]] || fail "REGISTRY_HOST must be a host name with an optional port"
[[ "$REPOSITORY" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]] || fail "REPOSITORY must be <owner>/<repository>"
[[ "$API_PORT" =~ ^[0-9]{4,5}$ ]] || fail "API_PORT must be a number from 1024 to 65535"
((10#$API_PORT >= 1024 && 10#$API_PORT <= 65535)) || fail "API_PORT must be a number from 1024 to 65535"
[[ "$API_DIR" =~ ^[A-Za-z0-9._/-]+$ && "$API_DIR" != /* && "$API_DIR" != *..* ]] || fail "API_DIR must be a relative path"
[[ -f "$API_DIR/Dockerfile" && ! -L "$API_DIR/Dockerfile" ]] || fail "$API_DIR/Dockerfile not found (or a symbolic link)"
case "${REGISTRY_INSECURE:-false}" in true | false) ;; *) fail "REGISTRY_INSECURE must be true or false" ;; esac

image="$(printf '%s/%s' "$REGISTRY_HOST" "$REPOSITORY" | tr '[:upper:]' '[:lower:]')"
executor="${KANIKO_EXECUTOR:-/kaniko/executor}"
docker_config="${KANIKO_DOCKER_CONFIG:-/kaniko/.docker}"

# The credentials go to a private file, not to a command line, and the file is removed when the script ends.
mkdir -p "$docker_config"
trap 'rm -f "$docker_config/config.json"' EXIT
(
  umask 077
  auth="$(printf '%s:%s' "$REGISTRY_USER" "$REGISTRY_TOKEN" | base64 | tr -d '\n')"
  printf '{"auths":{"%s":{"auth":"%s"}}}\n' "$REGISTRY_HOST" "$auth" >"$docker_config/config.json"
)
export DOCKER_CONFIG="$docker_config"

args=(
  --context "dir://$(cd "$API_DIR" && pwd)"
  --dockerfile Dockerfile
  --destination "$image:$VERSION"
  --build-arg "API_PORT=$API_PORT"
  --snapshot-mode redo
  --cache=false
)
if [[ "${REGISTRY_INSECURE:-false}" == "true" ]]; then
  args+=(--insecure --insecure-registry "$REGISTRY_HOST" --skip-tls-verify-registry "$REGISTRY_HOST")
fi

echo "build-image: building $image:$VERSION"
"$executor" "${args[@]}"
