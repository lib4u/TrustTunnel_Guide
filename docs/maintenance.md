# Обслуживание

[← К README](../README.md)

Все серверные команды выполняются под root. Этот рецепт использует `/opt/trusttunnel`, `/var/www/trusttunnel` и две службы: `trusttunnel` и `trusttunnel-site`.

## Статус, журналы и место на диске

```bash
systemctl status trusttunnel trusttunnel-site certbot.timer --no-pager
journalctl --namespace=trusttunnel -u trusttunnel -u trusttunnel-site -n 80 --no-pager
journalctl --namespace=trusttunnel --disk-usage
df -h /
du -sh /opt/trusttunnel /var/www/trusttunnel /var/log/letsencrypt
```

Журнал TrustTunnel и nginx ограничен отдельной настройкой [journald](../templates/journald.conf). Общий журнал ОС и логи Certbot имеют собственные правила хранения. Access log заглушки отключён. Не включайте `debug` постоянно на загруженной ноде.

## Повторная установка

Снова запустите `install.sh` с теми же параметрами. Для установки той же версии и домена он сохраняет учётные данные, `vpn.toml`, `hosts.toml`, `rules.toml`, nginx-конфиг и страницу, обновляет поставляемые unit-файлы и перезапускает службы. VPN кратковременно переподключится.

Если процесс оборвался после установки пакета nginx, его стандартная служба могла остаться на порту 80. Убедитесь, что это именно nginx от этой неоконченной установки, затем выполните `systemctl disable --now nginx.service` и повторите запуск.

Если на сервере всё установлено, но SSH оборвался до получения доступов, повторите запуск `install.sh` с теми же параметрами. Он заново передаст доступы по SSH с прежним паролем. Файлы экспорта на VPS не хранятся: они сохраняются только на компьютере, с которого запущен установщик.

При повторном запуске также удаляются четыре старых файла из `/opt/trusttunnel/client/` и поле `password` из `.installer-state.json`. Рабочий `credentials.toml` сохраняется без изменения пароля. Для ручной установки доступен [вывод в терминал без серверных копий](manual-install.md#получить-ссылку-логин-и-пароль).

## Добавить пользователя или сменить пароль

```bash
cd /opt/trusttunnel
cp -p credentials.toml "credentials.toml.backup.$(date -u +%Y%m%dT%H%M%SZ)"
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
nano credentials.toml
```

Добавьте отдельный блок или измените пароль в существующем:

```toml
[[client]]
username = "phone"
password = "REPLACE_WITH_THE_GENERATED_PASSWORD"
```

Затем:

```bash
chmod 600 credentials.toml
systemctl restart trusttunnel
./trusttunnel_endpoint vpn.toml hosts.toml -c phone -a tt.example.com:443 --format deeplink
```

Изменение `credentials.toml` применяется после перезапуска. Параметры максимального количества HTTP/2 и HTTP/3 соединений не равны лимиту устройств.

Автоматический установщик экспортирует первоначального пользователя, имя которого записано в `.installer-state.json`. Если удалили или переименовали его, используйте ручной экспорт нового пользователя. После смены пароля перевыпустите и передайте актуальные ссылки; старые файлы содержат прежний пароль.

## Сертификат

```bash
certbot certificates
systemctl list-timers certbot.timer
certbot renew --cert-name tt.example.com --dry-run --no-random-sleep-on-renew
```

Во время проверки и продления порт 80 должен быть свободен и доступен извне. После реального обновления сертификата deploy hook отправляет SIGHUP службе TrustTunnel. Проверить перечитывание отдельно: `systemctl reload trusttunnel`.

## Обновление версии

Установщик закрепляет проверенный релиз в `versions.env`, поэтому повторный запуск не выбирает новую версию автоматически. Перед обновлением прочитайте [официальные release notes](https://github.com/TrustTunnel/TrustTunnel/releases).

Для ручного обновления:

1. Сделайте приватную копию `/opt/trusttunnel` в `/root/backups/` с правами `700`.
2. Скачайте официальный архив нужной версии для архитектуры сервера. Проверьте его SHA-256 по release asset metadata GitHub; распакуйте во временный каталог.
3. Остановите `trusttunnel`, замените только бинарник и сохраните прежний для отката. Конфиги и сертификаты оставьте на месте.
4. Запустите службу, проверьте сайт и реальные подключения через HTTP/2 и HTTP/3. При ошибке верните прежний бинарник и запустите службу снова.

После ручного обновления не запускайте старый установщик поверх новой версии. `.installer-state.json` описывает установку этим проектом. При обновлении самого рецепта сопровождающий должен вместе изменить версию, обе контрольные суммы и прогнать [проверки](../tests/README.md).

## Замена страницы

Измените `/var/www/trusttunnel/index.html`. Статический HTML отдаётся без перезапуска. Для правок nginx-конфига:

```bash
nginx -t -c /opt/trusttunnel/nginx.conf
systemctl reload trusttunnel-site
```

## Удаление

Следующие команды удаляют конфиги и доступы **этого рецепта**. Сначала сохраните нужную копию. Сертификат Certbot и пакеты остаются в системе.

```bash
systemctl disable --now trusttunnel.service trusttunnel-site.service
rm -f /etc/systemd/system/trusttunnel.service /etc/systemd/system/trusttunnel-site.service
rm -f /etc/letsencrypt/renewal-hooks/deploy/trusttunnel
systemctl stop systemd-journald@trusttunnel.service systemd-journald@trusttunnel.socket
rm -f /etc/systemd/journald@trusttunnel.conf
rm -rf /opt/trusttunnel /var/www/trusttunnel
systemctl daemon-reload
```

Для удаления сертификата отдельно используйте `certbot delete --cert-name tt.example.com`. Правила firewall, пакет nginx и сохранённые журналы удаляйте только если они больше не нужны на сервере.
