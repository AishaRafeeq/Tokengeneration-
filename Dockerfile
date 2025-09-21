# Use official Python slim image
FROM python:3.12-slim

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV DJANGO_SETTINGS_MODULE=backend.settings
ENV TZ=Asia/Kolkata

WORKDIR /app

# Install system dependencies
RUN apt-get update --fix-missing \
    && apt-get install -y --no-install-recommends \
        apt-transport-https \
        ca-certificates \
        build-essential \
        libpq-dev \
        netcat-openbsd \
        tzdata \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set timezone
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy project
COPY . ./

# Create static and media directories
RUN mkdir -p /app/staticfiles /app/media/qrcodes \
    && chown -R appuser:appuser /app/media /app/staticfiles

# Make media persistent
VOLUME /app/media

# Collect static files
RUN python manage.py collectstatic --noinput

# Create a non-root user
RUN adduser --disabled-password --no-create-home appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Run ASGI server
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "backend.asgi:application"]
