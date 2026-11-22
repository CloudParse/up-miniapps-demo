#!/usr/bin/env python3
"""Claude Code PreToolUse hook: blocks changes to the protected files and the dangerous commands of AGENT.md section 5.1.

Protected: the deployment CI (.gitea/, .gitlab-ci.yml, miniapp.schema.json), the agent setup (.claude/: skills, agents,
hooks, settings) and the rule files (AGENT.md, CLAUDE.md), inside this project only. Also blocked: reading the .env
files, dumping the environment, force pushes, branch and tag deletion, history rewrites, skipped git hooks, deletion
outside the project, and edits of the Claude Code settings outside the project (they could turn this hook off).

How a shell command is checked:
- Every command substitution, `$(...)` or backticks, is checked as a command of its own, also inside double quotes.
- Heredoc bodies are data. A body with an unquoted delimiter is still searched for substitutions.
- The command is split on `;`, `&&`, `||`, `|`, `&` and newlines. Each simple command is parsed with shlex and checked
  on its program name and arguments. `sh -c`, `eval`, `env`, `sudo` and similar wrappers are unwrapped.
- A command that shlex cannot parse is blocked.

This is a guard rail for agents, not a security boundary. A person can still edit these files by hand, and a determined
command can get around it. The review (AGENT.md section 7.4) and the Gitea branch protection are the checks that count.
Standard library only. Exit code 2 blocks the tool call and shows the reason to the agent. An invalid event is blocked.
The settings start this file only when python3 exists, and block every call otherwise.
Tests: `python3 .claude/hooks/guard_test.py`.
"""

import json
import os
import re
import shlex
import sys
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

POLICY = "AGENT.md section 5.1"

PROTECTED_PATH = re.compile(
    r"(^|/)(\.gitea|\.claude)(/|$)"
    r"|(^|/)\.gitlab-ci\.yml$"
    r"|(^|/)miniapp\.schema\.json$"
    r"|(^|/)(AGENT|CLAUDE)\.md$"
)
PROTECTED_NAMES = (".gitea", ".claude", ".gitlab-ci.yml", "miniapp.schema.json", "AGENT.md", "CLAUDE.md")
SECRET_PATH = re.compile(r"(^|/)\.env(\.(?!(template|example)$)[^/]+)?$")
SECRET_NAMES = (".env", ".env.local", ".env.production", ".env.development")
# Claude Code settings outside the project: an edit there could turn this hook off.
USER_SETTINGS_PATH = re.compile(r"(^|/)\.claude/settings(\.[\w-]+)?\.json$|(^|/)\.claude\.json$")

SEPARATORS = {";", "&&", "||", "|", "&", "|&", ";;", "(", ")", "{", "}"}
REDIRECTS = {">", ">>", ">|", "&>", "&>>", "<>"}
WRAPPERS = {"sudo", "doas", "time", "nice", "nohup", "command", "exec", "builtin", "xargs", "timeout", "stdbuf"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
INTERPRETERS = {"python", "python3", "node", "perl", "ruby", "deno", "bun"}
WRITE_PROGRAMS = {"tee", "rm", "rmdir", "mv", "ln", "chmod", "chown", "truncate", "touch", "unlink", "mkdir", "patch", "shred"}
COPY_PROGRAMS = {"cp", "install", "rsync", "dd"}
GIT_PATH_WRITES = {"rm", "mv", "checkout", "restore", "apply", "am", "add", "commit", "update-index", "stash"}
SAFE_ENV_PROGRAMS = {"test", "[", "[[", "ls", "stat"}

WRITE_IN_CODE = re.compile(r"\b(write_text|write_bytes|writeFile|writeFileSync|appendFile|appendFileSync|unlink|rmSync|rmtree|remove|rename)\b|\bopen\([^)]*['\"][wax+]")
ENV_IN_CODE = re.compile(r"os\.environ\b(?!\s*\[|\.get)|process\.env\b(?![.\[])|\bENV\.to_h\b|%ENV\b")
GLOB_CHARS = re.compile(r"[*?\[]")


class Blocked(Exception):
    pass


def block(reason: str) -> None:
    raise Blocked(reason)


def project_root(event: dict[str, object]) -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or str(event.get("cwd") or ".")).resolve()


