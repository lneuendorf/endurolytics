import os
import tempfile
import unittest
from datetime import datetime

from analytics.weekly import aggregate_weekly_activity_summaries, get_recent_activities
from database.connection import Base, create_engine_from_url
from database.models import Activity


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_url = f"sqlite:///{os.path.join(self.temp_dir.name, 'analytics.db')}"
        self.engine = create_engine_from_url(self.db_url)
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_weekly_summary_groups_activities_by_week(self):
        with self.engine.begin() as conn:
            conn.execute(
                Activity.__table__.insert(),
                [
                    {
                        "activity_id": "1",
                        "date": datetime(2024, 1, 1, 0, 0, 0),
                        "activity_name": "Morning Run",
                        "sport": "running",
                        "duration_seconds": 3600,
                        "distance": 10000.0,
                    },
                    {
                        "activity_id": "2",
                        "date": datetime(2024, 1, 2, 0, 0, 0),
                        "activity_name": "Tempo Ride",
                        "sport": "cycling",
                        "duration_seconds": 5400,
                        "distance": 50000.0,
                    },
                    {
                        "activity_id": "3",
                        "date": datetime(2024, 1, 8, 0, 0, 0),
                        "activity_name": "Open Water Swim",
                        "sport": "swimming",
                        "duration_seconds": 1800,
                        "distance": 1500.0,
                    },
                ],
            )

        summaries = aggregate_weekly_activity_summaries(self.engine)
        self.assertEqual(len(summaries), 2)
        first_week = summaries[0]
        self.assertEqual(first_week["week_start"], "2024-01-01")
        self.assertEqual(first_week["running_duration_seconds"], 3600)
        self.assertEqual(first_week["cycling_duration_seconds"], 5400)
        self.assertEqual(first_week["total_duration_seconds"], 9000)
        self.assertEqual(first_week["total_distance_km"], 60.0)
        # No athlete settings seeded -> duration-only TSS estimate (IF 0.7):
        # run 1h -> 49.0, bike 1.5h -> 73.5, total 122.5.
        self.assertEqual(first_week["run_tss"], 49.0)
        self.assertEqual(first_week["bike_tss"], 73.5)
        self.assertEqual(first_week["total_tss"], 122.5)
        second_week = summaries[1]
        self.assertEqual(second_week["week_start"], "2024-01-08")
        self.assertEqual(second_week["swimming_duration_seconds"], 1800)
        # Swim 0.5h duration estimate -> 24.5 TSS.
        self.assertEqual(second_week["total_tss"], 24.5)

    def test_recent_activities_returns_latest_rows(self):
        with self.engine.begin() as conn:
            conn.execute(
                Activity.__table__.insert(),
                [
                    {
                        "activity_id": "1",
                        "date": datetime(2024, 1, 1, 0, 0, 0),
                        "activity_name": "Older Run",
                        "sport": "running",
                        "duration_seconds": 3000,
                        "distance": 8000.0,
                    },
                    {
                        "activity_id": "2",
                        "date": datetime(2024, 1, 3, 0, 0, 0),
                        "activity_name": "Newer Ride",
                        "sport": "cycling",
                        "duration_seconds": 4000,
                        "distance": 20000.0,
                    },
                ],
            )

        activities = get_recent_activities(self.engine, limit=1)
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0]["activity_name"], "Newer Ride")


if __name__ == "__main__":
    unittest.main()
