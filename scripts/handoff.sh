#!/bin/bash
# Route output from one team pane to another via smux tmux-bridge.
#
# Usage: bash handoff.sh <from-team> <to-team> [lines] [instruction]
#
# Examples:
#   bash scripts/handoff.sh team1 team2
#   bash scripts/handoff.sh team1 team2 100 "Implement this plan"
#   bash scripts/handoff.sh team2 team3 80  "Review for correctness"
#   bash scripts/handoff.sh team3 team1 40  "Summarize what was merged"

FROM="${1:?Usage: handoff.sh <from-team> <to-team> [lines] [instruction]}"
TO="${2:?to-team required}"
LINES="${3:-80}"
INSTRUCTION="${4:-Implement based on the above output}"

echo "📤 Reading $LINES lines from: $FROM"
OUTPUT=$(tmux-bridge read "$FROM" "$LINES")

if [ -z "$OUTPUT" ]; then
  echo "⚠️  No output captured from '$FROM' — is the pane active?"
  exit 1
fi

echo "📥 Sending to: $TO"
tmux-bridge type "$TO" "=== Handoff from $FROM ==="
tmux-bridge keys "$TO" "Enter"
tmux-bridge type "$TO" "$OUTPUT"
tmux-bridge keys "$TO" "Enter"
tmux-bridge type "$TO" "$INSTRUCTION"
tmux-bridge keys "$TO" "Enter"

echo "✅ Handoff complete: $FROM → $TO"
