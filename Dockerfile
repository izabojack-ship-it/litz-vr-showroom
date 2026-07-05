FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000 \
    CONTENT_DIR=/data/content

RUN apt-get update \
    && apt-get install -y --no-install-recommends libjpeg62-turbo zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt

COPY . .

RUN mkdir -p /data/content/files /data/content/published /data/content/draft /data/content/config

EXPOSE 10000

CMD uvicorn server.app:app --host 0.0.0.0 --port ${PORT:-10000}
