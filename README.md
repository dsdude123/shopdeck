# Shopdeck

A replacement server for the Nintendo 3DS eShop. Reimplements the eShop backend so 3DS consoles can browse, purchase, and download digital content from a custom storefront.

## Quick Start (Docker)

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- A hacked 3DS with [Luma3DS](https://github.com/LumaTeam/Luma3DS) and the [3DS SSL Patch](https://github.com/InternalLoss/3DS-SSL-Patch)

### Server Setup

```bash
# Clone the repo
git clone https://github.com/dsdude123/shopdeck.git
cd shopdeck

# Configure environment
cp .env.example .env
# Edit .env — at minimum set DJANGO_SECRET_KEY and POSTGRES_PASSWORD

# Start everything
docker compose up -d --build
```

This starts 5 services:
- **PostgreSQL** database
- **Django** (API + web portal) via gunicorn
- **Flask** (SOAP/XML services) via gunicorn
- **nginx** reverse proxy for browser access (port 80)
- **mitmproxy** forward proxy for 3DS traffic (port 8888)

### 3DS Setup

1. Install the [3DS SSL Patch](https://github.com/InternalLoss/3DS-SSL-Patch) — press SELECT at boot, enable "Enable external FIRMs and modules" and "Enable game patching" in the Luma3DS menu
2. Go to **System Settings > Internet Settings**, select your connection, tap **Change Settings**
3. Go to page 2, tap **Proxy Settings**, set to **Yes**
4. Enter your server's IP address as the proxy host, port `8888`
5. Save and return to the home menu
6. Open the Nintendo eShop — it should connect to your Shopdeck server

### Web Portal

Browse to `http://<server-ip>/` to access the web portal. The admin panel is at `http://<server-ip>/admin/` — it has no login and grants full superuser access by default. This is intended for trusted local networks only; **do not expose this server to the public Internet.**

### Managing Content

Use `cia-helper.py` to import 3DS CIA files into the CDN:

```bash
docker compose exec django python cia-helper.py <path-to-file.cia>
```

## Local Development (without Docker)

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser

# Terminal 1 — Django server
python manage.py runserver

# Terminal 2 — Flask server
python main.py
```

When running without Docker, configure `SOAP_URL` and `METADATA_API_URL` in `shopdeck/settings.py` and use [Charles Proxy](https://charlesproxy.com) or similar to route 3DS traffic to your local servers.

## Architecture

Two servers run simultaneously sharing the same database:

- **Django** (`manage.py`) — JSON APIs (`/ninja/ws/`, `/samurai/ws/<region>/`), web portal (`/`), admin (`/admin/`)
- **Flask** (`main.py`) — SOAP/XML services (`/ecs/`, `/ias/`, `/cas/`), CDN (`/ccs/`), asset serving (`/assets/`)

## Configuration

All settings can be configured via environment variables (see `.env.example`). When running without Docker, the defaults in `shopdeck/settings.py` are used.

| Variable | Description | Default |
|---|---|---|
| `DJANGO_SECRET_KEY` | Django secret key | insecure dev key |
| `POSTGRES_PASSWORD` | Database password | *(required in Docker)* |
| `SOAP_URL` | Hostname for SOAP services | `ecs.c.shop.nintendowifi.net` |
| `METADATA_API_URL` | Hostname for API/metadata | `ninja.ctr.shop.nintendo.net` |
| `WEBUI_NAME` | Name shown in web portal | `Shopdeck` |
| `IN_MAINTENANCE` | Enable maintenance mode | `False` |
| `ADMIN_USERNAME` | Username of the auto-created admin superuser | `admin` |

## Legal Disclaimer

Shopdeck is a server application only. It does not include, distribute, or provide any game ROMs, CIAs, or other copyrighted content. You are responsible for ensuring that any content you host or use with Shopdeck has been legally acquired. This project is intended for use with your own legally owned digital content.

## Credits

- ZeroSkill — JSON responses from official Nintendo eShop servers, documentation, and help getting tickets working
- DoggoITA — first contributor, rankings, new webUI, and votes
