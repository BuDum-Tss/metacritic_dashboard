FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_PATH=/data/metacritic.db

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

RUN useradd --create-home app && mkdir /data && chown app:app /data
USER app
VOLUME /data

EXPOSE 8000
# one process only: the scheduler must not be duplicated and SQLite has a single writer
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
