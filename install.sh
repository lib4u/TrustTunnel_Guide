#!/usr/bin/env bash
# TrustTunnel Installer — run on your computer; SSH handles authentication.
set -Eeuo pipefail
umask 077

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=lib/common.sh
source "$ROOT/lib/common.sh"
# shellcheck source=lib/messages.sh
source "$ROOT/lib/messages.sh"
# shellcheck source=lib/ui.sh
source "$ROOT/lib/ui.sh"

usage() {
    if [[ $TT_LANG == ru ]]; then cat <<'EOF'
TrustTunnel Installer

bash install.sh --lang ru --server root@203.0.113.10 --domain tt.example.com

  --lang        ru / en; без параметра — выбор языка в начале
  --server      IPv4 / имя сервера, с root@ или без; нужен root SSH
  --domain      Домен с A-записью на этот сервер (без AAAA и CDN-прокси)
  --ssh-port    Порт SSH, по умолчанию 22
  --identity    Путь к приватному SSH-ключу, необязательно
  --output      Каталог для доступов, по умолчанию ./access рядом со скриптом
  --help        Эта справка

Без обязательных параметров скрипт спросит их в терминале.
Пароль сервера, если нужен, запросит SSH. Не передавайте пароль аргументом.
Служебный email генерируется на сервере; запуск принимает условия Let's Encrypt.
Нужен отдельный VPS: Ubuntu 22.04/24.04 или Debian 12/13, systemd, x86_64/ARM64.
EOF
    else cat <<'EOF'
TrustTunnel Installer

bash install.sh --lang en --server root@203.0.113.10 --domain tt.example.com

  --lang        ru / en; otherwise choose the language at startup
  --server      Server IPv4 / hostname, optionally prefixed with root@; root SSH required
  --domain      Domain pointing to this server with an A record (no AAAA or CDN proxy)
  --ssh-port    SSH port, default 22
  --identity    Path to an SSH private key, optional
  --output      Directory for credentials, defaults to ./access beside this script
  --help        This help

Missing required options are prompted for interactively.
SSH asks for the server password if needed. Never pass a password as an argument.
A service email is generated on the server; running accepts the Let's Encrypt terms.
Requires a dedicated VPS: Ubuntu 22.04/24.04 or Debian 12/13, systemd, x86_64/ARM64.
EOF
    fi
}

# Read the language before displaying any other prompts or validation errors.
TT_LANG=''
help_requested=false
args=("$@")
for ((i=0; i<${#args[@]}; i++)); do
    case ${args[$i]} in --help|-h) help_requested=true ;; esac
    if [[ ${args[$i]} == --lang ]]; then
        require_value "${args[@]:$i}"
        TT_LANG=${args[$((i+1))]}
    fi
done
if [[ -z $TT_LANG && ! -t 0 ]] && $help_requested; then TT_LANG=en; fi
select_language
server='' domain='' ssh_port=22 identity='' output="$ROOT/access"
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h) usage; exit 0 ;;
        --lang) shift 2 ;;
        --server|--domain|--ssh-port|--identity|--output)
            require_value "$@"
            case $1 in
                --server) server=$2 ;;
                --domain) domain=$2 ;;
                --ssh-port) ssh_port=$2 ;;
                --identity) identity=$2 ;;
                --output) output=$2 ;;
            esac
            shift 2 ;;
        *) die unknown "$1" ;;
    esac
done

prompt() {
    [[ -t 0 ]] || die missing "$1"
    read -r -p "$(message "$2"): " REPLY
}
if ui_available && [[ -z $server || -z $domain ]]; then ui_form; fi
if [[ -z $server ]]; then prompt --server server_prompt; server=$REPLY; fi
if [[ -z $domain ]]; then prompt --domain domain_prompt; domain=$REPLY; fi
validate_domain "$domain"
[[ $server == *@* ]] || server="root@$server"
identity=$(expand_identity "$identity")
validate_ssh "$server" "$ssh_port" "$identity"
for cmd in ssh tar mktemp; do command -v "$cmd" >/dev/null || die dependency "$cmd"; done

tmp=$(mktemp -d "${TMPDIR:-/tmp}/tti.XXXXXXXX")
remote_dir=''
ssh_opts=(-p "$ssh_port" -o "ControlPath=$tmp/ssh" -o ControlMaster=auto
          -o ForwardAgent=no -o ClearAllForwardings=yes -o ConnectTimeout=20
          -o ServerAliveInterval=15 -o ServerAliveCountMax=4)
if [[ -n $identity ]]; then ssh_opts+=(-i "$identity" -o IdentitiesOnly=yes); fi
remote() { ssh "${ssh_opts[@]}" -o BatchMode=yes "$server" "$@"; }
cleanup() {
    local status=$?
    trap - EXIT
    if [[ $remote_dir =~ ^/tmp/trusttunnel-installer\.[a-zA-Z0-9]+$ ]]; then
        remote "rm -rf -- '$remote_dir'" </dev/null >/dev/null 2>&1 || true
    fi
    ssh "${ssh_opts[@]}" -O exit "$server" </dev/null >/dev/null 2>&1 || true
    rm -rf -- "$tmp"
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

ui_banner
log "$(message connecting "$server")"
ssh "${ssh_opts[@]}" -o ControlMaster=yes -o ControlPersist=600 -MNf "$server"
remote_dir=$(remote 'umask 077; mktemp -d /tmp/trusttunnel-installer.XXXXXXXX')
[[ $remote_dir =~ ^/tmp/trusttunnel-installer\.[a-zA-Z0-9]+$ ]] || die staging_failed
tar -C "$ROOT" -czf - server-install.sh versions.env lib templates |
    remote "tar -xzf - -C '$remote_dir'"
# All remote command arguments have been restricted to safe characters above.
remote "bash '$remote_dir/server-install.sh' --lang '$TT_LANG' --domain '$domain'"

log "$(message saving)"
mkdir -p -- "$output"
result_dir=$(mktemp -d "$output/$domain.XXXXXXXX")
remote "python3 -B '$remote_dir/lib/export.py' --lang '$TT_LANG' --format tar" > "$tmp/access.tar.gz"
tar -xzf "$tmp/access.tar.gz" -C "$result_dir" access.txt connection.txt endpoint.toml connection.png
chmod 600 "$result_dir/"*
ui_result "$result_dir"
