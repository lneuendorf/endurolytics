"""Sport-specific Training Stress Score (TSS) calculations.

Each discipline derives an intensity factor from the best available signal and
feeds it into the shared :func:`analytics.intensity.tss_from_intensity` formula:

* Bike  -> power vs. FTP
* Run   -> pace vs. threshold pace
* Swim  -> pace vs. critical swim speed (CSS)
* Any   -> heart rate vs. threshold HR (fallback)
* Any   -> duration-only estimate (last-resort fallback)

:func:`activity_tss` picks the most accurate method the inputs support.
"""

from __future__ import annotations

from dataclasses import dataclass

from .intensity import (
    intensity_factor_hr,
    intensity_factor_pace,
    intensity_factor_power,
    tss_from_intensity,
)

# Assumed intensity for the duration-only fallback (roughly an easy aerobic
# effort) so unconfigured data still produces a plausible, clearly-estimated load.
DEFAULT_ESTIMATED_INTENSITY = 0.70


@dataclass
class TssResult:
    tss: float
    intensity_factor: float | None
    method: str  # "power" | "pace" | "hr" | "duration"


def classify_discipline(sport: str | None) -> str | None:
    """Map a Garmin sport key to ``run`` / ``bike`` / ``swim`` (or ``None``)."""
    if not sport:
        return None
    key = sport.lower()
    if "swim" in key:
        return "swim"
    if "cycl" in key or "bike" in key or "biking" in key:
        return "bike"
    if "run" in key:
        return "run"
    return None


def pace_seconds_per_km(distance_meters: float | None, duration_seconds: float | None) -> float | None:
    """Average pace in seconds per kilometer, derived from distance and time."""
    if not distance_meters or not duration_seconds or distance_meters <= 0:
        return None
    return duration_seconds / (distance_meters / 1000.0)


def pace_seconds_per_100m(distance_meters: float | None, duration_seconds: float | None) -> float | None:
    """Average pace in seconds per 100 meters, derived from distance and time."""
    if not distance_meters or not duration_seconds or distance_meters <= 0:
        return None
    return duration_seconds / (distance_meters / 100.0)


def bike_tss(
    duration_seconds: float | None,
    ftp_watts: float | None,
    normalized_power: float | None = None,
    avg_power: float | None = None,
) -> float | None:
    """Power-based bike TSS (normalized power preferred, else average power)."""
    power = normalized_power or avg_power
    intensity = intensity_factor_power(power, ftp_watts)
    if intensity is None or not duration_seconds:
        return None
    return tss_from_intensity(duration_seconds, intensity)


def run_tss(
    duration_seconds: float | None,
    activity_pace_seconds_per_km: float | None,
    threshold_pace_seconds_per_km: float | None,
) -> float | None:
    """Pace-based run TSS using threshold pace."""
    intensity = intensity_factor_pace(threshold_pace_seconds_per_km, activity_pace_seconds_per_km)
    if intensity is None or not duration_seconds:
        return None
    return tss_from_intensity(duration_seconds, intensity)


def swim_tss(
    duration_seconds: float | None,
    activity_pace_seconds_per_100m: float | None,
    css_pace_seconds_per_100m: float | None,
) -> float | None:
    """CSS-based swim TSS."""
    intensity = intensity_factor_pace(css_pace_seconds_per_100m, activity_pace_seconds_per_100m)
    if intensity is None or not duration_seconds:
        return None
    return tss_from_intensity(duration_seconds, intensity)


def hr_tss(
    duration_seconds: float | None,
    avg_hr: float | None,
    threshold_hr: float | None,
    resting_hr: float | None = None,
) -> float | None:
    """Heart-rate-based TSS fallback."""
    intensity = intensity_factor_hr(avg_hr, threshold_hr, resting_hr)
    if intensity is None or not duration_seconds:
        return None
    return tss_from_intensity(duration_seconds, intensity)


def estimated_tss(duration_seconds: float | None) -> float | None:
    """Duration-only TSS estimate using an assumed easy-aerobic intensity."""
    if not duration_seconds or duration_seconds <= 0:
        return None
    return tss_from_intensity(duration_seconds, DEFAULT_ESTIMATED_INTENSITY)


def activity_tss(
    *,
    sport: str | None,
    duration_seconds: float | None,
    distance_meters: float | None = None,
    normalized_power: float | None = None,
    avg_power: float | None = None,
    avg_hr: float | None = None,
    ftp_watts: float | None = None,
    run_threshold_pace_seconds_per_km: float | None = None,
    swim_css_pace_seconds_per_100m: float | None = None,
    threshold_hr: float | None = None,
    resting_hr: float | None = None,
) -> TssResult | None:
    """Compute the best-available TSS for a single activity.

    Preference order per discipline: power/pace -> heart rate -> duration.
    Returns ``None`` only when there is no usable duration at all.
    """
    discipline = classify_discipline(sport)

    intensity: float | None = None
    method: str | None = None

    if discipline == "bike":
        power = normalized_power or avg_power
        intensity = intensity_factor_power(power, ftp_watts)
        if intensity is not None:
            method = "power"
    elif discipline == "run":
        activity_pace = pace_seconds_per_km(distance_meters, duration_seconds)
        intensity = intensity_factor_pace(run_threshold_pace_seconds_per_km, activity_pace)
        if intensity is not None:
            method = "pace"
    elif discipline == "swim":
        activity_pace = pace_seconds_per_100m(distance_meters, duration_seconds)
        intensity = intensity_factor_pace(swim_css_pace_seconds_per_100m, activity_pace)
        if intensity is not None:
            method = "pace"

    # Heart-rate fallback for any discipline when the primary signal is missing.
    if intensity is None:
        hr_intensity = intensity_factor_hr(avg_hr, threshold_hr, resting_hr)
        if hr_intensity is not None:
            intensity = hr_intensity
            method = "hr"

    if intensity is not None and method is not None and duration_seconds:
        return TssResult(
            tss=tss_from_intensity(duration_seconds, intensity),
            intensity_factor=intensity,
            method=method,
        )

    # Last resort: duration-only estimate.
    estimate = estimated_tss(duration_seconds)
    if estimate is None:
        return None
    return TssResult(tss=estimate, intensity_factor=DEFAULT_ESTIMATED_INTENSITY, method="duration")
