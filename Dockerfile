FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        git \
        openssh-client \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

COPY . .

RUN mkdir -p /srv/ztp_files /srv/config_repo

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
