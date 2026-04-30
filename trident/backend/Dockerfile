FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY docker-healthcheck.sh /usr/local/bin/docker-healthcheck.sh
RUN chmod +x /usr/local/bin/docker-healthcheck.sh

ENV PYTHONPATH=/app
ENV TRIDENT_LOG_LEVEL=INFO

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=15s \
  CMD /usr/local/bin/docker-healthcheck.sh

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
