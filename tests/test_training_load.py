import math
import unittest

from analytics.atl import ATL_TIME_CONSTANT_DAYS, compute_atl
from analytics.ctl import CTL_TIME_CONSTANT_DAYS, compute_ctl, exponentially_weighted_load
from analytics.intensity import (
    intensity_factor_hr,
    intensity_factor_pace,
    intensity_factor_power,
    tss_from_intensity,
)
from analytics.tsb import compute_tsb
from analytics.tss import (
    activity_tss,
    bike_tss,
    classify_discipline,
    estimated_tss,
    hr_tss,
    pace_seconds_per_100m,
    pace_seconds_per_km,
    run_tss,
    swim_tss,
)


class IntensityTests(unittest.TestCase):
    def test_one_hour_at_threshold_is_100_tss(self):
        self.assertAlmostEqual(tss_from_intensity(3600, 1.0), 100.0)

    def test_tss_scales_with_duration_and_intensity_squared(self):
        self.assertAlmostEqual(tss_from_intensity(1800, 1.0), 50.0)
        self.assertAlmostEqual(tss_from_intensity(3600, 0.5), 25.0)

    def test_non_positive_inputs_return_zero(self):
        self.assertEqual(tss_from_intensity(0, 1.0), 0.0)
        self.assertEqual(tss_from_intensity(3600, 0.0), 0.0)

    def test_intensity_factor_power(self):
        self.assertAlmostEqual(intensity_factor_power(250, 250), 1.0)
        self.assertAlmostEqual(intensity_factor_power(275, 250), 1.1)
        self.assertIsNone(intensity_factor_power(None, 250))
        self.assertIsNone(intensity_factor_power(250, 0))

    def test_intensity_factor_pace_faster_is_higher(self):
        # Threshold 300 s/km; running 270 s/km (faster) -> IF > 1.
        self.assertAlmostEqual(intensity_factor_pace(300, 270), 300 / 270)
        self.assertAlmostEqual(intensity_factor_pace(300, 300), 1.0)
        self.assertIsNone(intensity_factor_pace(None, 270))

    def test_intensity_factor_hr_with_and_without_reserve(self):
        self.assertAlmostEqual(intensity_factor_hr(160, 160), 1.0)
        # Heart-rate reserve: (150-50)/(160-50) = 100/110.
        self.assertAlmostEqual(intensity_factor_hr(150, 160, resting_hr=50), 100 / 110)
        self.assertIsNone(intensity_factor_hr(None, 160))


class SportTssTests(unittest.TestCase):
    def test_bike_tss_prefers_normalized_power(self):
        # 1 hour at NP == FTP -> 100 TSS.
        self.assertAlmostEqual(bike_tss(3600, 250, normalized_power=250), 100.0)
        # Falls back to avg power when NP missing.
        self.assertAlmostEqual(bike_tss(3600, 250, avg_power=250), 100.0)
        self.assertIsNone(bike_tss(3600, None, normalized_power=250))

    def test_run_tss(self):
        self.assertAlmostEqual(run_tss(3600, 300, 300), 100.0)
        self.assertIsNone(run_tss(3600, None, 300))

    def test_swim_tss(self):
        self.assertAlmostEqual(swim_tss(3600, 90, 90), 100.0)

    def test_hr_tss(self):
        self.assertAlmostEqual(hr_tss(3600, 160, 160), 100.0)

    def test_estimated_tss_uses_default_intensity(self):
        self.assertAlmostEqual(estimated_tss(3600), 49.0)
        self.assertIsNone(estimated_tss(0))

    def test_pace_helpers(self):
        self.assertAlmostEqual(pace_seconds_per_km(10000, 3000), 300.0)
        self.assertAlmostEqual(pace_seconds_per_100m(2000, 3000), 150.0)
        self.assertIsNone(pace_seconds_per_km(0, 3000))


class DisciplineTests(unittest.TestCase):
    def test_classify_discipline_handles_variants(self):
        self.assertEqual(classify_discipline("running"), "run")
        self.assertEqual(classify_discipline("trail_running"), "run")
        self.assertEqual(classify_discipline("treadmill_running"), "run")
        self.assertEqual(classify_discipline("cycling"), "bike")
        self.assertEqual(classify_discipline("indoor_cycling"), "bike")
        self.assertEqual(classify_discipline("mountain_biking"), "bike")
        self.assertEqual(classify_discipline("lap_swimming"), "swim")
        self.assertEqual(classify_discipline("open_water_swimming"), "swim")
        self.assertIsNone(classify_discipline("strength"))
        self.assertIsNone(classify_discipline(None))


class ActivityTssDispatchTests(unittest.TestCase):
    def test_bike_uses_power_method(self):
        result = activity_tss(
            sport="cycling", duration_seconds=3600, normalized_power=250, ftp_watts=250
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.method, "power")
        self.assertAlmostEqual(result.tss, 100.0)

    def test_run_uses_pace_method(self):
        result = activity_tss(
            sport="running",
            duration_seconds=3600,
            distance_meters=12000,  # 300 s/km
            run_threshold_pace_seconds_per_km=300,
        )
        self.assertEqual(result.method, "pace")
        self.assertAlmostEqual(result.tss, 100.0)

    def test_swim_uses_pace_method(self):
        result = activity_tss(
            sport="lap_swimming",
            duration_seconds=3600,
            distance_meters=4000,  # 90 s/100m
            swim_css_pace_seconds_per_100m=90,
        )
        self.assertEqual(result.method, "pace")
        self.assertAlmostEqual(result.tss, 100.0)

    def test_hr_fallback_when_primary_signal_missing(self):
        result = activity_tss(
            sport="cycling", duration_seconds=3600, avg_hr=160, threshold_hr=160
        )
        self.assertEqual(result.method, "hr")
        self.assertAlmostEqual(result.tss, 100.0)

    def test_duration_fallback_when_nothing_available(self):
        result = activity_tss(sport="cycling", duration_seconds=3600)
        self.assertEqual(result.method, "duration")
        self.assertAlmostEqual(result.tss, 49.0)

    def test_returns_none_without_duration(self):
        self.assertIsNone(activity_tss(sport="cycling", duration_seconds=0))


class LoadSeriesTests(unittest.TestCase):
    def test_ewma_rejects_non_positive_time_constant(self):
        with self.assertRaises(ValueError):
            exponentially_weighted_load([100, 100], 0)

    def test_single_day_matches_weight(self):
        weight = 1.0 - math.exp(-1.0 / CTL_TIME_CONSTANT_DAYS)
        ctl = compute_ctl([100.0])
        self.assertAlmostEqual(ctl[0], 100.0 * weight)

    def test_constant_load_converges_and_atl_leads_ctl(self):
        series = [100.0] * 200
        ctl = compute_ctl(series)
        atl = compute_atl(series)
        # Both approach the steady 100 TSS/day load (CTL ramps slowly).
        self.assertAlmostEqual(ctl[-1], 100.0, delta=1.0)
        self.assertAlmostEqual(atl[-1], 100.0, delta=1.0)
        # Shorter time constant ramps faster early on.
        self.assertGreater(atl[6], ctl[6])
        self.assertLess(ATL_TIME_CONSTANT_DAYS, CTL_TIME_CONSTANT_DAYS)

    def test_tsb_is_ctl_minus_atl(self):
        ctl = [50.0, 60.0]
        atl = [40.0, 80.0]
        self.assertEqual(compute_tsb(ctl, atl), [10.0, -20.0])

    def test_tsb_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            compute_tsb([1.0], [1.0, 2.0])


if __name__ == "__main__":
    unittest.main()
