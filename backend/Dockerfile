FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Install supercronic (static binary)
RUN curl -fsSL https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-amd64 \
    -o /usr/local/bin/supercronic \
    && chmod +x /usr/local/bin/supercronic

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code (build context = project root)
COPY backend/ .

# Copy crontab from project root
COPY crontab /app/crontab

RUN python manage.py collectstatic --noinput --settings=config.settings.production || true

EXPOSE 8000
