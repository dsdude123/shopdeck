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

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run Django server (API + Web Portal)
python manage.py runserver

# Run Flask server (SOAP services)
python main.py

# Database migrations
python manage.py makemigrations
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Django admin panel
# Available at /admin/ when Django server is running
```

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

Default is SQLite (`db.sqlite3`). The `requirements.txt` includes `psycopg2` for PostgreSQL support. The `metadata/views.py` imports `django.contrib.postgres.fields`, so some features may require PostgreSQL.
