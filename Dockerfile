# syntax=docker/dockerfile:1
FROM python:3.12.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r requirements.txt
RUN useradd --create-home --uid 10001 app && mkdir /app/backups && chown app:app /app/backups
COPY --chown=app:app financial_analytics ./financial_analytics
COPY --chown=app:app sql ./sql
COPY --chown=app:app app.py 03_relatorios.sql ./
COPY --chown=app:app .streamlit ./.streamlit
USER app
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]

FROM base AS test
USER root
COPY requirements-dev.txt .
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r requirements-dev.txt
COPY --chown=app:app tests ./tests
COPY --chown=app:app pyproject.toml 01_estrutura.sql 02_dados.sql ./
USER app
CMD ["pytest", "-q"]