def resolve(raw: str, base: Path) -> Path:
    expanded = os.path.expanduser(raw.replace("${HOME}", "~").replace("$HOME", "~"))
    path = Path(expanded)
    return (path if path.is_absolute() else base / path).resolve()


def is_protected(raw: str, base: Path, root: Path) -> bool:
    """True when the path is a protected file of the project or a Claude Code settings file."""
    if GLOB_CHARS.search(raw):
        name = raw.rstrip("/").rsplit("/", 1)[-1]
        if any(fnmatch(protected, name) for protected in PROTECTED_NAMES):
            return True
    path = resolve(raw, base)
    if USER_SETTINGS_PATH.search(path.as_posix()):
        return True
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        return False
    return bool(PROTECTED_PATH.search(relative))


def is_secret(raw: str) -> bool:
    name = raw.rstrip("/").rsplit("/", 1)[-1]
    if GLOB_CHARS.search(name):
        return any(fnmatch(secret, name) for secret in SECRET_NAMES)
    return bool(SECRET_PATH.search(raw))


def is_outside(raw: str, base: Path, root: Path, *, root_allowed: bool = False) -> bool:
    """True when the path leaves the project (or is the project itself), except the temporary folders."""
    if raw.startswith(("~", "$HOME", "${HOME}")):
        return True
    path = resolve(raw, base)
    if root in path.parents or (root_allowed and path == root):
        return False
    tmp = (Path("/tmp").resolve(), Path("/private/tmp"), Path(os.environ.get("TMPDIR", "/tmp")).resolve())
    return not any(path != folder and folder in path.parents for folder in tmp)


# ---------------------------------------------------------------- shell text


def take_substitution(text: str, start: int) -> int:
    """Index just after the `)` that closes the `$(` opened at `start`."""
    depth, index, quote = 0, start + 1, ""
    pending: list[str] = []
    while index < len(text):
        char = text[index]
        if not quote and char == "\n" and pending:
            for delimiter in pending:
                end = re.compile(r"^[ \t]*" + re.escape(delimiter) + r"[ \t]*$", re.MULTILINE).search(text, index + 1)
                index = end.end() if end else len(text)
            pending.clear()
            continue
        if not quote and text.startswith("<<", index) and not text.startswith("<<<", index):
            heredoc = re.match(r"<<-?\s*(['\"]?)([\w.-]+)\1", text[index:])
            if heredoc:
                pending.append(heredoc.group(2))
                index += heredoc.end()
                continue
        if quote:
            if char == quote:
                quote = ""
            elif char == "\\" and quote == '"':
                index += 1
        elif char in "'\"":
            quote = char
        elif char == "\\":
            index += 1
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    block("the command has an unclosed `$(`")
    return index


def flatten(text: str, check_inner) -> str:
    """Checks each substitution with `check_inner`, drops heredoc bodies and turns unquoted newlines into `;`."""
    out: list[str] = []
    pending_heredocs: list[tuple[str, bool]] = []
    index, quote = 0, ""
    while index < len(text):
        char = text[index]
        if quote == "'":
            out.append(char)
            if char == "'":
                quote = ""
            index += 1
            continue
        if char == "\\" and index + 1 < len(text):
            out.append(text[index : index + 2])
            index += 2
            continue
        if text.startswith("$(", index) and not text.startswith("$((", index):
            end = take_substitution(text, index)
            check_inner(text[index + 2 : end - 1])
            out.append("SUBSTITUTION")
            index = end
            continue
        if char == "`":
            end = text.find("`", index + 1)
            if end < 0:
                block("the command has an unclosed backtick")
            check_inner(text[index + 1 : end])
            out.append("SUBSTITUTION")
            index = end + 1
            continue
        if char == '"':
            quote = "" if quote == '"' else '"'
            out.append(char)
            index += 1
            continue
        if quote == '"':
            out.append(char)
            index += 1
            continue
        if char == "'":
            quote = "'"
            out.append(char)
            index += 1
            continue
        if char == "#" and (not out or out[-1][-1:] in {" ", "\t", ";", "\n", "&", "|", "("}):
            newline = text.find("\n", index)
            index = len(text) if newline < 0 else newline
            continue
        if text.startswith("<<<", index):
            out.append("<<<")
            index += 3
            continue
        heredoc = re.match(r"<<-?\s*(['\"]?)([\w.-]+)\1", text[index:])
        if heredoc:
            pending_heredocs.append((heredoc.group(2), heredoc.group(1) == ""))
            out.append(" ")
            index += heredoc.end()
            continue
        if char == "\n":
            out.append(" ; ")
            index += 1
            for delimiter, expands in pending_heredocs:
                end = re.compile(r"^[ \t]*" + re.escape(delimiter) + r"[ \t]*$", re.MULTILINE).search(text, index)
                body_end = end.start() if end else len(text)
                if expands:
                    flatten(text[index:body_end], check_inner)
                index = end.end() if end else len(text)
            pending_heredocs.clear()
            continue
        out.append(char)
        index += 1
    if quote:
        block("the command has an unclosed quote")
    return "".join(out)


