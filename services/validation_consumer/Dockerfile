FROM python:3.11.9-slim-bookworm

WORKDIR /app

COPY services/validation_consumer/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services /app/services

CMD ["python", "-m", "services.validation_consumer.main"]
