# Verification

Fast checks (Python 3.11+ for the test runner, Bash):

```bash
bash -n install.sh server-install.sh lib/common.sh lib/messages.sh lib/ui.sh templates/renew-hook.sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
shellcheck -x install.sh server-install.sh lib/common.sh lib/messages.sh lib/ui.sh templates/renew-hook.sh
```

These cover RU/EN help, rejected shell/SSH injection inputs, credential preservation, removal of legacy password copies, exports assembled in memory, export normalization, and real terminal interaction: language selection, arrow navigation, `q`/Ctrl-C and cursor restoration. Python and ShellCheck are development tools; the local installer/TUI does not require them.

Full integration test (Linux x86_64, Docker):

```bash
docker build -f tests/Dockerfile -t trusttunnel-installer-test:local .
python3 tests/integration.py
```

The test creates and removes a disposable privileged container with a private cgroup namespace to run actual systemd. It publishes SSH only to localhost and does not mount host directories or cgroups. All credentials and host keys belong to this disposable fixture.

It exercises real SSH upload/execution/download, official SHA-256-verified endpoint and client binaries, systemd units, nginx GET/HEAD responses, TLS verification, QR decoding, HTTP/2 and HTTP/3 VPN traffic, incorrect-password rejection, repeat installation, private output permissions, and TLS certificate reload through the actual deploy hook. It checks that the installer leaves no export files on the VPS and migrates older installations without changing their authentication password. The client fixture receives local exports through stdin; its temporary import/config files belong to the disposable test client.

The ACME boundary is simulated by `certbot-fixture.py` using a local test CA. **This test does not validate public DNS, real Let's Encrypt issuance/renewal or provider firewall reachability.** A live installation checks DNS, uses real Certbot, and performs a renewal dry run. The fixture downloads official binaries and requests `example.com` through the tunnel, so internet access is required.

The integration fixture uses Debian 12/x86_64. Other supported OS versions, ARM64, macOS/WSL terminals and mobile apps need separate environment testing; the fixture does not claim to cover them.
