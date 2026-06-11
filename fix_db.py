import sqlite3
db = sqlite3.connect("db/finally.db")
c = db.execute(
    "DELETE FROM analysis_results WHERE analyzed_at > '2026-06-03' AND signal = 'AVOID' AND rank IS NULL AND score IS NULL"
)
print("Deleted:", c.rowcount, "rows")

# Verify remaining runs
runs = db.execute(
    "SELECT run_id, analyzed_at, COUNT(*) as n FROM analysis_results GROUP BY run_id ORDER BY analyzed_at DESC"
).fetchall()
for r in runs:
    print(f"run {r[0][:8]}  at={r[1]}  n={r[2]}")

db.commit()
db.close()
