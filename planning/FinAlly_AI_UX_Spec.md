# AI UX Interaction Specification — FinAlly
**Product**: FinAlly (Freedom Ally) — Swing Trading Workstation  
**Scope**: AI Copilot HITL touchpoints — Steps 6, 7, 8, 9 from L3-A classification  
**Segment**: Retail swing trader · daily monitoring · non-full-time · $10K–$200K capital  
**Date**: 2026-05-23

---

## 1. Interaction Map

HITL steps from L3-A:

| Step | AI Action | Intervention Type | User Decision | Consequence if Wrong | Risk |
|---|---|---|---|---|---|
| **6** | Trader types question to AI copilot about a specific signal | Collaborative draft — AI synthesizes signal data into analysis | Provide question → read response → judge credibility | Trader misreads AI confidence as certainty → overtrusts | MEDIUM |
| **7** | AI copilot responds with recommendation citing scoring rules + ATR + support | Inline annotation — AI labels uncertain elements within response | Accept analysis / ask follow-up / dismiss and decide independently | AI recommendation accepted without verifying grounding data | MEDIUM |
| **8** | Trader decides to enter the trade | Blocking confirmation — full parameter review before any action | YES enter / NO pass / MODIFY parameters | Wrong position size, wrong ticker, wrong stop level entered | HIGH |
| **9** | Simulated order pre-filled from signal (entry, stop, target) | AI override possible — AI pre-fills, human approves final numbers | Confirm pre-fill / manually adjust any field / cancel | Parameter drift from signal → realized R/R worse than expected | HIGH |

---

## 2. Trust Calibration Journey

### Trust Arc (new FinAlly user → experienced user)

| Level | User State | Signal Count | AI Behavior | UX Pattern |
|---|---|---|---|---|
| **0 — Skeptic** | First week. No trade history. High doubt about AI analysis. | < 30 signals | Show full reasoning chain on every copilot response. Cite every data point used. Show "Based on: ATR=1.2%, SMA20>SMA50, support_score=2/3" explicitly | Verbose mode — all sources visible, no collapsing |
| **1 — Learner** | 30–100 signals. Starting to see pattern in score accuracy. | 30–99 | Moderate explanations. Highlight uncertain elements. Show score delta as learning signal. | Progressive disclosure — key facts up front, detail on expand |
| **2 — Collaborator** | 100–300 signals. Trusts copilot for routine analysis. | 100–299 | Compact mode: lead with recommendation, sources collapsible. Exceptions and low-confidence flags still visible. | Summary-first with "Show reasoning" toggle |
| **3 — Delegator** | 300+ signals. Trusts system for defined scope. | 300+ | Async: brief push notification with recommendation + one-tap to review full analysis. Manual entry remains mandatory. | Notification card + confirmation flow |

**Implementation rule**: Phase gate from L3-A (0/1/2/3 signal count) drives trust level automatically. No user-selectable setting — trust level is earned, not declared.

**Never skip Level 0**: Even a trader with 10 years of TradingView experience starts as a skeptic for the FinAlly AI copilot specifically.

### Trust Anti-Patterns — Explicitly Prohibited in FinAlly

| Anti-pattern | Why prohibited | FinAlly rule |
|---|---|---|
| "Here is the best trade for today" (no uncertainty) | Overtrust trigger — removes trader agency | All recommendations framed as "Based on current data, this setup scores X. Key risk: Y." |
| Showing raw confidence % (e.g. "87% confident") | Meaningless to traders; creates false precision | Use natural language tiers: "Strong setup", "Borderline — verify", "Not recommended" |
| Confirmation dialogs on every single copilot response | Undertrust spiral → user ignores all dialogs | Blocking confirm only at Step 8 (entry decision). Copilot responses never require confirmation to read. |
| Silent copilot failure (no response, spinner forever) | Destroys trust in one interaction | Hard timeout at 8 seconds → "Analysis unavailable — decide based on score and indicators shown" |
| AI auto-filling stop/target with no editable fields | Removes override path | All pre-filled fields editable. Diff badge shows "AI suggested: $185.30 → Your value: $184.00" |

---

## 3. Confidence Communication System

### Natural Language Confidence Vocabulary

