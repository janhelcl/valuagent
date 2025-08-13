FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (if needed later): build-essential
RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock /app/
RUN poetry config virtualenvs.create false \
 && poetry install --only main --no-interaction --no-ansi

COPY . /app

# Respect platform-provided PORT (Render sets this)
ENV PORT=8080
CMD ["sh", "-c", "uvicorn src.app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]