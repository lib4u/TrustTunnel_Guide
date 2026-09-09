# Ручная установка TrustTunnel и nginx

[← К README](../README.md) · [English](manual-install.en.md)

Результат: TrustTunnel на TCP/UDP 443, nginx с нашей страницей загрузки на `127.0.0.1:8081`, сертификат Let's Encrypt с автоматическим продлением и готовые доступы.

Команды рассчитаны на чистый Ubuntu 22.04/24.04 или Debian 12/13, x86_64/ARM64, с systemd и публичным IPv4 на интерфейсе. Домен должен иметь только A-запись на этот IPv4, без AAAA и CDN-прокси. Откройте TCP 80, TCP 443 и UDP 443 в панели VPS.

## Подготовить сервер и файлы рецепта

В каталоге скачанного репозитория **на своём компьютере** передайте открытые шаблоны на сервер:

```bash
tar -czf - versions.env templates lib |
  ssh root@203.0.113.10 'mkdir -p /root/trusttunnel-guide; tar -xzf - -C /root/trusttunnel-guide'
ssh root@203.0.113.10
```

Дальнейшие команды выполняются **на сервере под root**, в одной SSH-сессии. Замените домен:

```bash
umask 077
DOMAIN=tt.example.com
RECIPE=/root/trusttunnel-guide
cd "$RECIPE"
source versions.env

ss -lntup
getent ahostsv4 "$DOMAIN"
```

Проверьте, что 80/TCP, 443/TCP, 443/UDP и локальный 8081/TCP свободны, а IP в DNS правильный. Если на сервере уже есть ноды или nginx, используйте отдельный VPS либо сначала самостоятельно разберите существующую конфигурацию. Этот рецепт займёт указанные порты.

```bash
apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates curl certbot python3 python3-toml libgcc-s1 qrencode
```

Если UFW уже включён, добавьте правила:

```bash
ufw status
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
```

Включение UFW и правила для SSH зависят от вашей конфигурации. Локальные правила не заменяют firewall в панели хостинга.

## Скачать официальный TrustTunnel

Версия и SHA-256 берутся из открытого [versions.env](../versions.env), закреплённого на 1.1.0. Следующий блок останавливается при неподдерживаемой архитектуре или неверной контрольной сумме:

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

Ожидается версия `1.1.0`. Если блок завершился ошибкой, исправьте её до следующего шага.

## Получить сертификат

