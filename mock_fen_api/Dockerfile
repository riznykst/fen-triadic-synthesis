FROM python:3.11-slim

WORKDIR /app

COPY mock_fen_api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY mock_fen_api /app/mock_fen_api

EXPOSE 8100
CMD ["uvicorn", "mock_fen_api.main:app", "--host", "0.0.0.0", "--port", "8100"]
