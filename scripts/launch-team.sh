#!/bin/bash
# Launch Claude in yolo mode in a team pane, then optionally send a skill.
#
# Usage:
#   bash launch-team.sh <team-name> [skill-or-prompt]
#
# Examples:
#   bash launch-team.sh team1                    # bare Claude, no skill
#   bash launch-team.sh team1 "/plan"            # Claude + /plan skill
#   bash launch-team.sh team2 "/tdd"
#   bash launch-team.sh team3 "/code-review"
#   bash launch-team.sh team4 "/orchestrate"

TEAM="${1:?Usage: launch-team.sh <team-name> [skill-or-prompt]}"
SKILL="${2:-}"
SESSION="finally-teams"

PANE_IDX=$(tmux-bridge resolve "$TEAM" 2>/dev/null || echo "")
if [ -z "$PANE_IDX" ]; then
  echo "❌ Pane '$TEAM' not found. Run: bash scripts/smux-agents.sh"
  exit 1
fi

TARGET="$SESSION:0.$PANE_IDX"

# Step 1: navigate to the team's worktree
SLOT="${TEAM//team/t}"
PROJECT="/mnt/e/FILES 2026/MVP_VIBECODE+AGENTIC/finally"
WDIR="$PROJECT/.worktrees/$SLOT"

if [ ! -d "$WDIR" ]; then
  echo "❌ Worktree not found: $WDIR — run provision-worktrees.sh first"
  exit 1
fi

tmux send-keys -t "$TARGET" "cd '$WDIR'" Enter
sleep 0.3

# Step 2: launch Claude in yolo mode
tmux send-keys -t "$TARGET" "claude --dangerously-skip-permissions" Enter

# Step 3: if skill provided, wait for Claude to initialize then send it
if [ -n "$SKILL" ]; then
  echo "⏳ Waiting for Claude to initialize..."
  sleep 5
  tmux send-keys -t "$TARGET" "$SKILL" Enter
fi

echo "✅ $TEAM → .worktrees/$SLOT${SKILL:+  skill: $SKILL}"
