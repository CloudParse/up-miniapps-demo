#!/usr/bin/env python3
"""Tests of welcome.py: valid SessionStart JSON that names the three parts. Run: python3 .claude/hooks/welcome_test.py"""

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).with_name("welcome.py")


def main() -> None:
    result = subprocess.run([sys.executable, str(HOOK)], capture_output=True, text=True, check=True)
    output = json.loads(result.stdout)
    message = output["systemMessage"]
    context = output["hookSpecificOutput"]["additionalContext"]
    assert output["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    for part in ("miniapp/", "api/", "plugin/", "What do you want to build for Up?"):
        assert part in message, part
    assert message in context
    print("welcome.py: ok")


if __name__ == "__main__":
    main()
