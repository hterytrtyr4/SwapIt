# SwapIt — Exchange, Don't Purchase

![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-SQLAlchemy-003B57?logo=sqlite&logoColor=white)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952B3?logo=bootstrap&logoColor=white)
![Tests](https://img.shields.io/badge/tests-35%20passing-brightgreen)

**SwapIt** is a peer-to-peer barter marketplace where people exchange items they no
longer need for things they do — **no money, ever**. List an item, browse what others
are offering, get smart *potential-match* suggestions, send swap requests, and track
every exchange from request to completion.

Built as a lightweight, fully self-contained Flask application: Python + SQLite +
Bootstrap 5, no paid APIs, no external services, no build step.

**New here?** `make dev` starts a seeded demo in one command — see
[DEMO.md](DEMO.md) for the click-through script. Deployment is covered in
[DEPLOY.md](DEPLOY.md).

---

## 1. Features

| Area | What's included |
| --- | --- |
| **Authentication** | Register (name, email, password, confirm, optional college), login, logout, secure Werkzeug password hashing, session management, duplicate-email validation, protected routes |
| **Home page** | Hero ("Don't Buy It. Swap It."), How It Works, featured items (real listings), benefits, CTA, footer |
| **Marketplace** | Responsive item-card grid, search by item name, category filter, sort (newest / oldest / title A–Z), item detail pages — shows **only available items owned by other users** |
| **Listings (CRUD)** | Add / edit / delete your own items with image upload (Pillow-validated, resized, unique UUID filenames), condition, wanted-in-exchange, notes; ownership checks block editing others' items |
| **Smart matching** | Pure-Python matching engine (`matching.py`): text normalisation, stopword filtering, fuzzy keyword coverage, `difflib` sequence similarity, category hints → 0–100 **potential match** score with per-direction fit breakdown. Derived only from real database listings; nothing auto-accepted |
| **Swap requests** | Requester picks one of their own available items → requests another user's item (optional message). Receiver accepts / rejects; requester cancels; participants mark completed. Statuses: *pending, accepted, rejected, completed, cancelled* |
| **Consistency rules** | No self-requests, no duplicate pending requests for the same exchange, only the receiver accepts/rejects, only the requester cancels, accepting reserves both items and auto-cancels overlapping pending requests, database transactions with rollback on failure |
| **Dashboard** | Stats (total listings, active listings, pending requests, accepted swaps, completed swaps), My Items with availability filter, Incoming / Sent requests with action buttons, Suggested Matches, Swap History |
| **Profile** | View & edit name / email / college, change password (verified with current password), member-since date, total listed items, completed swaps. Password hashes are never exposed |
| **UI/UX** | White + soft-lavender canvas, violet accent, Plus Jakarta Sans type, rounded cards, subtle shadows, hover effects, status badges, proper empty states, flash notifications, polished on desktop / laptop / tablet / mobile |
| **Security** | CSRF protection on every state-changing form (Flask-WTF), server-side validation, image upload verification (extension + Pillow `verify()` + re-encode), 5 MB upload cap, SQL-injection-safe ORM queries, ownership checks (403), safe `next` redirect handling, secrets via environment variables, HTTP-only `SameSite=Lax` cookies |

---

## 2. Tech stack

* **Backend:** Python 3.10+, Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF (CSRF)
* **Database:** SQLite (SQLAlchemy ORM, foreign keys enforced via `PRAGMA foreign_keys=ON`)
* **Frontend:** HTML5, CSS3, Bootstrap 5.3 (vendored locally in `static/vendor/`),
  Bootstrap Icons 1.11 (vendored), vanilla JavaScript, Jinja2 templates
* **Images:** Pillow (validation, EXIF stripping, resizing)
* **Matching:** Python standard library (`difflib`, `re`, `math`) — no paid APIs
* **Production server:** Gunicorn

Everything is free and open source. The app is fully offline-capable (Bootstrap,
icons, and fonts fall back to system fonts if Google Fonts is unreachable).

---

## 3. Project structure

```
SwapIt/
├── app.py                 # Application factory, error handlers, blueprint registration
├── config.py              # Config classes (env-driven secrets, upload limits, categories)
├── models.py              # User, Item, SwapRequest models + status constants
├── matching.py            # Smart swap matching engine (0-100 potential match scores)
├── seed_demo.py           # Optional demo data seeder (never runs automatically)
├── requirements.txt       # Production dependencies (incl. gunicorn)
├── Makefile               # install / run / dev / test / seed / reset / check / health / clean
├── Procfile               # gunicorn start command (Render, Heroku-style hosts)
├── render.yaml            # Render blueprint (free web service)
├── vercel.json            # Vercel serverless routing + bundled templates/static
├── api/index.py           # Vercel WSGI entry point
├── README.md              # This file
├── DEMO.md                # 3-minute demo script + demo accounts
├── DEPLOY.md              # Deploy walkthrough + troubleshooting table
├── VIVA_SCRIPT.md         # Walkthrough notes for a viva / review
├── .env.example           # Environment variable template
├── .gitignore
├── .vercelignore          # Trims the serverless bundle
│
├── routes/
│   ├── __init__.py
│   ├── auth.py            # /register /login /logout
│   ├── marketplace.py     # / /marketplace /item/<id>
│   ├── items.py           # /items/add /items/<id>/edit /items/<id>/delete
│   ├── swaps.py           # /swaps/request/<id> + accept/reject/cancel/complete
│   └── dashboard.py       # /dashboard /matches /profile
│
├── templates/
│   ├── base.html          # Navbar, flash messages, footer
│   ├── index.html         # Landing page
│   ├── login.html / register.html
│   ├── marketplace.html / item_detail.html
│   ├── add_item.html / edit_item.html
│   ├── swap_request.html / matches.html
│   ├── dashboard.html / profile.html
│   ├── partials/          # item_card.html, item_form.html
│   └── errors/            # 403 / 404 / 413 / 500
│
├── static/
│   ├── css/style.css      # Design system (lavender/violet theme)
│   ├── js/main.js         # Alert auto-dismiss, delete confirms, image preview
│   ├── uploads/           # User-uploaded item images (runtime)
│   └── vendor/            # Bootstrap 5 + Bootstrap Icons (offline-ready)
│
├── tests/
│   └── test_app.py        # 35 end-to-end tests covering all 14 workflows
│
└── instance/              # SQLite database lives here (runtime, git-ignored)
```

---

## 4. Run locally

### Quick start (one command)

```bash
make dev        # creates .venv, installs deps, seeds demo data, starts the server
# → http://127.0.0.1:5000
```

| Command | What it does |
| --- | --- |
| `make` | list every target |
| `make install` | create `.venv/` and install `requirements.txt` |
| `make run` | start the dev server (`HOST`/`PORT` overridable) |
| `make dev` | `install` + `seed` + `run` — the first-time path |
| `make test` | run the 35-test suite verbosely |
| `make seed` | load demo users, listings and swaps |
| `make reset` | wipe the local DB + uploads, then reseed |
| `make check` | compile-check sources, print versions |
| `make health` | curl the running server |
| `make clean` | remove caches and test artifacts |

No `make` on Windows? Use `python -m venv .venv` then the manual steps below.

### Manual steps

```bash
# 1. Get the code and enter the project
cd SwapIt

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) configure environment
cp .env.example .env               # then edit SECRET_KEY etc.

# 5. Run the development server
python app.py
# → http://127.0.0.1:5000
```

Tables are created automatically on first launch. To load demo users and listings:

```bash
python seed_demo.py
# demo accounts: aarav@demo.swapit / priya@demo.swapit / rohan@demo.swapit
# password for all: password123
```

Then follow [DEMO.md](DEMO.md) for a guided tour of what to click and why it
matters (the calculator ↔ textbook match is the highlight).

### Run the test-suite

```bash
python -m unittest discover -s tests -v
```

---

## 5. Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | `dev-only-insecure-secret-key` | Signs sessions & CSRF tokens — **set a strong value in production** |
| `DATABASE_URL` | `sqlite:///swapit.db` | SQLAlchemy database URI (`postgres://`/`postgresql://` are normalised to the psycopg2 driver automatically) |
| `FLASK_CONFIG` | — | `production` (HTTPS cookies) or `testing`; anything else = default |
| `SESSION_COOKIE_SECURE` | `0` | `1` to force HTTPS-only cookies (on automatically in production) |
| `AUTO_CREATE_DB` | `1` | `1` creates tables on startup (fine for demos; use migrations for serious prod) |
| `MEDIA_BACKEND` | `local` | `local` stores uploads in `static/uploads/`; `db` stores images in the database (for read-only serverless filesystems) |
| `ASSET_CDN` | `0` | `1` loads Bootstrap/Icons from the jsDelivr CDN instead of `static/vendor/` |
| `UPLOAD_FOLDER` | `static/uploads` | Where local-mode images are written |
| `MAX_UPLOAD_MB` | `5` | Max request/upload size in megabytes |
| `FLASK_DEBUG` | `0` | Set `1` only for local debugging |
| `PORT` / `HOST` | `5000` / `0.0.0.0` | Dev server binding (production uses gunicorn) |

Generate a secret key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 6. Deployment (free tier)

> Full walkthrough, environment matrix and a troubleshooting table live in
> [DEPLOY.md](DEPLOY.md). This section is the summary.

SwapIt deploys as a single serverless WSGI app. The supported free-tier path is
**Vercel (app) + Supabase Postgres (database)**; Render remains a valid
alternative and is described below "subject to current availability and limits".

### Vercel + Supabase (the deployed setup)

1. **Database** — create a free [Supabase](https://supabase.com) project.
   Copy the **Transaction pooler** connection string
   (`postgresql://…pooler.supabase.com:6543/postgres?sslmode=require`) and set it
   as `DATABASE_URL`. Tables are created on first boot (`AUTO_CREATE_DB=1`).
2. **App** — create a Vercel project and deploy this repository (Git or
   `vercel deploy`). The repo already contains:
   * `api/index.py` — WSGI entry (`from app import app`),
   * `vercel.json` — routes every path to the Flask app and bundles
     `templates/` + `static/` into the function,
   * `requirements.txt` — includes `psycopg2-binary` and `gunicorn`.
3. **Environment variables** on Vercel (Production + Preview):

   ```
   FLASK_CONFIG=production
   SECRET_KEY=<strong random value>
   DATABASE_URL=<supabase transaction pooler URI>
   MEDIA_BACKEND=db        # images in the DB — serverless FS is read-only
   ASSET_CDN=1             # Bootstrap from jsDelivr — no vendored files needed
   SESSION_COOKIE_SECURE=1
   MAX_UPLOAD_MB=4
   AUTO_CREATE_DB=1
   ```

4. Deploy. The deployment exposes the Flask app at every route.

**Honest free-tier caveats**

* Supabase free tier: 500 MB database, project **pauses after 7 days of
  inactivity** — a cold database needs a dashboard visit to wake up.
  Item images live in the database (`MEDIA_BACKEND=db`), so large photos count
  against the 500 MB; uploads are capped at 4 MB and resized to ≤1280 px.
* Vercel free (Hobby): serverless functions sleep when idle — the first request
  after idle can take a few seconds. Execution and bandwidth soft limits apply.
* **Vercel Deployment Protection**: if the project's *Deployment Protection* is
  set to "All deployments" (or the account enforces it), `*.vercel.app`
  URLs show a Vercel login wall for anonymous visitors. Custom domains are
  exempt, or turn protection off in **Project → Settings → Deployment
  Protection** (Hobby's "standard" setting only covers preview URLs).
* `AUTO_CREATE_DB=1` is a bootstrap convenience. For real production traffic,
  disable it and run proper migrations.

### Render (free web service) — alternative

1. Push this repository to GitHub.
2. On [render.com](https://render.com) → **New → Web Service** → connect the repo.
3. Settings:
   * **Runtime:** Python 3
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT`
   * **Environment:** add `SECRET_KEY` (generate a strong value) and, for
     persistence, `DATABASE_URL` pointing at a managed Postgres.
4. Deploy. Render runs `gunicorn app:app`; tables are created on first boot.

### ⚠️ Persistent storage — read this honestly

* The local demo uses **SQLite + file uploads** on the container's **ephemeral
  disk**. On free/ephemeral hosts **the database and uploaded images are wiped
  on every redeploy or restart**. This is a limitation of the free hosting
  model, not of the app — nothing is claimed to be persistent unless you
  configure it.
* To keep data between deploys: use a managed Postgres (`DATABASE_URL`, e.g.
  Supabase as above) and `MEDIA_BACKEND=db` (images in the database), or mount a
  persistent disk and point `UPLOAD_FOLDER`/`DATABASE_URL` at it.

---

## 7. How the matching algorithm works

`matching.py` computes **potential match** scores entirely from real listings:

1. **Normalisation** — lowercase, strip punctuation, remove English stopwords.
2. **Token coverage** — how much of "what I want" is covered by the other
   item's title/description/category tokens (fuzzy equality via `difflib`).
3. **Sequence similarity** — `difflib.SequenceMatcher` ratio over the
   normalised strings, with a bonus for phrase containment.
4. **Category hint** — a small boost when the wanted text names the item's category.
5. **Mutual score** — the geometric mean of both directions
   (their item fits my want × my item fits their want), so a one-sided match can
   never rank high. Pairs scoring ≥ 45/100 are surfaced, labelled
   *potential match*, with the per-direction fit shown. Suggestions are never
   auto-accepted — humans decide.

Classic example: User A offers a *Calculator* and wants an *Engineering Book*;
User B offers an *Engineering Book* and wants a *Calculator* → SwapIt flags a
high-scoring mutual match for both users.

---

## 8. Testing

`tests/test_app.py` contains **35 automated tests** (stdlib `unittest`, no extra
dependencies) covering the required workflows:

1. Register a new user (+ duplicate email, password mismatch, short password)
2. Login / logout / wrong password / protected-route redirect
3. Add item with image (+ form validation)
4. Browse marketplace (+ own items hidden, unavailable items hidden)
5. Search, category filter, sorting
6. Edit / delete own listing (+ 403 for other users' listings)
7. Mutual match generation (Calculator ↔ Engineering Book) + Matches page
8. Send swap request (+ self-request blocked, duplicate blocked)
9. Accept / reject / cancel (+ auto-cancel of overlapping pending requests)
10. Duplicate request prevention
11. Unauthorized actions (only receiver accepts, only requester cancels, double-accept ignored)
12. Complete an accepted swap (+ pending cannot complete, active items cannot be deleted)
13. Dashboard statistics + profile page + password change
14. CSRF enforcement (400 without token), password hashes never exposed, 404 page

All 35 tests pass. A separate live HTTP smoke test also verified the full
request → accept → complete workflow through the running server with CSRF
tokens, image upload, and dashboard stat rendering.

---

## 9. Known limitations & design notes

* **Availability filter location:** the brief requires the public marketplace to
  show *only available items belonging to other users*, so the availability
  filter lives in **Dashboard → My Items** (All / Available / Reserved / Swapped),
  while the marketplace provides search, category filter and sorting.
* **Matching is heuristic** (string similarity + keywords). It is intentionally
  lightweight and explainable; it can miss synonym-level matches
  ("laptop" vs "notebook computer") unless words overlap.
* **Images are stored on local disk** (`static/uploads/`); see the persistent
  storage warning above for production.
* **Email delivery is out of scope** — notifications are shown in-app (flash
  messages and a navbar badge for pending requests).
* **No messaging/chat** — request messages (500 chars) cover coordination.
* Demo data (`seed_demo.py`) is optional and clearly labelled; matching
  suggestions and requests are always computed from real database rows.

---

## 10. Documentation map

| Doc | Read it for |
| --- | --- |
| [README.md](README.md) | features, structure, local setup, env vars, how matching works |
| [DEMO.md](DEMO.md) | the 3-minute demo script, demo accounts, resettable seed data |
| [DEPLOY.md](DEPLOY.md) | Vercel + Supabase, Render, Docker, troubleshooting |
| [VIVA_SCRIPT.md](VIVA_SCRIPT.md) | answer-by-answer notes for a project viva |

---

## 11. License

Built with free and open-source technologies (Flask, Bootstrap, Pillow, SQLite).
Use, modify and learn from it freely.
