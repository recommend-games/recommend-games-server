FROM python:3.14-slim

ENV LANG=C.UTF-8
ENV MAILTO=''
ENV PYTHONPATH=.
ENV PYTHONUNBUFFERED=1
# Install into the image's own site-packages, not a virtualenv.
ENV UV_PROJECT_ENVIRONMENT=/usr/local
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.12.8 /uv /uvx /bin/

WORKDIR /app

# Runtime dependencies only -- the build/dev groups (torch, invoke, pandas,
# scikit-learn, ...) run on the developer machine and never enter the image.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-default-groups --no-install-project

COPY VERSION VERSION
COPY rg rg
COPY games games
COPY static static
COPY data data

RUN useradd --create-home gamer
USER gamer

CMD gunicorn \
    --bind 0.0.0.0:$PORT \
    --workers 1 \
    --threads 8 \
    rg.wsgi:application
