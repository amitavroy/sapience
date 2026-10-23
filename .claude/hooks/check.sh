#!/usr/bin/env bash
# Stop hook: lint, format check and tests must pass before Claude can finish.
# Exit 2 sends the output back to Claude.
cd "$CLAUDE_PROJECT_DIR" || exit 1

# Already continuing because of this hook: let Claude stop rather than loop forever.
if [ "$(jq -r '.stop_hook_active // false')" = "true" ]; then exit 0; fi

# Nothing changed since the last commit: nothing to check.
if [ -z "$(git status --porcelain)" ]; then exit 0; fi

out=$(
  { uv run ruff check . \
    && uv run ruff format --check . \
    && uv run pytest -q -x; } 2>&1
) || {
  echo "Checks failed. Fix these before finishing:" >&2
  echo "$out" | tail -60 >&2
  exit 2
}
