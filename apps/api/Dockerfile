FROM python:3.11-slim

WORKDIR /app

# Install system deps for psycopg2 and build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project files (context is apps/api)
COPY pyproject.toml alembic.ini ./
COPY alembic ./alembic
COPY src ./src

RUN pip install --no-cache-dir -e .

# Run migrations then uvicorn (Render sets PORT)
ENV PYTHONPATH=/app
EXPOSE 8080

CMD ["sh", "-c", "alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
