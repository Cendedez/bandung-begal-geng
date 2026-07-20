# Staging Backend Deployment

The staging VPS runs FastAPI, PostGIS, and the private moderator dashboard in Docker. Vercel hosts the public Next.js PWA separately. Vercel forwards PWA requests from `/api` to FastAPI over HTTPS, while the database remains private to the Docker network.

## Prerequisites

- A Linux VPS with Docker Engine and Docker Compose.
- A Linux VPS with a public IPv4 address.
- Two DNS A records pointing to the VPS public IP: one for `API_DOMAIN` and one for `MODERATOR_DOMAIN`.
- The Vercel project and custom domain defined in `PWA_DOMAIN`. See `README_Vercel.md`.
- Ports 80 and 443 open on the VPS firewall.

## First deployment

1. Set real values in `deploy/staging.env` using `deploy/staging.env.example` as the field reference.
2. Run `docker compose --env-file deploy/staging.env -f docker-compose.staging.yml up --build -d`.
3. Follow bootstrap progress with `docker compose --env-file deploy/staging.env -f docker-compose.staging.yml logs -f bootstrap`.
4. After bootstrap completes, verify `https://API_DOMAIN/health` and `https://MODERATOR_DOMAIN`.
5. Set `INTERNAL_API_URL=https://API_DOMAIN` in the Vercel project, then deploy the PWA as described in `README_Vercel.md`.

The bootstrap task applies the schema, imports the audited legacy incidents, and imports named OSM road segments for Kota Bandung, Kota Cimahi, and Kabupaten Bandung. It is idempotent and can be rerun when the source road data needs refresh.

## Operations

- Check service state: `docker compose --env-file deploy/staging.env -f docker-compose.staging.yml ps`
- Create a database backup: `docker compose --env-file deploy/staging.env -f docker-compose.staging.yml exec -T database pg_dump -U $POSTGRES_USER $POSTGRES_DB > bandung-crime.sql`
- Update after a code change: `docker compose --env-file deploy/staging.env -f docker-compose.staging.yml up --build -d`

Do not expose port 5432, port 8000, or port 8501 directly to the public internet. Caddy obtains and renews HTTPS certificates after DNS is correct.
