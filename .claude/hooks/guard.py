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

import glob
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
SHELL_KEYWORDS = {"if", "then", "else", "elif", "while", "until", "do", "!", "{", "coproc"}
WRAPPERS = {"sudo", "doas", "time", "nice", "nohup", "command", "exec", "builtin", "xargs", "timeout", "stdbuf"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
INTERPRETERS = {"python", "python3", "node", "perl", "ruby", "deno", "bun"}
WRITE_PROGRAMS = {"tee", "rm", "rmdir", "mv", "ln", "chmod", "chown", "truncate", "touch", "unlink", "mkdir", "patch", "shred"}
COPY_PROGRAMS = {"cp", "install", "rsync", "dd"}
GIT_PATH_WRITES = {"rm", "mv", "checkout", "restore", "apply", "am", "commit", "update-index", "stash"}
SAFE_ENV_PROGRAMS = {"test", "[", "[[", "ls", "stat", "echo", "printf"}

WRITE_IN_CODE = re.compile(
    r"\b(unlink|rename|symlink|rm|rmdir|cp|copyFile|writeFile|appendFile|truncate|ftruncate)(Sync)?\b"
    r"|\b(write_text|write_bytes|rmtree|createWriteStream)\b|\bos\.(remove|removedirs)\b"
    r"|\bshutil\.(copy\w*|move)\b|\bos\.(replace|link|truncate)\b"
    r"|\bopen\([^,)]*,\s*(mode\s*=\s*)?['\"](r\+|[wax])|\.open\(\s*(mode\s*=\s*)?['\"](r\+|[wax])|\bmode\s*=\s*['\"](r\+|[wax])"
    r"|\bopen\(.*\)\s*,\s*['\"](r\+|[wax])"
)
ENV_IN_CODE = re.compile(r"os\.environ\b(?!\s*\[|\.get)|process\.env\b(?![.\[])|\bENV\.to_h\b|%ENV\b")
GLOB_CHARS = re.compile(r"[*?\[]")


class Blocked(Exception):
    pass


def block(reason: str) -> None:
    raise Blocked(reason)


def project_root(event: dict[str, object]) -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or str(event.get("cwd") or ".")).resolve()


def resolve_pattern(raw: str, base: Path) -> Path:
    """A glob pattern made absolute, without resolving its wildcards."""
    expanded = os.path.expanduser(raw.replace("${HOME}", "~").replace("$HOME", "~"))
    return Path(expanded) if os.path.isabs(expanded) else base.resolve() / expanded


def resolve(raw: str, base: Path) -> Path:
    expanded = os.path.expanduser(raw.replace("${HOME}", "~").replace("$HOME", "~"))
    path = Path(expanded)
    return (path if path.is_absolute() else base / path).resolve()


def shell_glob_matches(name: str, pattern: str) -> bool:
    """Shell glob semantics: a pattern that does not start with `.` never matches a dotfile."""
    if name.startswith(".") and not pattern.startswith("."):
        return False
    return fnmatch(name, pattern)


def is_protected(raw: str, base: Path, root: Path) -> bool:
    """True when the path is a protected file of the project or a Claude Code settings file."""
    if GLOB_CHARS.search(raw):
        # Expand like the shell would. In the project root, also match the names that do not exist yet.
        pattern = str(resolve_pattern(raw, base))
        if any(is_protected(match, base, root) for match in glob.glob(pattern)):
            return True
        folder, _, name = pattern.rstrip("/").rpartition("/")
        if Path(folder or "/").resolve() == root and any(shell_glob_matches(protected, name) for protected in PROTECTED_NAMES):
            return True
        return False
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
        return any(shell_glob_matches(secret, name) for secret in SECRET_NAMES)
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


def scan_substitutions(text: str, check_inner) -> None:
    """Checks the substitutions of an unquoted heredoc body. Quotes are literal there."""
    index = 0
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text.startswith("$(", index):
            end = take_substitution(text, index)
            check_inner(text[index + 2 : end - 1].strip("()") if text.startswith("$((", index) else text[index + 2 : end - 1])
            index = end
            continue
        if text[index] == "`":
            end = text.find("`", index + 1)
            if end < 0:
                block("the command has an unclosed backtick")
            check_inner(text[index + 1 : end])
            index = end + 1
            continue
        index += 1


