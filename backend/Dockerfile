FROM python:3.12-slim@sha256:3d5ed973e45820f5ba5e46bd065bd88b3a504ff0724d85980dcd05eab361fcf4

# Enables BuildKit inline cache so 'cache_from: openvoorsocials:latest' works on next deploy
ARG BUILDKIT_INLINE_CACHE=1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ffmpeg only — libpq-dev/gcc not needed (psycopg2-binary is a pre-built wheel)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Supercronic bundled in repo — no GitHub download needed at build time
COPY bin/supercronic-linux-amd64 /usr/local/bin/supercronic
RUN chmod +x /usr/local/bin/supercronic

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
