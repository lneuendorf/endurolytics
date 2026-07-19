import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from pipeline.filter_activities import is_endurance_activity
from pipeline.run_sync import login_with_retries
from pipeline.sync_garmin import GarminSyncService
from database.connection import Base, create_engine_from_url
from database.models import ActivityRaw, Activity


class GarminSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_url = f"sqlite:///{os.path.join(self.temp_dir.name, 'test.db')}"
        self.engine = create_engine_from_url(self.db_url)
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_endurance_activity_filtering(self):
        self.assertTrue(is_endurance_activity({"activityType": {"typeKey": "running"}}))
        self.assertTrue(is_endurance_activity({"sportType": {"sportTypeKey": "cycling"}}))
        self.assertTrue(is_endurance_activity({"activityType": {"typeKey": "swimming"}}))
        self.assertFalse(is_endurance_activity({"activityType": {"typeKey": "strength"}}))
        self.assertFalse(is_endurance_activity({"activityType": {"typeKey": "cardio"}}))

    def test_sync_persists_new_activities_and_skips_duplicates(self):
        fake_client = MagicMock()
        fake_client.get_activities.return_value = [
            {"activityId": 101, "activityType": {"typeKey": "running"}, "activityName": "Morning Run", "startTimeGMT": "2024-01-01T00:00:00Z", "duration": 3600, "distance": 10000, "averageHR": 145, "maxHR": 160},
            {"activityId": 101, "activityType": {"typeKey": "running"}, "activityName": "Morning Run", "startTimeGMT": "2024-01-01T00:00:00Z", "duration": 3600, "distance": 10000, "averageHR": 145, "maxHR": 160},
            {"activityId": 102, "activityType": {"typeKey": "cycling"}, "activityName": "Tempo Ride", "startTimeGMT": "2024-01-02T00:00:00Z", "duration": 5400, "distance": 50000, "averageHR": 130, "maxHR": 150},
        ]

        service = GarminSyncService(self.engine)
        imported = service.sync(fake_client, limit=10)

        self.assertEqual(imported, 2)
        with service.session_scope() as session:
            activities = session.query(Activity).all()
            raw_rows = session.query(ActivityRaw).all()

        self.assertEqual(len(activities), 2)
        self.assertEqual(len(raw_rows), 2)
        self.assertEqual(activities[0].sport, "running")
        self.assertEqual(activities[1].sport, "cycling")

    def test_login_retries_on_rate_limit(self):
        class RateLimitedClient:
            def __init__(self):
                self.calls = 0

            def login(self, tokenstore=None):
                self.calls += 1
                if self.calls < 3:
                    raise RuntimeError("mobile+cffi returned 429: Mobile login returned 429")
                return None, None

        client = RateLimitedClient()
        with patch("pipeline.run_sync.time.sleep", return_value=None):
            login_with_retries(client, tokenstore_path="/tmp/garmin_tokens", retries=3, backoff_seconds=0)

        self.assertEqual(client.calls, 3)


if __name__ == "__main__":
    unittest.main()
