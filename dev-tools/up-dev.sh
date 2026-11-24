#!/usr/bin/env bash
# up-dev.sh: starts, stops and checks the development servers of this project in the background.
#
#   dev-tools/up-dev.sh start [api] [miniapp] [plugin]   start them (default: every part that exists), wait until they answer
#   dev-tools/up-dev.sh stop [api] [miniapp] [plugin]    stop them (default: all)
#   dev-tools/up-dev.sh restart [part...]                stop, then start
#   dev-tools/up-dev.sh status                           which part runs, on which port, at which address
#   dev-tools/up-dev.sh logs <part> [lines]              the last lines of the log of one part (default 40)
#
# Parts and ports: api (FastAPI, 21514), miniapp (Vite, 21515), plugin (Vite, development page of the Studio plugin, 21516).
# Logs and process group ids go to .up-dev/ at the repository root (git-ignored).
# Each part runs in its own process group, so `stop` also stops the child processes (esbuild, the reload worker).
# Missing dependencies are installed first (uv sync in api/, npm ci in miniapp/ and plugin/).
# Exit code 1 when a part failed or an argument is wrong.
# The script never reads nor prints the values of api/.env: the API reads that file itself (api/app/core/dotenv.py).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$ROOT/.up-dev"
ALL_PARTS=(api miniapp plugin)
START_TIMEOUT_SECONDS=90
STOP_TIMEOUT_SECONDS=10

say() { printf '%s\n' "$*"; }
fail() { printf 'up-dev: %s\n' "$*" >&2; exit 1; }

port_of() {
  case "$1" in
    api) echo 21514 ;;
    miniapp) echo 21515 ;;
    plugin) echo 21516 ;;
  esac
}

# The path that proves the part answers. Vite answers on / ; the API has its hello route.
probe_path() {
  case "$1" in
    api) echo /api/v1/hello ;;
    *) echo / ;;
  esac
}

# Extended regular expression that the commands of a part's process group match. A process group id read from a stale
# file (the pod restarted, the pids were reused) belongs to other programs: it never matches.
command_pattern() {
  case "$1" in
    api) echo 'python[0-9.]* -m app' ;;
    *) echo 'vite|esbuild' ;;
  esac
}

# The address to open in the browser. In a Coder workspace: the button address, built like up-project-notes does
# (https://<app>--<workspace>--<owner>--<organisation>.<apps domain>/). The port URLs (https://21515--main--...) do not
# open the pages. Outside Coder: localhost.
url_of() {
  local part="$1" proxy="${VSCODE_PROXY_URI:-}" agent="${CODER_WORKSPACE_AGENT_NAME:-main}" suffix=""
  local prefix="{{port}}--${agent}--"
  [ "$part" = api ] && suffix="docs"
  if [[ "$proxy" == *"$prefix"* ]]; then
    printf '%s%s' "${proxy/"$prefix"/${part}--}" "$suffix"
  elif [ -n "$proxy" ]; then
    printf '(not available: this Coder has no apps domain; use the buttons of the workspace page in Coder)'
  else
    printf 'http://localhost:%s/%s' "$(port_of "$part")" "$suffix"
  fi
}

# HTTP status of the part on localhost, 000 when nothing answers. `localhost` because the Vite host guard
# (dev-tools/hostGuard.ts) answers 403 to an IP address in the Host header.
http_code() {
  curl -s -o /dev/null -m 2 -w '%{http_code}' "http://localhost:$(port_of "$1")$(probe_path "$1")" 2>/dev/null || true
}

answers() { local code; code="$(http_code "$1")"; [ -n "$code" ] && [ "$code" != 000 ]; }

pid_file() { echo "$STATE/$1.pid"; }
log_file() { echo "$STATE/$1.log"; }

# True while a process of group $2 runs the program of part $1.
group_alive() {
  local part="$1" pgid="$2"
  ps -A -o pgid= -o command= 2>/dev/null |
    awk -v g="$pgid" '$1 == g { $1 = ""; print }' |
    grep -Eiq "$(command_pattern "$part")"
}

