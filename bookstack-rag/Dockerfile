# ==============================================================================
# Stage 1 build — multi-stage so we can cherry-pick the qdrant binary
# from the upstream qdrant image without dragging in its full filesystem.
# ==============================================================================

ARG BUILD_FROM
FROM qdrant/qdrant:v1.17.1 AS qdrant_source

FROM ${BUILD_FROM}

ENV LANG=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Build dependencies — most ML wheels for amd64/aarch64 ship as manylinux
# binaries, but a couple of indirect deps still expect a working compiler.
# curl is used by the api/run script to wait for qdrant readiness.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies. torch ships ~700 MB of GPU-less wheels so this is
# by far the slowest layer; we install it before copying app code so the
# layer cache survives most edits during development.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --break-system-packages -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Pre-download the default embedding model into the image so the add-on's
# first start is fast and predictable. Users who configure a different
# model pay the download cost on first run only.
ENV HF_HOME=/usr/local/share/huggingface
RUN mkdir -p "$HF_HOME" \
    && python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('nomic-ai/nomic-embed-text-v1.5', trust_remote_code=True)"

# qdrant binary from the upstream image — pinned to match qdrant-client.
COPY --from=qdrant_source /qdrant/qdrant /usr/local/bin/qdrant

# App code and s6-overlay service definitions.
COPY app/ /app/app/
COPY rootfs/ /
RUN chmod a+x /etc/s6-overlay/s6-rc.d/api/run \
    && chmod a+x /etc/s6-overlay/s6-rc.d/api/finish \
    && chmod a+x /etc/s6-overlay/s6-rc.d/qdrant/run

LABEL \
    io.hass.name="BookStack RAG" \
    io.hass.description="Local RAG over BookStack-exported Home Assistant documentation" \
    io.hass.type="addon" \
    io.hass.version="0.2.0" \
    io.hass.arch="amd64|aarch64" \
    maintainer="dibi73 <https://github.com/dibi73>"
