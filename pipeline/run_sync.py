import os
import time

from dotenv import load_dotenv
from garminconnect import Garmin

from database.connection import init_db
from pipeline.process_activities import process_all
from pipeline.sync_garmin import GarminSyncService


load_dotenv()


def _is_rate_limit_error(exc: Exception) -> bool:
    error_text = str(exc).lower()
    return "429" in error_text or "rate limited" in error_text or "too many requests" in error_text


def login_with_retries(client, tokenstore_path: str | None = None, retries: int = 3, backoff_seconds: int = 30):
    effective_tokenstore = tokenstore_path or os.getenv("GARMINTOKENS") or os.path.expanduser("~/.garminconnect")

    for attempt in range(1, retries + 1):
        try:
            return client.login(effective_tokenstore)
        except Exception as exc:
            if not _is_rate_limit_error(exc) or attempt == retries:
                raise

            wait_seconds = backoff_seconds * attempt
            print(f"Garmin login was rate limited. Retrying in {wait_seconds}s ({attempt}/{retries})...")
            time.sleep(wait_seconds)

    raise RuntimeError("Garmin login retries exhausted")


def main() -> None:
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    database_url = os.getenv("DATABASE_URL", "sqlite:///endurolytics.db")

    if not email or not password:
        raise RuntimeError("Set GARMIN_EMAIL and GARMIN_PASSWORD before running the sync")

    engine = init_db(database_url)
    client = Garmin(email, password, prompt_mfa=lambda: input("Enter Garmin MFA code: "))
    login_with_retries(
        client,
        tokenstore_path=os.getenv("GARMINTOKENS") or os.path.expanduser("~/.garminconnect"),
        retries=int(os.getenv("GARMIN_LOGIN_RETRIES", "3")),
        backoff_seconds=int(os.getenv("GARMIN_LOGIN_BACKOFF_SECONDS", "30")),
    )

    service = GarminSyncService(engine)
    imported = service.sync(client, limit=500)
    print(f"Imported {imported} new endurance activities")

    counts = process_all(engine=engine)
    print(
        f"Processed {counts['activity_metrics']} activity metrics and "
        f"{counts['weekly_training']} weekly rollups"
    )


if __name__ == "__main__":
    main()
