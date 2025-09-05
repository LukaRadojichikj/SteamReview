FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY . .

# Create non-root user with a fixed UID and use it
RUN adduser --disabled-password --gecos "" --uid 10001 appuser && chown -R 10001:10001 /app
USER 10001

ENV LLM_CACHE_FILE=.cache/llm_cache.json
ENTRYPOINT ["python","main.py"]
