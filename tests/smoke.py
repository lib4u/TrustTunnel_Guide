#!/usr/bin/env python3
"""Run inside the disposable systemd container after installation."""
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.request
import toml


def run(*args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, **kwargs).stdout


root = Path('/opt/trusttunnel')
files = {name: base64.b64decode(value) for name, value in json.load(sys.stdin).items()}
endpoint = toml.loads(files['endpoint.toml'].decode())
assert not (root / 'client').exists()
assert 'password' not in json.loads((root / '.installer-state.json').read_text())
assert endpoint['has_ipv6'] is False
assert endpoint['skip_verification'] is False
assert run('systemctl', 'is-active', 'trusttunnel', 'trusttunnel-site').split() == ['active', 'active']
assert '127.0.0.1:8081' in run('ss', '-Hlnt', 'sport = :8081')
assert '0.0.0.0:8081' not in run('ss', '-Hlnt', 'sport = :8081')

for path in ('/', '/some/deep/path'):
    page = run('curl', '-fsS', '--noproxy', '*', f'https://tt.test{path}')
    assert page == Path('/var/www/trusttunnel/index.html').read_text()
    headers = run('curl', '-fsSI', '--noproxy', '*', f'https://tt.test{path}').lower()
    assert '200' in headers.splitlines()[0] and 'proxy-authenticate' not in headers
decoded_qr = subprocess.run(['zbarimg', '--raw', '-q', '-'], input=files['connection.png'],
                            capture_output=True, check=True).stdout.decode().strip()
assert decoded_qr == files['connection.txt'].decode().strip()
print('PASS: systemd, verified TLS, nginx GET/HEAD, loopback origin and QR decode', flush=True)

with tempfile.TemporaryDirectory(prefix='tt-client-') as directory:
    work = Path(directory)
    # Only the test client needs a temporary import file; the installer never writes it on the VPS.
    (work / 'endpoint.toml').write_bytes(files['endpoint.toml'])
    asset = 'trusttunnel_client-v1.1.5-linux-x86_64'
    archive = work / 'client.tar.gz'
    urllib.request.urlretrieve(f'https://github.com/TrustTunnel/TrustTunnelClient/releases/download/v1.1.5/{asset}.tar.gz', archive)
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == '759557812e7a280183f720e373b374f3fccb95758532cf8a94bea903dec2ca96'
    run('tar', '-xzf', str(archive), '-C', str(work), f'{asset}/trusttunnel_client', f'{asset}/setup_wizard')
    binary = work / asset / 'trusttunnel_client'
    full = work / 'client.toml'
    run(str(work / asset / 'setup_wizard'), '--mode', 'non-interactive',
        '--endpoint_config', str(work / 'endpoint.toml'), '--settings', str(full))
    config = toml.load(full)
    # These are disposable test credentials, never production accounts.
    run(str(work / asset / 'setup_wizard'), '--mode', 'non-interactive',
        '--deeplink', files['connection.txt'].decode().strip(), '--settings', str(work / 'link.toml'))
    from_link = toml.load(work / 'link.toml')
    assert from_link['endpoint']['has_ipv6'] is False
    assert from_link['endpoint']['password'] == endpoint['password']
    assert config['endpoint']['has_ipv6'] is False
    assert config['endpoint']['password'] == endpoint['password']
    config['loglevel'] = 'warn'
    config['killswitch_enabled'] = False
    config['listener'] = {'socks': {'address': '127.0.0.1:1080'}}
    config['endpoint']['dns_upstreams'] = ['1.1.1.1']

    for protocol in ('http2', 'http3'):
        config['endpoint']['upstream_protocol'] = protocol
        config['endpoint']['password'] = endpoint['password']
        full.write_text(toml.dumps(config))
        with (work / 'client.log').open('w') as log:
            process = subprocess.Popen([str(binary), '-c', str(full)], stdout=log, stderr=log)
            try:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError('Client exited during startup: ' + (work / 'client.log').read_text()[-1500:])
                    try:
                        with socket.create_connection(('127.0.0.1', 1080), timeout=0.1):
                            break
                    except OSError:
                        time.sleep(0.1)
                result = subprocess.run(['curl', '-fsS', '--max-time', '35', '--noproxy', '',
                                         '--socks5-hostname', '127.0.0.1:1080', 'https://example.com'],
                                        capture_output=True, text=True)
                if result.returncode or 'Example Domain' not in result.stdout:
                    raise RuntimeError(f'{protocol} tunnel failed: {result.stderr}; ' + (work / 'client.log').read_text()[-1500:])
                print(f'PASS: {protocol} real VPN request', flush=True)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

auth_context = ssl.create_default_context()
auth_context.set_alpn_protocols(['http/1.1'])
authorization = base64.b64encode((endpoint['username'] + ':incorrect-test-password').encode()).decode()
with socket.create_connection(('127.0.0.1', 443), timeout=10) as tcp:
    with auth_context.wrap_socket(tcp, server_hostname='tt.test') as tls:
        tls.sendall(('CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n'
                     + f'Proxy-Authorization: Basic {authorization}\r\nUser-Agent: linux test\r\n\r\n').encode())
        rejected = http.client.HTTPResponse(tls)
        rejected.begin()
        assert rejected.status == 407, f'Expected authentication failure, got HTTP {rejected.status}'
print('PASS: incorrect password rejected by the endpoint (407)', flush=True)

# Verify that the real Certbot hook changes the certificate served over TLS.
context = ssl.create_default_context()
def peer_certificate():
    with socket.create_connection(('127.0.0.1', 443), timeout=5) as tcp:
        with context.wrap_socket(tcp, server_hostname='tt.test') as tls:
            return tls.getpeercert(binary_form=True)

before = peer_certificate()
certs = Path('/etc/letsencrypt/live/tt.test')
run('openssl', 'x509', '-req', '-in', '/tmp/test-ca/request.pem', '-CA', '/tmp/test-ca/cert.pem',
    '-CAkey', '/tmp/test-ca/key.pem', '-set_serial', '42', '-days', '2',
    '-out', str(certs / 'leaf.pem'), '-extfile', '/tmp/test-ca/extensions')
(certs / 'fullchain.pem').write_bytes((certs / 'leaf.pem').read_bytes() + Path('/tmp/test-ca/cert.pem').read_bytes())
run('/etc/letsencrypt/renewal-hooks/deploy/trusttunnel', env={**os.environ, 'RENEWED_LINEAGE': str(certs)})
for _ in range(30):
    if peer_certificate() != before:
        break
    time.sleep(0.1)
else:
    raise AssertionError('The renewal hook did not reload the served TLS certificate')
print('PASS: certificate rotation and live SIGHUP reload', flush=True)
