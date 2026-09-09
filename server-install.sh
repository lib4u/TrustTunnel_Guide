#!/usr/bin/env bash
# Installed by install.sh over an authenticated SSH connection; also usable locally.
set -Eeuo pipefail
umask 077
export LC_ALL=C
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=lib/common.sh
source "$ROOT/lib/common.sh"
# shellcheck source=lib/messages.sh
source "$ROOT/lib/messages.sh"
# shellcheck source=versions.env
source "$ROOT/versions.env"

domain='' TT_LANG=''
while [[ $# -gt 0 ]]; do
    case $1 in
        --domain|--lang)
            require_value "$@"
            case $1 in --domain) domain=$2 ;; --lang) TT_LANG=$2 ;; esac
            shift 2 ;;
        *) die unknown "$1" ;;
    esac
done
select_language
validate_domain "$domain"
[[ $EUID -eq 0 ]] || die root_required
[[ -f /etc/os-release ]] || die os_missing
# shellcheck disable=SC1091
source /etc/os-release
case "$ID:$VERSION_ID" in
    ubuntu:22.04|ubuntu:24.04|debian:12|debian:13) ;;
    *) die os_unsupported "$ID:$VERSION_ID" ;;
esac
[[ -d /run/systemd/system ]] || die systemd_required
for cmd in ss ip flock; do command -v "$cmd" >/dev/null || die server_dependency "$cmd"; done
exec 9>/run/lock/trusttunnel-installer.lock
flock -n 9 || die locked
case $(uname -m) in
    x86_64) arch=x86_64; digest=$TT_SHA256_X86_64 ;;
    aarch64) arch=aarch64; digest=$TT_SHA256_AARCH64 ;;
    *) die arch_unsupported ;;
esac

base=/opt/trusttunnel
fresh=true
if [[ -e $base ]]; then
    [[ -f $base/.installer-state.json ]] || die existing_directory "$base"
    fresh=false
    if ! python3 - "$base/.installer-state.json" "$domain" "$TT_VERSION" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
if s.get('domain') != sys.argv[2] or s.get('version') != sys.argv[3]:
    sys.exit(1)
PY
    then die state_mismatch; fi
    # Do not silently replace a binary that was manually upgraded after installation.
    if [[ -f $base/trusttunnel_endpoint ]]; then
        if [[ $("$base/trusttunnel_endpoint" --version) != "$TT_VERSION" ]]; then die state_mismatch; fi
    fi
fi
if $fresh && [[ -n $(systemctl cat trusttunnel.service 2>/dev/null || true) ]]; then
    die existing_service
fi
if $fresh && [[ -e /etc/nginx/nginx.conf || -e /etc/systemd/system/trusttunnel-site.service ]]; then
    die nginx_exists
fi
for spec in 'tcp 80' 'tcp 443' 'udp 443' 'tcp 8081'; do
    read -r protocol port <<< "$spec"
    if ! $fresh && [[ $port != 80 ]]; then continue; fi
    if [[ $protocol == tcp ]]; then listeners=$(ss -H -ltn "sport = :$port");
    else listeners=$(ss -H -lun "sport = :$port"); fi
    [[ -z $listeners ]] || die busy_port "$port" "$protocol"
done

