#!/usr/bin/env bash
# Run the build command of a miniapp.yaml section (miniapp or plugin) in its folder, with a scrubbed environment.
#
# `env -i` keeps the runner's variables (CI_*, the Gitea token, anything a step exported) away from the build command, and a
# fresh HOME keeps it away from the runner's home. This is hygiene, NOT a security boundary: the repository's own workflow
# and scripts decide what runs, and a writer of the repository can change them (docs/deploy.md, "Security model").
# Usage: run-build.sh miniapp|plugin
set -euo pipefail

section="${1:?usage: run-build.sh miniapp|plugin}"
case "$section" in miniapp | plugin) ;; *) echo "run-build: unknown section '$section'" >&2; exit 1 ;; esac

here="$(cd "$(dirname "$0")" && pwd)"
config="python3 $here/miniapp_config.py"
dir="$($config get "$section.dir")"
build="$($config get "$section.build")"
if [[ -z "$dir" || -z "$build" ]]; then
  echo "run-build: miniapp.yaml has no $section build" >&2
  exit 1
fi

home="$(mktemp -d)"
trap 'rm -rf "$home"' EXIT
cd "$dir"
echo "run-build: $section: $build"
env -i PATH="$PATH" HOME="$home" TMPDIR="$home" CI=true sh -c "$build"
