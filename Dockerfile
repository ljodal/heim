FROM ghcr.io/astral-sh/uv:python3.14-alpine AS base

WORKDIR /app

FROM base AS builder

RUN apk add --no-cache gcc libffi-dev musl-dev openssl-dev

# Install dependencies
COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-dev --no-install-project

# Build and install project
COPY ./heim ./heim
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.14-alpine AS final

WORKDIR /app

RUN apk add --no-cache libffi

# Copy virtualenv from the builder
COPY --from=builder /app/.venv /app/.venv

COPY ./heim/frontend/templates ./heim/frontend/templates

ENV PATH="/app/.venv/bin:$PATH" \
    VIRTUAL_ENV="/app/.venv"
