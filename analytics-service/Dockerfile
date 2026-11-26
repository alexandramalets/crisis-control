FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.lock.txt .
RUN pip install -r requirements.lock.txt

COPY app ./app

RUN useradd --system --uid 10001 appuser
USER appuser

EXPOSE 8001

ENV HEALTHCHECK_PATH=/analytics/v1/health
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=5 \
    CMD python -m app.docker_health

CMD ["python", "-m", "app"]
