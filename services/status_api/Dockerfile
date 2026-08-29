FROM python:3.11.9-slim-bookworm

WORKDIR /app

COPY services/status_api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services /app/services
COPY web /app/web

EXPOSE 8082
CMD ["uvicorn", "services.status_api.main:app", "--host", "0.0.0.0", "--port", "8082"]
