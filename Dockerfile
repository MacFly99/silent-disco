FROM python:3.12-slim

WORKDIR /app

# Dépendances système (rien de spécial pour cette app)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Volumes montés en runtime : config + logs + caches OAuth
# (voir docker-compose.yml)
ENV PYTHONUNBUFFERED=1

EXPOSE 5001

# gunicorn + eventlet pour SocketIO
CMD ["gunicorn", "-c", "gunicorn_conf.py", "app:app"]
