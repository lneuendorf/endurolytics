import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from pipeline.filter_activities import (
    is_endurance_activity,
    is_multisport_parent,
)
from pipeline.run_sync import login_with_retries
from pipeline.sync_garmin import GarminSyncService
from database.connection import Base, create_engine_from_url
from database.models import ActivityRaw, Activity


def _leg_detail(activity_id, type_key, start, distance, duration, avg_hr=None, np=None):
    """Build a Garmin ``get_activity`` detail payload for a multisport child leg."""
    return {
        "activityId": activity_id,
        "activityName": type_key,
        "activityTypeDTO": {"typeKey": type_key},
        "summaryDTO": {
            "startTimeGMT": start,
            "distance": distance,
            "duration": duration,
            "averageHR": avg_hr,
            "normalizedPower": np,
        },
    }



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

    def test_multisport_parent_and_leg_filtering(self):
        # Individual multisport leg sports should be importable.
        self.assertTrue(is_endurance_activity({"activityType": {"typeKey": "open_water_swimming"}}))
        # Transitions and the parent container itself should not be imported directly.
        self.assertFalse(is_endurance_activity({"activityType": {"typeKey": "transition_v2"}}))
        self.assertFalse(is_endurance_activity({"activityType": {"typeKey": "multi_sport"}}))
        # Parent detection covers the type key, the flag, and child metadata.
        self.assertTrue(is_multisport_parent({"activityType": {"typeKey": "multi_sport"}}))
        self.assertTrue(is_multisport_parent({"isMultiSportParent": True}))
        self.assertTrue(is_multisport_parent({"metadataDTO": {"childIds": [1, 2]}}))
        self.assertFalse(is_multisport_parent({"activityType": {"typeKey": "running"}}))

    def test_multisport_activity_is_decomposed_into_legs(self):
        parent = {"activityId": 900, "activityType": {"typeKey": "multi_sport"}, "activityName": "Triathlon"}
        parent_detail = {
            "metadataDTO": {"childIds": [901, 902, 903, 904, 905]},
        }
        legs = {
            901: _leg_detail(901, "open_water_swimming", "2024-06-01T12:00:00.0", 1500, 1800, avg_hr=130),
            902: _leg_detail(902, "transition_v2", "2024-06-01T12:30:00.0", 100, 120),
            903: _leg_detail(903, "cycling", "2024-06-01T12:32:00.0", 40000, 4800, avg_hr=150),
            904: _leg_detail(904, "transition_v2", "2024-06-01T13:52:00.0", 50, 60),
            905: _leg_detail(905, "running", "2024-06-01T13:53:00.0", 10000, 3300, avg_hr=160, np=300),
        }

        fake_client = MagicMock()
        fake_client.get_activities.return_value = [parent]
        fake_client.get_activity.side_effect = lambda aid: parent_detail if int(aid) == 900 else legs[int(aid)]

        service = GarminSyncService(self.engine)
        imported = service.sync(fake_client, limit=10)

        # Swim, bike and run legs are stored; both transitions are skipped.
        self.assertEqual(imported, 3)
        with service.session_scope() as session:
            sports = sorted(a.sport for a in session.query(Activity).all())
        self.assertEqual(sports, ["cycling", "open_water_swimming", "running"])

    def test_duplicate_recording_keeps_richer_signal(self):
        # The bike leg was recorded twice: a multisport child leg with HR, and a
        # standalone head-unit ride with no HR/power. Same time, ~same distance.
        parent = {"activityId": 900, "activityType": {"typeKey": "multi_sport"}, "activityName": "70.3"}
        parent_detail = {"metadataDTO": {"childIds": [903]}}
        bike_leg = _leg_detail(903, "cycling", "2024-06-07T12:58:41.0", 89917.0, 10949, avg_hr=150)
        standalone_bike = {
            "activityId": 950,
            "activityType": {"typeKey": "road_biking"},
            "activityName": "Head-unit Ride",
            "startTimeGMT": "2024-06-07T12:59:02.0",
            "distance": 89942.0,
            "duration": 10979,
        }

        fake_client = MagicMock()
        fake_client.get_activities.return_value = [parent, standalone_bike]
        fake_client.get_activity.side_effect = lambda aid: parent_detail if int(aid) == 900 else bike_leg

        service = GarminSyncService(self.engine)
        imported = service.sync(fake_client, limit=10)

        self.assertEqual(imported, 1)
        with service.session_scope() as session:
            activities = session.query(Activity).all()
        self.assertEqual(len(activities), 1)
        # The multisport leg (with HR) wins over the signal-less standalone ride.
        self.assertEqual(activities[0].activity_id, "903")
        self.assertEqual(activities[0].avg_hr, 150)

    def test_duplicate_removes_previously_stored_weaker_copy(self):
        # First sync stores only the standalone head-unit ride (no HR).
        standalone_bike = {
            "activityId": 950,
            "activityType": {"typeKey": "road_biking"},
            "activityName": "Head-unit Ride",
            "startTimeGMT": "2024-06-07T12:59:02.0",
            "distance": 89942.0,
            "duration": 10979,
        }
        first_client = MagicMock()
        first_client.get_activities.return_value = [standalone_bike]
        service = GarminSyncService(self.engine)
        self.assertEqual(service.sync(first_client, limit=10), 1)

        # Later sync also sees the multisport parent whose bike leg has HR.
        parent = {"activityId": 900, "activityType": {"typeKey": "multi_sport"}, "activityName": "70.3"}
        parent_detail = {"metadataDTO": {"childIds": [903]}}
        bike_leg = _leg_detail(903, "cycling", "2024-06-07T12:58:41.0", 89917.0, 10949, avg_hr=150)
        second_client = MagicMock()
        second_client.get_activities.return_value = [parent, standalone_bike]
        second_client.get_activity.side_effect = lambda aid: parent_detail if int(aid) == 900 else bike_leg

        imported = service.sync(second_client, limit=10)

        self.assertEqual(imported, 1)
        with service.session_scope() as session:
            ids = sorted(a.activity_id for a in session.query(Activity).all())
        # The weaker, previously-stored standalone ride is replaced by the leg.
        self.assertEqual(ids, ["903"])

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
