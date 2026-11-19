#!/usr/bin/env bash
# Tests of the CI scripts and workflows: Python unit tests, the Kaniko script test and shellcheck.
set -euo pipefail
cd "$(dirname "$0")"
python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'
tests/test_build_image.sh
if command -v shellcheck >/dev/null; then shellcheck build-image.sh check.sh tests/test_build_image.sh; fi
