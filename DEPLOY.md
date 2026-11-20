# Deploying SwapIt

Three deploy paths, all free-tier friendly. Pick one:

| Path | Database | Images | Best for |
| --- | --- | --- | --- |
| [Vercel + Supabase](#1-vercel--supabase) | Postgres (Supabase) | in DB (`MEDIA_BACKEND=db`) | a public link with a real HTTPS URL |
| [Render](#2-render) | SQLite on disk, or Postgres | on disk, or in DB | a single always-on container |
| [Docker / any VPS](#3-docker--vps) | whatever you point it at | disk or DB | full control, no cold starts |

The app itself needs no build step — it is plain Flask + Jinja + vendored CSS.

---

## 0. Pre-flight checklist

Run these locally before deploying; if any fail, the deploy will fail too.

```bash
make check                       # sources compile, deps import
make test                        # 35/35 pass
SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))")
echo "Set this in your host's env vars: $SECRET_KEY"
```

Generate the secret **once**, store it in the host's environment settings, and
never commit it. `SECRET_KEY` signs sessions and CSRF tokens; a weak value lets
anyone forge a login.

---

## 1. Vercel + Supabase

### 1.1 Database

1. Create a free [Supabase](https://supabase.com) project.
2. **Project Settings → Database → Connection string → Transaction pooler**
   and copy the URI. It looks like:
   ```
   postgresql://postgres.abcdefgh:PASSWORD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require
   ```
   Use the **pooler** (port `6543`), not the direct connection — serverless
   functions open many short-lived connections and will exhaust a direct limit.
3. Keep the password safe; it goes into `DATABASE_URL` only.

### 1.2 App

The repository is already wired for Vercel:

| File | Purpose |
| --- | --- |
| `api/index.py` | WSGI entry point — Vercel imports `app` from here |
| `vercel.json` | routes `/(.*)` → `api/index.py`, bundles `templates/**` + `static/**` |
| `requirements.txt` | includes `psycopg2-binary` (Postgres driver) and `gunicorn` |
| `.vercelignore` | keeps the venv, tests, local DB and demo uploads out of the bundle |

Deploy with Git (import the repo at [vercel.com/new](https://vercel.com/new)) or
with the CLI:

```bash
npm i -g vercel        # once
vercel                 # preview deploy
vercel --prod          # production deploy
```

### 1.3 Environment variables

Set these for **Production** (and Preview if you want previews to work):

| Variable | Value | Why |
| --- | --- | --- |
| `FLASK_CONFIG` | `production` | enables HTTPS-only cookies |
| `SECRET_KEY` | the random hex from step 0 | sessions + CSRF |
| `DATABASE_URL` | Supabase pooler URI | persistent data |
| `MEDIA_BACKEND` | `db` | serverless filesystem is read-only — images must live in the DB |
| `ASSET_CDN` | `1` | loads Bootstrap/Icons from jsDelivr; smaller bundle |
| `SESSION_COOKIE_SECURE` | `1` | belt-and-braces with `FLASK_CONFIG` |
| `MAX_UPLOAD_MB` | `4` | Vercel caps request bodies around 4.5 MB |
| `AUTO_CREATE_DB` | `1` | creates tables on first request (switch off once you add migrations) |

Then redeploy — environment changes only take effect on a new deployment.

### 1.4 First-run verification

1. Open the deployment URL → hero page renders.
2. **Register** an account (this proves DB writes work).
3. Add an item **with an image** (this proves `MEDIA_BACKEND=db` works).
4. Log out, log back in (this proves the session cookie is being accepted over
   HTTPS — a secure-cookie misconfiguration shows up exactly here).

---

## 2. Render

A blueprint is included: [`render.yaml`](render.yaml). Either click
**New → Blueprint** and point Render at this repo, or configure a web service
manually:

- **Runtime:** Python 3
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `gunicorn app:app --bind 0.0.0.0:$PORT` (also in `Procfile`)
- **Health check path:** `/` (the home page is cheap and touches no DB tables
  beyond a small read)

Environment variables: `SECRET_KEY`, `FLASK_CONFIG=production`, and — to survive
restarts — `DATABASE_URL` (a Render/Neon/Supabase Postgres) plus `MEDIA_BACKEND=db`.

> **Render disks are ephemeral on the free plan.** Without an external
> `DATABASE_URL`, the SQLite file is recreated empty on every deploy, restart or
> wake-from-sleep.

---

## 3. Docker / VPS

Any host that can run `gunicorn` works. Minimal container:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV FLASK_CONFIG=production HOST=0.0.0.0 PORT=8000
EXPOSE 8000
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4"]
```

```bash
docker build -t swapit .
docker run -p 8000:8000 -e SECRET_KEY="$(openssl rand -hex 32)" swapit
```

Mount a volume at `/app/instance` (SQLite) and `/app/static/uploads` (images) if
you stay on the local media backend, or use Postgres + `MEDIA_BACKEND=db`.

---

## 4. Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `500` on every page, logs mention `no such table` | `AUTO_CREATE_DB` is `0` and migrations never ran | set `AUTO_CREATE_DB=1` for the first deploy, or run `db.create_all()` |
| `500` when saving an item with a photo | `MEDIA_BACKEND=local` on a read-only filesystem | set `MEDIA_BACKEND=db` |
| Uploaded images show as broken after a redeploy | images were written to the ephemeral disk | `MEDIA_BACKEND=db`, or mount a persistent volume |
| Logged-out immediately after logging in | `SESSION_COOKIE_SECURE=1` while browsing over plain HTTP | serve over HTTPS, or set the flag to `0` locally |
| `403 CSRF` / `400` on forms right after deploy | `SECRET_KEY` changed between requests (e.g. random per instance) | set one fixed `SECRET_KEY` |
| Vercel URL asks for a Vercel login | *Deployment Protection* is on | Project → Settings → Deployment Protection → allow anonymous, or use a custom domain |
| First request after idle takes ~10 s | free-tier function/database cold start | expected; hit the URL once to warm it |
| Supabase errors after a quiet week | free projects pause after 7 days idle | open the Supabase dashboard to resume |
| `psycopg2` build error on install | no prebuilt wheel matched the Python version | keep `psycopg2-binary` pinned in `requirements.txt`; Python 3.11–3.12 have wheels |
| CSS/bootstrap missing | `static/` not bundled with the function | keep `includeFiles` in `vercel.json` (already set) |

---

## 5. What is *not* production-ready (by design)

This is a course/demo project, and it says so honestly:

- `AUTO_CREATE_DB` is a bootstrap convenience, not a migration system.
- No email verification, password reset, or rate limiting on login.
- Signals run synchronously in the request; fine at demo scale.
- No background jobs, no cache, no CDN for user images.

Add those before pointing real traffic at it.
