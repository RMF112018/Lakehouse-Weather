# syntax=docker/dockerfile:1
#
# Extends felddy/weewx:5 with a current, pinned rtl_433 binary.
# weewx-sdr and the dashboard skin are installed into the persistent /data
# volume by scripts/install-extensions.sh after Gate 1 succeeds.

ARG RTL433_REF=3792adf1075acb7c6447f7c27df9920fd4f2d41a

FROM debian:bookworm-slim AS rtl433-build
ARG RTL433_REF
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git cmake make gcc g++ pkg-config \
      libusb-1.0-0-dev librtlsdr-dev \
    && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/merbanan/rtl_433.git /src/rtl_433 \
    && cd /src/rtl_433 \
    && git checkout "${RTL433_REF}" \
    && cmake -S . -B build -DENABLE_SOAPYSDR=OFF \
    && cmake --build build --parallel \
    && cmake --install build --prefix /opt/rtl433

FROM felddy/weewx:5
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
      rtl-sdr librtlsdr0 procps \
    && rm -rf /var/lib/apt/lists/*
COPY --from=rtl433-build /opt/rtl433/bin/rtl_433 /usr/local/bin/rtl_433
USER weewx
