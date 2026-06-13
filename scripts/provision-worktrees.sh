#!/bin/bash
# Provision generic team worktrees (t1–t4) from current HEAD.
# Usage: bash provision-worktrees.sh [t1 t2 t3 t4]
# Default: provisions all 4 slots.
set -e

PROJECT="/mnt/e/FILES 2026/MVP_VIBECODE+AGENTIC/finally"
cd "$PROJECT"

if [ $# -eq 0 ]; then
  SLOTS=(t1 t2 t3 t4)
else
  SLOTS=("$@")
fi
BASE_BRANCH=$(git branch --show-current)

echo "Base branch : $BASE_BRANCH"
echo "Slots       : ${SLOTS[*]}"
echo ""

for slot in "${SLOTS[@]}"; do
  BRANCH="team/$slot"
  WPATH=".worktrees/$slot"

  if [ -d "$WPATH" ]; then
    git worktree remove --force "$WPATH" 2>/dev/null || rm -rf "$WPATH"
  fi
  git branch -D "$BRANCH" 2>/dev/null || true
  git worktree add "$WPATH" -b "$BRANCH"
  echo "  ✅  .worktrees/$slot  →  branch: $BRANCH"
done

echo ""
git worktree list
