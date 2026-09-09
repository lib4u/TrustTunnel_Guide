FROM debian:12-slim
ENV container=docker
RUN apt-get update && apt-get install -y --no-install-recommends \
    systemd systemd-sysv dbus openssh-server ca-certificates curl openssl \
    iproute2 python3 python3-toml certbot libgcc-s1 qrencode zbar-tools \
    && rm -rf /var/lib/apt/lists/* \
    && systemctl enable ssh
COPY tests/certbot-fixture.py /usr/local/bin/certbot
RUN chmod 755 /usr/local/bin/certbot
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
