# Manual installation of TrustTunnel and nginx

[← Back to README](../README.en.md) · [Русский](manual-install.md)

This guide sets up TrustTunnel on TCP/UDP 443, nginx with our loading page at `127.0.0.1:8081`, a Let's Encrypt certificate with automatic renewal, and connection credentials ready to use.

The commands assume a clean Ubuntu 22.04/24.04 or Debian 12/13 server, x86_64/ARM64, running systemd with a public IPv4 address on its network interface. The domain must have an A record pointing to that IPv4 address, with no AAAA record or CDN proxy. Allow inbound TCP 80, TCP 443 and UDP 443 in your VPS provider's firewall.

## Prepare the server and recipe files

From the downloaded repository directory **on your computer**, upload the templates and helper files to the server:

```bash
tar -czf - versions.env templates lib |
  ssh root@203.0.113.10 'mkdir -p /root/trusttunnel-guide; tar -xzf - -C /root/trusttunnel-guide'
ssh root@203.0.113.10
```

Run the remaining commands **as root on the server**, in the same SSH session. Replace the example domain:

```bash
umask 077
DOMAIN=tt.example.com
RECIPE=/root/trusttunnel-guide
cd "$RECIPE"
source versions.env

ss -lntup
getent ahostsv4 "$DOMAIN"
```

Check that TCP 80, TCP 443, UDP 443 and local TCP 8081 are free, and that DNS resolves to the correct IP. If the server already runs other VPN nodes or nginx, use a separate VPS or review its existing configuration first. This recipe will occupy those ports.

```bash
apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates curl certbot python3 python3-toml libgcc-s1 qrencode
```

If UFW is already enabled, add these rules:

```bash
ufw status
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
```

Enabling UFW and configuring SSH access depend on your existing setup. Local firewall rules do not replace the firewall settings in your hosting provider's panel.

## Download the official TrustTunnel release

The version and SHA-256 checksums come from [versions.env](../versions.env), which pins release 1.1.0. The following block stops if the architecture is unsupported or the checksum does not match:

```bash
(
  set -eu
  case $(uname -m) in
    x86_64) ARCH=x86_64; HASH=$TT_SHA256_X86_64 ;;
    aarch64) ARCH=aarch64; HASH=$TT_SHA256_AARCH64 ;;
    *) echo 'Unsupported architecture' >&2; exit 1 ;;
  esac
  ASSET="trusttunnel-v$TT_VERSION-linux-$ARCH"
  WORK=$(mktemp -d)
  trap 'rm -rf "$WORK"' EXIT
  curl -fSL --retry 3 \
    "https://github.com/TrustTunnel/TrustTunnel/releases/download/v$TT_VERSION/$ASSET.tar.gz" \
    -o "$WORK/endpoint.tar.gz"
  printf '%s  %s\n' "$HASH" "$WORK/endpoint.tar.gz" | sha256sum -c -
  tar -xzf "$WORK/endpoint.tar.gz" -C "$WORK"
  install -d -m 700 /opt/trusttunnel
  install -m 755 "$WORK/$ASSET/trusttunnel_endpoint" /opt/trusttunnel/trusttunnel_endpoint
  install -m 644 "$WORK/$ASSET/LICENSE" /opt/trusttunnel/UPSTREAM-LICENSE
  /opt/trusttunnel/trusttunnel_endpoint --version
)
```

The expected version is `1.1.0`. If this block fails, fix the error before continuing.

## Obtain a certificate

