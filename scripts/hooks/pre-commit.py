#!/usr/bin/env python3
"""
Pre-commit hook — Phase 0 anti-chaos rule.

Blocks any NEW root-level .py file from being committed unless it's in the
allowlist. Modifying existing root files is fine; adding new ones forces a
conscious choice. Override with `git commit --no-verify` if you really need to.

Allowlist starts generous: every .py file currently tracked at root passes.
As Phase 1+ migrates files into cogs/ / core/ / services/, prune this list.
"""
import subprocess
import sys

# Files allowed to live at the repo root indefinitely.
ENTRY_POINTS = {
    "main.py",
    "config.py",
}

# Currently at root (Phase 0 reality). These will move out in later phases.
# When a file moves, delete it from this set so a future re-add is blocked.
PHASE_0_ROOT = {
    "admin_subscription.py",
    "automod.py",
    "birthday.py",
    "casino_config_addition.py",
    "casino_db.py",
    "database.py",
    "devdreams_setup_1.py",
    "economy.py",
    "fun.py",
    "games.py",
    "giveaway.py",
    "leaderboard.py",
    "lemonsqueezy_payment.py",
    "levels.py",
    "music_data.py",
    "music_discovery.py",
    "music_trivia.py",
    "payment.py",
    "polls.py",
    "profile.py",
    "questions.py",
    "reaction_roles.py",
    "reminders.py",
    "reply_utils.py",
    "spotify.py",
    "subscription.py",
    "subscription_tasks.py",
    "support_forms.py",
    "utils.py",
}

ALLOWED = ENTRY_POINTS | PHASE_0_ROOT


def added_root_python_files() -> list[str]:
    """Return paths of newly-added .py files at the repo root."""
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=A"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if not out:
        return []
    return [p for p in out.splitlines() if p.endswith(".py") and "/" not in p]


def main() -> int:
    violations = [p for p in added_root_python_files() if p not in ALLOWED]
    if not violations:
        return 0
    print("\n[pre-commit] Blocked new root-level .py file(s):", file=sys.stderr)
    for p in violations:
        print(f"  - {p}", file=sys.stderr)
    print(
        "\nAnti-chaos rule (Phase 0): new feature files should live under cogs/, "
        "core/, services/, scripts/, or another domain folder — not at the repo root.\n"
        "If this is genuinely a top-level concern, add it to ENTRY_POINTS in "
        "scripts/hooks/pre-commit.py and re-run.\n"
        "To bypass once: git commit --no-verify",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
