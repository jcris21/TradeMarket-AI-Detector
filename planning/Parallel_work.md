# Plan: smux + dmux — Parallel Claude Code Teams with Git Worktrees

## Two Tools, Two Distinct Roles

| Tool | Role | What it does |
|------|------|-------------|
| **dmux** | Pane orchestrator | `npm install -g dmux` — press `n` to spawn agent pane, `m` to merge results back. ECC helper (`orchestrate-worktrees.js`) provisions worktrees + panes from a `plan.json`. Supports Claude Code, Codex, OpenCode, Gemini. |
| **smux** | Cross-pane bridge | tmux-bridge CLI — `read-before-act` protocol. Lets one agent read another pane's output and type into it. Communication layer between running panes. |

**How they complement each other:**
- **dmux** manages the lifecycle: create worktrees, spawn panes, merge output back
- **smux** handles real-time cross-team routing: read pane A → send output to pane B

## Context

Replace fixed agent-role panes (planner, architect, tdd-guide, code-reviewer) with
generic **Team1–Team4** slots. Each team is a blank worktree + tmux pane. The role,
skill, or agent type is assigned **at launch time**, not hardcoded. This enables:

- Agile reassignment: Team1 can run `/apply` today, `/tdd` tomorrow
- Safe parallelization: every team works on its own isolated git branch
- Reliable isolation: yolo mode per team, no cross-contamination
- Flexible composition: a team can be a single Claude instance, a sub-agent, or
  an entire agent team (e.g., `devfleet`, `orchestrate`)

**Result:** Developer edits `scripts/dmux-plan.json`, runs `node scripts/orchestrate-worktrees.js scripts/dmux-plan.json --execute`, and all Team panes launch in parallel worktrees — smux tmux-bridge available for cross-team handoffs.

---

## Architecture

```
Windows 11 Host (browser)
       │ localhost:8822
       ▼
┌──────────────────────────────────────────────────────────────┐
│  WSL2 Ubuntu                                                 │
│                                                              │
│  dmux session: finally-teams                                 │
│  ┌──────────────────┬──────────────────┐                     │
│  │ pane[team1]      │ pane[team2]      │                     │
│  │ worktree: t1     │ worktree: t2     │                     │
│  │ skill: on-demand │ skill: on-demand │                     │
│  │ yolo mode        │ yolo mode        │                     │
│  ├──────────────────┼──────────────────┤                     │
│  │ pane[team3]      │ pane[team4]      │                     │
│  │ worktree: t3     │ worktree: t4     │                     │
│  │ skill: on-demand │ skill: on-demand │                     │
│  │ yolo mode        │ yolo mode        │                     │
│  └──────────────────┴──────────────────┘                     │
│                                                              │
│  dmux keys: n → new pane  |  m → merge pane output          │
│  smux tmux-bridge: cross-team read/type communication        │
└──────────────────────────────────────────────────────────────┘
         │ /mnt/e/FILES 2026/MVP_VIBECODE+AGENTIC/finally
         ▼
   Main repo  (provisioned by orchestrate-worktrees.js)
   ├── .worktrees/t1/   ← branch: team/t1
   ├── .worktrees/t2/   ← branch: team/t2
   ├── .worktrees/t3/   ← branch: team/t3
   └── .worktrees/t4/   ← branch: team/t4
   └── .orchestration/finally-teams/
       ├── team1/task.md  handoff.md  status.md
       ├── team2/task.md  handoff.md  status.md
       ├── team3/task.md  handoff.md  status.md
       └── team4/task.md  handoff.md  status.md
```

---

## Prerequisite: WSL2 + tooling

```powershell
# PowerShell as Admin (Windows)
wsl --install -d Ubuntu && wsl --set-default-version 2
```

```bash
# Inside WSL2
sudo apt update && sudo apt install -y tmux git curl nodejs npm

# dmux  (pane orchestrator + ECC helper)
npm install -g dmux

# smux  (cross-pane bridge)
curl -fsSL https://shawnpana.com/smux/install.sh | bash && source ~/.bashrc

# Claude Code
npm install -g @anthropic-ai/claude-code
```