def tokenize(text: str) -> list[str]:
    lexer = shlex.shlex(text, posix=True, punctuation_chars=";&|()<>")
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError:
        block("the command cannot be parsed")
        return []


def split_commands(tokens: list[str]) -> list[tuple[list[str], str]]:
    """Simple commands with the separator that follows each one."""
    commands: list[tuple[list[str], str]] = []
    current: list[str] = []
    for token in tokens:
        if token in SEPARATORS or (token and set(token) <= set(";&|()")):
            commands.append((current, token))
            current = []
        else:
            current.append(token)
    commands.append((current, ""))
    return [(words, separator) for words, separator in commands if words]


# ---------------------------------------------------------------- checks


def split_redirects(words: list[str]) -> tuple[list[str], list[str]]:
    """Arguments and redirection targets. `2>&1` and `>/dev/null` write nothing."""
    operator = set("<>&|")
    args: list[str] = []
    targets: list[str] = []
    index = 0
    while index < len(words):
        word = words[index]
        following = words[index + 1] if index + 1 < len(words) else ""
        if word.isdigit() and following and set(following) <= operator and following not in SEPARATORS:
            index += 1
            continue
        if word and set(word) <= operator and word not in SEPARATORS:
            if ">" in word and not word.endswith("&") and following and following != "/dev/null" and not following.isdigit():
                targets.append(following)
            index += 2
            continue
        args.append(word)
        index += 1
    return args, targets


def strip_leading(args: list[str]) -> list[str]:
    """Drops variable assignments and wrappers in front of the program."""
    while args:
        word = args[0]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word):
            args = args[1:]
        elif os.path.basename(word) in WRAPPERS:
            args = args[1:]
            while args and args[0].startswith("-"):
                args = args[1:]
        else:
            break
    return args


def check_git(args: list[str], base: Path, root: Path) -> None:
    index = 1
    while index < len(args) and args[index].startswith("-"):
        option = args[index]
        if option in {"-C", "-c"} and index + 1 < len(args):
            if option == "-c" and args[index + 1].lower().startswith("core.hookspath"):
                block("the command turns the git hooks off")
            index += 2
        else:
            index += 1
    if index >= len(args):
        return
    sub, rest = args[index], args[index + 1 :]
    if sub in {"commit", "tag", "merge"}:
        kept: list[str] = []
        skip = False
        for word in rest:
            if skip:
                skip = False
                continue
            if word in {"-m", "--message", "-F", "--file"} or re.fullmatch(r"-[a-zA-Z]*m", word):
                skip = True
                if word not in {"-m", "--message", "-F", "--file"}:
                    kept.append(word[:-1])
                continue
            if word.startswith(("--message=", "--file=")):
                continue
            kept.append(word)
        rest = kept
    short = "".join(word[1:] for word in rest if re.fullmatch(r"-[a-zA-Z]+", word))
    longs = {word.split("=", 1)[0] for word in rest if word.startswith("--")}
    if sub == "push" and ("f" in short or "d" in short or longs & {"--force", "--force-with-lease", "--force-if-includes", "--mirror", "--delete", "--prune"} or any(word.startswith(("+", ":")) for word in rest)):
        block("the command force pushes or deletes on the remote")
    if sub in {"branch", "tag"} and ("d" in short.lower() or "--delete" in longs):
        block("the command deletes a branch or a tag")
    if sub == "update-ref" and "d" in short:
        block("the command deletes a reference")
    if sub in {"filter-branch", "filter-repo", "replace"} or (sub == "rebase" and "--root" in longs):
        block("the command rewrites the history")
    if sub == "reset" and longs & {"--hard", "--merge", "--keep"}:
        block("the command rewrites the history")
    if sub == "commit" and ("--amend" in longs or "--no-verify" in longs or "n" in short):
        block("the command rewrites the history or skips the git hooks")
    if sub in {"push", "merge", "rebase"} and "--no-verify" in longs:
        block("the command skips the git hooks")
    if sub == "clean" and "x" in short.lower():
        block("the command deletes ignored files such as .env")
    if sub == "config" and any(word.lower() == "core.hookspath" for word in rest) and len([w for w in rest if not w.startswith("-")]) > 1:
        block("the command turns the git hooks off")
    if sub in GIT_PATH_WRITES:
        paths = rest[rest.index("--") + 1 :] if "--" in rest else [word for word in rest if not word.startswith("-")]
        if any(is_protected(path, base, root) for path in paths):
            block("the command may change a protected file (deployment CI, agent setup or rules)")


