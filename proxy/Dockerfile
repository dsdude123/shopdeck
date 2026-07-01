FROM mitmproxy/mitmproxy
COPY addon.py /addon/addon.py
# The 3DS only speaks TLS 1.1 with old RSA / SHA-1 ciphers. Modern mitmproxy
# (built on OpenSSL 3.x) refuses that ClientHello by default, so the eShop's
# HTTPS handshakes fail before any request is parsed — which is why only the
# plaintext connection test (port 80, no TLS) ever shows up in the logs while
# the console reports 007-2705. Lower the accepted TLS floor to SSL3 (this also
# enables TLS 1.0/1.1) and drop the OpenSSL security level to 0 so the weak
# legacy ciphers the console offers are negotiable.
CMD ["mitmdump", "--mode", "regular", "--listen-port", "8888", \
     "-s", "/addon/addon.py", \
     "--set", "block_global=false", \
     "--set", "tls_version_client_min=SSL3", \
     "--set", "ciphers_client=DEFAULT@SECLEVEL=0"]
