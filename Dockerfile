FROM public.ecr.aws/docker/library/python:3.12-slim-bookworm AS builder

ENV POETRY_VERSION=1.8.0 \
    POETRY_HOME=/opt/poetry \
    PATH=/opt/poetry/bin:$PATH \
    POETRY_VIRTUALENVS_CREATE=false \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y curl git && \
    curl -sSL https://install.python-poetry.org | python3 - && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /code
COPY ./pyproject.toml ./poetry.lock* /code/

RUN poetry install --no-interaction --no-dev

# Runtime stage
FROM public.ecr.aws/docker/library/python:3.12-slim-bookworm

WORKDIR /code

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY ./app /code/app
COPY ./entrypoint.sh /code/entrypoint.sh

ENV PYTHONUNBUFFERED=true
ENV PYTHONPATH="/code"

EXPOSE 8000

ENTRYPOINT ["/code/entrypoint.sh"]