def check_inline_code(program: str, code: str, base: Path, root: Path) -> None:
    if ENV_IN_CODE.search(code):
        block("the command dumps the environment")
    names = re.findall(r"[\w./~-]+", code)
    if any(is_secret(name) for name in names):
        block("the command reads a .env file, which holds secrets")
    if WRITE_IN_CODE.search(code) and any(is_protected(name, base, root) for name in names if "/" in name or "." in name):
        block("the command may change a protected file (deployment CI, agent setup or rules)")


def check_simple(words: list[str], base: Path, root: Path) -> Path:
    """Checks one simple command and returns the working folder after it (it changes only with `cd`)."""
    args, targets = split_redirects(words)
    for target in targets:
        if is_protected(target, base, root):
            block("the command writes to a protected file (deployment CI, agent setup or rules)")
    for word in words:
        if re.search(r"/proc/[^/\s]*/environ\b", word):
            block("the command dumps the environment")
    args = strip_leading(args)
    if not args:
        return base
    program = os.path.basename(args[0])
    rest = args[1:]

    if program == "cd":
        return resolve(rest[0], base) if rest and not rest[0].startswith("-") else base
    if program == "env":
        remaining = [word for word in rest if not word.startswith("-")]
        if not strip_leading(remaining):
            block("the command dumps the environment")
        return check_simple(strip_leading(remaining), base, root)
    if program == "printenv" or (program in {"export", "set"} and all(word in {"-p"} for word in rest)):
        block("the command dumps the environment")
    if program in {"declare", "typeset"} and any(re.fullmatch(r"-[a-zA-Z]*[px][a-zA-Z]*", word) for word in rest) and not [w for w in rest if not w.startswith("-")]:
        block("the command dumps the environment")
    if program == "compgen" and "-v" in rest:
        block("the command dumps the environment")
    if program == "eval":
        check_command(" ".join(rest), base, root)
        return base

    if program in SHELLS:
        for index, word in enumerate(rest):
            if re.fullmatch(r"-[a-zA-Z]*c[a-zA-Z]*", word) and index + 1 < len(rest):
                check_command(rest[index + 1], base, root)
                return base
        if rest and not rest[0].startswith("-") and is_protected(rest[0], base, root):
            return base
        return base
    if program.rstrip("0123456789.") in INTERPRETERS or program in INTERPRETERS:
        for index, word in enumerate(rest):
            if word in {"-c", "-e", "--eval", "-p", "--print", "-E"} and index + 1 < len(rest):
                check_inline_code(program, rest[index + 1], base, root)
                break

    env_file_values = {rest[i + 1] for i, word in enumerate(rest[:-1]) if word == "--env-file"}
    env_file_values |= {word.split("=", 1)[1] for word in rest if word.startswith("--env-file=")}
    operands = [word for word in rest if not word.startswith("-")]
    if program in {"rm", "rmdir", "shred", "unlink"} and any(is_outside(word, base, root) for word in operands):
        block("the command deletes outside the project")
    secret_operands = [word for word in operands if is_secret(word) and word not in env_file_values]
    if secret_operands:
        safe = program in SAFE_ENV_PROGRAMS or (program == "git" and rest[:1] == ["check-ignore"])
        safe |= program == "cp" and len(operands) == 2 and re.search(r"\.env\.(template|example)$", operands[0]) is not None
        if not safe:
            block("the command reads a .env file, which holds secrets (use `uv run --env-file .env ...`)")

    if program == "git":
        check_git(args, base, root)
    if program in {"sed", "perl", "ruby"} and any(re.fullmatch(r"-[a-zA-Z]*i\S*", word) or word.startswith("--in-place") for word in rest):
        if any(is_protected(word, base, root) for word in operands):
            block("the command may change a protected file (deployment CI, agent setup or rules)")
    if program in WRITE_PROGRAMS and any(is_protected(word, base, root) for word in operands):
        block("the command may change a protected file (deployment CI, agent setup or rules)")
    if program in COPY_PROGRAMS and operands and is_protected(operands[-1], base, root):
        block("the command may change a protected file (deployment CI, agent setup or rules)")
    if program == "dd" and any(word.startswith("of=") and is_protected(word[3:], base, root) for word in rest):
        block("the command may change a protected file (deployment CI, agent setup or rules)")
    if program == "find" and {"-delete", "-exec", "-execdir", "-ok"} & set(rest):
        roots = [word for word in rest if not word.startswith("-")][:1] or ["."]
        if is_outside(roots[0], base, root, root_allowed=True) or any(is_protected(word, base, root) for word in operands):
            block("the command deletes or changes files outside the project or protected files")
    return base


