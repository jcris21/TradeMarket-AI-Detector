#!/bin/bash
# Open a new tmux window for a story, cd to its worktree, and launch Claude.
#
# Usage:
#   bash scripts/new-story.sh <worktree> <story-label> [prompt]
#
# Examples:
#   bash scripts/new-story.sh t1 us-103
#   bash scripts/new-story.sh t4 us-301 "/openspec-apply-change us-301-two-layer-score-architecture"
#   bash scripts/new-story.sh t2 us-200 "continua implementando US-200"
#
# The script creates (or reuses) the 'finally' tmux session and opens a new
# window named '<worktree>-<story-label>'. Each window gets two panes:
#   - top  (60%): working view — shows git status at open
#   - bottom (40%): Claude running in --dangerously-skip-permissions mode

set -e

SLOT="${1:?Usage: new-story.sh <worktree> <story-label> [prompt]}"
LABEL="${2:?Usage: new-story.sh <worktree> <story-label> [prompt]}"
PROMPT="${3:-}"

PROJECT="/mnt/e/FILES 2026/MVP_VIBECODE+AGENTIC/finally"
WDIR="$PROJECT/.worktrees/$SLOT"
SESSION="finally"
WINDOW_NAME="${SLOT}-${LABEL}"

if [ ! -d "$WDIR" ]; then
  echo "❌ Worktree not found: $WDIR"
  echo "   Run: bash scripts/provision-worktrees.sh"
  exit 1
fi

# Create session if it doesn't exist
tmux new-session -d -s "$SESSION" -x 220 -y 50 2>/dev/null || true

# Create new window
tmux new-window -t "$SESSION" -n "$WINDOW_NAME"

# Top pane: cd to worktree and show status
tmux send-keys -t "$SESSION:$WINDOW_NAME" "cd '$WDIR' && git status -s && git log --oneline -3" Enter

# Split: bottom pane 40% for Claude
tmux split-window -t "$SESSION:$WINDOW_NAME" -v -p 40

# Bottom pane: launch Claude
tmux send-keys -t "$SESSION:$WINDOW_NAME.1" "cd '$WDIR' && claude --dangerously-skip-permissions" Enter

# Optionally send a prompt after Claude initializes
if [ -n "$PROMPT" ]; then
  echo "⏳ Waiting 6s for Claude to initialize..."
  sleep 6
  tmux send-keys -t "$SESSION:$WINDOW_NAME.1" "$PROMPT" Enter
fi

echo "✅ Window '$WINDOW_NAME' ready in session '$SESSION'"
echo "   Attach: tmux attach -t $SESSION"
echo "   Window: $WINDOW_NAME  |  Worktree: $WDIR"
