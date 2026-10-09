FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Librerias nativas que pide GeoDjango
RUN apt-get update \
    && apt-get install -y --no-install-recommends binutils libproj-dev gdal-bin \
    && rm -rf /var/lib/apt/lists/*

# Usuario sin privilegios
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

COPY --chown=appuser:appuser . .

USER appuser
