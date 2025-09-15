FROM python:3.12-slim


ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DEBIAN_FRONTEND=noninteractive
ENV DJANGO_SETTINGS_MODULE=backend.settings


WORKDIR /app


RUN apt-get update --fix-missing \
    && apt-get install -y --no-install-recommends \
        apt-transport-https \
        ca-certificates \
        build-essential \
        libpq-dev \
        netcat-openbsd \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r requirements.txt


COPY . ./
RUN python manage.py collectstatic --noinput

RUN mkdir -p /app/media/qrcodes

# If you use a non-root user, also:
# RUN chown -R appuser:appuser /app/media


RUN adduser --disabled-password --no-create-home appuser
USER appuser


EXPOSE 8000


CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "backend.asgi:application"]