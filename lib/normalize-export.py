#!/usr/bin/env python3
"""Align native 1.1.0 exports with this recipe's IPv4-only endpoint.

Upstream lib/src/client_config.rs hardcodes has_ipv6=true. Replace only tag 0x04
in its native link, following upstream DEEP_LINK.md; preserve all other fields.
"""
import base64
from pathlib import Path
import re
import sys


def read_varint(data, offset):
    if offset >= len(data):
        raise ValueError("Truncated QUIC varint")
    size = 1 << (data[offset] >> 6)
    end = offset + size
    if end > len(data):
        raise ValueError("Truncated QUIC varint")
    return int.from_bytes(data[offset:end], "big") & ((1 << (size * 8 - 2)) - 1), end


def ipv4_link(link):
    if not link.startswith("tt://?"):
        raise ValueError("Expected a tt://? link")
    encoded = link[6:]
    data = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
    offset = 0
    result = bytearray()
    version = None
    while offset < len(data):
        start = offset
        tag, offset = read_varint(data, offset)
        size, offset = read_varint(data, offset)
        end = offset + size
        if end > len(data):
            raise ValueError("Truncated TLV field")
        if tag == 0:
            version = data[offset:end]
        if tag != 4:
            result.extend(data[start:end])
        offset = end
    if version != b"\x01":
        raise ValueError("Unsupported deep-link version")
    result.extend(b"\x04\x01\x00")
    return "tt://?" + base64.urlsafe_b64encode(result).decode().rstrip("=")


def normalize_exports(link_text, config_text):
    # The upstream CLI appends a human-readable QR website hint after the URI.
    links = [line.strip() for line in link_text.splitlines() if line.startswith('tt://?')]
    if len(links) != 1:
        raise ValueError('Expected exactly one exported link')
    link = ipv4_link(links[0])
    config, count = re.subn(r'^has_ipv6\s*=\s*(true|false)\s*$', 'has_ipv6 = false',
                           config_text, flags=re.MULTILINE)
    if count != 1:
        raise ValueError('Expected one has_ipv6 field in the native TOML export')
    return link + "\n", config


if __name__ == "__main__":
    link_path, config_path = map(Path, sys.argv[1:])
    link, config = normalize_exports(link_path.read_text(), config_path.read_text())
    link_path.write_text(link)
    config_path.write_text(config)
