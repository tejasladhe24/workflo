FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

RUN uv pip install --system boto3 hatchling

COPY packages ./packages
COPY registry/publish.py ./registry/publish.py

CMD ["python", "registry/publish.py"]