def check_command(command: str, base: Path, root: Path) -> None:
    flat = flatten(command, lambda inner: check_command(inner, base, root))
    previous_program = ""
    previous_separator = ""
    for words, separator in split_commands(tokenize(flat)):
        args = strip_leading(split_redirects(words)[0])
        program = os.path.basename(args[0]) if args else ""
        if previous_separator in {"|", "|&"} and previous_program in {"curl", "wget"} and (program in SHELLS or program in INTERPRETERS):
            block("the command runs a downloaded script")
        base = check_simple(words, base, root)
        previous_program, previous_separator = program, separator


# ---------------------------------------------------------------- tools


def check_path(raw: str, event: dict[str, object], *, writing: bool) -> None:
    root = project_root(event)
    base = Path(str(event.get("cwd") or root))
    if is_secret(PurePosixPath(raw.replace("\\", "/")).as_posix()):
        block(f"`{raw}` holds secrets")
    if writing and is_protected(raw, base, root):
        block(f"`{raw}` is a protected file (deployment CI, agent setup, rules or Claude Code settings)")


def check_event(event: object) -> None:
    if not isinstance(event, dict):
        block("the hook received an invalid event")
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        block("the hook received an invalid event")
    if tool == "Bash":
        root = project_root(event)
        check_command(str(tool_input.get("command", "")), Path(str(event.get("cwd") or root)).resolve(), root)
    elif tool in {"Edit", "Write", "MultiEdit", "NotebookEdit"}:
        check_path(str(tool_input.get("file_path") or tool_input.get("notebook_path") or ""), event, writing=True)
    elif tool == "Read":
        check_path(str(tool_input.get("file_path", "")), event, writing=False)
    elif tool == "Grep":
        check_path(str(tool_input.get("path") or "."), event, writing=False)
        glob = str(tool_input.get("glob") or "")
        for part in (part for part in re.split(r"[{},\s]+", glob) if part):
            name = part.rsplit("/", 1)[-1]
            if is_secret(part) or any(fnmatch(secret, name) for secret in SECRET_NAMES):
                block(f"the glob `{glob}` reaches a .env file, which holds secrets")


def main() -> None:
    try:
        check_event(json.load(sys.stdin))
    except json.JSONDecodeError:
        print(f"Blocked by .claude/hooks/guard.py ({POLICY}): the hook received an invalid event.", file=sys.stderr)
        sys.exit(2)
    except Blocked as reason:
        print(f"Blocked by .claude/hooks/guard.py ({POLICY}): {reason}. Ask a maintainer of the project if this is really needed.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