work=$(mktemp -d /tmp/trusttunnel-setup.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
trap 'printf "%s\n" "$(message failed)" >&2' ERR
run_quiet() {
    local status
    if "$@" > "$work/command.log" 2>&1; then return 0; else status=$?; fi
    tail -n 40 "$work/command.log" >&2
    return "$status"
}
stage() { local number=$1; shift; log "[$number/8] $(message "$@")"; }
stage 1 dependencies
export DEBIAN_FRONTEND=noninteractive
run_quiet apt-get update -qq
run_quiet apt-get install -y --no-install-recommends ca-certificates curl certbot python3 python3-toml libgcc-s1 qrencode

stage 2 dns_check
if ! python3 - "$domain" <<'PY'
import json, socket, subprocess, sys
domain = sys.argv[1]
local = {a['local'] for iface in json.loads(subprocess.check_output(['ip', '-j', '-4', 'addr']))
         for a in iface.get('addr_info', []) if a.get('scope') == 'global'}
try:
    resolved = {r[4][0] for r in socket.getaddrinfo(domain, 443, socket.AF_INET, socket.SOCK_STREAM)}
except socket.gaierror as error:
    sys.exit(f'DNS A lookup failed: {domain}: {error}')
if not resolved or not resolved.issubset(local):
    sys.exit(f'DNS A: {sorted(resolved)}; server IPv4: {sorted(local)}')
try:
    v6 = socket.getaddrinfo(domain, 443, socket.AF_INET6, socket.SOCK_STREAM)
except socket.gaierror as error:
    if error.errno not in (socket.EAI_NONAME, socket.EAI_ADDRFAMILY, socket.EAI_NODATA):
        raise
    v6 = []
if v6:
    sys.exit('DNS AAAA: ' + str(sorted({r[4][0] for r in v6})))
print('DNS OK')
PY
then die dns_failed; fi

if command -v ufw >/dev/null && ufw status | awk 'NR==1 {exit ($0 != "Status: active")}'; then
    log "$(message ufw)"
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow 443/udp
fi

stage 3 download "$TT_VERSION"
asset="trusttunnel-v$TT_VERSION-linux-$arch"
curl --fail --show-error --silent --location --retry 3 --connect-timeout 20 --max-time 300 \
    "https://github.com/TrustTunnel/TrustTunnel/releases/download/v$TT_VERSION/$asset.tar.gz" -o "$work/endpoint.tar.gz"
printf '%s  %s\n' "$digest" "$work/endpoint.tar.gz" | sha256sum -c -
tar -xzf "$work/endpoint.tar.gz" -C "$work" "$asset/trusttunnel_endpoint" "$asset/LICENSE"
"$work/$asset/trusttunnel_endpoint" --version

stage 4 certificate
install -d -m 755 /etc/letsencrypt
email_file=/etc/letsencrypt/trusttunnel-installer-email
if [[ ! -s $email_file ]]; then
    printf 'acme-%s@%s\n' "$(tr -d '-' </proc/sys/kernel/random/uuid)" "$domain" > "$email_file"
    chmod 600 "$email_file"
fi
email=$(cat "$email_file")
run_quiet certbot certonly --standalone --non-interactive --agree-tos --email "$email" \
    --cert-name "$domain" -d "$domain" --keep-until-expiring

install -d -m 700 "$base"
python3 "$ROOT/lib/configure.py" "$base" "$domain" "$TT_VERSION"
if [[ ! -f $base/vpn.toml ]]; then install -m 600 "$ROOT/templates/vpn.toml" "$base/vpn.toml"; fi
stage 5 website
run_quiet apt-get install -y --no-install-recommends nginx
# This recipe owns nginx on a clean VPS; its package service must not occupy port 80.
run_quiet systemctl disable --now nginx.service
if [[ ! -f $base/nginx.conf ]]; then install -m 600 "$ROOT/templates/nginx.conf" "$base/nginx.conf"; fi
install -d -m 755 /var/www/trusttunnel
if [[ ! -f /var/www/trusttunnel/index.html ]]; then
    install -m 644 "$ROOT/templates/index.html" /var/www/trusttunnel/index.html
fi
# Rename avoids overwriting a running executable on a repeated install.
install -m 755 "$work/$asset/trusttunnel_endpoint" "$base/trusttunnel_endpoint.new"
mv -f "$base/trusttunnel_endpoint.new" "$base/trusttunnel_endpoint"
install -m 644 "$work/$asset/LICENSE" "$base/UPSTREAM-LICENSE"
install -m 644 "$ROOT/templates/trusttunnel.service" /etc/systemd/system/trusttunnel.service
install -m 644 "$ROOT/templates/trusttunnel-site.service" /etc/systemd/system/trusttunnel-site.service
install -m 644 "$ROOT/templates/journald.conf" /etc/systemd/journald@trusttunnel.conf
install -d -m 755 /etc/letsencrypt/renewal-hooks/deploy
install -m 700 "$ROOT/templates/renew-hook.sh" /etc/letsencrypt/renewal-hooks/deploy/trusttunnel

stage 6 starting
systemctl daemon-reload
run_quiet systemctl enable --now certbot.timer
run_quiet systemctl enable trusttunnel.service trusttunnel-site.service
systemctl restart systemd-journald@trusttunnel.service
systemctl restart trusttunnel-site.service
systemctl restart trusttunnel.service
systemctl is-active --quiet trusttunnel.service
run_quiet curl --fail --show-error --silent --noproxy '*' --retry 8 --retry-connrefused --retry-delay 1 \
    --connect-timeout 5 --max-time 10 --resolve "$domain:443:127.0.0.1" \
    -D "$work/headers" "https://$domain/" -o "$work/page"
if ! cmp -s "$work/page" /var/www/trusttunnel/index.html ||
    ! awk 'tolower($0) ~ /^proxy-authenticate:/ {bad=1} END {exit bad}' "$work/headers"; then
    die website_failed
fi
[[ -n $(ss -H -ltn 'sport = :443') && -n $(ss -H -lun 'sport = :443') ]] || die ports_missing
systemctl reload trusttunnel.service
if [[ ! -f $base/.renewal-tested ]]; then
    stage 7 renewal_check
    run_quiet certbot renew --cert-name "$domain" --dry-run --no-random-sleep-on-renew
    touch "$base/.renewal-tested"
fi

stage 8 ready
