# Install the project's pre-commit hook on this clone.
# Run from the repo root: .\scripts\hooks\install.ps1
$ErrorActionPreference = "Stop"

$repoRoot   = git rev-parse --show-toplevel
$source     = Join-Path $repoRoot "scripts\hooks\pre-commit.py"
$hookPath   = Join-Path $repoRoot ".git\hooks\pre-commit"

if (-not (Test-Path $source)) {
    Write-Error "Source hook not found: $source"
    exit 1
}

# .git/hooks/pre-commit is a sh script that calls our Python hook.
@"
#!/bin/sh
# Auto-installed by scripts/hooks/install.ps1 — calls the project's Python hook.
exec python "`$(git rev-parse --show-toplevel)/scripts/hooks/pre-commit.py"
"@ | Set-Content -Path $hookPath -NoNewline -Encoding ASCII

Write-Host "Installed pre-commit hook at $hookPath"
Write-Host "It will run scripts/hooks/pre-commit.py on every commit."
Write-Host "Bypass once: git commit --no-verify"
