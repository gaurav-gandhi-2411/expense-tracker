# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# Build tools may be required by some prophet/stan transitive deps on certain platforms.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# ── CPU-only torch MUST be installed before sentence-transformers ────────────
# Default `pip install torch` from PyPI pulls the CUDA-enabled wheel (~2 GB).
# CPU-only is ~200 MB and satisfies the same version constraint.
# pip will see torch is already installed when resolving sentence-transformers
# deps and will not reinstall the CUDA version.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# ── Project dependencies ─────────────────────────────────────────────────────
# Listed explicitly to avoid a pip build-backend round-trip for pyproject.toml.
# Keep in sync with pyproject.toml [project].dependencies.
RUN pip install --no-cache-dir \
    alembic \
    fastapi \
    groq \
    joblib \
    prophet \
    psycopg2-binary \
    "pydantic>=2" \
    pydantic-settings \
    "pyjwt[crypto]" \
    python-dotenv \
    scikit-learn \
    sentence-transformers \
    "sqlalchemy>=2.0" \
    "uvicorn[standard]"

# ── Application source ────────────────────────────────────────────────────────
COPY app/ app/
COPY migrations/ migrations/
COPY alembic.ini .
COPY scripts/ scripts/

# Non-root user for security
RUN adduser --disabled-password --gecos "" appuser
USER appuser

ENV PORT=8080
EXPOSE 8080

# exec form ensures uvicorn is PID 1 and receives SIGTERM from Cloud Run
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