---

## Step-by-Step Implementation

### Step 1 — Ensure .worktrees/ is gitignored

Verify `.gitignore` contains:
```
.worktrees/
```

### Step 2 — dmux-plan.json (declarative team config)

Create `scripts/dmux-plan.json` — the single config file that defines all teams.
Edit this file to change assignments before each session:

```json
{
  "sessionName": "finally-teams",
  "baseRef": "HEAD",
  "launcherCommand": "cd {worktree_path} && claude --dangerously-skip-permissions",
  "workers": [
    {
      "name": "team1",
      "task": "Blank — assign skill at launch. Example: /apply"
    },
    {
      "name": "team2",
      "task": "Blank — assign skill at launch. Example: /tdd"
    },
    {
      "name": "team3",
      "task": "Blank — assign skill at launch. Example: /code-review"
    },
    {
      "name": "team4",
      "task": "Blank — assign skill at launch. Example: /orchestrate"
    }
  ]
}
```

To assign a skill to a specific team before launching, set its `"task"` field:
```json
{ "name": "team1", "task": "/apply — implement openspec change US-104" }
```

### Step 3 — start-teams.sh (single entry point via dmux ECC helper)

Create `scripts/start-teams.sh`:

```bash
#!/bin/bash
# Boots the full environment using dmux ECC orchestrator.
# Edit scripts/dmux-plan.json to assign skills/tasks before running.
set -e

PROJECT="/mnt/e/FILES 2026/MVP_VIBECODE+AGENTIC/finally"
cd "$PROJECT"

echo "🚀 Launching parallel teams via dmux..."
node scripts/orchestrate-worktrees.js scripts/dmux-plan.json --execute

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅  Environment ready"
echo "  Attach    : tmux attach -t finally-teams"
echo "  dmux keys : n = new pane  |  m = merge pane"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
git worktree list
```

### Step 4 — launch-team.sh (on-demand skill assignment to a running pane)

For assigning a skill to an already-running pane without restarting.
Create `scripts/launch-team.sh`:

```bash
#!/bin/bash
# Send a skill or prompt to a team pane that is already running Claude.
#
# Usage:
#   bash launch-team.sh <team-name> <skill-or-prompt>
#
# Examples:
#   bash launch-team.sh team1 "/apply"
#   bash launch-team.sh team2 "/tdd"
#   bash launch-team.sh team3 "/code-review"
#   bash launch-team.sh team4 "/orchestrate"

TEAM="${1:?Usage: launch-team.sh <team-name> <skill>}"
SKILL="${2:?Skill or prompt required}"

PANE_IDX=$(tmux-bridge resolve "$TEAM" 2>/dev/null || echo "")
if [ -z "$PANE_IDX" ]; then
  echo "❌ Pane '$TEAM' not found. Is the dmux session running?"
  exit 1
fi

tmux send-keys -t "finally-teams:0.$PANE_IDX" "$SKILL" Enter
echo "✅ $TEAM ← $SKILL"
```

### Step 6 — handoff.sh (cross-team via smux bridge)

Create `scripts/handoff.sh`:

```bash
#!/bin/bash
# Pass output from one team pane to another.
# Usage: bash handoff.sh <from-team> <to-team> [lines] [instruction]
FROM="${1:?from-team required}"
TO="${2:?to-team required}"
LINES="${3:-80}"
INSTRUCTION="${4:-Implement based on the above output}"

echo "📤 Reading $LINES lines from: $FROM"
OUTPUT=$(tmux-bridge read "$FROM" "$LINES")

echo "📥 Sending to: $TO"
tmux-bridge type "$TO" "=== Handoff from $FROM ==="
tmux-bridge keys "$TO" "Enter"
tmux-bridge type "$TO" "$OUTPUT"
tmux-bridge keys "$TO" "Enter"
tmux-bridge type "$TO" "$INSTRUCTION"
tmux-bridge keys "$TO" "Enter"

echo "✅ Handoff: $FROM → $TO"
```

