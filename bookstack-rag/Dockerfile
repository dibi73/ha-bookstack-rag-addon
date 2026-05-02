ARG BUILD_FROM
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --break-system-packages -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY app/ /app/app/

COPY rootfs/ /
RUN chmod a+x /etc/s6-overlay/s6-rc.d/api/run \
    && chmod a+x /etc/s6-overlay/s6-rc.d/api/finish

LABEL \
    io.hass.name="BookStack RAG" \
    io.hass.description="Local RAG over BookStack-exported Home Assistant documentation" \
    io.hass.type="addon" \
    io.hass.version="0.1.0" \
    maintainer="dibi73 <https://github.com/dibi73>"
