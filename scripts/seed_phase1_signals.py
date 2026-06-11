"""Seed 31 conclusive analysis signals to push the DB from Phase 0 → Phase 1 (Pilot).

Run from the project root:
    python scripts/seed_phase1_signals.py

Phase thresholds:
    Phase 0 (Calibration): conclusive < 30
    Phase 1 (Pilot):        30 <= conclusive < 100
    Phase 2 (Evaluation):   100 <= conclusive < 300
    Phase 3 (Confident):    conclusive >= 300

Conclusive = TARGET_HIT + STOP_HIT rows in analysis_results.
The DB currently has 2 conclusive signals; this script adds 31 more → total 33.
"""

import sqlite3
import uuid
from datetime import datetime, timedelta

DB_PATH = "db/finally.db"
USER_ID = "default"
RUN_ID = "seed-phase1-run"

# 31 signals: 20 TARGET_HIT (~65% hit rate) + 11 STOP_HIT (~35%)
# avg_gain ~8%, avg_loss ~2.5% → realized RR ~3.2 (green)
SIGNALS = [
    # (ticker, outcome, actual_gain_pct, actual_loss_pct)
    ("AAPL",  "TARGET_HIT", 7.8,  None),
    ("MSFT",  "TARGET_HIT", 9.2,  None),
    ("NVDA",  "TARGET_HIT", 12.1, None),
    ("GOOGL", "STOP_HIT",   None, 2.3),
    ("TSLA",  "TARGET_HIT", 8.5,  None),
    ("META",  "TARGET_HIT", 7.1,  None),
    ("AMZN",  "STOP_HIT",   None, 2.8),
    ("JPM",   "TARGET_HIT", 6.4,  None),
    ("V",     "TARGET_HIT", 5.9,  None),
    ("NFLX",  "STOP_HIT",   None, 2.1),
    ("AAPL",  "TARGET_HIT", 8.3,  None),
    ("MSFT",  "STOP_HIT",   None, 2.6),
    ("NVDA",  "TARGET_HIT", 11.7, None),
    ("GOOGL", "TARGET_HIT", 7.4,  None),
    ("TSLA",  "STOP_HIT",   None, 3.1),
    ("META",  "TARGET_HIT", 6.8,  None),
    ("AMZN",  "TARGET_HIT", 9.5,  None),
    ("JPM",   "STOP_HIT",   None, 2.4),
    ("V",     "TARGET_HIT", 7.2,  None),
    ("NFLX",  "TARGET_HIT", 10.1, None),
    ("AAPL",  "STOP_HIT",   None, 2.0),
    ("MSFT",  "TARGET_HIT", 8.8,  None),
    ("NVDA",  "STOP_HIT",   None, 2.9),
    ("GOOGL", "TARGET_HIT", 6.6,  None),
    ("TSLA",  "TARGET_HIT", 13.2, None),
    ("META",  "STOP_HIT",   None, 2.2),
    ("AMZN",  "TARGET_HIT", 8.0,  None),
    ("JPM",   "TARGET_HIT", 5.5,  None),
    ("V",     "STOP_HIT",   None, 2.7),
    ("NFLX",  "TARGET_HIT", 9.8,  None),
    ("AAPL",  "TARGET_HIT", 7.6,  None),
]

assert len(SIGNALS) == 31, f"Expected 31 signals, got {len(SIGNALS)}"

def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    base_time = datetime.utcnow() - timedelta(days=30)

    inserted = 0
    with conn:
        for i, (ticker, outcome, gain, loss) in enumerate(SIGNALS):
            analyzed_at = (base_time + timedelta(days=i)).isoformat()
            conn.execute(
                """
                INSERT INTO analysis_results (
                    id, user_id, run_id, ticker,
                    rank, score, signal, confidence,
                    risk_reward_ratio, entry_price, target_price, stop_loss,
                    support_validated, argument,
                    analyzed_at,
                    outcome, actual_gain_pct, actual_loss_pct, hold_days
                ) VALUES (
                    ?, ?, ?, ?,
                    NULL, 72.0, 'BUY', 0.75,
                    3.5, 100.0, 108.0, 97.0,
                    1, 'Seeded for Phase 1 simulation',
                    ?,
                    ?, ?, ?, 10.0
                )
                """,
                (
                    str(uuid.uuid4()), USER_ID, RUN_ID, ticker,
                    analyzed_at,
                    outcome, gain, loss,
                ),
            )
            inserted += 1

    conn.close()

    # Verify
    conn2 = sqlite3.connect(DB_PATH)
    conn2.row_factory = sqlite3.Row
    cur = conn2.execute(
        "SELECT outcome, COUNT(*) as n FROM analysis_results "
        "WHERE user_id = ? AND outcome IN ('TARGET_HIT','STOP_HIT') "
        "GROUP BY outcome",
        (USER_ID,),
    )
    rows = cur.fetchall()
    conn2.close()

    total = 0
    for row in rows:
        print(f"  {row['outcome']}: {row['n']}")
        total += row['n']
    print(f"\nTotal conclusive signals: {total}")
    print(f"Phase: {'1 (Pilot) ✓' if 30 <= total < 100 else str(total)}")
    print(f"\nInserted {inserted} rows into {DB_PATH}")


if __name__ == "__main__":
    main()