Example flows:
```bash
# Team1 plans, Team2 implements, Team3 reviews
bash scripts/handoff.sh team1 team2 100 "Implement this plan"
bash scripts/handoff.sh team2 team3 80  "Review and fix issues"
bash scripts/handoff.sh team3 team1 40  "Summarize what was merged"
```

### Step 7 — merge-teams.sh (merge completed work back to main)

Create `scripts/merge-teams.sh`:

```bash
#!/bin/bash
# Usage: bash merge-teams.sh [t1 t2 t3 t4]
# Merges specified team branches. Default: all 4.
set -e

PROJECT="/mnt/e/FILES 2026/MVP_VIBECODE+AGENTIC/finally"
cd "$PROJECT"

SLOTS=("${@:-t1 t2 t3 t4}")
BASE=$(git branch --show-current)

for slot in "${SLOTS[@]}"; do
  BRANCH="team/$slot"
  echo "Merging $BRANCH → $BASE"
  git merge --no-ff "$BRANCH" -m "merge: $BRANCH into $BASE" || {
    echo "⚠️  Conflict in $BRANCH — resolve manually then re-run"
    exit 1
  }
  echo "✅ $BRANCH merged"
done
```

---

## Typical Workflow

```
# 1. Boot environment (once per session)
bash scripts/start-teams.sh

# 2. Assign teams on-demand as needed
bash scripts/launch-team.sh team1 .worktrees/t1 "/apply"       # apply openspec
bash scripts/launch-team.sh team2 .worktrees/t2 "/tdd"         # TDD implementation
bash scripts/launch-team.sh team3 .worktrees/t3 "/code-review" # review team2's output
bash scripts/launch-team.sh team4 .worktrees/t4                # free agent, no skill

# 3. Attach to session and watch all 4 teams in terminal
tmux attach -t finally-teams

# 4. Pass work between teams via smux
bash scripts/handoff.sh team1 team2 100 "Implement this plan"
bash scripts/handoff.sh team2 team3 80  "Review for correctness"

# 5. Merge completed branches
bash scripts/merge-teams.sh t1 t2          # merge only t1 and t2
bash scripts/merge-teams.sh                # merge all 4
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `scripts/dmux-plan.json` | Declarative team config — edit before each session |
| `scripts/start-teams.sh` | Full boot via dmux ECC helper |
| `scripts/launch-team.sh` | On-demand: send skill/prompt to a running pane via smux |
| `scripts/handoff.sh` | smux bridge: route output between team panes |
| `scripts/merge-teams.sh` | Merge team branches back to main |

`scripts/provision-worktrees.sh` and `scripts/smux-agents.sh` are superseded by
`orchestrate-worktrees.js` (bundled with dmux) — they can be kept as manual fallbacks.

No backend or frontend app files are modified.

---

## Verification

1. `bash scripts/start-teams.sh` → 4 worktrees created, 4 Claude panes active
2. `git worktree list` → shows `.worktrees/t1` through `.worktrees/t4`
3. `tmux attach -t finally-teams` → 4 panes visible, Claude running in each
4. `bash scripts/launch-team.sh team1 "/apply"` → team1 receives `/apply` skill
5. `bash scripts/handoff.sh team1 team2` → team2 receives team1's output via smux
6. Press `m` in dmux → merges current pane's output back to main session
7. `bash scripts/merge-teams.sh t1` → team/t1 branch merges cleanly into main

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| WSL2 not installed | Docker Desktop with Ubuntu container as fallback |
| Merge conflicts between teams | Teams work on isolated branches; merge one at a time |
| yolo mode runs unreviewed code | Isolated branch — no impact on main until explicit merge |
| Claude CLI not in WSL2 PATH | `npm install -g @anthropic-ai/claude-code` in WSL2 |
| dmux `orchestrate-worktrees.js` not found | Copy from dmux package: `$(npm root -g)/dmux/scripts/` |
| tmux-bridge pane IDs lost on restart | `smux-agents.sh` is idempotent — safe to re-run as fallback |
| launch-team.sh: wrong pane index | Uses `tmux-bridge resolve` to find pane by name, not hardcoded index |
