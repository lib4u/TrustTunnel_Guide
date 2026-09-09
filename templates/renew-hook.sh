#!/bin/sh
set -eu
# Reload only when Certbot renews this node's certificate.
domain=$(cat /opt/trusttunnel/domain)
if [ "${RENEWED_LINEAGE:-}" = "/etc/letsencrypt/live/$domain" ]; then
    systemctl reload trusttunnel.service
fi
