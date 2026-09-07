# Docker build environment for OOMAnalyser
#
# Copyright (c) 2026 Carsten Grohmann and contributors
# License: MIT (see LICENSE.txt)
# THIS PROGRAM COMES WITH NO WARRANTY

FROM python:3.7-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    rollup \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir Transcrypt==3.7.16
WORKDIR /app

# Build stage: copy full repository source and execute build
FROM builder AS build-env
COPY . /app
RUN transcrypt --build --map --nomin --sform --esv 6 OOMAnalyser.py && \
    rollup --config rollup.config.mjs

# Export stage: contains only the target output files for local filesystem extraction
FROM scratch AS export
COPY --from=build-env /app/OOMAnalyser.js /
COPY --from=build-env /app/OOMAnalyser.html /
