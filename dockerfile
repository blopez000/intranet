# ====== BASE ======
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/appuser/.local/bin:${PATH}"

# Instalar dependencias del sistema mínimas
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no root
RUN useradd -ms /bin/bash appuser
USER appuser
WORKDIR /app

# ====== DEPENDENCIAS ======
COPY --chown=appuser:appuser requirements.txt ./
RUN pip install --user -r requirements.txt

# ====== CÓDIGO ======
COPY --chown=appuser:appuser . .

# ====== PRODUCCIÓN ======
EXPOSE 8000
CMD ["gunicorn", "-w", "3", "--threads", "8", "-t", "120", "-b", "0.0.0.0:8000", "wsgi:app"]

