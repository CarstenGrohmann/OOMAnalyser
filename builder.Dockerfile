FROM python:3.7-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    make \
    rollup \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir virtualenv
RUN ln -s /usr/local/bin/python /usr/bin/python3.7
WORKDIR /app

# Copy configuration files first to cache python virtualenv setup
COPY requirements.txt Makefile ./
RUN make venv

# Build stage: copy full repository source and execute build
FROM builder AS build-env
COPY . /app
RUN make build

# Export stage: contains only the target output files for local filesystem extraction
FROM scratch AS export
COPY --from=build-env /app/OOMAnalyser.js /
COPY --from=build-env /app/OOMAnalyser.html /
