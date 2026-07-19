"""Intensity Factor (IF) and the core Training Stress Score (TSS) formula.

All TSS variants (bike power, run pace, swim CSS, HR) reduce to the same core
relationship once an intensity factor is known:

    TSS = duration_hours * IF^2 * 100

An IF of 1.0 sustained for one hour therefore equals 100 TSS by definition.
"""

from __future__ import annotations


def tss_from_intensity(duration_seconds: float, intensity_factor: float) -> float:
    """Return TSS for a session of ``duration_seconds`` at ``intensity_factor``."""
    if duration_seconds <= 0 or intensity_factor <= 0:
        return 0.0
    duration_hours = duration_seconds / 3600.0
    return duration_hours * (intensity_factor ** 2) * 100.0


def intensity_factor_power(power: float | None, ftp_watts: float | None) -> float | None:
    """IF from power: ``power / FTP`` (normalized power preferred)."""
    if not power or not ftp_watts:
        return None
    if power <= 0 or ftp_watts <= 0:
        return None
    return power / ftp_watts


def intensity_factor_pace(
    threshold_pace: float | None, activity_pace: float | None
) -> float | None:
    """IF from pace expressed as seconds per fixed distance.

    Faster efforts have a smaller ``activity_pace`` (fewer seconds per distance),
    so ``threshold_pace / activity_pace`` grows above 1.0 as intensity rises.
    Both paces must use the same unit (e.g. seconds per km, or per 100 m).
    """
    if not threshold_pace or not activity_pace:
        return None
    if threshold_pace <= 0 or activity_pace <= 0:
        return None
    return threshold_pace / activity_pace


def intensity_factor_hr(
    avg_hr: float | None,
    threshold_hr: float | None,
    resting_hr: float | None = None,
) -> float | None:
    """IF from heart rate.

    When ``resting_hr`` is provided a heart-rate-reserve ratio is used
    (``(avg - rest) / (threshold - rest)``); otherwise a simple ``avg / threshold``
    ratio is applied. HR-based IF is a fallback and less precise than
    power/pace-based intensity.
    """
    if not avg_hr or not threshold_hr:
        return None
    if avg_hr <= 0 or threshold_hr <= 0:
        return None
    if resting_hr:
        denom = threshold_hr - resting_hr
        if denom <= 0:
            return None
        return (avg_hr - resting_hr) / denom
    return avg_hr / threshold_hr
