FROM ubuntu:21.10

ARG DEFAULT_POSTGRES_PASSWORD=postgres

ENV DEBIAN_FRONTEND noninteractive
RUN apt-get -y update && apt-get install -y \
    curl \
    fonts-droid-fallback \
    gdal-bin \
    git \
    jq \
    libmapnik3.1 \
    mapnik-utils \
    netcat \
    osm2pgsql \
    osmium-tool \
    postgresql-13-postgis-3 \
    python3 \
    python3-mapnik \
    python3-pip \
    python3-psycopg2 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sL https://deb.nodesource.com/setup_12.x | bash - && apt-get install -y \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g carto

COPY imagery/requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

COPY osm/docker/renderer/conf/postgresql.conf /etc/postgresql/13/main/
COPY osm/docker/renderer/conf/pg_hba.conf /etc/postgresql/13/main/
RUN chown postgres: /etc/postgresql/13/main/*

ENV PGPASSWORD=${DEFAULT_POSTGRES_PASSWORD}

COPY scripts/revision_entrypoint.sh /entrypoint.sh
ENTRYPOINT [ "/entrypoint.sh" ]
