import os
import tempfile
import unittest
from datetime import datetime

from database.connection import Base, create_engine_from_url
from database.models import Activity, ActivityMetrics, AthleteSettings, WeeklyTraining
from pipeline.process_activities import process_all


class ProcessingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_url = f"sqlite:///{os.path.join(self.temp_dir.name, 'proc.db')}"
        self.engine = create_engine_from_url(self.db_url)
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)

        with self.engine.begin() as conn:
            conn.execute(
                AthleteSettings.__table__.insert(),
                [{"athlete_id": "default", "ftp_watts": 250, "run_threshold_pace_seconds_per_km": 300.0}],
            )
            conn.execute(
                Activity.__table__.insert(),
                [
                    {
                        "activity_id": "bike-1",
                        "date": datetime(2024, 1, 1, 8, 0, 0),
                        "activity_name": "FTP Ride",
                        "sport": "cycling",
                        "duration_seconds": 3600,
                        "distance": None,
                        "normalized_power": 250.0,
                    },
                    {
                        "activity_id": "run-1",
                        "date": datetime(2024, 1, 2, 8, 0, 0),
                        "activity_name": "Threshold Run",
                        "sport": "running",
                        "duration_seconds": 3600,
                        "distance": 12000.0,  # 300 s/km == threshold
                        "normalized_power": None,
                    },
                ],
            )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_process_populates_metrics_and_weekly(self):
        counts = process_all(engine=self.engine)
        self.assertEqual(counts["activity_metrics"], 2)
        self.assertEqual(counts["weekly_training"], 1)

        with self.engine.connect() as conn:
            metrics = {
                row.activity_id: row
                for row in conn.execute(ActivityMetrics.__table__.select())
            }

        self.assertEqual(metrics["bike-1"].discipline, "bike")
        self.assertEqual(metrics["bike-1"].tss_method, "power")
        self.assertAlmostEqual(metrics["bike-1"].tss, 100.0)
        self.assertAlmostEqual(metrics["bike-1"].bike_tss, 100.0)
        self.assertIsNone(metrics["bike-1"].run_tss)

        self.assertEqual(metrics["run-1"].discipline, "run")
        self.assertEqual(metrics["run-1"].tss_method, "pace")
        self.assertAlmostEqual(metrics["run-1"].tss, 100.0)

        with self.engine.connect() as conn:
            weeks = list(conn.execute(WeeklyTraining.__table__.select()))
        self.assertEqual(len(weeks), 1)
        week = weeks[0]
        self.assertAlmostEqual(week.total_tss, 200.0)
        self.assertAlmostEqual(week.run_tss, 100.0)
        self.assertAlmostEqual(week.bike_tss, 100.0)
        self.assertAlmostEqual(week.total_hours, 2.0)
        self.assertAlmostEqual(week.run_distance, 12.0)
        self.assertAlmostEqual(week.longest_run, 12.0)
        self.assertGreater(week.ctl, 0.0)

    def test_processing_is_idempotent(self):
        first = process_all(engine=self.engine)
        second = process_all(engine=self.engine)
        self.assertEqual(first, second)

        with self.engine.connect() as conn:
            metric_count = conn.execute(ActivityMetrics.__table__.select()).fetchall()
            week_count = conn.execute(WeeklyTraining.__table__.select()).fetchall()
        self.assertEqual(len(metric_count), 2)
        self.assertEqual(len(week_count), 1)


if __name__ == "__main__":
    unittest.main()
