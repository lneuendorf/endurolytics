# Enduralytics

## Garmin import

This repository now includes a starter Garmin Connect import pipeline.

### Setup

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your Garmin credentials.
4. Create/upgrade the database schema:
   - `alembic upgrade head`
5. (Optional) Seed athlete thresholds (FTP, threshold pace, CSS, HR) from `.env`:
   - `python -m database.settings`
6. Run the sync (also computes training-load metrics):
   - `python -m pipeline.run_sync`
7. (Optional) Recompute metrics without syncing:
   - `python -m pipeline.process_activities`

### Database & migrations

- Schema is managed with [Alembic](https://alembic.sqlalchemy.org/). Migrations
  live in `database/migrations/`.
- Apply the latest schema with `alembic upgrade head`.
- After changing a model in `database/models.py`, generate a migration with
  `alembic revision --autogenerate -m "describe change"`, review it, then run
  `alembic upgrade head`.
- The connection URL comes from `DATABASE_URL` (defaults to local SQLite). Bare
  `postgres://` URLs from Neon/Render are normalized to the `psycopg2` driver
  automatically.

### What it does

- Authenticates with Garmin Connect via `python-garminconnect`
- Pulls recent activities
- Filters to endurance sports
- Stores raw Garmin payloads in `activity_raw`
- Stores normalized activity rows in `activities`
- Skips duplicate activities by `activity_id`
- Computes per-activity training load (`activity_metrics`) and weekly rollups
  (`weekly_training`), including TSS, CTL, ATL, and TSB

### Training-load processing

- After each sync, `pipeline.run_sync` runs the processing stage to derive
  metrics. Run it standalone with `python -m pipeline.process_activities`.
- Processing is idempotent: it recomputes every value in place, so it is safe to
  rerun after editing athlete thresholds (`python -m database.settings`).
- TSS is derived from the best available signal per activity: bike power vs. FTP,
  run pace vs. threshold pace, swim pace vs. CSS, then heart rate, then a
  duration-only estimate. The method used is recorded on each metrics row.

### Notes

- The initial implementation uses SQLite by default for local development.
- For PostgreSQL, set `DATABASE_URL` to your connection string.
- The first run may prompt for an MFA code if Garmin requires it.
- Adopting Alembic on an existing SQLite database: the schema was stamped at the
  initial revision, so `alembic upgrade head` is a no-op until the next migration.

## Dashboard

Run the Dash app locally:

- `python -m app.app` (serves at http://localhost:8050)

Pages: Overview, Weekly, Training Load, Activities, Glossary (metric definitions
and formulas), and Settings (edit FTP / threshold pace / CSS / HR and optionally
recompute all historical metrics).

## Deployment

### Dashboard on Render

- The app exposes a WSGI server as `app.app:server` for gunicorn.
- `render.yaml` defines a free web service that installs requirements, runs
  `alembic upgrade head`, then starts gunicorn.
- Set the `DATABASE_URL` env var (Neon PostgreSQL connection string) in the
  Render dashboard.
- A `Dockerfile` is also provided for container-based hosts.

### Automated Garmin sync on GitHub Actions

- `.github/workflows/garmin_sync.yml` runs the sync + processing every hour
  (and on demand via "Run workflow").
- Required repository secrets: `GARMIN_EMAIL`, `GARMIN_PASSWORD`, `DATABASE_URL`
  (use the same Neon connection string as Render).
- Optional `GARMIN_TOKEN_BASE64`: a base64-encoded Garmin token directory from a
  successful local login, so CI can authenticate without an MFA prompt. Generate
  it after a local sync with `tar -cf oauth.tar -C ~/.garminconnect . && base64 -i oauth.tar`.

### Secrets and files to never commit

- `.env` (Garmin credentials), local `*.db` databases, and the `.garminconnect/`
  token cache are gitignored — keep them out of version control.
- Garmin credentials belong in **GitHub Actions** secrets (the sync runs there);
  Render only needs `DATABASE_URL`, and Neon stores no app secrets.
