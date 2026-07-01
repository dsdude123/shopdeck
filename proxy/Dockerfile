# Pin to mitmproxy 9.0.1: it bundles cryptography 38.x, which links OpenSSL
# 1.1.1. The 3DS only speaks TLS 1.0/1.1 with old RSA / SHA-1 ciphers, and
# newer mitmproxy images ship an OpenSSL (3.x) that has those protocols
# compiled out entirely — it can't even negotiate them, and setting a legacy
# tls_version_client_min makes mitmproxy crash on startup. OpenSSL 1.1.1 still
# supports them, so the eShop's HTTPS handshakes can complete and its requests
# reach the addon (instead of only the plaintext connection test showing up
# while the console reports 007-2705).
FROM mitmproxy/mitmproxy:9.0.1
COPY addon.py /addon/addon.py
# Lower the accepted TLS floor to TLS 1.0 (the console negotiates 1.1) and drop
# the OpenSSL security level to 0 so the weak legacy ciphers it offers are
# negotiable.
# connection_strategy=lazy: the addon rewrites every request to our own
# django/flask backends, so mitmproxy must NOT eagerly connect to the real
# (dead) Nintendo servers first — doing so just spams "Server TLS handshake
# failed / certificate verify failed" before the request is rerouted. Lazy
# defers the upstream connection until after the addon has rewritten the host.
CMD ["mitmdump", "--mode", "regular", "--listen-port", "8888", \
     "-s", "/addon/addon.py", \
     "--set", "block_global=false", \
     "--set", "connection_strategy=lazy", \
     "--set", "tls_version_client_min=TLS1", \
     "--set", "ciphers_client=DEFAULT@SECLEVEL=0"]
