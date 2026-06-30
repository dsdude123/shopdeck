FROM mitmproxy/mitmproxy
COPY addon.py /addon/addon.py
CMD ["mitmdump", "--mode", "regular", "--listen-port", "8888", "-s", "/addon/addon.py", "--set", "block_global=false"]
