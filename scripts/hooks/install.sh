#!/bin/sh
# Install the project's pre-commit hook on this clone (Linux/macOS, used on the Pi).
# Run from the repo root: ./scripts/hooks/install.sh
set -e

repo_root="$(git rev-parse --show-toplevel)"
source_hook="$repo_root/scripts/hooks/pre-commit.py"
hook_path="$repo_root/.git/hooks/pre-commit"

if [ ! -f "$source_hook" ]; then
  echo "Source hook not found: $source_hook" >&2
  exit 1
fi

cat > "$hook_path" <<INNER
#!/bin/sh
exec python3 "\$(git rev-parse --show-toplevel)/scripts/hooks/pre-commit.py"
INNER
chmod +x "$hook_path"

echo "Installed pre-commit hook at $hook_path"
echo "Bypass once: git commit --no-verify"
