#!/usr/bin/env python3
"""Offline ACME boundary for disposable integration containers only."""
from pathlib import Path
import subprocess
import sys


def run(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


args = sys.argv[1:]
if "renew" in args:
    print("TEST ONLY: ACME renewal simulated; no public certificate requested.")
    sys.exit(0)

domain = args[args.index("--cert-name") + 1]
root = Path("/etc/letsencrypt/live") / domain
root.mkdir(parents=True, exist_ok=True)
if (root / "fullchain.pem").exists():
    sys.exit(0)
ca = Path("/tmp/test-ca")
ca.mkdir(exist_ok=True)
run("openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256",
    "-nodes", "-keyout", str(ca / "key.pem"), "-out", str(ca / "cert.pem"),
    "-days", "2", "-subj", "/CN=TrustTunnel Integration Test CA")
run("openssl", "req", "-new", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256",
    "-nodes", "-keyout", str(root / "privkey.pem"), "-out", str(ca / "request.pem"),
    "-subj", f"/CN={domain}")
(ca / "extensions").write_text(f"subjectAltName=DNS:{domain}\nextendedKeyUsage=serverAuth\n")
run("openssl", "x509", "-req", "-in", str(ca / "request.pem"), "-CA", str(ca / "cert.pem"),
    "-CAkey", str(ca / "key.pem"), "-CAcreateserial", "-days", "2", "-out", str(root / "leaf.pem"),
    "-extfile", str(ca / "extensions"))
(root / "fullchain.pem").write_bytes((root / "leaf.pem").read_bytes() + (ca / "cert.pem").read_bytes())
Path("/usr/local/share/ca-certificates/trusttunnel-test.crt").write_bytes((ca / "cert.pem").read_bytes())
run("update-ca-certificates")
print("TEST ONLY: local CA certificate issued.")
