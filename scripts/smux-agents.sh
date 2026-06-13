#!/bin/bash
# Build a 2x2 tmux layout with 4 generic team panes.
# No skills or agents assigned — use launch-team.sh for that.
set -e

SESSION="finally-teams"

tmux kill-session -t "$SESSION" 2>/dev/null || true
tmux new-session -d -s "$SESSION" -x 220 -y 50
tmux rename-window -t "$SESSION:0" "teams"

# 2x2 grid: split right, then split each column vertically
tmux split-window -h -t "$SESSION:teams"
tmux split-window -v -t "$SESSION:teams.0"
tmux split-window -v -t "$SESSION:teams.1"

# Name panes via smux tmux-bridge
tmux-bridge name 0 "team1"
tmux-bridge name 1 "team2"
tmux-bridge name 2 "team3"
tmux-bridge name 3 "team4"

echo "✅ smux layout ready — session: $SESSION"
echo ""
tmux-bridge list
