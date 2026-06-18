# Evidence.dev dashboard-as-code.
#
# We scaffold the official Evidence template (so package.json pins a known-good
# set of @evidence-dev/* packages incl. the postgres connector), then overlay
# our own pages + sources. The postgres connection is supplied entirely via
# EVIDENCE_SOURCE__warehouse__* environment variables from docker-compose.
FROM node:20-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates wget git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Scaffold the canonical template, then drop its sample pages/sources.
RUN npx --yes degit evidence-dev/template . && rm -rf pages sources

# Overlay our dashboard + data source definitions.
COPY pages ./pages
COPY sources ./sources

RUN npm install

EXPOSE 3000

# Dev server connects live to Postgres and renders; robust for a one-shot.
CMD ["npx", "evidence", "dev", "--host", "0.0.0.0", "--port", "3000"]
