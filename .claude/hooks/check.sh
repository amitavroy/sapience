#!/usr/bin/env bash
# Stop hook. Exit 2 sends the output back to Claude, which then has to act on it.
#   lint, format check and tests must pass
# Skipped when the tree is clean, when it is unchanged since the last passing run (a chat-only
# turn), and when the turn was a /do-commit.
cd "$CLAUDE_PROJECT_DIR" || exit 1

input=$(cat)
# true when Claude is already continuing because a Stop hook blocked it.
# Unparseable input (e.g. jq missing) counts as true, so the loop guards below still apply.
active=$(jq -r '.stop_hook_active // false' <<<"$input" 2>/dev/null)
[ -z "$active" ] && active=true
sid=$(jq -r '.session_id // "default"' <<<"$input" 2>/dev/null)
transcript=$(jq -r '.transcript_path // empty' <<<"$input" 2>/dev/null)

# Nothing changed since the last commit: nothing to check or review.
if [ -z "$(git status --porcelain)" ]; then exit 0; fi

# The turn was a /do-commit: committing is not a change to check or review. The last real prompt
# is the latest non-meta user message that is not a task or agent notification.
if [ -n "$transcript" ] && [ -r "$transcript" ]; then
  last_prompt=$(
    jq -r 'select(.type == "user" and (.isMeta | not) and (.message.content | type) == "string")
      | .message.content
      | select(contains("<task-notification>") | not)
      | select(contains("<local-command-caveat>") | not)
      | tojson' "$transcript" 2>/dev/null | tail -n 1
  )
  case "$last_prompt" in *"<command-name>/do-commit</command-name>"*) exit 0 ;; esac
fi

# Per-session state, so parallel sessions in one checkout don't interfere.
state="$(git rev-parse --git-dir)/claude-stop-hook/${sid:-default}"
mkdir -p "$state"
if [ "$active" != "true" ]; then
  echo 0 >"$state/fails"
  echo 0 >"$state/review_requested"
fi

# Fingerprint of the tree: status + diff + untracked file contents.
hash=$(
  {
    git status --porcelain
    git diff HEAD
    git ls-files -o --exclude-standard -z | xargs -0 shasum
  } 2>/dev/null | shasum | cut -d' ' -f1
)
# Nothing changed since the last run that passed: a chat-only turn needs no check or review.
if [ "$active" != "true" ] && [ "$hash" = "$(cat "$state/passed" 2>/dev/null)" ]; then exit 0; fi

out=$(
  { uv run ruff check . \
    && uv run ruff format --check . \
    && uv run pytest -q -x; } 2>&1
) || {
  fails=$(($(cat "$state/fails" 2>/dev/null || echo 0) + 1))
  echo "$fails" >"$state/fails"
  # Stuck on something Claude cannot fix: stop blocking instead of looping forever.
  if [ "$active" = "true" ] && [ "$fails" -ge 3 ]; then
    echo '{"systemMessage": "Stop hook: checks still failing after repeated attempts, giving up. Run the checks yourself."}'
    exit 0
  fi
  echo "Checks failed. Fix these before finishing:" >&2
  echo "$out" | tail -60 >&2
  exit 2
}

echo "$hash" >"$state/passed"
exit 0
