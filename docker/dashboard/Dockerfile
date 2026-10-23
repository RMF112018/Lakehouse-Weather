# Pinned base and complete hash-locked Python 3.12 Linux amd64 runtime.
FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
ARG WEATHER_SOURCE_REVISION
ARG WEATHER_SOURCE_TREE
LABEL org.opencontainers.image.revision=$WEATHER_SOURCE_REVISION \
      org.opencontainers.image.source-tree=$WEATHER_SOURCE_TREE \
      org.opencontainers.image.source="https://github.com/RMF112018/Lakehouse-Weather"
WORKDIR /app
COPY requirements-serving.lock /app/requirements-serving.lock
RUN pip install --no-cache-dir --require-hashes --only-binary=:all: --requirement /app/requirements-serving.lock
COPY weather /app/weather
COPY web /app/web
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 WEATHER_MODE=demo
USER 10001:10001
EXPOSE 8765
CMD ["gunicorn", "--config", "python:weather.gunicorn_config", "weather.wsgi:create_app()"]
