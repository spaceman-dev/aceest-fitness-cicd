# syntax=docker/dockerfile:1
#
# ACEest Fitness & Gym
#   builder : runtime dependencies in /opt/venv
#   test    : builder + dev dependencies + test suite   (docker build --target test)
#   runtime : slim, non-root image that gunicorn runs   (default target)

FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
# copied alone so this layer is reused until the dependencies change
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install -r requirements.txt


FROM builder AS test

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY requirements.txt requirements-dev.txt pytest.ini .flake8 ./
RUN pip install -r requirements-dev.txt
COPY ACEest_Fitness.py ./
COPY aceest ./aceest
COPY tests ./tests

CMD ["pytest", "-p", "no:cacheprovider"]


FROM python:3.12-slim AS runtime

ARG APP_VERSION=dev
ARG GIT_COMMIT=unknown

LABEL org.opencontainers.image.title="aceest-fitness" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT}" \
      org.opencontainers.image.source="https://github.com/spaceman-dev/aceest-fitness-cicd"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    FLASK_ENV=production

RUN groupadd --gid 10001 aceest \
    && useradd --uid 10001 --gid aceest --no-create-home --shell /usr/sbin/nologin aceest

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
# code stays root-owned and read-only for the app user
COPY ACEest_Fitness.py ./
COPY aceest ./aceest

# numeric so Kubernetes can verify runAsNonRoot
USER 10001
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=2).status == 200 else 1)"

# one worker per container - Kubernetes scales with replicas instead
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", \
     "--no-control-socket", "--access-logfile", "-", "ACEest_Fitness:app"]