Certbot temporarily binds to port 80. Running it with `--agree-tos` accepts the [Let's Encrypt terms](https://letsencrypt.org/repository/). A service email address is generated on the server:

```bash
EMAIL="acme-$(tr -d '-' </proc/sys/kernel/random/uuid)@$DOMAIN"
certbot certonly --standalone --non-interactive --agree-tos \
  --email "$EMAIL" --cert-name "$DOMAIN" -d "$DOMAIN"
```

Check that `fullchain.pem` and `privkey.pem` exist:

```bash
ls -l "/etc/letsencrypt/live/$DOMAIN/"
```

If issuance fails, check DNS, external access to port 80, and any AAAA records. Obtain a certificate before starting the service.

## Create a user and configuration files

Generate a random username and password locally on the server. Run this block once for a new installation:

```bash
cd /opt/trusttunnel
TT_USER="tt_$(python3 -c 'import secrets; print(secrets.token_hex(4))')"
TT_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
cat > credentials.toml <<EOF
[[client]]
username = "$TT_USER"
password = "$TT_PASSWORD"
EOF
unset TT_PASSWORD

cat > hosts.toml <<EOF
[[main_hosts]]
hostname = "$DOMAIN"
cert_chain_path = "/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
private_key_path = "/etc/letsencrypt/live/$DOMAIN/privkey.pem"
EOF

printf '%s\n' "$DOMAIN" > domain
touch rules.toml
install -m 600 "$RECIPE/templates/vpn.toml" vpn.toml
chmod 600 credentials.toml hosts.toml rules.toml domain
```

Contents of [vpn.toml](../templates/vpn.toml):

```toml
listen_address = "0.0.0.0:443"
credentials_file = "credentials.toml"
rules_file = "rules.toml"
ipv6_available = false
allow_private_network_connections = false
auth_failure_status_code = 407

[listen_protocols.http1]
[listen_protocols.http2]
[listen_protocols.quic]

[reverse_proxy]
server_address = "127.0.0.1:8081"
path_mask = "/"
```

`allow_private_network_connections = false` prevents VPN clients from connecting to private addresses. In version 1.1.0, the reverse proxy can still reach its explicitly configured local nginx origin. [Release notes for this fix](https://github.com/TrustTunnel/TrustTunnel/releases/tag/v1.1.0).

Do not add `non_connect_auth_failure_status_code`: that response can take precedence over the reverse proxy page. HTTP/2 uses TCP and HTTP/3 uses UDP, so both transports need port 443.

## Install nginx with the website

Install the package first. Its default service may start automatically on port 80; disable it and use a separate service with our configuration:

```bash
apt-get install -y --no-install-recommends nginx
systemctl disable --now nginx.service
install -m 600 "$RECIPE/templates/nginx.conf" /opt/trusttunnel/nginx.conf
install -d -m 755 /var/www/trusttunnel
install -m 644 "$RECIPE/templates/index.html" /var/www/trusttunnel/index.html
```

The [nginx configuration](../templates/nginx.conf) listens only on `127.0.0.1:8081`. Nginx handles the static page, `HEAD` requests, caching and other HTTP responses. Unknown paths return the same loading page. Access logging is disabled; errors go to the service journal with storage limits.

You can replace `/var/www/trusttunnel/index.html` with your own static page. For installations managed by the automatic installer, rerunning it preserves an existing page.

## Start the services and limit journal storage

The [TrustTunnel service](../templates/trusttunnel.service) runs the official binary, and the [website service](../templates/trusttunnel-site.service) runs nginx. Both write to a separate `trusttunnel` journal namespace: persistent storage is limited to 100 MB, runtime storage to 50 MB, and retention to 7 days. These are journald storage limits, rather than an exact size limit for each individual file.

```bash
install -m 644 "$RECIPE/templates/trusttunnel.service" /etc/systemd/system/trusttunnel.service
install -m 644 "$RECIPE/templates/trusttunnel-site.service" /etc/systemd/system/trusttunnel-site.service
install -m 644 "$RECIPE/templates/journald.conf" /etc/systemd/journald@trusttunnel.conf
systemctl daemon-reload
systemctl enable --now trusttunnel-site.service trusttunnel.service
systemctl status trusttunnel-site.service trusttunnel.service --no-pager
```

Check the HTTPS response from the server, then from your computer. Set `DOMAIN` again if you use another terminal. Run `ss` on the server to inspect its listening ports:

```bash
curl -i "https://$DOMAIN/"
curl -I "https://$DOMAIN/any-path"
ss -lntup
```

Expect `200 OK`, the loading page, and no `Proxy-Authenticate` header on a regular GET/HEAD request. Nginx should listen only on loopback:8081, and TrustTunnel on TCP/UDP 443. Keep TLS verification enabled; do not use `curl -k` for this check.

## Configure certificate renewal

```bash
install -d -m 755 /etc/letsencrypt/renewal-hooks/deploy
install -m 700 "$RECIPE/templates/renew-hook.sh" /etc/letsencrypt/renewal-hooks/deploy/trusttunnel
systemctl enable --now certbot.timer
systemctl reload trusttunnel.service
certbot renew --cert-name "$DOMAIN" --dry-run --no-random-sleep-on-renew
```

The [deploy hook](../templates/renew-hook.sh) reloads TLS settings using SIGHUP only after this domain's certificate is renewed. Password changes require a process restart; SIGHUP reloads TLS settings. [Official certificate renewal guide](https://github.com/TrustTunnel/TrustTunnel/blob/v1.1.0/CERT_RENEWAL.md).

## Export the link, username and password

```bash
python3 -B "$RECIPE/lib/export.py" --lang en --format text --username "$TT_USER"
```

The command prints the domain, port, username, password and ready-to-use `tt://` link directly in the terminal. It does not create connection files on the server. If you opened a new SSH session, set `RECIPE` again and read the value for `TT_USER` from `/opt/trusttunnel/credentials.toml`.

To download the files and QR code **to your computer**, open a separate terminal on that computer and run:

```bash
(
  set -euo pipefail
  umask 077
  mkdir -p access
  RESULT=$(mktemp -d ./access/trusttunnel.XXXXXXXX)
  ssh root@203.0.113.10 \
    'python3 -B /root/trusttunnel-guide/lib/export.py --lang en --format tar' |
    tar -xzf - -C "$RESULT"
  printf 'Connection files and QR code: %s\n' "$RESULT"
)
```

The archive is assembled in memory and streamed over SSH. Only your computer receives `access.txt`, `connection.txt`, `connection.png` and `endpoint.toml`; the VPS keeps its working authentication file, `credentials.toml`. For a manual installation, omitting `--username` selects the first user in that file.

[export.py](../lib/export.py) uses the official exporter and [normalize-export.py](../lib/normalize-export.py) to set `has_ipv6 = false` in both formats: the official 1.1.0 exporter sets it to `true` regardless of the server configuration. Other link fields are preserved. [Upstream code](https://github.com/TrustTunnel/TrustTunnel/blob/v1.1.0/lib/src/client_config.rs).

**[Client setup (Russian) →](clients.md)** · **[Maintenance (Russian) →](maintenance.md)**

A manual installation does not create the automatic installer's management marker. Therefore, `install.sh` will not take over this installation if you run it later. Maintain it using the steps above and the maintenance guide.
