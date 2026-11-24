#!/usr/bin/env python3
"""SessionStart hook (startup only): the welcome message of the project, for the user and for Claude.

The message explains the three parts of the project (miniapp/, api/, plugin/) and asks what the user wants to build for Up.
Run its test: python3 .claude/hooks/welcome_test.py
"""

import json

WELCOME = """Claude Code is ready in this project.

This Up mini-app project has three parts:
- miniapp/: the mini-app. A web app shown inside the Up phone app and, when deviceTypes allows it, on the Up website. React and the Up SDK, French UI text.
- api/: its backend (FastAPI). It keeps the data in PostgreSQL, the cache and the bucket, and checks the Up user tokens.
- plugin/: the admin page of the mini-app, in the Studio. Admins use it to put data into the database: content, settings, moderation.

To run it, say "start everything": Claude runs dev-tools/up-dev.sh start and gives you the addresses.

What do you want to build for Up? Describe your idea and Claude plans it with you."""

CONTEXT = (
    "At the start of this session the user saw this welcome message:\n\n"
    + WELCOME
    + "\n\nIf the user's first message describes something to build, treat it as the answer: "
    "follow the skill up-miniapp-project, say which parts (miniapp/, api/, plugin/) it touches and plan it with the user. "
    "If it is a concrete task or a question, do it directly. "
    "If it asks to start or run the project, follow the skill up-miniapp-start: run dev-tools/up-dev.sh start at once. "
    "If it is only a greeting, briefly ask again what they want to build for Up."
)


def main() -> None:
    print(
        json.dumps(
            {
                "systemMessage": WELCOME,
                "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": CONTEXT},
            }
        )
    )


if __name__ == "__main__":
    main()
