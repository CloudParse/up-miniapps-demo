#!/usr/bin/env bash
# Puts the local environment back to a clean state, then you start again from
# step 1 of SETUP.md.
#
#   scripts/reset.sh          # containers + volumes, ports 21509-21515, backend .env
#   scripts/reset.sh --all    # also keys/, dependencies, caches, build output and the frontend .env
#
# What the default reset does:
#   1. `docker compose down -v`: removes the containers and their volumes
#      (PostgreSQL, Redis, RustFS), so the Hub starts with an empty database.
#   2. Stops the processes of THIS checkout still listening on the template's
#      ports (the mini-app backend on 21514, the Vite dev server on 21515).
#      Anything else on those ports is reported and left alone.
#   3. Deletes up-miniapps-template-python-backend/.env: its credentials belong to
#      the mini-app registered in the database that step 1 just wiped.
set -euo pipefail

# Physical path (-P): lsof reports process working directories without symlinks.
ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd -P)"
COMPOSE_FILE="$ROOT/docker-compose.yml"
BACKEND_DIR="$ROOT/up-miniapps-template-python-backend"
FRONTEND_DIR="$ROOT/up-miniapps-react-template"

usage() { sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//'; }

full_reset=0
case "$#:${1:-}" in
  0:) ;;
  1:--all) full_reset=1 ;;
  1:-h | 1:--help) usage; exit 0 ;;
  *) usage >&2; exit 1 ;;
esac

require() { command -v "$1" >/dev/null || { echo "Missing dependency: $1" >&2; exit 1; }; }
require docker
require jq
require lsof

# Same precedence as docker compose: the shell environment, then the root .env
# (see .env.template), then the default. The .env is read, never executed.
compose_port() { # <variable> <default>
  local value="${!1:-}"
  if [[ -z "$value" && -f "$ROOT/.env" ]]; then
    value="$(sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*//p" "$ROOT/.env" | tail -n 1 | sed 's/[[:space:]]#.*//' | tr -d "\"' \r")"
  fi
  echo "${value:-$2}"
}
PORTS=(
  "$(compose_port CLOUDPARSE_BACKEND_PORT 21509)"
  "$(compose_port POSTGRES_PORT 21510)"
  "$(compose_port REDIS_PORT 21511)"
  "$(compose_port RUSTFS_API_PORT 21512)"
  "$(compose_port RUSTFS_CONSOLE_PORT 21513)"
  21514 # mini-app backend (up-miniapps-template-python-backend/configs/config.toml)
  21515 # Vite dev server (up-miniapps-react-template/vite.config.ts)
)

process_cwd() { # <pid>; empty when the process exited in the meantime
  lsof -a -p "$1" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' || true
}

stop_port() { # <port>
  local port="$1" pid cwd pids=()
  for pid in $(lsof -nP -t -iTCP:"$port" -sTCP:LISTEN || true); do
    cwd="$(process_cwd "$pid")"
    if [[ "$cwd" == "$ROOT" || "$cwd" == "$ROOT"/* ]]; then
      pids+=("$pid")
    else
      echo "    port $port: held by pid $pid ($(ps -p "$pid" -o comm=)), not started from this project, left alone" >&2
    fi
  done
  ((${#pids[@]})) || return 0

  echo "    port $port: stopping pid ${pids[*]}"
  kill "${pids[@]}" 2>/dev/null || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    kill -0 "${pids[@]}" 2>/dev/null || return 0
    sleep 0.5
  done
  kill -9 "${pids[@]}" 2>/dev/null || true
}

remove_file() { # <path relative to ROOT>
  if [[ -e "$ROOT/$1" ]]; then
    rm -rf "${ROOT:?}/$1"
    echo "    removed $1"
  fi
}

echo "1/3 Removing the containers and their volumes..."
project="$(docker compose -f "$COMPOSE_FILE" config --format json | jq -r .name)"
docker compose -f "$COMPOSE_FILE" down -v --remove-orphans
# `down -v` only knows the volumes declared today; volumes of services since
# removed from docker-compose.yml survive it, so drop them by project label.
leftover_volumes="$(docker volume ls -q --filter "label=com.docker.compose.project=$project")"
for volume in $leftover_volumes; do
  docker volume rm "$volume" >/dev/null
  echo "    removed leftover volume $volume"
done

echo "2/3 Freeing ports ${PORTS[*]}..."
for port in "${PORTS[@]}"; do
  stop_port "$port"
done

echo "3/3 Removing local state..."
remove_file up-miniapps-template-python-backend/.env

if ((full_reset)); then
  for path in keys \
    up-miniapps-template-python-backend/.venv \
    up-miniapps-template-python-backend/.mypy_cache \
    up-miniapps-template-python-backend/.pytest_cache \
    up-miniapps-template-python-backend/.ruff_cache \
    up-miniapps-react-template/node_modules \
    up-miniapps-react-template/dist \
    up-miniapps-react-template/.env; do
    remove_file "$path"
  done
  find "$BACKEND_DIR" -type d -name __pycache__ -prune -exec rm -rf {} +
fi

echo "Done. Start again from step 1 of SETUP.md."
