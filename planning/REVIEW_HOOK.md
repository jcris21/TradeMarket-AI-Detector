diff --git a/.claude/settings.json b/.claude/settings.json
index aa06f43..c59a4ab 100644
--- a/.claude/settings.json
+++ b/.claude/settings.json
@@ -1,7 +1,14 @@
 {
-  "enabledPlugins": {
-    "frontend-design@claude-plugins-official": true,
-    "context7@claude-plugins-official": true,
-    "playwright@claude-plugins-official": true
+  "hooks": {
+    "Stop": [
+      {
+        "hooks": [
+          {
+            "type": "command",
+            "command": "cd /c/Users/ASUS/Documents/ProyectosNoCode/Vibe_EngineerExpert_Project/finally && git diff HEAD > planning/REVIEW_HOOK.md 2>&1"
+          }
+        ]
+      }
+    ]
   }
-}
+}
\ No newline at end of file
diff --git a/README.md b/README.md
index 3f2582a..397dad9 100644
--- a/README.md
+++ b/README.md
@@ -60,3 +60,6 @@ finally/
 ## License
 
 See [LICENSE](LICENSE).
+
+---
+*Last updated: 2026-04-07*
diff --git a/planning/PLAN.md b/planning/PLAN.md
index bc1811b..66822d8 100644
--- a/planning/PLAN.md
+++ b/planning/PLAN.md
@@ -454,3 +454,70 @@ The container is designed to deploy to AWS App Runner, Render, or any container
 - Portfolio visualization: heatmap renders with correct colors, P&L chart has data points
 - AI chat (mocked): send a message, receive a response, trade execution appears inline
 - SSE resilience: disconnect and verify reconnection
+
+---
+
+## 13. Review Notes
+
+_Added 2026-04-07. Questions, clarifications, and simplification opportunities for the team._
+
+### Questions & Clarifications
+
+**§2 — Daily change %**
+The watchlist shows "daily change %" but the simulator has no concept of a previous close. Is this "change since page load", "change since simulator start", or a synthetic value? The implementation should pick one and document it here to avoid inconsistency between the watchlist panel and the main chart area.
+
+**§6 — SSE stream and dynamic watchlist**
+The SSE endpoint pushes updates for "all tickers known to the system." When the user adds a new ticker mid-session, does the stream automatically include it, or must the client reconnect? If reconnect is required, the frontend needs to handle that explicitly — this should be clarified for the Frontend Engineer.
+
+**§6 & §7 — Positions in removed watchlist tickers**
+If a user buys AAPL, then removes AAPL from the watchlist, should AAPL still appear in the positions table and receive price updates? The plan implies the SSE stream is scoped to the watchlist, which would break P&L calculations for off-watchlist holdings. Needs a decision.
+
+**§7 — `portfolio_snapshots` retention**
+Snapshots are written every 30 seconds indefinitely. At that rate, ~2,880 rows/day accumulate with no mention of pruning. Define a retention window (e.g., keep 7 days) or the table will grow unboundedly and slow down the P&L chart query over time.
+
+**§7 — Lazy init: startup vs. first request**
+"The backend checks for the SQLite database on startup (or first request)" — pick one. Startup init is safer (avoids a race if two requests arrive simultaneously on a cold container) and is the cleaner behavior to document.
+
+**§9 — "cerebras-inference skill"**
+The LLM section references this skill but it is not in the planning directory. Agents need to find it before they can implement the chat endpoint. Add either a path reference or inline the key configuration (model ID, base URL pattern, auth header) so the Backend Engineer is unblocked.
+
+**§9 — Model identifier**
+`openrouter/openai/gpt-oss-120b` — verify this model ID is current on OpenRouter. If the ID changes, the chat endpoint will silently fail at runtime. Consider making the model name an env var (`LLM_MODEL`) with this as the default, so it can be swapped without a code change.
+
+**§9 — `watchlist_changes` "remove" action**
+The structured output schema shows `{"ticker": "PYPL", "action": "add"}` but does not illustrate the remove action. Confirm `action: "remove"` is the expected value and add it to the example to prevent agent ambiguity.
+
+**§9 — Conversation history window**
+"Loads recent conversation history" — how many messages? Without a defined limit, a long chat session will balloon the prompt and may exceed the model's context window. Specify a cap (e.g., last 20 messages or last N tokens).
+
+---
+
+### Feedback
+
+**§3 vs §7 — Contradiction on multi-user**
+The architecture rationale says "No auth = no multi-user = no need for a database server" to justify SQLite. But every table has a `user_id` column to "enable future multi-user support." These two statements pull in opposite directions. The current single-user scope is the right call — just remove the multi-user forward-compatibility framing to reduce confusion. If multi-user ever happens, SQLite would need to be replaced anyway due to concurrent write limitations.
+
+**§9 — LLM failure handling**
+No behavior is specified for when OpenRouter is down, returns a 429, or the response fails structured output validation. The Backend Engineer needs a fallback: return a plain error message in the `message` field, do not execute any trades, and surface the HTTP status to the frontend. Add this to §9.
+
+**§12 — Mock LLM response not specified**
+The E2E tests depend on `LLM_MOCK=true` returning "deterministic mock responses" but the exact mock payload is not defined here. The E2E test author and the Backend Engineer need to agree on what the mock returns (e.g., a fixed `message`, zero trades, zero watchlist changes) so tests can assert against it reliably.
+
+---
+
+### Simplification Opportunities
+
+**Merge §3 rationale into §3 diagram**
+The "Why These Choices" table in §3 is valuable but the `backend/db/` vs `db/` path distinction is explained twice — once in §4's directory tree and again in the Key Boundaries prose. One clear explanation is enough; remove the duplicate.
+
+**§11 — Drop `docker-compose.yml` or commit to it**
+The plan lists `docker-compose.yml` as an "optional convenience wrapper" but also documents raw `docker run` in the start scripts. Maintaining both adds surface area for divergence (different volume names, env var handling). Pick one as the canonical run method; keep the other only if it provides concrete value (e.g., compose for the test environment only).
+
+**§11 — Move "Optional Cloud Deployment" out of scope**
+The Terraform/App Runner section is marked a stretch goal but occupies a full subsection in the deployment chapter. Move it to a one-line note at the bottom or a separate `STRETCH_GOALS.md` file, so agents don't spend time on it before the core is done.
+
+**§4 Key Boundaries — trim prose**
+The Key Boundaries section largely restates what the directory tree already communicates. The only value-add lines are the lazy init note and the agent autonomy grants. Consider cutting it to just those two points.
+
+**`users_profile` table name**
+Minor: the table is named `users_profile` (plural noun + singular noun). Rename to `user_profile` or simply `users` for consistency with standard SQL naming and to avoid confusion with the future multi-user framing.
