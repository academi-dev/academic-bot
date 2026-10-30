# Dockerfile para Academic Bot
FROM python:3.11-slim AS base

# Configuración de variables de entorno de Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Instalar dependencias del sistema mínimas
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copiar el código fuente
COPY bot/ ./bot/

# Crear usuario sin privilegios por seguridad
RUN adduser --disabled-password --gecos "" academic && \
    chown -R academic:academic /app

USER academic

# Ejecución del bot
CMD ["python", "-m", "bot.main"]
