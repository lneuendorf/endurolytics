"""Acute Training Load (ATL) — short-term "fatigue".

ATL is an exponentially weighted moving average of daily TSS with a 7-day time
constant, sharing the EWMA engine defined in :mod:`analytics.ctl`.
"""

from __future__ import annotations

from typing import Sequence

from .ctl import exponentially_weighted_load

ATL_TIME_CONSTANT_DAYS = 7


def compute_atl(daily_tss: Sequence[float], initial: float = 0.0) -> list[float]:
    """Per-day ATL (7-day time constant)."""
    return exponentially_weighted_load(daily_tss, ATL_TIME_CONSTANT_DAYS, initial)
