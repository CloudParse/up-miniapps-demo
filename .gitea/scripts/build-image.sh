#!/usr/bin/env bash
# Build the API image with Kaniko (no Docker daemon) and push it to the Gitea container registry. Pushes only: the
# platform deletes the old images, the CI token and this account never delete.
#
# Environment (never arguments):
#   REGISTRY_HOST    registry host the nodes pull from (runner env CI_REGISTRY_HOST)
#   REPOSITORY       <owner>/<repository> of the project; the image is <REGISTRY_HOST>/<REPOSITORY> in lower case
#   VERSION          semver of this deployment, becomes the image tag
#   API_DIR          folder of the API (build context, holds the Dockerfile)
#   API_PORT         port the container listens on (build argument)
#   REGISTRY_USER, REGISTRY_TOKEN   account that pushes (write:package)
#   REGISTRY_INSECURE=true          registry with a local-CA certificate or plain HTTP (local clusters only)
#   KANIKO_EXECUTOR                 path of the executor (default /kaniko/executor)
set -euo pipefail

: "${REGISTRY_HOST:?REGISTRY_HOST is required}" "${REPOSITORY:?REPOSITORY is required}" "${VERSION:?VERSION is required}" "${API_DIR:?API_DIR is required}"
: "${API_PORT:?API_PORT is required}" "${REGISTRY_USER:?REGISTRY_USER is required}" "${REGISTRY_TOKEN:?REGISTRY_TOKEN is required}"

if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "build-image: VERSION must be a plain semver such as 1.2.3, got '$VERSION'" >&2
  exit 1
fi
if [[ ! -f "$API_DIR/Dockerfile" ]]; then
  echo "build-image: $API_DIR/Dockerfile not found" >&2
  exit 1
fi

registry_host="$REGISTRY_HOST"
IMAGE="$(printf '%s/%s' "$REGISTRY_HOST" "$REPOSITORY" | tr '[:upper:]' '[:lower:]')"
executor="${KANIKO_EXECUTOR:-/kaniko/executor}"

# The credentials go to a private file, not to a command line.
docker_config="$(mktemp -d)"
trap 'rm -rf "$docker_config"' EXIT
(
  umask 077
  auth="$(printf '%s:%s' "$REGISTRY_USER" "$REGISTRY_TOKEN" | base64 | tr -d '\n')"
  printf '{"auths":{"%s":{"auth":"%s"}}}\n' "$registry_host" "$auth" >"$docker_config/config.json"
)
export DOCKER_CONFIG="$docker_config"

args=(
  --context "dir://$(cd "$API_DIR" && pwd)"
  --dockerfile Dockerfile
  --destination "$IMAGE:$VERSION"
  --build-arg "API_PORT=$API_PORT"
  --snapshot-mode redo
  --cache=false
)
if [[ "${REGISTRY_INSECURE:-false}" == "true" ]]; then
  args+=(--insecure --insecure-registry "$registry_host" --skip-tls-verify-registry "$registry_host")
fi

echo "build-image: building $IMAGE:$VERSION"
"$executor" "${args[@]}"
