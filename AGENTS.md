# AGENTS.md

## Purpose & Operating Mode
This repository is an automation system for running exactly one upload per platform
(Instagram → YouTube → TikTok) in controlled, debuggable steps.

Codex must behave as an infra-aware execution agent, not a generic coding assistant.

Primary goals:
- Deterministic runs (no retries, no loops, no fan-out)
- Minimal, paste-ready shell commands
- Zero scope creep
- One pass to green

---

## Mandatory Context Files
Before proposing any command or code change, always read:

- .codex/context.md
- .codex/chat_dump.md
- AGENTS.md (this file)

If information is missing, ask explicitly before proceeding.

---

## Execution Environment Assumptions
- Python 3.11
- Linux (Amazon Linux / EC2)
- Automation runs locally OR via AWS SSM
- Selenium + Chrome + chromedriver required for Instagram & YouTube
- Disk space is constrained

---

## Environment Setup (Local Only)
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
Sanity check (must pass):

bash
Copy code
PYTHONPATH=src python scripts/sanity_check.py
Canonical Execution Commands
Local CLI (single video)
bash
Copy code
PYTHONPATH=src python -m agent \
  --video sample_videos/test_tiktok.mp4 \
  --id local-test
End-to-End Script Examples
bash
Copy code
PYTHONPATH=src python scripts/test_instagram_upload.py ...
PYTHONPATH=src python scripts/test_youtube_upload.py ...
PYTHONPATH=src python scripts/test_tiktok_upload.py ...
Database
bash
Copy code
PYTHONPATH=src alembic upgrade head
Platform-Specific Rules
Instagram
--profile-dir is mandatory

Chrome profile must already exist

Headless defaults to false

Uses Selenium + Chrome + chromedriver

Fail fast on missing driver or disk pressure

YouTube
Uses Selenium

Requires logged-in Chrome profile

Must not reuse Instagram profiles

Exactly one video per invocation

TikTok
Uses tiktok-uploader or Selenium fallback

Cookies/session must already exist

No account switching during run

AWS SSM Rules (Critical)
When generating AWS SSM commands:

Output only paste-ready bash

One logical action per command

Avoid brace expansion {}

Avoid complex quoting

Avoid subshell arithmetic

Avoid inline heredocs inside commands[]

Prefer simple bash -lc blocks

If a command fails:

Next response must be diagnostic only

Do not attempt a fix until diagnostics are returned

Disk & System Safety
Assume disk is tight

Never download Chrome/driver unless required

Clean caches conservatively

Never delete Chrome profile Default directories

Never delete cookies or login state

Cache cleanup must be POSIX-safe

Coding Style & Naming
Indentation: 4 spaces

Imports: explicit, absolute (agent., tools.)

snake_case: modules/functions/vars

PascalCase: classes

SCREAMING_SNAKE_CASE: constants

Python 3.11 typing

Prefer X | None over Optional[X]

Testing Guidelines
Framework: pytest

Run all:

bash
Copy code
PYTHONPATH=src pytest -q
Single file:

bash
Copy code
PYTHONPATH=src pytest -q tests/agent/services/test_launch_group_service.py
Naming:

Files: test_*.py

Functions: test_*

Commit & PR Guidelines
Conventional Commits: feat:, fix:, docs:, refactor:

PRs must include:

Summary

How tested (commands + output)

Operational notes (env vars, infra, migrations)

Logs/screenshots if automation changed

Security & Configuration
Never commit secrets (.env, cookies, keys)

Examples must be sanitized

Document all new env vars

Agent Behavior Constraints (Non-Negotiable)
No speculative fixes

No refactors unless requested

No retries unless approved

No parallel platform execution

One platform → one video → one run

