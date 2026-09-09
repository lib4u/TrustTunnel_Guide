# Подключение клиентов

[← К README](../README.md)

## Телефон и графический клиент

1. Установите [официальный TrustTunnel-клиент](https://github.com/TrustTunnel/TrustTunnelFlutterClient#readme) для своей платформы.
2. Добавьте сервер через импорт ссылки `tt://` из терминала или `connection.txt`. Можно использовать QR-код `connection.png`.
3. Подключитесь и откройте сайт, показывающий внешний IP. Он должен соответствовать исходящему адресу вашего VPS.

Названия кнопок зависят от версии приложения. [Официальная инструкция импорта](https://github.com/TrustTunnel/TrustTunnelFlutterClient#server-configuration).

Для ручного ввода используйте домен, порт `443`, логин и пароль из результата установки. Сертификат публичный: проверка TLS должна быть включена. Ссылку, QR и пароль передавайте только тем, кому разрешаете использовать сервер.

## CLI на компьютере

Скачайте [официальный CLI-клиент](https://github.com/TrustTunnel/TrustTunnelClient/releases) под свою систему. Экспорт `endpoint.toml` описывает сервер: его нужно передать мастеру, чтобы получить полный конфиг клиента.

```bash
./setup_wizard --mode non-interactive \
  --endpoint_config /path/to/endpoint.toml \
  --settings trusttunnel_client.toml
```

Для системного туннеля запустите клиент с правами администратора:

```bash
sudo ./trusttunnel_client -c trusttunnel_client.toml
```

Для проверки без изменения маршрутов откройте полный конфиг и вместо секции `[listener.tun]` с её полями задайте:

```toml
[listener.socks]
address = "127.0.0.1:1080"
```

В начале файла задайте `killswitch_enabled = false`. SOCKS-режим действует только на приложения, явно использующие этот прокси. Запустите клиент без `sudo` и в другом терминале:

```bash
curl --socks5-hostname 127.0.0.1:1080 https://api.ipify.org
```

Чтобы проверить оба транспорта, меняйте `upstream_protocol` в секции `[endpoint]` между `"http2"` и `"http3"`, перезапуская клиент после каждого изменения. В сетях, блокирующих UDP, используйте HTTP/2. [Справочник CLI](https://github.com/TrustTunnel/TrustTunnelClient/blob/v1.1.5/trusttunnel/README.md).

## Если не подключается

| Симптом | Что проверить |
| --- | --- |
| `https://домен/` не открывается | A-запись, отсутствие AAAA/CDN, TCP 443, службы и сертификат |
| Сайт открывается, VPN не работает | Логин/пароль, импорт правильной ссылки, журнал TrustTunnel |
| HTTP/2 работает, HTTP/3 нет | UDP 443 в UFW, панели VPS и клиентской сети |
| Ошибка сертификата | Домен/SNI, время на устройствах, срок сертификата; не отключайте проверку |
| Сайт отвечает 407 на обычный GET | `[reverse_proxy]`, nginx и отсутствие `non_connect_auth_failure_status_code` |
| Внешний IP не изменился | Активное VPN-подключение, режим клиента и исключения маршрутизации |

Диагностика на сервере:

```bash
systemctl status trusttunnel trusttunnel-site --no-pager
journalctl --namespace=trusttunnel -u trusttunnel -u trusttunnel-site -n 80 --no-pager
```
