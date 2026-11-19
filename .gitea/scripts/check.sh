#!/usr/bin/env bash
# Tests of the CI scripts and workflows: Python unit tests, the Kaniko script test and shellcheck.
# The Python tests need PyYAML and jsonschema (they check the workflows and the schema); without them uv provides both.
set -euo pipefail
cd "$(dirname "$0")"
if python3 -c 'import yaml, jsonschema' 2>/dev/null; then
  python=(python3)
elif command -v uv >/dev/null; then
  python=(uv run --no-project --quiet --with pyyaml --with jsonschema python)
else
  echo "check.sh: install PyYAML and jsonschema (pip install pyyaml jsonschema) or uv" >&2
  exit 1
fi
"${python[@]}" -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'
tests/test_build_image.sh
if command -v shellcheck >/dev/null; then shellcheck build-image.sh run-build.sh check.sh tests/test_build_image.sh; else echo "check.sh: shellcheck not installed, skipped" >&2; fi
