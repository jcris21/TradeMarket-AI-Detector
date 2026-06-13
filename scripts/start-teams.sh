#!/bin/bash
# Boot parallel Claude teams via dmux ECC orchestrator.
# Edit scripts/dmux-plan.json to assign skills/tasks before running.
set -e

PROJECT="/mnt/e/FILES 2026/MVP_VIBECODE+AGENTIC/finally"
cd "$PROJECT"

# Locate orchestrate-worktrees.js bundled with dmux
DMUX_SCRIPTS="$(npm root -g)/dmux/scripts"
ORCHESTRATOR="$DMUX_SCRIPTS/orchestrate-worktrees.js"

if [ ! -f "$ORCHESTRATOR" ]; then
  echo "❌ orchestrate-worktrees.js not found at $ORCHESTRATOR"
  echo "   Run: npm install -g dmux"
  exit 1
fi

echo "🚀 Launching parallel teams via dmux..."
node "$ORCHESTRATOR" scripts/dmux-plan.json --execute

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅  Teams running"
echo "  Attach    : tmux attach -t finally-teams"
echo "  dmux keys : n = new pane  |  m = merge pane"
echo "  Assign    : bash scripts/launch-team.sh team1 /apply"
echo "  Handoff   : bash scripts/handoff.sh team1 team2"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
git worktree list
