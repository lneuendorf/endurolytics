import os
import tempfile
import unittest

from database.connection import Base, create_engine_from_url, session_scope
from database.settings import get_athlete_settings, upsert_athlete_settings


class AthleteSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_url = f"sqlite:///{os.path.join(self.temp_dir.name, 'settings.db')}"
        self.engine = create_engine_from_url(self.db_url)
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_upsert_creates_then_updates_without_clobbering(self):
        with session_scope(self.db_url) as session:
            created = upsert_athlete_settings(
                session,
                ftp_watts=250,
                run_threshold_pace_seconds_per_km=255.0,
                swim_css_pace_seconds_per_100m=95.0,
            )
            self.assertEqual(created.ftp_watts, 250)

        # Partial update: only FTP provided, others must be preserved.
        with session_scope(self.db_url) as session:
            updated = upsert_athlete_settings(session, ftp_watts=260)
            self.assertEqual(updated.ftp_watts, 260)
            self.assertEqual(updated.run_threshold_pace_seconds_per_km, 255.0)
            self.assertEqual(updated.swim_css_pace_seconds_per_100m, 95.0)

        # Only one row should exist for the default athlete.
        with session_scope(self.db_url) as session:
            settings = get_athlete_settings(session)
            self.assertIsNotNone(settings)
            self.assertEqual(settings.athlete_id, "default")

    def test_none_values_are_ignored(self):
        with session_scope(self.db_url) as session:
            upsert_athlete_settings(session, ftp_watts=200)
        with session_scope(self.db_url) as session:
            updated = upsert_athlete_settings(session, ftp_watts=None, max_hr=185)
            self.assertEqual(updated.ftp_watts, 200)
            self.assertEqual(updated.max_hr, 185)


if __name__ == "__main__":
    unittest.main()