No raw percentages ever. Use these tiers consistently:

| Signal Strength | Copilot Phrasing | Visual Indicator | User Action Expected |
|---|---|---|---|
| **Strong** (all scoring components agree) | "This setup meets all structural criteria. ATR-validated stop, 3/3 support confirmation, trend aligned. Score: 82." | Green dot · solid border on analysis card | Optional review — can act directly |
| **Moderate** (2+ components agree, 1 borderline) | "This setup qualifies but has one borderline factor: [specific factor]. Worth entering if you're comfortable with [specific risk]." | Amber dot · dashed border | Review recommended — check cited factor |
| **Weak** (borderline overall or conflicting signals) | "This setup is close to the qualifying threshold. [Specific weakness]. I'd wait for a cleaner entry." | Red dot · greyed card | Explicit user decision required — copilot recommends passing |
| **Insufficient data** | "I don't have enough signal history on [ticker] to assess pattern reliability. Only [N] prior signals." | Grey dot · "Limited data" badge | Treat as new ticker — reduce position size |

### Output Annotation in Copilot Responses

Every AI-generated analysis must visibly tag its data sources inline:

```
"The AAPL setup scores 78/100. [STRONG] 
 
Stop viability: ✅ Stop at $185.30 = 1.6x ATR(14) — outside noise floor
Trend: ✅ SMA20 ($189.40) > SMA50 ($185.10) — with-trend entry  
Support: ✅ 2/3 confirmed (Pivot S1 + SMA20 acting as support; BB lower not tested)
MACD: ✅ Bullish crossover, histogram > 0
RSI: ✅ 58 — within entry zone (50–75 for uptrend)
Volume: ✅ 1.8x SMA20 — institutional conviction

Borderline factor: [AMBER] Support score 2/3 (not 3/3) — pivot S1 at $183.10,
 price is 1.2 ATR above it (slightly far). Acceptable but not ideal.

Recommendation: Entry valid at $191.20. Set stop at $185.30, target $204.50 (R/R 3.4).
 Final decision is yours."
```

**Tagging rules**:
- `[STRONG]` / `[AMBER]` / `[WEAK]` prefixes on each component — never buried in prose
- Every cited value pulled from live `TechnicalIndicators` dataclass — never generated by LLM
- Final paragraph always ends with "Final decision is yours" — non-negotiable

---

## 4. Human Override Patterns

### Step 6 — Asking the Copilot (intervention: collaborative draft)

**Override Tier 1 — Immediate**:
- Dismiss response without reading: single swipe/close
- Ask follow-up question: free text input always visible below response
- "Analyze differently" shortcut buttons: ["Focus on risk", "Show bearish case", "Compare to similar setups"]

**Override Tier 2 — Guided correction**:
- Thumbs down on response → "What was wrong?" prompt with 4 options:
  - "Data seems incorrect"
  - "Recommendation doesn't match my read of the chart"
  - "Too vague — need specifics"
  - "Other"
- Feedback stored in SQLite for Phase 2 profit factor memory

**Override Tier 3 — Control expansion**:
- "Don't analyze [ticker] with copilot" — persistent per-ticker exclusion
- "Always show full reasoning" — pin verbose mode regardless of trust level

### Step 7 — Reading AI Recommendation (intervention: inline annotation)

**Visible at all times** (never hidden):
- Every cited data value links to the raw indicator in the dashboard
- "I disagree — enter anyway" option always present (logs disagreement for learning)
- "Skip AI analysis" toggle at top of copilot panel — switches to raw score display only

**The disagreement log is important**: When a trader overrides a WEAK copilot recommendation and the trade succeeds, that's a learning signal. When they follow a STRONG recommendation and it fails, also learning signal. Both feed the profit_factor_memory (Phase 2).

### Step 8 — Trade Entry Decision (intervention: blocking confirmation)

This is the **only blocking confirmation** in the flow. It must be frictionful enough to be conscious but not so complex it slows execution.

**Confirmation dialog structure**:

