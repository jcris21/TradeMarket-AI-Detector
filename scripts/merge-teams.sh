#!/bin/bash
# Merge completed team branches back into the current branch.
#
# Usage: bash merge-teams.sh [t1 t2 t3 t4]
# Default: merges all 4 slots.
set -e

PROJECT="/mnt/e/FILES 2026/MVP_VIBECODE+AGENTIC/finally"
cd "$PROJECT"

if [ $# -eq 0 ]; then
  SLOTS=(t1 t2 t3 t4)
else
  SLOTS=("$@")
fi
BASE=$(git branch --show-current)

echo "Target branch : $BASE"
echo "Merging slots : ${SLOTS[*]}"
echo ""

for slot in "${SLOTS[@]}"; do
  BRANCH="team/$slot"

  if ! git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    echo "  ⚠️  Branch $BRANCH does not exist — skipping"
    continue
  fi

  echo "  Merging $BRANCH → $BASE"
  git merge --no-ff "$BRANCH" -m "merge: $BRANCH into $BASE" || {
    echo "  ❌ Conflict in $BRANCH — resolve manually then re-run"
    exit 1
  }
  echo "  ✅ $BRANCH merged"
done

echo ""
echo "Done. Current branch: $BASE"
git log --oneline -5
