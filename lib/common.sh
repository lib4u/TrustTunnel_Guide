#!/usr/bin/env bash

die() { printf '%s: %s\n' "$(message error)" "$(message "$@")" >&2; exit 1; }
log() { printf '\n→ %s\n' "$*" >&2; }

validate_domain() {
    local label='[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?'
    [[ ${#1} -le 253 && $1 =~ ^$label(\.$label)+$ ]] ||
        die domain_invalid
}

expand_identity() {
    if [[ $1 == \~/* ]]; then printf '%s/%s' "$HOME" "${1:2}"; else printf '%s' "$1"; fi
}

validate_ssh() {
    local target=$1 port=$2 key=$3
    [[ $target == *@* ]] || target="root@$target"
    [[ $target =~ ^root@[A-Za-z0-9][A-Za-z0-9.-]*$ ]] || die server_invalid
    if ! [[ $port =~ ^[0-9]{1,5}$ ]] || ! (( 10#$port >= 1 && 10#$port <= 65535 )); then
        die port_invalid
    fi
    [[ -z $key || -f $key ]] || die key_missing
}

require_value() {
    [[ $# -ge 2 && -n $2 && $2 != --* ]] || die value "$1"
}
