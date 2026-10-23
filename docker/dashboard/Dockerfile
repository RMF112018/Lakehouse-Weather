# Nonproduction candidate. Pinned base and exact tested PostgreSQL dependencies.
FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
WORKDIR /app
COPY requirements-postgres.txt /app/requirements-postgres.txt
RUN pip install --no-cache-dir --requirement /app/requirements-postgres.txt
COPY weather /app/weather
COPY web /app/web
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 WEATHER_MODE=demo
USER 10001:10001
EXPOSE 8765
CMD ["python", "-m", "weather", "serve", "--host", "0.0.0.0", "--port", "8765"]
