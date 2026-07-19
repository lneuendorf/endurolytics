# Endurolytics dashboard image (Render / any container host).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the application source.
COPY . .

# Render provides $PORT; default to 8050 for local runs.
ENV PORT=8050
EXPOSE 8050

# Apply migrations, then serve the Dash app via gunicorn.
CMD ["sh", "-c", "alembic upgrade head && gunicorn app.app:server --bind 0.0.0.0:${PORT} --workers 2 --timeout 120"]
