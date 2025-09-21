FROM python:3.12-slim

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV DJANGO_SETTINGS_MODULE=backend.settings

# Set working directory
WORKDIR /app

# Install dependencies
RUN apt-get update --fix-missing \
    && apt-get install -y --no-install-recommends \
        apt-transport-https \
        ca-certificates \
        build-essential \
        libpq-dev \
        netcat-openbsd \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy project files
COPY . ./

# Create static & media directories BEFORE collectstatic
RUN mkdir -p /app/staticfiles /app/media/qrcodes

# Collect static files
RUN python manage.py collectstatic --noinput

# Create non-root user and fix permissions
RUN adduser --disabled-password --no-create-home appuser \
    && chown -R appuser:appuser /app/media /app/staticfiles

# Switch to non-root user
USER appuser

# Expose port and run Daphne
EXPOSE 8000
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "backend.asgi:application"]
