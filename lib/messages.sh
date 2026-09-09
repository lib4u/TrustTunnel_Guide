#!/usr/bin/env bash
# Keep shell translations here so both entry points use the same vocabulary.

message() {
    local key=$1 en ru
    shift
    case $key in
        error) en='Error'; ru='Ошибка' ;;
        value) en='Missing value for %s.'; ru='Для %s требуется значение.' ;;
        domain_invalid) en='Use a domain such as tt.example.com, without https://, a port or a path. Use punycode for IDNs.'; ru='Нужен домен вроде tt.example.com, без https://, порта и пути. IDN — в punycode.' ;;
        unknown) en='Unknown option: %s'; ru='Неизвестный параметр: %s' ;;
        missing) en='Missing %s. See --help.'; ru='Не хватает %s. См. --help.' ;;
        server_prompt) en='Server (root@IP)'; ru='Сервер (root@IP)' ;;
        domain_prompt) en='Domain (tt.example.com)'; ru='Домен (tt.example.com)' ;;
        port_prompt) en='SSH port'; ru='Порт SSH' ;;
        key_prompt) en='SSH key (optional)'; ru='SSH-ключ (необязательно)' ;;
        form_title) en='Your server'; ru='Ваш сервер' ;;
        form_subtitle) en='TrustTunnel + nginx + TLS certificate'; ru='TrustTunnel + nginx + TLS-сертификат' ;;
        form_missing) en='Fill in the server and domain.'; ru='Заполните сервер и домен.' ;;
        start) en='Start installation'; ru='Начать установку' ;;
        navigation) en='↑ ↓ select  ·  Enter edit/continue  ·  q quit'; ru='↑ ↓ выбор  ·  Enter изменить/продолжить  ·  q выход' ;;
        edit_hint) en='Enter keeps the value; a single - clears it.'; ru='Enter сохраняет значение; одиночный - очищает его.' ;;
        server_invalid) en='Use root@IPv4 or root@hostname.'; ru='Нужен root@IPv4 или root@имя-сервера.' ;;
        port_invalid) en='SSH port must be between 1 and 65535.'; ru='Порт SSH должен быть от 1 до 65535.' ;;
        key_missing) en='SSH key file not found.'; ru='Файл SSH-ключа не найден.' ;;
        dependency) en='Install %s first.'; ru='Сначала установите %s.' ;;
        connecting) en='Connecting to %s. SSH may ask for a password or host key confirmation.'; ru='Подключение к %s. SSH может запросить пароль или подтверждение ключа хоста.' ;;
        staging_failed) en='Cannot create a temporary directory on the server.'; ru='Не удалось создать временный каталог на сервере.' ;;
        saving) en='Saving connection details on this computer'; ru='Сохраняю данные подключения на этом компьютере' ;;
        installed) en='TrustTunnel is installed. Connection details:'; ru='TrustTunnel установлен. Данные подключения:' ;;
        link) en='Import link'; ru='Ссылка для импорта' ;;
        saved) en='Files and QR code saved to: %s'; ru='Файлы и QR-код сохранены в: %s' ;;
        client_check) en='Connect in your client to verify the VPN. See docs/clients.md.'; ru='Подключитесь в клиенте для проверки VPN. См. docs/clients.md.' ;;
        root_required) en='Root access is required on the server.'; ru='На сервере нужен root.' ;;
        os_missing) en='/etc/os-release was not found.'; ru='Не найдена /etc/os-release.' ;;
        os_unsupported) en='Supported: Ubuntu 22.04/24.04 and Debian 12/13. Detected: %s.'; ru='Поддерживаются Ubuntu 22.04/24.04 и Debian 12/13. Обнаружено: %s.' ;;
        systemd_required) en='A server running systemd is required.'; ru='Нужен сервер с работающим systemd.' ;;
        server_dependency) en='Server is missing %s (iproute2 / util-linux).'; ru='На сервере отсутствует %s (iproute2 / util-linux).' ;;
        locked) en='Another installation is already running.'; ru='Другая установка уже запущена.' ;;
        arch_unsupported) en='Only x86_64 and ARM64 are supported.'; ru='Поддерживаются только x86_64 и ARM64.' ;;
        existing_directory) en='%s already exists and is not managed by this installer.'; ru='%s уже существует и не принадлежит этому установщику.' ;;
        existing_service) en='trusttunnel.service already exists. Check the previous installation.'; ru='Служба trusttunnel.service уже существует. Проверьте прежнюю установку.' ;;
        nginx_exists) en='An existing nginx installation was found. Use a clean VPS for this recipe.'; ru='Найдена существующая установка nginx. Для этого рецепта нужен чистый VPS.' ;;
        website) en='Installing nginx and the website'; ru='Устанавливаю nginx и заглушку сайта' ;;
        website_failed) en='Website check failed: unexpected response or Proxy-Authenticate header.'; ru='Проверка сайта не пройдена: неожиданный ответ или заголовок Proxy-Authenticate.' ;;
        busy_port) en='Port %s/%s is in use. Free it before installing (see ss -lntup).'; ru='Порт %s/%s занят. Освободите его перед установкой (см. ss -lntup).' ;;
        failed) en='Installation stopped. Diagnostics: journalctl --namespace=trusttunnel -u trusttunnel -n 50'; ru='Установка прервана. Диагностика: journalctl --namespace=trusttunnel -u trusttunnel -n 50' ;;
        dependencies) en='Installing dependencies'; ru='Устанавливаю зависимости' ;;
        dns_check) en='Checking DNS: A must point directly to this VPS; AAAA must be absent'; ru='Проверяю DNS: A должна указывать непосредственно на этот VPS, AAAA отсутствовать' ;;
        dns_failed) en='DNS check failed. Fix A/AAAA records, disable the CDN proxy and wait for DNS propagation.'; ru='Проверка DNS не пройдена. Исправьте A/AAAA, отключите CDN-прокси и дождитесь обновления DNS.' ;;
        ufw) en='Allowing 80/tcp, 443/tcp and 443/udp in the existing active UFW firewall'; ru='Открываю 80/tcp, 443/tcp и 443/udp в уже включённом UFW' ;;
        state_mismatch) en='Existing installation has a different domain/version. See docs/maintenance.md.'; ru='Существующая установка использует другой домен/версию. См. docs/maintenance.md.' ;;
        download) en='Downloading official TrustTunnel %s and verifying SHA-256'; ru='Скачиваю официальный TrustTunnel %s и проверяю SHA-256' ;;
        certificate) en="Obtaining a Let's Encrypt certificate (HTTP-01, inbound TCP 80)"; ru="Получаю сертификат Let's Encrypt (HTTP-01, входящий TCP 80)" ;;
        starting) en='Starting the service and automatic certificate renewal'; ru='Запускаю сервис и автоматическое обновление сертификата' ;;
        ports_missing) en='Both TCP and UDP port 443 must be listening.'; ru='Не открыты оба порта 443: TCP и UDP.' ;;
        renewal_check) en="Testing certificate renewal using the Let's Encrypt staging server"; ru="Проверяю продление сертификата через тестовый сервер Let's Encrypt" ;;
        exporting) en='Exporting the link, QR code and client configuration'; ru='Экспортирую ссылку, QR-код и конфигурацию клиента' ;;
        link_missing) en='The endpoint did not return a tt:// link.'; ru='Endpoint не вернул ссылку tt://.' ;;
        ready) en='HTTPS check passed. Ready to send connection details over SSH.'; ru='HTTPS-проверка пройдена. Можно передать доступы по SSH.' ;;
        *) printf 'Unknown message: %s\n' "$key" >&2; return 1 ;;
    esac
    if [[ ${TT_LANG:-en} == ru ]]; then en=$ru; fi
    # Translation formats are static strings defined in this function.
    # shellcheck disable=SC2059
    printf "$en" "$@"
}

select_language() {
    if [[ -z ${TT_LANG:-} ]]; then
        if declare -F ui_language >/dev/null && ui_available; then
            ui_language
            return
        fi
        if [[ -t 0 ]]; then
            printf 'Choose language / Выберите язык:\n  1) Русский\n  2) English\n' >&2
            while true; do
                read -r -p '[1/2]: ' TT_LANG
                case $TT_LANG in 1|ru) TT_LANG=ru; break ;; 2|en) TT_LANG=en; break ;; esac
                printf 'Введите 1 или 2 / Enter 1 or 2.\n' >&2
            done
        else
            printf 'Select a language with --lang ru or --lang en / Укажите --lang ru или --lang en.\n' >&2
            exit 1
        fi
    fi
    case $TT_LANG in ru|en) ;; *) printf 'Invalid --lang: use ru or en / Допустимы ru или en.\n' >&2; exit 1 ;; esac
}
