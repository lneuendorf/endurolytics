"""Training Stress Balance (TSB) — "form" = fitness minus fatigue.

TSB is CTL minus ATL. A positive TSB indicates freshness; a negative TSB
indicates accumulated fatigue.
"""

from __future__ import annotations

from typing import Sequence


def compute_tsb(ctl: Sequence[float], atl: Sequence[float]) -> list[float]:
    """Per-day TSB as element-wise ``CTL - ATL``.

    ``ctl`` and ``atl`` must be aligned, equal-length daily series.
    """
    if len(ctl) != len(atl):
        raise ValueError("ctl and atl series must be the same length")
    return [c - a for c, a in zip(ctl, atl)]
