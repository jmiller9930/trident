FROM python:3.12-slim

WORKDIR /worker

COPY app ./app

ENV PYTHONPATH=/worker

CMD ["python", "-m", "app.main"]
