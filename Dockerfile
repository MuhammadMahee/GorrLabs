# syntax=docker/dockerfile:1
# any sentence transformer model; models to use can be found at https://huggingface.co/models?library=sentence-transformers
# Leaderboard: https://huggingface.co/spaces/mteb/leaderboard
# IMPORTANT: If you change the embedding model and vice versa, you aren't able to use RAG Chat
# with your previous documents loaded in Arkive! You need to re-embed them.
ARG USE_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
ARG USE_RERANKING_MODEL=""

ARG BUILD_HASH=dev-build
# Override at your own risk - non-root configurations are untested
ARG UID=0
ARG GID=0

######## Arkive frontend ########
FROM --platform=$BUILDPLATFORM node:22-alpine3.20 AS build
ARG BUILD_HASH

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --force

COPY .npmrc postcss.config.js svelte.config.js tailwind.config.js tsconfig.json vite.config.ts ./
COPY scripts/prepare-pyodide.js ./scripts/prepare-pyodide.js
COPY src ./src
COPY static ./static
ENV APP_BUILD_HASH=${BUILD_HASH}
RUN npm run build

######## Arkive backend ########
FROM python:3.11.14-slim-bookworm AS base

ARG USE_EMBEDDING_MODEL
ARG USE_RERANKING_MODEL
ARG UID
ARG GID

ENV PYTHONUNBUFFERED=1

ENV ENV=prod \
    PORT=8080 \
    USE_EMBEDDING_MODEL_DOCKER=${USE_EMBEDDING_MODEL} \
    USE_RERANKING_MODEL_DOCKER=${USE_RERANKING_MODEL}

ENV OPENAI_API_BASE_URL=""

ENV OPENAI_API_KEY="" \
    ARKIVE_SECRET_KEY="" \
    SCARF_NO_ANALYTICS=true \
    DO_NOT_TRACK=true \
    ANONYMIZED_TELEMETRY=false

## RAG Embedding model settings ##
ENV RAG_EMBEDDING_MODEL="$USE_EMBEDDING_MODEL_DOCKER" \
    RAG_RERANKING_MODEL="$USE_RERANKING_MODEL_DOCKER" \
    SENTENCE_TRANSFORMERS_HOME="/app/backend/data/cache/embedding/models"

## Tiktoken model settings ##
ENV TIKTOKEN_ENCODING_NAME="cl100k_base" \
    TIKTOKEN_CACHE_DIR="/app/backend/data/cache/tiktoken"

## Hugging Face download cache ##
ENV HF_HOME="/app/backend/data/cache/embedding/models"

WORKDIR /app/backend

ENV HOME=/root
RUN if [ $UID -ne 0 ]; then \
    if [ $GID -ne 0 ]; then \
    addgroup --gid $GID app; \
    fi; \
    adduser --uid $UID --gid $GID --home $HOME --disabled-password --no-create-home app; \
    fi

RUN mkdir -p $HOME/.cache/chroma
RUN echo -n 00000000-0000-0000-0000-000000000000 > $HOME/.cache/chroma/telemetry_user_id

RUN chown -R $UID:$GID /app $HOME

COPY --chown=$UID:$GID ./backend/requirements.txt ./requirements.txt

# Install build deps, compile Python packages, then purge build tools — all in one
# layer so the compiler/headers don't appear in the final image.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential gcc python3-dev \
        curl jq ffmpeg \
    && pip3 install --no-cache-dir uv \
    && pip3 install 'torch<=2.9.1' --index-url https://download.pytorch.org/whl/cpu --no-cache-dir \
    && uv pip install --system -r requirements.txt --no-cache-dir \
    && apt-get purge -y build-essential gcc python3-dev \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* \
    && mkdir -p /app/backend/data \
    && chown -R $UID:$GID /app/backend/data/

# copy built frontend files
COPY --chown=$UID:$GID --from=build /app/build /app/build
COPY --chown=$UID:$GID --from=build /app/package.json /app/package.json

# copy backend files
COPY --chown=$UID:$GID ./backend .

EXPOSE 8080

HEALTHCHECK CMD curl --silent --fail http://localhost:${PORT:-8080}/health | jq -ne 'input.status == true' || exit 1

USER $UID:$GID

ARG BUILD_HASH
ENV ARKIVE_BUILD_VERSION=${BUILD_HASH}
ENV DOCKER=true

CMD [ "bash", "start.sh"]
