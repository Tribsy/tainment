# Pre-commit hook

The hook (`pre-commit.py`) blocks any *new* `.py` file added at the repo root unless it's in the allowlist. It exists to enforce Phase 0's anti-chaos rule: features go into `cogs/`, infra goes into `core/`, integrations go into `services/`. The repo root stays small and intentional.

Modifying existing root files is fine — the hook only fires on additions.

## Install on this clone

```powershell
# Windows / PowerShell
.\scripts\hooks\install.ps1
```

```sh
# Linux / macOS / Pi
./scripts/hooks/install.sh
```

The installer writes a thin shell wrapper into `.git/hooks/pre-commit` that calls the tracked Python script. Re-run after `git clone` on each new machine.

## Bypass once

```sh
git commit --no-verify
```

Use sparingly — every bypass is a deliberate exception. Document why in the commit message.

## Updating the allowlist

Edit `pre-commit.py`. Two sets:

- `ENTRY_POINTS` — files that legitimately live at the root forever (`main.py`, `config.py`).
- `PHASE_0_ROOT` — files that *currently* live at root but will move out in Phases 1+. As each migration completes, delete its entry so a future re-add is blocked.
