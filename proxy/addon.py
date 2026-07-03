import os
from mitmproxy import http

FLASK_HOST = "flask"
FLASK_PORT = 5000
DJANGO_HOST = "django"
DJANGO_PORT = 8000

# Temporary debug capture: dump connects, requests, full bodies, and errors to
# stdout (visible via `docker compose logs proxy`). Set PROXY_CAPTURE=0 to
# disable without rebuilding. Defaults on while we diagnose the eShop flow.
CAPTURE = os.environ.get("PROXY_CAPTURE", "1") not in ("0", "false", "False", "")
MAX_BODY = 4096
TEXT_HINTS = ("json", "xml", "text", "html")


def http_connect(flow: http.HTTPFlow):
    # Fires for every HTTPS tunnel the console opens, even if no request ever
    # completes — reveals the target host of a failing/pass-through call.
    if CAPTURE:
        print(f"\n>>> CONNECT {flow.request.host}:{flow.request.port}", flush=True)


def request(flow: http.HTTPFlow):
    host = flow.request.pretty_host
    # Remember the real Nintendo hostname before we rewrite it, so later log
    # lines show e.g. ninja.ctr.shop.nintendo.net instead of the internal target.
    flow.metadata["orig_host"] = host

    # Log on arrival so requests that never get a response are still visible.
    if CAPTURE:
        print(f">>> {flow.request.method} {host}{flow.request.path}", flush=True)

    # The 3DS connection test (conntest.nintendowifi.net) must reach the real
    # Nintendo endpoint. The console doesn't just check for a 200 — it validates
    # the "X-Organization: Nintendo" response header, and treats its absence as a
    # captive portal / no-internet condition. Per the development-setup wiki, only
    # the eShop hostnames are redirected; conntest passes straight through to the
    # internet so the console gets the genuine response (header included).
    if host == "conntest.nintendowifi.net":
        return

    if "nintendowifi.net" in host:
        flow.request.host = FLASK_HOST
        flow.request.port = FLASK_PORT
        flow.request.scheme = "http"
    elif "nintendo.net" in host:
        flow.request.host = DJANGO_HOST
        flow.request.port = DJANGO_PORT
        flow.request.scheme = "http"


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
    # Fires when a flow fails without a normal response (connect/TLS/read error).
    if not CAPTURE:
        return
    try:
        host = flow.metadata.get("orig_host", getattr(flow.request, "pretty_host", "?"))
        path = getattr(flow.request, "path", "")
        print(f"\n!!! FLOW ERROR {host}{path}: {flow.error}", flush=True)
    except Exception as e:
        print(f"[capture error] {e}", flush=True)