# The process group this script started for the part, when it still runs. A stale file is deleted.
running_group() {
  local part="$1" file pgid
  file="$(pid_file "$part")"
  [ -f "$file" ] || return 1
  pgid="$(cat "$file" 2>/dev/null)"
  if [[ "$pgid" =~ ^[0-9]+$ ]] && group_alive "$part" "$pgid"; then
    echo "$pgid"
    return 0
  fi
  rm -f "$file"
  return 1
}

exists() { [ -d "$ROOT/$1" ]; }

install_deps() {
  local part="$1" dir="$ROOT/$1"
  case "$part" in
    api)
      [ -x "$dir/.venv/bin/python" ] && return 0
      command -v uv >/dev/null || { say "api: FAILED, uv is missing. In a Coder workspace run up-project-setup."; return 1; }
      say "api: installing the dependencies (uv sync)"
      (cd "$dir" && uv sync --quiet) || { say "api: FAILED, uv sync failed"; return 1; }
      ;;
    miniapp | plugin)
      [ -d "$dir/node_modules" ] && return 0
      command -v npm >/dev/null || { say "$part: FAILED, npm is missing. Install Node.js 26."; return 1; }
      say "$part: installing the dependencies (npm ci)"
      (cd "$dir" && npm ci --no-audit --no-fund --loglevel=error) || { say "$part: FAILED, npm ci failed"; return 1; }
      ;;
  esac
}

launch() {
  local part="$1" dir="$ROOT/$1" log
  log="$(log_file "$part")"
  : >"$log"
  # set -m: the job gets its own process group, whose id is the job's pid. `stop` signals the whole group.
  # trap '' HUP: the server survives the end of the terminal or of the agent's command that started it.
  # </dev/null: no terminal input. Vite 8 exits on stdin "end" unless CI=true; a paused /dev/null never sends it (checked
  # with Vite 8.3.8). If a later Vite exits at once here, set CI=true for the two Vite parts.
  set -m
  case "$part" in
    api)
      if [ ! -f "$dir/.env" ]; then
        say "api: api/.env is missing. In a Coder workspace run up-project-setup. On a laptop copy api/.env.template to api/.env."
      fi
      (trap '' HUP; cd "$dir" && exec .venv/bin/python -m app) </dev/null >>"$log" 2>&1 &
      ;;
    miniapp)
      (trap '' HUP; cd "$dir" && exec node_modules/.bin/vite) </dev/null >>"$log" 2>&1 &
      ;;
    plugin)
      (trap '' HUP; cd "$dir" && exec node_modules/.bin/vite --config vite.dev.config.ts) </dev/null >>"$log" 2>&1 &
      ;;
  esac
  echo $! >"$(pid_file "$part")"
  set +m
}

show_log_tail() { say "Last lines of .up-dev/$1.log:"; tail -n 25 "$(log_file "$1")"; }

wait_until_up() {
  local part="$1" pgid="$2" waited=0
  while ! answers "$part"; do
    # The group was created a moment ago: check that it exists, not its command (the subshell may not have run exec yet).
    if ! kill -0 -- "-$pgid" 2>/dev/null; then
      say "$part: FAILED, the process stopped."
      show_log_tail "$part"
      return 1
    fi
    if [ "$waited" -ge "$START_TIMEOUT_SECONDS" ]; then
      say "$part: FAILED, no answer on port $(port_of "$part") after ${START_TIMEOUT_SECONDS}s."
      show_log_tail "$part"
      return 1
    fi
    sleep 1
    waited=$((waited + 1))
  done
}

start_part() {
  local part="$1" pgid
  exists "$part" || { say "$part: no $part/ folder, skipped"; return 0; }
  if pgid="$(running_group "$part")"; then
    say "$part: already running (process group $pgid, port $(port_of "$part"))"
    return 0
  fi
  if answers "$part"; then
    say "$part: port $(port_of "$part") already answers (started elsewhere, for example in a terminal). Left as it is."
    return 0
  fi
  install_deps "$part" || return 1
  launch "$part"
  pgid="$(cat "$(pid_file "$part")")"
  wait_until_up "$part" "$pgid" || return 1
  say "$part: running on port $(port_of "$part")"
}

