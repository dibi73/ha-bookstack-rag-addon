# ==============================================================================
# Multi-stage build — first stage cherry-picks the qdrant binary from the
# upstream image, second stage assembles the runtime environment.
#
# Since v0.5.0 this Dockerfile is consumed by `home-assistant/builder` (per
# build.yaml) and the resulting per-arch images are published to ghcr.io.
# `image:` in config.yaml points users at those, so the Supervisor pulls
# instead of building locally — no more BUILD_FROM-injection drama.
#
# The smoke-build CI workflow (build.yml) passes BUILD_FROM as a build-arg
# to keep the same image format. v0.4.1–v0.4.4 hardcoded
# python:3.12-slim-bookworm to survive Supervisor's BUILD_FROM injection;
# now that local builds are off the table we can take the value from
# build.yaml again.
# ==============================================================================

FROM qdrant/qdrant:v1.17.1 AS qdrant_source

ARG BUILD_FROM=python:3.12-slim-bookworm
FROM ${BUILD_FROM}

ARG S6_OVERLAY_VERSION=3.2.0.2
ARG TARGETARCH

ENV LANG=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    S6_BEHAVIOUR_IF_STAGE2_FAILS=2 \
    S6_KEEP_ENV=1

# System packages:
# - ca-certificates: HTTPS to PyPI / HuggingFace
# - curl + xz-utils: the s6-overlay install at the next layer
# - build-essential: any wheel that still needs to compile
# - libunwind8: provides libunwind-ptrace.so.0 which the qdrant binary
#   we copy in below dynamically links against. Without this qdrant
#   fails to start with "error while loading shared libraries:
#   libunwind-ptrace.so.0: cannot open shared object file".
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        xz-utils \
        build-essential \
        libunwind8 \
    && rm -rf /var/lib/apt/lists/*

# s6-overlay v3 — noarch userland + arch-specific binaries.
RUN set -eux \
    && case "${TARGETARCH:-amd64}" in \
        amd64) S6_ARCH=x86_64 ;; \
        arm64) S6_ARCH=aarch64 ;; \
        *) echo "Unsupported TARGETARCH: ${TARGETARCH}" >&2; exit 1 ;; \
       esac \
    && curl -fsSL "https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz" \
        | tar -C / -Jxpf - \
    && curl -fsSL "https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${S6_ARCH}.tar.xz" \
        | tar -C / -Jxpf -

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

# App code (incl. the static UI bundle under app/ui/) and s6-overlay
# service definitions.
COPY app/ /app/app/
COPY rootfs/ /
RUN chmod a+x /etc/s6-overlay/s6-rc.d/api/run \
    && chmod a+x /etc/s6-overlay/s6-rc.d/api/finish \
    && chmod a+x /etc/s6-overlay/s6-rc.d/qdrant/run

ENTRYPOINT ["/init"]

LABEL \
    io.hass.name="BookStack RAG" \
    io.hass.description="Local RAG over BookStack-exported Home Assistant documentation" \
    io.hass.type="addon" \
    io.hass.version="0.5.0" \
    io.hass.arch="amd64|aarch64" \
    maintainer="dibi73 <https://github.com/dibi73>"
