# Vercel PWA Deployment

This deploys the public `web/` Next.js PWA to Vercel. The API, PostGIS database, and Streamlit moderator dashboard remain on the staging VPS.

## Required values

Choose these three hostnames before deployment:

| Purpose | Example hostname | Hosted by |
| --- | --- | --- |
| Public PWA | `staging.example.com` | Vercel |
| Public API | `api-staging.example.com` | VPS / Caddy |
| Moderator dashboard | `moderator-staging.example.com` | VPS / Caddy |

The PWA is intentionally configured to call relative `/api` URLs. Vercel rewrites them to the API URL stored in `INTERNAL_API_URL`, so browsers do not need direct API URLs or a special Android build.

## One-time manual setup

1. Create a private GitHub repository and push this project to it. Do not commit `deploy/staging.env`, `.env`, or `web/.env.local`.
2. In Vercel, select **Add New Project**, import that GitHub repository, and set **Root Directory** to `web`.
3. Under **Settings > Environment Variables**, add this value for Preview and Production:

   ```text
   INTERNAL_API_URL=https://api-staging.example.com
   ```

   Replace the hostname with the real `API_DOMAIN`. Leave `NEXT_PUBLIC_API_BASE_URL` unset: the application defaults to its same-origin `/api` path.
4. Deploy once to obtain a `*.vercel.app` preview URL.
5. Add the intended public hostname in **Vercel > Settings > Domains**. Apply the exact DNS record Vercel shows for that hostname, then set `PWA_DOMAIN` in `deploy/staging.env` to this hostname.
6. On the VPS, set `API_DOMAIN`, `MODERATOR_DOMAIN`, and `PWA_DOMAIN` in `deploy/staging.env`, then deploy the backend stack. Caddy will issue HTTPS certificates after the API and moderator DNS records point to the VPS.
7. Redeploy the Vercel project after `https://API_DOMAIN/health` returns a JSON response with `"status": "ok"`.

## Verify

1. Open `https://PWA_DOMAIN` on an Android phone and submit a test report.
2. Confirm the PWA map loads reports and the report page can search roads.
3. Open `https://MODERATOR_DOMAIN`, moderate the test report, then verify that a published, mappable report appears on the PWA map.
4. Delete or reject the test report when verification is complete.

## Operational notes

- Vercel preview URLs are accepted by the API CORS configuration. Keep the API public HTTPS endpoint limited to this application; Postgres is never public.
- The moderator dashboard has its own application password. Use a unique, long value for `MODERATOR_PASSWORD` in the VPS environment file.
- Vercel environment variables must contain the API origin only, without a trailing `/api` path.
