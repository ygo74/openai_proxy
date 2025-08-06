FROM python:3.12

WORKDIR /code

# Install poetry
RUN pip install poetry

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root

COPY ./src ./src
