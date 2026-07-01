from mitmproxy import http

FLASK_HOST = "flask"
FLASK_PORT = 5000
DJANGO_HOST = "django"
DJANGO_PORT = 8000


def request(flow: http.HTTPFlow):
    host = flow.request.pretty_host

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
