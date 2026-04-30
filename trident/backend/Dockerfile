FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY pytest.ini .
COPY app ./app
COPY tests ./tests
COPY clawbot_100e_proof.py .
COPY clawbot_100f_proof.py .
COPY docker-healthcheck.sh /usr/local/bin/docker-healthcheck.sh
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-healthcheck.sh /usr/local/bin/docker-entrypoint.sh

ENV PYTHONPATH=/app
ENV TRIDENT_LOG_LEVEL=INFO

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=35s \
  CMD /usr/local/bin/docker-healthcheck.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