```
┌─────────────────────────────────────────────────────┐
│  ⚠️  Confirm Trade Entry                            │
│                                                     │
│  AAPL  ▲ BUY    Score: 78/100    Fresh: 1.2h ago   │
│                                                     │
│  Entry:   $191.20   (next market open)              │
│  Stop:    $185.30   [-3.1%]  ATR ✔ viable          │
│  Target:  $204.50   [+6.9%]  Support 2/3           │
│  R/R:     3.4:1                                     │
│                                                     │
│  Per $10 risked:  +$2.20 if target  -$0.65 if stop │
│                                                     │
│  Copilot says:  [STRONG] All criteria met           │
│                                                     │
│  [  CANCEL  ]              [  ✅ ENTER TRADE  ]    │
└─────────────────────────────────────────────────────┘
```

**Rules for this dialog**:
- Full parameters always shown — no "continue from previous screen" shortcuts
- ATR viability badge present — if stop is inside noise, show `❌ ATR WARNING` in red
- "Enter Trade" button is green ONLY if all hard gates pass (ATR ✔, R/R ≥ 3.0)
- If any hard gate fails, "Enter Trade" label changes to "⚠️ Enter Anyway (suboptimal)" in orange
- No countdown timer — trader decides at their own pace
- No "Don't show this again" checkbox — confirmation is always required

### Step 9 — Order Pre-fill (intervention: AI override possible)

**Pre-fill source transparency**:

```
Entry:   $191.20  [AI: from signal]     [edit]
Stop:    $185.30  [AI: SMA20×0.97]     [edit]  
Target:  $204.50  [AI: Pivot R1]       [edit]
Size:    [manual — not pre-filled]
```

**Edit behavior**:
- Any edited field shows diff badge: "AI: $185.30 → Yours: $184.00"
- If edited stop < ATR floor: inline warning "⚠️ Stop inside ATR noise floor (ATR: $3.20, your stop dist: $1.20)"
- If edited target reduces R/R below 3.0: inline warning "⚠️ R/R now 2.1 — below minimum threshold"
- Warnings are informational only — trader can still proceed
- "Reset to AI values" link always visible if trader wants to revert

**Position size is never pre-filled**: Trader enters manually. FinAlly does not know account size or risk tolerance. The Bet-Size Card shows per-$10 metrics to let traders scale mentally.

---

## 5. Feedback Loop Architecture

### Implicit Feedback (zero user effort)

Tracked automatically in `analysis_results` SQLite table:

| Signal | What it means | How collected |
|---|---|---|
| Copilot response read time > 30s | High engagement — recommendation was considered | Timestamp on panel open/close |
| Copilot shown → trade NOT entered | Recommendation not compelling enough (or WEAK correctly avoided) | Entry event absence after copilot session |
| Copilot shown → trade entered within 5 min | Recommendation was persuasive | Entry event timestamp vs copilot timestamp |
| "I disagree — enter anyway" clicked | Trader overrode copilot | Explicit disagreement flag on trade record |
| Edited stop/target before confirmation | Pre-fill not trusted | Field-level edit event |

### Explicit Feedback (minimal user effort)

| Trigger | UI | Options |
|---|---|---|
| After any copilot response | 👍 / 👎 | One tap — no text required |
| After 3 consecutive 👎 | "What's not working?" | 4-option picker (see Step 6 overrides above) |
| After trade outcome recorded | "Was the copilot analysis helpful?" | Yes / No / Didn't use it |

### Feedback Integration (Phase 2)

```python
# profit_factor_memory: rolling per-ticker signal quality
profit_factor_30d = sum(gains_last_30) / sum(losses_last_30)

# Copilot calibration: agreement rate between copilot recommendation and outcome
copilot_accuracy = hits_where_copilot_strong / total_where_copilot_strong
copilot_disagreement_success = hits_where_trader_overrode_weak / total_where_trader_overrode_weak
```

If `copilot_disagreement_success > copilot_accuracy`: the trader's intuition is outperforming the copilot → surface this in the performance panel as "Your judgment vs AI: You're winning".

---

## 6. Cognitive Load Analysis