# Heredoc bodies of the command being checked, by placeholder. Read when the program is a shell or an interpreter.
HEREDOCS: dict[str, str] = {}


def flatten(text: str, check_inner) -> str:
    """Checks each substitution with `check_inner`, keeps heredoc bodies aside and turns unquoted newlines into `;`."""
    out: list[str] = []
    pending_heredocs: list[tuple[str, bool, str]] = []
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
            if not quote and text[index + 1] in "()":
                out.append(" FIND_OPEN " if text[index + 1] == "(" else " FIND_CLOSE ")
            else:
                out.append(text[index : index + 2])
            index += 2
            continue
        if not quote and text[index : index + 3] in {"'('", "')'", '"("', '")"'}:
            out.append(" FIND_OPEN " if text[index + 1] == "(" else " FIND_CLOSE ")
            index += 3
            continue
        if not quote and text.startswith('$"', index):
            index += 1
            continue
        if not quote and text.startswith("$'", index):
            end = index + 2
            while end < len(text) and text[end] != "'":
                end += 2 if text[end] == "\\" else 1
            if end >= len(text):
                block("the command has an unclosed quote")
            try:
                decoded = text[index + 2 : end].encode("latin-1", "backslashreplace").decode("unicode_escape")
            except UnicodeDecodeError:
                decoded = text[index + 2 : end]
            out.append(shlex.quote(decoded))
            index = end + 1
            continue
        if text.startswith("$((", index):
            end = take_substitution(text, index)
            scan_substitutions(text[index + 3 : end - 2], check_inner)
            out.append("ARITHMETIC")
            index = end
            continue
        if text.startswith("$(", index):
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
            placeholder = f"HEREDOC_{len(HEREDOCS)}_"
            HEREDOCS[placeholder] = ""
            pending_heredocs.append((heredoc.group(2), heredoc.group(1) == "", placeholder))
            out.append(f" {placeholder} ")
            index += heredoc.end()
            continue
        if char == "\n":
            out.append(" ; ")
            index += 1
            for delimiter, expands, placeholder in pending_heredocs:
                end = re.compile(r"^[ \t]*" + re.escape(delimiter) + r"[ \t]*$", re.MULTILINE).search(text, index)
                body_end = end.start() if end else len(text)
                HEREDOCS[placeholder] = text[index:body_end]
                if expands:
                    scan_substitutions(text[index:body_end], check_inner)
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


