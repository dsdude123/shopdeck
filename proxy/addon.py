import os
from mitmproxy import http

FLASK_HOST = "flask"
FLASK_PORT = 5000
DJANGO_HOST = "django"
DJANGO_PORT = 8000

# The console was advertised exactly these two hosts in service_hosts; they are
# the only ones we intercept and route to our backends.
SOAP_HOST = os.environ.get("SOAP_URL", "ecs.c.shop.nintendowifi.net")
META_HOST = os.environ.get("METADATA_API_URL", "ninja.ctr.shop.nintendo.net")

# The 3DS connection test. We serve it locally so the setup never depends on the
# real Nintendo host being reachable. The console only checks for HTTP 200 and
# the "X-Organization: Nintendo" response header (its absence reads as a captive
# portal / no-internet condition).
CONNTEST_HOST = "conntest.nintendowifi.net"
CONNTEST_BODY = (
    b'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" '
    b'"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n'
    b"            <html>\n"
    b"            <head>\n"
    b"              <title>HTML Page</title>\n"
    b"            </head>\n"
    b'            <body bgcolor="#FFFFFF">\n'
    b"            This is test.html page\n"
    b"            </body>\n"
    b"            </html>\n"
)

# Hosts we intercept rather than kill. Everything else the console pings
# (nus NetUpdate, nppl privacy policy, the CDNs, account.nintendo.net,
# mii-secure, ...) carries no data the eShop uses, so we drop those connections
# locally — no real-Nintendo round-trip, and no ~50s of connect timeouts.
ALLOWED_HOSTS = {SOAP_HOST, META_HOST, CONNTEST_HOST}

# Temporary debug capture: dump connects, requests, full bodies, and errors to
# stdout (visible via `docker compose logs proxy`). Set PROXY_CAPTURE=0 to
# disable without rebuilding.
CAPTURE = os.environ.get("PROXY_CAPTURE", "1") not in ("0", "false", "False", "")
MAX_BODY = 4096
TEXT_HINTS = ("json", "xml", "text", "html")


def running():
    print(
        f"[addon] intercepting {SOAP_HOST} + {META_HOST}; serving {CONNTEST_HOST} "
        f"locally; dropping every other host",
        flush=True,
    )


def http_connect(flow: http.HTTPFlow):
    # Pre-TLS decision point. Let the eShop hosts (and conntest, though it's
    # HTTP) through; drop every other host before any handshake so nothing
    # leaves for real Nintendo and the console fails fast instead of waiting on
    # a connect timeout.
    if CAPTURE:
        print(f"\n>>> CONNECT {flow.request.host}:{flow.request.port}", flush=True)
    if flow.request.host not in ALLOWED_HOSTS:
        flow.kill()


def request(flow: http.HTTPFlow):
    host = flow.request.pretty_host
    flow.metadata["orig_host"] = host

    if CAPTURE:
        print(f">>> {flow.request.method} {host}{flow.request.path}", flush=True)

    # Serve the connection test locally (no upstream).
    if host == CONNTEST_HOST:
        flow.response = http.Response.make(
            200,
            CONNTEST_BODY,
            {"Content-Type": "text/html", "X-Organization": "Nintendo"},
        )
        return

    if host == SOAP_HOST:
        flow.request.host = FLASK_HOST
        flow.request.port = FLASK_PORT
        flow.request.scheme = "http"
    elif host == META_HOST:
        flow.request.host = DJANGO_HOST
        flow.request.port = DJANGO_PORT
        flow.request.scheme = "http"
    else:
        # Any non-eShop plain-HTTP request that slipped past http_connect.
        flow.kill()


def response(flow: http.HTTPFlow):
    if not CAPTURE:
        return
    try:
        host = flow.metadata.get("orig_host", flow.request.pretty_host)
        status = flow.response.status_code
        print(f"\n### {flow.request.method} {host}{flow.request.path} -> {status}", flush=True)

        if flow.request.method in ("POST", "PUT") and flow.request.content:
            body = flow.request.get_text(strict=False) or ""
            print("--- REQ BODY:\n" + body[:MAX_BODY], flush=True)

        ct = flow.response.headers.get("content-type", "")
        if ct == "" or any(h in ct for h in TEXT_HINTS):
            body = flow.response.get_text(strict=False) or ""
            print("--- RESP BODY:\n" + body[:MAX_BODY], flush=True)
        else:
            size = len(flow.response.raw_content or b"")
            print(f"--- RESP BODY: <{size} bytes {ct}>", flush=True)
    except Exception as e:
        print(f"[capture error] {e}", flush=True)


def error(flow: http.HTTPFlow):
    # Fires when a flow fails without a normal response (connect/TLS/read error,
    # or our own kill()). Only log the hosts we actually intercept, so the
    # dropped firmware pings don't spam the log.
    if not CAPTURE:
        return
    try:
        host = flow.metadata.get("orig_host", getattr(flow.request, "pretty_host", "?"))
        if host in ALLOWED_HOSTS:
            path = getattr(flow.request, "path", "")
            print(f"\n!!! FLOW ERROR {host}{path}: {flow.error}", flush=True)
    except Exception as e:
        print(f"[capture error] {e}", flush=True)
