from mitmproxy import http

FLASK_HOST = "flask"
FLASK_PORT = 5000
DJANGO_HOST = "django"
DJANGO_PORT = 8000


def request(flow: http.HTTPFlow):
    host = flow.request.pretty_host

    if host == "conntest.nintendowifi.net":
        flow.response = http.Response.make(200, b"", {"Content-Type": "text/plain"})
        return

    if "nintendowifi.net" in host:
        flow.request.host = FLASK_HOST
        flow.request.port = FLASK_PORT
        flow.request.scheme = "http"
    elif "nintendo.net" in host:
        flow.request.host = DJANGO_HOST
        flow.request.port = DJANGO_PORT
        flow.request.scheme = "http"
