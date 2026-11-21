#!/usr/bin/env python3
"""Claude Code PreToolUse hook: blocks changes to the protected files and the dangerous commands of AGENT.md section 5.1.

Protected: the deployment CI (.gitea/, .gitlab-ci.yml, miniapp.schema.json), the agent setup (.claude/: skills, agents,
hooks, settings) and the rule files (AGENT.md, CLAUDE.md), inside this project only. Also blocked: reading the .env
files, dumping the environment, force pushes, branch and tag deletion, history rewrites, skipped git hooks, deletion
outside the project.

This is a guard rail for agents, not a security boundary. It blocks the common forms only: a person can still edit
these files by hand, and a determined command can get around a pattern match. The review (AGENT.md section 7.4) and the
Gitea branch protection are the checks that count. Standard library only. Exit code 2 blocks the tool call and shows the
reason to the agent. An invalid event is blocked. The settings start this file only when python3 exists, and block
every call otherwise.
"""

import json
import os
import re
import sys
from pathlib import Path, PurePosixPath

POLICY = "AGENT.md section 5.1"

PROTECTED_PATH = re.compile(
    r"(^|/)(\.gitea|\.claude)(/|$)"
    r"|(^|/)\.gitlab-ci\.yml$"
    r"|(^|/)miniapp\.schema\.json$"
    r"|(^|/)(AGENT|CLAUDE)\.md$"
)
SECRET_PATH = re.compile(r"(^|/)\.env(\.(?!template$)[^/]+)?$")

# The same names, as they can appear inside a shell command.
PROTECTED_IN_COMMAND = re.compile(
    r"\.gitea\b|\.claude\b|\.gitlab-ci\.yml|miniapp\.schema\.json|\bAGENT\.md|\bCLAUDE\.md"
)
# Redirections that write nothing, and quoted text (an arrow such as `=>` in a grep pattern), removed before looking for a write.
HARMLESS_IN_COMMAND = re.compile(r"'[^']*'|\"[^\"]*\"|\d?>&\d|&?\d?>\s*/dev/null")
WRITE_IN_COMMAND = re.compile(
    r">"
    r"|\b(sed|perl|ruby)\s+(-\w+\s+)*-\w*i"
    r"|\b(tee|rm|rmdir|mv|cp|ln|chmod|chown|truncate|touch|install|rsync|dd|unlink|mkdir|patch)\b"
    r"|\bgit\s+(rm|mv|checkout|restore|reset|apply|am|stash|clean|add|commit|update-index)\b"
    r"|\bfind\b.*\s-(delete|exec|execdir)\b"
    r"|\b(write_text|write_bytes|writeFile|writeFileSync|appendFile)\b|\bopen\([^)]*['\"][wax+]"
)
# --env-file .env passes the file to a program without printing it: that use is allowed.
SECRET_IN_COMMAND = re.compile(
    r"(?<!--env-file )(?<!--env-file=)(?<![\w./-])([^\s=]*/)?\.env(\.(?!template\b)[\w-]+)?(?![\w.-])"
)
# Uses of a .env file that read no content: the first-run copy from the template, existence and ignore checks.
SAFE_ENV_USE = re.compile(
    r"\bcp\s+(\S*/)?\.env\.template\s+(\S*/)?\.env(?![\w.-])"
    r"|\btest\s+-[ef]\s+\S*\.env(?![\w.-])"
    r"|\[\s+-[ef]\s+\S*\.env\s+\]"
    r"|\bgit\s+check-ignore\s+(-\w+\s+)*\S*\.env(?![\w.-])"
)
COMMAND_START = r"(^|[;&|(]\s*|\bthen\s+|\bdo\s+)"
DANGEROUS_COMMAND = [
    (re.compile(COMMAND_START + r"(env|printenv|export\s+-p|set|declare\s+-x)\s*($|[|;&>)])", re.MULTILINE), "dumps the environment"),
    (re.compile(r"\bprintenv\b"), "dumps the environment"),
    (re.compile(r"\bgit\s+push\b.*(\s--force\b|\s-f\b|\s--force-with-lease\b|\s--mirror\b|\s--delete\b|\s-d\b|\s:\S|\s\+\S)"), "force push or remote delete"),
    (re.compile(r"\bgit\s+(branch|tag)\b.*\s(-d|-D|--delete)\b"), "deletes a branch or a tag"),
    (re.compile(r"\bgit\s+(filter-branch|filter-repo|replace)\b|\bgit\s+rebase\b.*\s--root\b|\bgit\s+reset\s+(\S+\s+)*--hard\b|\bgit\s+commit\b.*\s--amend\b"), "rewrites the history"),
    (re.compile(r"\bgit\s+commit\b.*\s(--no-verify|-n)\b|\bgit\s+(push|merge)\b.*\s--no-verify\b"), "skips the git hooks"),
    (re.compile(r"\brm\s+(-\w+\s+)*(/|~|\$HOME|\$\{HOME\}|\.\.)\S*"), "deletes outside the project"),
    (re.compile(r"\b(curl|wget)\b[^|;&]*\|\s*(ba|z)?sh\b"), "runs a downloaded script"),
]


def block(reason: str) -> None:
    print(f"Blocked by .claude/hooks/guard.py ({POLICY}): {reason}. Ask a maintainer of the project if this change is really needed.", file=sys.stderr)
    sys.exit(2)


def project_relative(raw: str, event: dict[str, object]) -> str | None:
    """The path relative to the project root, or None when it is outside the project (Claude Code's own files in ~/.claude)."""
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or str(event.get("cwd") or ".")).resolve()
    path = Path(raw)
    if not path.is_absolute():
        path = Path(str(event.get("cwd") or root)) / path
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return None


def check_path(raw: str, event: dict[str, object], *, writing: bool) -> None:
    if SECRET_PATH.search(PurePosixPath(raw.replace("\\", "/")).as_posix()):
        block(f"`{raw}` holds secrets")
    relative = project_relative(raw, event)
    if writing and relative is not None and PROTECTED_PATH.search(relative):
        block(f"`{raw}` is a protected file (deployment CI, agent setup or rules)")


def check_command(command: str) -> None:
    for pattern, reason in DANGEROUS_COMMAND:
        if pattern.search(command):
            block(f"the command {reason}")
    if SECRET_IN_COMMAND.search(SAFE_ENV_USE.sub("", command)):
        block("the command reads a .env file, which holds secrets (use `uv run --env-file .env ...`)")
    if PROTECTED_IN_COMMAND.search(command) and WRITE_IN_COMMAND.search(HARMLESS_IN_COMMAND.sub("", command)):
        block("the command may change a protected file (deployment CI, agent setup or rules)")


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        block("the hook received an invalid event")
    if not isinstance(event, dict):
        block("the hook received an invalid event")
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    if tool == "Bash":
        check_command(str(tool_input.get("command", "")))
    elif tool in {"Edit", "Write", "MultiEdit", "NotebookEdit"}:
        check_path(str(tool_input.get("file_path") or tool_input.get("notebook_path") or ""), event, writing=True)
    elif tool == "Read":
        check_path(str(tool_input.get("file_path", "")), event, writing=False)
    elif tool == "Grep":
        check_path(str(tool_input.get("path") or "."), event, writing=False)


if __name__ == "__main__":
    main()
