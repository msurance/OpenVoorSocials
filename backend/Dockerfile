FROM python:3.12-slim@sha256:3d5ed973e45820f5ba5e46bd065bd88b3a504ff0724d85980dcd05eab361fcf4

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install supercronic (static binary) — cached layer, only re-runs if this line changes
RUN curl -fsSL https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-amd64 \
    -o /usr/local/bin/supercronic \
    && chmod +x /usr/local/bin/supercronic

# requirements first — this layer is cached until requirements.txt changes
COPY backend/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# App code — ARG before COPY forces cache bust on every build
ARG CACHEBUST=1
COPY backend/ .
COPY crontab /app/crontab
COPY logobanners/ /app/logobanners/

RUN python manage.py collectstatic --noinput --settings=config.settings.production || true

EXPOSE 8000
