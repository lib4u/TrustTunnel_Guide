# TrustTunnel Guide

[Русский](README.md) · [Manual installation](docs/manual-install.en.md)

## 1. What is TrustTunnel?

[TrustTunnel](https://github.com/TrustTunnel/TrustTunnel) is an open-source VPN protocol and server developed by the AdGuard team. It carries traffic over HTTPS using HTTP/2 or HTTP/3, supports TCP and UDP inside the tunnel, and lets you operate your own endpoint. [Official clients](https://github.com/TrustTunnel/TrustTunnel#clients) support importing connection details.

This recipe also installs a real nginx origin at `127.0.0.1:8081`. Regular browser requests receive a loading page. Authenticated VPN traffic is forwarded to the internet. This does not guarantee availability on every network or prevent blocking the server IP.

## 2. Manual server installation

Follow the [manual guide](docs/manual-install.en.md). The complete service and nginx templates are in [templates](templates).

Both methods require a clean VPS running Ubuntu 22.04/24.04 or Debian 12/13 with systemd, x86_64 or ARM64, root SSH access, and a domain pointing directly to the VPS interface's public IPv4 address. Remove AAAA records and disable any CDN proxy. Open inbound TCP 80, TCP 443 and UDP 443 in your provider firewall. Port 8081 must also be free locally.

The recipe uses IPv4; NAT and existing nginx installations need separate configuration. TCP 80 must remain available for certificate renewal.

## 3. TrustTunnel Installer

Download this repository, open its directory and run:

```bash
bash install.sh
```

Choose **2) English** at startup. Use the arrow keys and Enter to fill in the server form; press `q` to quit. The TUI is plain Bash: no gum, dialog or local Python required. SSH uses your key or prompts for the server password. Requires Bash, OpenSSH and tar on Linux, macOS or Windows/WSL. Running the installer accepts the [Let's Encrypt terms](https://letsencrypt.org/repository/).

For unattended language selection:

```bash
bash install.sh --lang en \
  --server root@203.0.113.10 \
  --domain tt.example.com
```

Optional flags: `--identity ~/.ssh/id_ed25519`, `--ssh-port 2222`, `--output ./access`.

The certificate's service email is generated and saved on the server automatically.

The installer prints the **domain, port, username, password and `tt://` link** in the terminal. It also saves `access.txt`, `connection.txt`, `connection.png` (QR code) and `endpoint.toml` **on your computer**, in `access/<domain>.<suffix>/`. These files contain credentials: file permissions are `600`, directory permissions are `700`, and `access/` is gitignored.

Exports are streamed over SSH without being saved on the VPS. The server keeps the working `credentials.toml` required for TrustTunnel authentication; installer metadata does not contain the password. A repeat installation removes export files and duplicate metadata passwords left by older installer versions.

The installer provisions the official endpoint, verifies its SHA-256, installs nginx with the website, obtains and tests renewal of the certificate, enables systemd services, and checks the HTTPS response. It adds the necessary rules to an already active UFW firewall. System utilities retain their own output language.

Repeated installation with the same domain/version preserves credentials and custom configs, and restarts the services. Version upgrades and user changes are covered by [maintenance](docs/maintenance.md) (Russian). Use an [official client](https://github.com/TrustTunnel/TrustTunnelFlutterClient#server-configuration) to import the link/QR and verify the actual VPN from your network.

Pinned endpoint: [1.1.0](https://github.com/TrustTunnel/TrustTunnel/releases/tag/v1.1.0). [Versions and hashes](versions.env) · [Tests](tests/README.md).