stop_part() {
  local part="$1" pgid waited=0
  if ! pgid="$(running_group "$part")"; then
    if answers "$part"; then
      say "$part: port $(port_of "$part") answers, but this script did not start it: stop it where it runs (Ctrl+C in its terminal)"
    else
      say "$part: not running"
    fi
    return 0
  fi
  # The group was checked: it runs this part's program. Signal the group only, never a single pid.
  kill -TERM -- "-$pgid" 2>/dev/null
  while group_alive "$part" "$pgid" && [ "$waited" -lt "$STOP_TIMEOUT_SECONDS" ]; do
    sleep 1
    waited=$((waited + 1))
  done
  if group_alive "$part" "$pgid"; then
    kill -KILL -- "-$pgid" 2>/dev/null
    sleep 1   # let the kernel release the port before a restart binds it again
  fi
  rm -f "$(pid_file "$part")"
  say "$part: stopped"
}

status_part() {
  local part="$1" pgid state
  exists "$part" || return 0
  if pgid="$(running_group "$part")"; then
    state="running (process group $pgid)"
    answers "$part" || state="starting or not answering (process group $pgid, see dev-tools/up-dev.sh logs $part)"
  elif answers "$part"; then
    state="running (started outside this script)"
  else
    state="stopped"
  fi
  printf '%-8s %-6s %s\n' "$part" "$(port_of "$part")" "$state"
}

print_urls() {
  local part label
  say ""
  if [ -n "${VSCODE_PROXY_URI:-}" ]; then
    say "Open (in the browser signed in to Coder; only you can):"
  else
    say "Open:"
  fi
  for part in "${ALL_PARTS[@]}"; do
    if ! exists "$part" || ! answers "$part"; then continue; fi
    case "$part" in api) label="API:     " ;; miniapp) label="Mini-app:" ;; plugin) label="Plugin:  " ;; esac
    say "  $label $(url_of "$part")"
  done
  say "Logs: dev-tools/up-dev.sh logs <api|miniapp|plugin>. Stop: dev-tools/up-dev.sh stop"
}

# Sets PARTS from the arguments (default: every part that exists). Runs in the main shell, so `fail` ends the script.
PARTS=()
select_parts() {
  local part
  PARTS=()
  if [ "$#" -eq 0 ]; then
    for part in "${ALL_PARTS[@]}"; do
      if exists "$part"; then PARTS+=("$part"); fi
    done
    # bash 3.2 with set -u fails on an empty "${PARTS[@]}": refuse here with a clear message.
    [ "${#PARTS[@]}" -gt 0 ] || fail "no part folder (api/, miniapp/, plugin/) in $ROOT"
    return 0
  fi
  for part in "$@"; do
    case "$part" in
      api | miniapp | plugin) PARTS+=("$part") ;;
      *) fail "unknown part: $part (api, miniapp or plugin)" ;;
    esac
  done
}

main() {
  local command="${1:-}" part status=0 lines
  [ "$#" -gt 0 ] && shift
  command -v curl >/dev/null || fail "curl is missing"
  command -v ps >/dev/null || fail "ps is missing"
  mkdir -p "$STATE"
  case "$command" in
    start)
      # The API first: Vite proxies /api/ to it.
      select_parts "$@"
      for part in "${PARTS[@]}"; do start_part "$part" || status=1; done
      print_urls
      ;;
    stop)
      select_parts "$@"
      for part in "${PARTS[@]}"; do stop_part "$part"; done
      ;;
    restart)
      select_parts "$@"
      for part in "${PARTS[@]}"; do stop_part "$part"; done
      for part in "${PARTS[@]}"; do start_part "$part" || status=1; done
      print_urls
      ;;
    status)
      for part in "${ALL_PARTS[@]}"; do status_part "$part"; done
      print_urls
      ;;
    logs)
      part="${1:-}"
      lines="${2:-40}"
      [ -n "$part" ] || fail "usage: dev-tools/up-dev.sh logs <api|miniapp|plugin> [lines]"
      select_parts "$part"
      [[ "$lines" =~ ^[0-9]+$ ]] || fail "lines must be a number: $lines"
      [ -f "$(log_file "$part")" ] || fail "$part: no log yet (start it with dev-tools/up-dev.sh start $part)"
      tail -n "$lines" "$(log_file "$part")"
      ;;
    *)
      sed -n '2,8p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      [ -z "$command" ] || status=1
      ;;
  esac
  return "$status"
}

main "$@"
