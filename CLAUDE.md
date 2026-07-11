# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Shopdeck is a replacement server for the Nintendo 3DS eShop. It reimplements the eShop's backend services so 3DS consoles can browse, purchase, and download digital content from a custom storefront.

## Architecture

The project runs **two separate servers** that must both be running:

1. **Django server** (`manage.py`) — handles the JSON API endpoints and the web portal UI. Runs on standard Django dev server.
2. **Flask server** (`main.py`) — handles SOAP/XML services that the 3DS console firmware communicates with directly. Runs as a standalone Flask app.

Both servers share the same database and Django ORM models (defined in `shopdeckdb/models.py`).

### Django Apps

- **`api/`** (Ninja) — JSON API at `/ninja/ws/`. Handles session management, balance, purchases, wishlists, transactions, and voting. This is what the eShop client app on the 3DS talks to for store operations.
- **`metadata/`** (Samurai) — JSON API at `/samurai/ws/<region>/`. Serves catalog data: title listings, directories/categories, search, news, rankings, movies, and publisher/genre metadata.
- **`webui/`** — Browser-facing portal at `/`. User registration, login, title browsing, wishlist management, balance/prepaid card redemption, and search.
- **`shopdeckdb/`** — Shared models and middleware. Contains all ORM models and `ShopMiddleware` (maintenance mode, authentication enforcement, account termination checks).

### Flask Blueprints (SOAP XML Services)

- **`ecs.py`** (ECommerceSOAP) — Account status, ticket generation/delivery, balance checks, tax info. Generates binary eTickets from `basetik.bin`/`basetik_licence.bin` templates.
- **`ias.py`** (IdentityAuthenticationSOAP) — Device registration, challenge-response auth, country setting.
- **`cas.py`** (CatalogingSOAP) — Title metadata and DLC item lookups via SOAP.
- **`cdn.py`** — Serves TMD and content files from the `cdn/` directory for title downloads.
- **`assetcdn.py`** — Serves static assets (icons, banners) from the `assetcdn/` directory.

### Key Configuration

Settings in `shopdeck/settings.py`:
- `SOAP_URL` / `METADATA_API_URL` — must be set to the hostnames where the Flask and Django servers are reachable by the 3DS.
- `IN_MAINTENANCE` — enables maintenance mode across both API and web UI.
- `TOS_ESHOP` — custom terms of service text shown in the eShop.
- `AUTH_USER_MODEL` is `shopdeckdb.User` (extends `AbstractUser` with a `linked_ds` FK to `Client3DS`).

## Docker Deployment

The primary deployment method is Docker Compose. It runs 5 services: PostgreSQL, Django (gunicorn), Flask (gunicorn), nginx (reverse proxy for browsers), and mitmproxy (forward proxy replacing Charles Proxy for 3DS traffic).

```bash
# Start all services
cp .env.example .env  # then edit .env
docker compose up -d --build

# View logs
docker compose logs -f

# Stop services
docker compose down

# Import CIA files (manual extraction helper — prints instructions only)
docker compose exec django python cia-helper.py <file.cia>
```

### Automatic CIA Import

The `importer` service (in `docker-compose.yml`) runs `manage.py watch_intake`,
which watches `${DATA_DIR}/intake` for dropped `.cia` files. Each is imported
end-to-end automatically: content `.app` files + `tmd.bin` are written to
`cdn/<TITLE_ID>/`, the SMDH icon to `assetcdn/icons/<TITLE_ID>.png`, and an
immediately-public, free `Title` row is created (idempotent — re-dropping a CIA
updates it). Processed files move to `intake/processed/`; failures move to
`intake/failed/`. Decryption needs `boot9.bin` — set `BOOT9_PATH` in `.env`.

```bash
# Auto-import: just drop a file into the intake folder
cp game.cia data/intake/

# One-shot manual import (file or a directory of .cia files)
docker compose exec importer python manage.py import_cia /app/intake/game.cia
```

The shared import logic lives in `shopdeckdb/cia_import.py`, used by both the
`import_cia` and `watch_intake` management commands.

### Proxy Architecture

The mitmproxy container (port 8888) replaces Charles Proxy. The addon script at `proxy/addon.py` routes by hostname:
- `*.nintendowifi.net` → Flask container (SOAP/CDN)
- `*.nintendo.net` → Django container (API/metadata)
- All other traffic passes through to the internet.

## Local Development (without Docker)

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser

# Terminal 1
python manage.py runserver

# Terminal 2
python main.py
```

All settings in `shopdeck/settings.py` read from environment variables with fallback defaults, so local dev works without any `.env` file.

## Key Domain Concepts

- **Client3DS** — represents a registered 3DS console, identified by `consoleid`. Each has a balance, region, language, and device token.
- **Title** — a game/application with a 16-char title ID (`tid`), linked to a publisher, genre, platform, and category.
- **ownedTitle** / **ownedTicket** — ownership records linking a Client3DS to purchased titles or DLC items. Tickets are generated with random IDs using `os.urandom`.
- **eTicket generation** (in `ecs.py`) — binary ticket files are constructed by patching `basetik.bin` with the title ID, ticket ID, console ID, and account ID at specific byte offsets.
- **Session management** — the Ninja API uses Django's `SessionStore` with cookie name `JSESSIONID`. Sessions are keyed by `deviceid`.
- **SOAP parsing** — Flask blueprints parse incoming XML with `xmltodict` and render XML responses using Jinja2 templates in `templates/`.

## Templates

- `templates/` — XML response templates for SOAP services (ECS, IAS, CAS).
- `webtemplates/` — HTML templates for the Django web portal (configured as `DIRS` in Django `TEMPLATES` setting).

## Database

Docker uses PostgreSQL (required — `metadata/views.py` imports `django.contrib.postgres.fields`). Local dev falls back to SQLite if `POSTGRES_DB` env var is not set, but some metadata features will not work without PostgreSQL.