Certbot временно займёт порт 80. Запуск с `--agree-tos` принимает [условия Let's Encrypt](https://letsencrypt.org/repository/).

```bash
EMAIL="acme-$(tr -d '-' </proc/sys/kernel/random/uuid)@$DOMAIN"
certbot certonly --standalone --non-interactive --agree-tos \
  --email "$EMAIL" --cert-name "$DOMAIN" -d "$DOMAIN"
```

Убедитесь, что появились `fullchain.pem` и `privkey.pem`:

```bash
ls -l "/etc/letsencrypt/live/$DOMAIN/"
```

При ошибке проверьте DNS, доступность порта 80 снаружи и AAAA-записи. Не переходите к запуску службы без сертификата.

## Создать пользователя и конфиги

Генерируем случайные логин и пароль локально на сервере. Этот блок выполняется один раз для новой установки:

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

Содержимое [vpn.toml](../templates/vpn.toml):

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

`allow_private_network_connections = false` запрещает VPN-клиентам подключения к приватным адресам. В версии 1.1.0 эта настройка допускает обращение самого reverse proxy к указанному локальному nginx. [Описание исправления](https://github.com/TrustTunnel/TrustTunnel/releases/tag/v1.1.0).

Не добавляйте `non_connect_auth_failure_status_code`: такой ответ может получить приоритет над страницей reverse proxy. HTTP/2 использует TCP, HTTP/3 — UDP; нужны оба порта 443.

## Установить nginx с заглушкой

Сначала ставим пакет. Его стандартная служба может автоматически запуститься на 80-м порту — отключаем её и используем отдельную службу с нашим конфигом:

```bash
apt-get install -y --no-install-recommends nginx
systemctl disable --now nginx.service
install -m 600 "$RECIPE/templates/nginx.conf" /opt/trusttunnel/nginx.conf
install -d -m 755 /var/www/trusttunnel
install -m 644 "$RECIPE/templates/index.html" /var/www/trusttunnel/index.html
```

[Конфиг nginx](../templates/nginx.conf) слушает только `127.0.0.1:8081`. Статическую страницу, `HEAD`, кеширование и другие HTTP-ответы обрабатывает nginx. Неизвестный путь возвращает ту же оболочку страницы загрузки. Access log отключён, ошибки отправляются в ограниченный журнал службы.

Можно заменить `/var/www/trusttunnel/index.html` своей статической страницей. Повторная автоматическая установка сохраняет её, если она существует.

## Запустить службы и ограничить журналы

[Служба TrustTunnel](../templates/trusttunnel.service) запускает официальный бинарник, а [служба сайта](../templates/trusttunnel-site.service) — nginx. Оба журнала находятся в отдельном namespace `trusttunnel`: лимит дискового журнала 100 МБ, оперативного — 50 МБ, срок хранения — 7 дней. Это лимиты хранения journald, а не точный предел размера каждого файла.

```bash
install -m 644 "$RECIPE/templates/trusttunnel.service" /etc/systemd/system/trusttunnel.service
install -m 644 "$RECIPE/templates/trusttunnel-site.service" /etc/systemd/system/trusttunnel-site.service
install -m 644 "$RECIPE/templates/journald.conf" /etc/systemd/journald@trusttunnel.conf
systemctl daemon-reload
systemctl enable --now trusttunnel-site.service trusttunnel.service
systemctl status trusttunnel-site.service trusttunnel.service --no-pager
```

Теперь проверьте с сервера и затем со своего компьютера:

```bash
curl -i "https://$DOMAIN/"
curl -I "https://$DOMAIN/any-path"
ss -lntup
```

Ожидается `200 OK`, страница загрузки и отсутствие `Proxy-Authenticate` у обычного GET/HEAD. Nginx слушает только loopback:8081; TrustTunnel — TCP/UDP 443. Для TLS-проверки не используйте `curl -k`.

## Настроить продление сертификата

```bash
install -d -m 755 /etc/letsencrypt/renewal-hooks/deploy
install -m 700 "$RECIPE/templates/renew-hook.sh" /etc/letsencrypt/renewal-hooks/deploy/trusttunnel
systemctl enable --now certbot.timer
systemctl reload trusttunnel.service
certbot renew --cert-name "$DOMAIN" --dry-run --no-random-sleep-on-renew
```

[Deploy hook](../templates/renew-hook.sh) перечитывает сертификат через SIGHUP только после обновления сертификата этого домена. Смена паролей требует перезапуска процесса; SIGHUP предназначен для TLS-настроек. [Официальный гайд по продлению](https://github.com/TrustTunnel/TrustTunnel/blob/v1.1.0/CERT_RENEWAL.md).

## Получить ссылку, логин и пароль

```bash
python3 -B "$RECIPE/lib/export.py" --lang ru --format text --username "$TT_USER"
```

Команда выведет домен, порт, логин, пароль и готовую ссылку `tt://` прямо в терминал. Она не создаёт файлы доступа на сервере. Если вы открыли новую SSH-сессию, снова задайте `RECIPE`, а `TT_USER` возьмите из `/opt/trusttunnel/credentials.toml`.

Чтобы получить файлы и QR-код **на свой компьютер**, откройте на нём отдельный терминал и выполните:

```bash
(
  set -euo pipefail
  umask 077
  mkdir -p access
  RESULT=$(mktemp -d ./access/trusttunnel.XXXXXXXX)
  ssh root@203.0.113.10 \
    'python3 -B /root/trusttunnel-guide/lib/export.py --lang ru --format tar' |
    tar -xzf - -C "$RESULT"
  printf 'Доступы и QR-код: %s\n' "$RESULT"
)
```

Архив формируется в памяти и передаётся по SSH. Только на компьютере появятся `access.txt`, `connection.txt`, `connection.png` и `endpoint.toml`; на VPS остаётся рабочий файл авторизации `credentials.toml`. Для ручной установки без `--username` выбирается первый пользователь этого файла.

[export.py](../lib/export.py) использует официальный экспорт и [normalize-export.py](../lib/normalize-export.py), чтобы задать `has_ipv6 = false` в обоих форматах: официальный exporter 1.1.0 выставляет этот признак в `true` независимо от настройки сервера. Остальные поля ссылки сохраняются. [Код upstream](https://github.com/TrustTunnel/TrustTunnel/blob/v1.1.0/lib/src/client_config.rs).

**[Подключение в клиенте →](clients.md)** · **[Обслуживание →](maintenance.md)**

Ручная установка не создаёт служебный маркер автоматического установщика. Поэтому `install.sh` не возьмёт её под управление при повторном запуске; обслуживайте её по инструкции выше и в разделе обслуживания.