| Interaction | Simultaneous Decisions | Info to Process | Time Pressure | Cognitive Load | Status |
|---|---|---|---|---|---|
| Step 6: Formulating copilot question | 1 | Signal score + personal read | Low | **LOW** | ✅ Acceptable |
| Step 7: Reading AI recommendation | 1 (accept/reject/follow-up) | Response + cited indicators (5-7 data points) | Low | **MEDIUM** | ✅ Acceptable with annotation tagging |
| Step 8: Entry confirmation dialog | 3 (enter/cancel/modify) | Entry + stop + target + R/R + copilot verdict + freshness | MEDIUM (pre-market) | **HIGH** ⚠️ | Needs redesign |
| Step 9: Order pre-fill review | 2 (accept pre-fill / edit) | 3 pre-filled fields + 1 manual field | MEDIUM | **MEDIUM** | ✅ Acceptable |

**Step 8 cognitive load is HIGH** — redesign required:

Current problem: confirmation dialog shows 8 data points simultaneously under time pressure.

**Fix — Two-tier confirmation**:
```
Tier 1 (default, fast): 
  "AAPL ▲ BUY · Score 78 · R/R 3.4 · ATR ✔"  
  [PASS]  [ENTER]

Tier 2 (expand, optional):
  Full parameter grid + copilot verdict + per-$10 display
  Accessible via "Show details ▼" — not required to enter
```

Goal: reduce mandatory decision-making to 1 binary choice (enter / pass). Full detail available but not blocking.

---

## 7. Explainability Specification

| AI Action | Explanation Type | Detail Level | Access | Format |
|---|---|---|---|---|
| Copilot recommendation | Why + What data | Full | Always visible in response | Tagged inline annotation (see Section 3) |
| Score component breakdown | Why | Summary | On-demand (expand score badge) | Mini scorecard: 8 components, ✅/⚠️/❌ |
| ATR viability badge | Why + What data | Brief | Always visible on signal card | Tooltip: "Stop $185.30 = 1.6x ATR(14) = outside noise floor" |
| Support score 2/3 | What data | Brief | On hover | "S1 ✅ · SMA ✅ · BB lower ❌ (price too far)" |
| Pre-filled stop value | What data | Brief | Inline label | "[AI: SMA20 × 0.97]" |
| Pre-filled target value | What data | Brief | Inline label | "[AI: Pivot R1 — 20-period high]" |
| Signal freshness | Why | Brief | Always visible | "Generated 1.2h ago · Still in optimal window" |
| Score delta | What + Why | Brief | Always visible | "↑ +6 from last run — conviction building" |

**Audit trail** (available but not surfaced by default): Full copilot response history per ticker accessible in signal archive. Useful for reviewing "what did AI say before a loss".

---

## 8. Anti-Pattern Checklist

- [x] No overtrust triggers — all recommendations include uncertainty framing
- [x] No silent failures — hard timeout at 8s with graceful fallback message
- [x] No blocking confirmations on copilot responses (only on Step 8 entry)
- [x] No raw confidence percentages — natural language tiers only
- [x] All AI-generated content labeled with source tag `[AI: ...]`
- [x] Manual takeover always available — "Skip AI analysis" toggle persists
- [x] Override path visible without scrolling on all AI surfaces
- [x] Step 8 dialog shows ATR viability — entry blocked from green state if stop invalid
- [x] Position size never pre-filled — trader's risk tolerance is not known to system
- [x] Disagreement tracking built in — "I disagree — enter anyway" always present
- [x] Trust level earned from signal count, not user-declared
- [x] "Final decision is yours" — mandatory last line in every copilot response

---

## 9. Scope Note for L4

These interaction specs generate the following additional stories beyond what was defined in L4:

| New Story | Epic | Points | Priority |
|---|---|---|---|
| Copilot panel with verbose/compact trust modes | Epic 4 — AI Copilot | 5 | Sprint 3 |
| Two-tier entry confirmation dialog (Tier 1 fast / Tier 2 expand) | Epic 1 — Dashboard | 3 | Sprint 2 |
| Pre-fill diff badges + ATR warning on manual edit | Epic 1 — Dashboard | 2 | Sprint 2 |
| 👍/👎 copilot feedback + disagreement log | Epic 4 — AI Copilot | 3 | Sprint 3 |
| "Show reasoning" toggle + verbose/compact mode switch | Epic 4 — AI Copilot | 2 | Sprint 3 |
| Copilot accuracy vs trader-override panel | Epic 3 — Performance | 3 | Sprint 4 |