def split_redirects(words: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Arguments, output targets and input sources. `2>&1` and `>/dev/null` write nothing."""
    operator = set("<>&|")
    args: list[str] = []
    targets: list[str] = []
    sources: list[str] = []
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
            if "<" in word and word != "<<<" and following:
                sources.append(following)
            index += 2
            continue
        args.append(word)
        index += 1
    return args, targets, sources


def strip_leading(args: list[str]) -> list[str]:
    """Drops variable assignments and wrappers in front of the program."""
    while args:
        word = args[0]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word) or word in SHELL_KEYWORDS:
            args = args[1:]
        elif os.path.basename(word) in WRAPPERS:
            args = args[1:]
            while args and args[0].startswith("-"):
                args = args[1:]
        else:
            break
    return args


def program_of(args: list[str]) -> str:
    """The program a command runs, `env` and wrappers unwrapped."""
    args = strip_leading(args)
    while args and os.path.basename(args[0]) == "env":
        args = strip_leading([word for word in args[1:] if not word.startswith("-")])
    return os.path.basename(args[0]) if args else ""


def long_options(words: list[str], known: set[str]) -> set[str]:
    """The known long options among `words`. git accepts any unambiguous prefix, so `--amen` counts as `--amend`."""
    found: set[str] = set()
    for word in words:
        if not word.startswith("--"):
            continue
        name = word.split("=", 1)[0]
        found |= {option for option in known if option == name or (len(name) >= 4 and option.startswith(name))}
    return found


GIT_DANGEROUS_LONGS = {
    "--force", "--force-with-lease", "--force-if-includes", "--mirror", "--delete", "--prune", "--no-verify",
    "--amend", "--hard", "--merge", "--keep", "--root",
}


def check_git(args: list[str], base: Path, root: Path) -> None:
    index = 1
    while index < len(args) and args[index].startswith("-"):
        option = args[index]
        if option in {"-C", "-c"} and index + 1 < len(args):
            if option == "-c" and args[index + 1].lower().startswith("core.hookspath"):
                block("the command turns the git hooks off")
            if option == "-C":
                base = resolve(args[index + 1], base)
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
    longs = long_options(rest, GIT_DANGEROUS_LONGS)
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


def check_inline_code(code: str, base: Path, root: Path) -> None:
    if ENV_IN_CODE.search(code):
        block("the command dumps the environment")
    names = re.findall(r"[\w./~-]+", code)
    if any(is_secret(name) for name in names):
        block("the command reads a .env file, which holds secrets")
    if WRITE_IN_CODE.search(code) and any(is_protected(name, base, root) for name in names if "/" in name or "." in name):
        block("the command may change a protected file (deployment CI, agent setup or rules)")


# Options that take a value, for the runners whose own command is checked too.
RUNNER_VALUE_OPTIONS = {
    "uv": {"--env-file", "--with", "--python", "-p", "--directory", "--project", "--package", "--group", "--extra", "--index", "--from"},
    "npx": {"--package", "-p", "--call", "-c"},
    "docker": {"-e", "--env", "--env-file", "-v", "--volume", "--name", "-p", "--publish", "-w", "--workdir", "-u", "--user", "--network", "--entrypoint", "--mount", "--label", "-l"},
}


def runner_command(program: str, rest: list[str]) -> list[str] | None:
    """The command run by `uv run`, `npx`, `bunx`, `docker run` or `docker exec`, or None."""
    if program == "uv" and rest[:1] == ["run"]:
        values, rest = RUNNER_VALUE_OPTIONS["uv"], rest[1:]
    elif program in {"npx", "bunx", "pnpx"}:
        values = RUNNER_VALUE_OPTIONS["npx"]
    elif program in {"docker", "podman"} and rest[:1] in (["run"], ["exec"]):
        values, rest = RUNNER_VALUE_OPTIONS["docker"], rest[1:]
    else:
        return None
    index = 0
    while index < len(rest) and rest[index].startswith("-"):
        index += 2 if rest[index] in values else 1
    remaining = rest[index:]
    if program in {"docker", "podman"}:
        remaining = remaining[1:]
    return remaining


def operands_of(program: str, rest: list[str]) -> list[str]:
    """Non-option arguments, without the value of `--env-file` (a program reads it, nothing prints it) nor a grep pattern."""
    operands: list[str] = []
    skip = False
    for word in rest:
        if skip:
            skip = False
            continue
        if word == "--env-file":
            skip = True
            continue
        if not word.startswith("-"):
            operands.append(word)
    if program in {"grep", "egrep", "fgrep", "rg"} and operands and not {"-e", "-f", "--regexp", "--file"} & set(rest):
        operands = operands[1:]
    return operands


def check_simple(words: list[str], base: Path, root: Path, piped_from: list[str] | None = None) -> Path:
    """Checks one simple command and returns the working folder after it (it changes only with `cd` and `pushd`)."""
    args, targets, sources = split_redirects(words)
    for target in targets:
        if is_protected(target, base, root):
            block("the command writes to a protected file (deployment CI, agent setup or rules)")
    for source in sources:
        if is_secret(source):
            block("the command reads a .env file, which holds secrets")
    for word in words:
        if re.search(r"/proc/[^/\s]*/environ\b", word):
            block("the command dumps the environment")
    args = strip_leading(args)
    if not args:
        return base
    program = os.path.basename(args[0])
    rest = args[1:]
    heredoc_bodies = [HEREDOCS[word] for word in words if word in HEREDOCS]
    heredoc_bodies += [words[index + 1] for index, word in enumerate(words[:-1]) if word == "<<<"]

    if program in {"cd", "pushd"}:
        folders = [word for word in rest if not word.startswith("-")]
        return resolve(folders[0], base) if folders else base
    if program == "env":
        remaining = [word for word in rest if not word.startswith("-")]
        if not strip_leading(remaining):
            block("the command dumps the environment")
        return check_simple(strip_leading(remaining) + [word for word in words if word in HEREDOCS], base, root, piped_from)
    if program == "printenv" or (program in {"export", "set"} and all(word in {"-p"} for word in rest)):
        block("the command dumps the environment")
    if program in {"declare", "typeset"} and any(re.fullmatch(r"-[a-zA-Z]*[px][a-zA-Z]*", word) for word in rest) and not [w for w in rest if not w.startswith("-")]:
        block("the command dumps the environment")
    if program == "compgen" and "-v" in rest:
        block("the command dumps the environment")
    if program == "eval":
        check_command(" ".join(rest), base, root)
        return base

    # Code given to a shell or an interpreter: -c/-e, a heredoc, or text piped from echo, printf or a heredoc.
    piped_code = piped_from or []
    if program in SHELLS:
        for index, word in enumerate(rest):
            if re.fullmatch(r"-[a-zA-Z]*c[a-zA-Z]*", word) and index + 1 < len(rest):
                check_command(rest[index + 1], base, root)
                return base
        for code in heredoc_bodies + piped_code:
            check_command(code, base, root)
        return base
    if program.rstrip("0123456789.") in INTERPRETERS or program in INTERPRETERS:
        for index, word in enumerate(rest):
            if word in {"-c", "-e", "--eval", "-p", "--print", "-E"} and index + 1 < len(rest):
                check_inline_code(rest[index + 1], base, root)
                break
        for code in heredoc_bodies + piped_code:
            check_inline_code(code, base, root)

    nested = runner_command(program, rest)
    if nested:
        check_simple(nested, base, root)

    operands = operands_of(program, rest)
    if program in {"rm", "rmdir", "shred", "unlink"} and any(is_outside(word, base, root) for word in operands):
        block("the command deletes outside the project")
    if nested is None and any(is_secret(word) for word in operands):
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
    if program in COPY_PROGRAMS | {"mv"}:
        destinations = operands[-1:]
        destinations += [rest[i + 1] for i, word in enumerate(rest[:-1]) if word in {"-t", "--target-directory"}]
        destinations += [word.split("=", 1)[1] for word in rest if word.startswith("--target-directory=")]
        if any(is_protected(word, base, root) for word in destinations):
            block("the command may change a protected file (deployment CI, agent setup or rules)")
    if program == "dd" and any(word.startswith("of=") and is_protected(word[3:], base, root) for word in rest):
        block("the command may change a protected file (deployment CI, agent setup or rules)")
    if program == "find":
        check_find(rest, base, root)
    return base


FIND_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}
FIND_NAME_FILTERS = {"-name": False, "-iname": True}
FIND_PATH_FILTERS = {"-path": False, "-ipath": True, "-wholename": False, "-iwholename": True}
FIND_REGEX_FILTERS = {"-regex": False, "-iregex": True}
SKIPPED_FOLDERS = {"node_modules", ".venv", ".git", "dist", "dist-ci", "__pycache__"}


def protected_files_under(folder: Path, root: Path) -> list[Path]:
    """The protected files and folders that exist under `folder` (the folder itself included)."""
    found: list[Path] = []
    if not folder.is_dir():
        try:
            relative = folder.resolve().relative_to(root).as_posix()
        except ValueError:
            return found
        return [folder] if PROTECTED_PATH.search(relative) else found
    for current, folders, files in os.walk(folder):
        folders[:] = [name for name in folders if name not in SKIPPED_FOLDERS]
        for name in [*folders, *files, ""]:
            path = Path(current, name) if name else Path(current)
            try:
                relative = path.resolve().relative_to(root).as_posix()
            except ValueError:
                continue
            if PROTECTED_PATH.search(relative):
                found.append(path)
    return found


def find_test(word: str, value: str, path: Path, shown: str) -> bool | None:
    """The result of one name, path or regex test on `path`, or None when `word` is not such a test."""
    if word in FIND_NAME_FILTERS:
        fold = FIND_NAME_FILTERS[word]
        return fnmatch(path.name.lower() if fold else path.name, value.lower() if fold else value)
    if word in FIND_PATH_FILTERS:
        fold = FIND_PATH_FILTERS[word]
        return fnmatch(shown.lower() if fold else shown, value.lower() if fold else value)
    if word in FIND_REGEX_FILTERS:
        if re.search(r"\\[<>`'bBwW]", value):
            return True  # emacs word and buffer operators: not translated, counted as a match
        value = re.sub(r"\\([(){}|+?])", r"\1", value)  # basic and emacs operators, written as extended
        try:
            return re.fullmatch(value, shown, re.IGNORECASE if FIND_REGEX_FILTERS[word] else 0) is not None
        except re.error:
            return True
    return None


# Tests and options of find that take one argument. -fprintf takes two.
FIND_ONE_ARGUMENT = {
    "-name", "-iname", "-path", "-ipath", "-wholename", "-iwholename", "-regex", "-iregex", "-lname", "-ilname",
    "-type", "-xtype", "-maxdepth", "-mindepth", "-newer", "-anewer", "-cnewer", "-mtime", "-mmin", "-atime", "-amin",
    "-ctime", "-cmin", "-size", "-user", "-group", "-uid", "-gid", "-perm", "-regextype", "-samefile", "-links",
    "-inum", "-used", "-fstype", "-context", "-printf", "-fprint", "-fprint0", "-fls", "-newermt", "-flags",
}
FIND_WRITES = {"-fprint", "-fprint0", "-fprintf", "-fls"}


class FindExpression:
    """Evaluates a find expression for one path, with the precedence of find (`!`, then `-a`, then `-o`, then `,`)
    and short-circuit evaluation. Each value is the set of results it may have: a test this hook does not know may be
    true or false. `reaches` is True when the expression may run its action (-delete, -exec...) on the path."""

    def __init__(self, tokens: list[str], path: Path, shown: str) -> None:
        self.tokens, self.index, self.path, self.shown = tokens, 0, path, shown

    def peek(self) -> str | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def take(self) -> str:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def parse_list(self) -> tuple[set[bool], bool]:
        values, reaches = self.parse_or()
        while self.peek() == ",":
            self.take()
            values, more = self.parse_or()
            reaches = reaches or more
        return values, reaches

    def parse_or(self) -> tuple[set[bool], bool]:
        values, reaches = self.parse_and()
        while self.peek() in {"-o", "-or"}:
            self.take()
            right, right_reaches = self.parse_and()
            if False in values:
                reaches = reaches or right_reaches
                values = ({True} if True in values else set()) | right
        return values, reaches

    def parse_and(self) -> tuple[set[bool], bool]:
        values, reaches = self.parse_unary()
        while self.peek() not in {None, "-o", "-or", ",", ")"}:
            if self.peek() in {"-a", "-and"}:
                self.take()
            right, right_reaches = self.parse_unary()
            if True in values:
                reaches = reaches or right_reaches
                values = ({False} if False in values else set()) | right
        return values, reaches

    def parse_unary(self) -> tuple[set[bool], bool]:
        token = self.take()
        if token in {"-not", "!"}:
            values, reaches = self.parse_unary()
            return {not value for value in values}, reaches
        if token == "(":
            values, reaches = self.parse_list()
            if self.peek() != ")":
                raise ValueError("unclosed parenthesis")
            self.take()
            return values, reaches
        if token in FIND_EXEC:
            while self.peek() not in {None, ";", "+"}:
                self.take()
            if self.peek() is not None:
                self.take()
            return {True, False}, True
        if token == "-delete":
            return {True}, True
        if token == "-fprintf":
            self.take()
            self.take()
            return {True}, True
        if token in FIND_ONE_ARGUMENT:
            argument = self.take()
            result = find_test(token, argument, self.path, self.shown)
            if token in FIND_WRITES:
                return {True}, True
            return ({result} if result is not None else {True, False}), False
        if token in {"-true", "-print", "-print0", "-ls", "-prune", "-depth", "-xdev", "-mount", "-follow", "-noleaf", "-d", "-x"}:
            return {True}, False
        if token == "-false":
            return {False}, False
        return {True, False}, False


def find_expression(rest: list[str]) -> list[str]:
    """The expression of a find command: what follows its options and start folders."""
    index = 0
    while index < len(rest) and (rest[index] in {"-L", "-H", "-P", "-D", "-O", "-E", "-X", "-s", "-x", "-d", "-f"} or re.fullmatch(r"-O\d", rest[index])):
        index += 2 if rest[index] in {"-D", "-O", "-f"} else 1
    while index < len(rest) and not rest[index].startswith("-") and rest[index] not in {"!", "(", ","}:
        index += 1
    return rest[index:]


def find_selects(path: Path, start: str, folder: Path, rest: list[str]) -> bool:
    """Whether the find expression may run its action on `path`. An expression it cannot parse counts as yes."""
    shown = start.rstrip("/") + "/" + path.relative_to(folder).as_posix() if path != folder else start
    expression = FindExpression(find_expression(rest), path, shown)
    try:
        _, reaches = expression.parse_list()
    except (ValueError, IndexError):
        return True
    return reaches or expression.peek() is not None


def find_starts(rest: list[str]) -> list[str]:
    """The start folders of a find command, after its -L, -H, -P, -D and -O options."""
    index = 0
    starts: list[str] = []
    while index < len(rest) and (rest[index] in {"-L", "-H", "-P", "-D", "-O", "-E", "-X", "-s", "-x", "-d", "-f"} or re.fullmatch(r"-O\d", rest[index])):
        if rest[index] == "-f" and index + 1 < len(rest):
            starts.append(rest[index + 1])
        index += 2 if rest[index] in {"-D", "-O", "-f"} else 1
    while index < len(rest) and not rest[index].startswith("-") and rest[index] not in {"!", "("}:
        starts.append(rest[index])
        index += 1
    return starts or ["."]


def check_find(rest: list[str], base: Path, root: Path) -> None:
    """Checks each `-exec` command as a command, with `{}` standing for a file of the searched folder. When find
    deletes or changes files, blocks it if its tests may select a protected file under a start folder."""
    rest = ["(" if word == "FIND_OPEN" else ")" if word == "FIND_CLOSE" else word for word in rest]
    starts = find_starts(rest)
    commands: list[list[str]] = []
    index = 0
    while index < len(rest):
        if rest[index] in FIND_EXEC:
            end = index + 1
            while end < len(rest) and rest[end] not in {";", "+"}:
                end += 1
            commands.append(rest[index + 1 : end])
            index = end + 1
        else:
            index += 1
    changes = "-delete" in rest
    for index, word in enumerate(rest[:-1]):
        if word in {"-fprint", "-fprint0", "-fprintf", "-fls"} and is_protected(rest[index + 1], base, root):
            block("the command writes to a protected file (deployment CI, agent setup or rules)")
    for command in commands:
        program = program_of(command)
        in_place = program in {"sed", "perl", "ruby"} and any(re.fullmatch(r"-[a-zA-Z]*i\S*", word) for word in command)
        changes |= program in WRITE_PROGRAMS | COPY_PROGRAMS | {"mv"} or in_place
        check_simple([str(resolve(starts[0], base) / "FIND_RESULT") if word == "{}" else word for word in command], base, root)
    if not changes:
        return
    for start in starts:
        if is_outside(start, base, root, root_allowed=True):
            block("the command deletes or changes files outside the project")
        folder = resolve(start, base)
        for path in protected_files_under(folder, root):
            if find_selects(path, start, folder, rest):
                block(f"the command may delete or change the protected file `{path.relative_to(root).as_posix() or '.'}`")


def piped_text(words: list[str]) -> list[str]:
    """Text a command writes to the next one: the arguments of echo and printf, the body of a heredoc."""
    args = strip_leading(split_redirects(words)[0])
    program = os.path.basename(args[0]) if args else ""
    texts = [HEREDOCS[word] for word in words if word in HEREDOCS]
    if program in {"echo", "printf"}:
        texts.append(" ".join(word for word in args[1:] if not re.fullmatch(r"-[neE]+", word)))
    return texts


def runs_module_or_script(words: list[str]) -> bool:
    """True when an interpreter runs a module (-m) or a script file: its standard input is then data, not code."""
    args = strip_leading(words)[1:]
    if "-m" in args:
        return True
    return any(not word.startswith("-") for word in args)


def check_command(command: str, base: Path, root: Path) -> None:
    flat = flatten(command, lambda inner: check_command(inner, base, root))
    previous_words: list[str] = []
    previous_separator = ""
    for words, separator in split_commands(tokenize(flat)):
        program = program_of(split_redirects(words)[0])
        piped = previous_separator in {"|", "|&"}
        runs_stdin = program in SHELLS or (program in INTERPRETERS and not runs_module_or_script(split_redirects(words)[0]))
        if piped and program_of(split_redirects(previous_words)[0]) in {"curl", "wget"} and runs_stdin:
            block("the command runs a downloaded script")
        base = check_simple(words, base, root, piped_text(previous_words) if piped else None)
        previous_words, previous_separator = words, separator


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
        HEREDOCS.clear()
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
