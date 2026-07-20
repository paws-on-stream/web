FROM node:22-alpine AS frontend
WORKDIR /app
COPY package.json package-lock.json build.mjs ./
COPY frontend_src ./frontend_src
RUN npm ci && npm run build

FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN pip install --no-cache-dir poetry && poetry config virtualenvs.create false
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root --no-interaction
COPY paws_on_stream_web ./paws_on_stream_web
COPY --from=frontend /app/paws_on_stream_web/static ./paws_on_stream_web/static
RUN SECRET_KEY=build-only-not-used-at-runtime python paws_on_stream_web/manage.py collectstatic --noinput
EXPOSE 8000
CMD ["gunicorn", "--chdir", "paws_on_stream_web", "--bind", "0.0.0.0:8000", "--workers", "3", "paws_on_stream_web.wsgi:application"]
