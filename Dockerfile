FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[dev]"

COPY configs ./configs
COPY scripts ./scripts
COPY datasets ./datasets

ENV AGENTEVALOPS_DATABASE_URL=sqlite:////app/.agentevalops/agentevalops.db
ENV AGENTEVALOPS_ARTIFACT_ROOT=/app/reports

ENTRYPOINT ["agenteval"]
