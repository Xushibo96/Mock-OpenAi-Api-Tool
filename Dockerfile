FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt /app/
COPY mock_openai_tool /app/mock_openai_tool

RUN apt-get update && \
    apt-get install -y gcc libpq-dev build-essential g++ libsasl2-dev && \
    python3 -m pip install --no-cache-dir -r /app/requirements.txt && \
    rm -rf ~/.cache/pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

EXPOSE 8000

CMD ["uvicorn", "mock_openai_tool.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
