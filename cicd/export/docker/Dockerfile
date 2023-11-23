FROM debian:bookworm-slim

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update --fix-missing \
  && apt-get install -y --no-install-recommends \
  git \
  qgis-server \
  software-properties-common \
  xauth \
  xvfb \
  && apt-get clean

COPY scripts/revision_entrypoint.sh /entrypoint.sh
ENTRYPOINT [ "/entrypoint.sh" ]