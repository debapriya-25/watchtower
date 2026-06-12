# syntax=docker/dockerfile:1
#
# Watchtower backend — production-ready multi-stage image.
#
#   * Stage 1 (builder): installs Python dependencies into an isolated venv so
#     the heavy build context never reaches the final image.
#   * Stage 2 (runtime): slim image, non-root user, only the venv + app code.
#
# Build context is the repository root (so both requirements.txt and backend/
# are available). Build with:  docker build -t watchtower-backend .

# --------------------------------------------------------------------------- #
# Stage 1 — builder
# --------------------------------------------------------------------------- #
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

# Dedicated virtualenv keeps the dependency tree easy to copy into the runtime.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build

# Copy ONLY the requirements first so the (slow) dependency install layer is
# cached and reused whenever application source changes but deps do not.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# --------------------------------------------------------------------------- #
# Stage 2 — runtime
# --------------------------------------------------------------------------- #
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_ENV=production

# Create an unprivileged user to run the application.
RUN groupadd --system app && \
    useradd --system --gid app --home-dir /app --no-create-home app

# Bring the prebuilt virtualenv over from the builder stage.
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Application source (the backend/ package: app/, alembic/, scripts/, etc.).
COPY backend/ /app/

# Normalise line endings on the entrypoint (in case of CRLF on Windows) and
# make it executable, then hand ownership of the app tree to the non-root user.
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh && \
    chmod +x /app/docker-entrypoint.sh && \
    chown -R app:app /app

USER app

EXPOSE 8000

# Container-level liveness/readiness: the API's own /health endpoint (which also
# checks Postgres + Redis). start-period covers first-boot migrations.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status==200 else 1)" || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
