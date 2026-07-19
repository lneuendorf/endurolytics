"""Chronic Training Load (CTL) — long-term "fitness".

CTL is an exponentially weighted moving average of daily TSS with a 42-day time
constant. The same EWMA engine is reused by :mod:`analytics.atl`.
"""

from __future__ import annotations

import math
from typing import Sequence

CTL_TIME_CONSTANT_DAYS = 42


def exponentially_weighted_load(
    daily_tss: Sequence[float],
    time_constant_days: int,
    initial: float = 0.0,
) -> list[float]:
    """Return the per-day EWMA of a contiguous daily TSS series.

    Uses the impulse-response form::

        today = yesterday * exp(-1/tc) + tss_today * (1 - exp(-1/tc))

    ``daily_tss`` must be a gap-free daily series (missing days = 0.0).
    """
    if time_constant_days <= 0:
        raise ValueError("time_constant_days must be positive")

    decay = math.exp(-1.0 / time_constant_days)
    weight = 1.0 - decay

    series: list[float] = []
    previous = initial
    for tss in daily_tss:
        current = previous * decay + (tss or 0.0) * weight
        series.append(current)
        previous = current
    return series


def compute_ctl(daily_tss: Sequence[float], initial: float = 0.0) -> list[float]:
    """Per-day CTL (42-day time constant)."""
    return exponentially_weighted_load(daily_tss, CTL_TIME_CONSTANT_DAYS, initial)
