# ==============================================================================
# Stage 1 build — multi-stage so we can cherry-pick the qdrant binary
# from the upstream qdrant image without dragging in its full filesystem.
#
# Base is the upstream python:3.12-slim-bookworm (debian/glibc). Home
# Assistant publishes only an alpine variant of base-python, but PyTorch
# (transitive via sentence-transformers) ships no musllinux wheels. We
# bootstrap s6-overlay v3 ourselves so the supervisor still has the
# auto-restart-on-PID-1-death behaviour HA expects.
# ==============================================================================

ARG BUILD_FROM
FROM qdrant/qdrant:v1.17.1 AS qdrant_source

FROM ${BUILD_FROM}

ARG S6_OVERLAY_VERSION=3.2.0.2
ARG TARGETARCH

ENV LANG=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    S6_BEHAVIOUR_IF_STAGE2_FAILS=2 \
    S6_KEEP_ENV=1

# System packages: curl + xz for the s6-overlay install, build-essential
# for any wheel that still needs to compile, ca-certificates for HTTPS.
# We keep build-essential in the final image because removing it would
# also drop libstdc++ which torch needs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        xz-utils \
        build-essential \
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
    io.hass.version="0.4.0" \
    io.hass.arch="amd64|aarch64" \
    maintainer="dibi73 <https://github.com/dibi73>"
