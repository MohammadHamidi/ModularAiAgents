# PostgreSQL with schema init baked in (no bind mount needed).
# Avoids "Is a directory" when init.sql is missing in deploy context.
FROM postgres:15-alpine

# Copy init script from build context into the image.
# Build context is ai_platform (parent of services/).
COPY services/db/init.sql /docker-entrypoint-initdb.d/init.sql
