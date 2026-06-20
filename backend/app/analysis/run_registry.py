"""In-memory registry for tracking live analysis-run state (US-204).

Run state is ephemeral — lost on restart. There is no DB persistence by design.
Completed/failed runs are evicted 10 minutes after `completed_at`.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

RunStage = Literal["data", "scoring", "complete", "failed"]

_TERMINAL_STAGES = {"complete", "failed"}
_EVICT_AFTER_SECONDS = 10 * 60


@dataclass
class RunState:
    """Live state for a single analysis run.

    `scored` holds in-progress scored assets (as plain dicts) so the
    `?partial=true` endpoint can read top-N results before the run persists.
    """

    run_id: str
    stage: RunStage
    tickers_total: int
    tickers_completed: int = 0
    errors_so_far: list[dict] = field(default_factory=list)
    started_at: str = ""
    completed_at: str | None = None
    scored: list[dict] = field(default_factory=list)

    def estimated_remaining_seconds(self) -> float | None:
        """Linear extrapolation of remaining time.

        `(elapsed / completed) * (total - completed)`. Returns None when no
        ticker has completed yet (avoids division by zero).
        """
        if self.tickers_completed <= 0:
            return None
        if self.tickers_total <= self.tickers_completed:
            return 0.0
        try:
            started = datetime.fromisoformat(self.started_at)
        except (ValueError, TypeError):
            return None
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        remaining = self.tickers_total - self.tickers_completed
        return round((elapsed / self.tickers_completed) * remaining, 1)

    def to_status_dict(self) -> dict:
        """Serialize for the GET /status endpoint."""
        return {
            "run_id": self.run_id,
            "stage": self.stage,
            "tickers_total": self.tickers_total,
            "tickers_completed": self.tickers_completed,
            "errors_so_far": self.errors_so_far,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "estimated_remaining_seconds": self.estimated_remaining_seconds(),
        }


_registry: dict[str, RunState] = {}
_lock = asyncio.Lock()


def get_active_run() -> RunState | None:
    """Return the first run whose stage is not terminal, else None."""
    for state in _registry.values():
        if state.stage not in _TERMINAL_STAGES:
            return state
    return None


def get_run(run_id: str) -> RunState | None:
    """Return the run state for `run_id`, or None if not in the registry."""
    return _registry.get(run_id)


def register_run(state: RunState) -> None:
    """Add a run to the registry."""
    _registry[state.run_id] = state


def evict_expired_runs() -> None:
    """Remove terminal runs whose `completed_at` is older than 10 minutes."""
    now = datetime.now(timezone.utc)
    expired: list[str] = []
    for run_id, state in _registry.items():
        if not state.completed_at:
            continue
        try:
            completed = datetime.fromisoformat(state.completed_at)
        except (ValueError, TypeError):
            continue
        if (now - completed).total_seconds() > _EVICT_AFTER_SECONDS:
            expired.append(run_id)
    for run_id in expired:
        del _registry[run_id]


def clear_registry() -> None:
    """Test helper: wipe all run state."""
    _registry.clear()
