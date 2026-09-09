#!/usr/bin/env bash
# A small terminal UI using Bash and ANSI sequences; no external UI runtime.

ui_available() { [[ -t 0 && -t 1 && ${TERM:-dumb} != dumb ]]; }

ui_colors() {
    UI_ACCENT='' UI_DIM='' UI_BOLD='' UI_RESET=''
    if [[ -t 1 && ${TERM:-dumb} != dumb && -z ${NO_COLOR+x} ]]; then
        UI_ACCENT=$'\033[36m' UI_DIM=$'\033[2m' UI_BOLD=$'\033[1m' UI_RESET=$'\033[0m'
    fi
}

ui_begin() {
    ui_colors
    UI_ACTIVE=true
    printf '\033[?1049h\033[?25l'
    trap 'ui_end' EXIT
    trap 'ui_end; exit 130' INT
    trap 'ui_end; exit 143' TERM
}

ui_end() {
    if [[ ${UI_ACTIVE:-false} == true ]]; then
        printf '\033[0m\033[?25h\033[?1049l'
        UI_ACTIVE=false
    fi
}

ui_heading() {
    printf '\033[2J\033[H\n  %s%sTrustTunnel Installer%s\n' "$UI_BOLD" "$UI_ACCENT" "$UI_RESET"
    printf '  %s────────────────────────────────────────────────────────%s\n' "$UI_DIM" "$UI_RESET"
}

ui_key() {
    UI_KEY=''
    local key rest=''
    if ! read -rsn 1 key; then ui_end; exit 130; fi
    case $key in
        $'\033')
            read -rsn 2 -t 1 rest || true
            case $rest in '[A') UI_KEY=up ;; '[B') UI_KEY=down ;; esac ;;
        '') UI_KEY=enter ;;
        q|Q) ui_end; exit 130 ;;
        *) UI_KEY=$key ;;
    esac
}

ui_option() {
    local selected=$1 text=$2
    if [[ $selected == true ]]; then
        printf '  %s› %s%s\n' "$UI_ACCENT" "$text" "$UI_RESET"
    else
        printf '    %s\n' "$text"
    fi
}

ui_language() {
    local selected=0
    ui_begin
    while true; do
        ui_heading
        printf '\n  Choose language / Выберите язык\n\n'
        ui_option "$([[ $selected == 0 ]] && echo true || echo false)" '1  Русский'
        ui_option "$([[ $selected == 1 ]] && echo true || echo false)" '2  English'
        printf '\n  %s↑ ↓  ·  Enter  ·  1 / 2  ·  q — exit / выход%s\n' "$UI_DIM" "$UI_RESET"
        ui_key
        case $UI_KEY in
            up|down) selected=$((1-selected)) ;;
            1) TT_LANG=ru; break ;;
            2) TT_LANG=en; break ;;
            enter) if [[ $selected == 0 ]]; then TT_LANG=ru; else TT_LANG=en; fi; break ;;
        esac
    done
    export TT_LANG
    ui_end
}

ui_form() {
    local selected=0 i label value input error=''
    local labels values
    ui_begin
    while true; do
        labels=("$(message server_prompt)" "$(message domain_prompt)"
                "$(message port_prompt)" "$(message key_prompt)" "$(message start)")
        values=("${server:--}" "${domain:--}" "$ssh_port" "${identity:--}" '')
        ui_heading
        printf '\n  %s\n  %s%s%s\n\n' "$(message form_title)" "$UI_DIM" "$(message form_subtitle)" "$UI_RESET"
        for ((i=0; i<5; i++)); do
            label=${labels[$i]}
            value=${values[$i]}
            # Keep the menu compact; full values are shown in the editor.
            if [[ ${#value} -gt 46 ]]; then value="${value:0:43}..."; fi
            if [[ $i -lt 4 ]]; then label="$label: $value"; fi
            ui_option "$([[ $selected == "$i" ]] && echo true || echo false)" "$label"
            [[ $i != 3 ]] || printf '\n'
        done
        printf '\n  %s%s%s\n' "$UI_DIM" "$(message navigation)" "$UI_RESET"
        [[ -z $error ]] || printf '\n  %s\n' "$error"
        ui_key
        case $UI_KEY in
            up) selected=$(((selected+4)%5)) ;;
            down) selected=$(((selected+1)%5)) ;;
            enter)
                if [[ $selected == 4 ]]; then
                    error=''
                    if [[ -z $server || -z $domain ]]; then
                        error=$(message form_missing)
                        continue
                    fi
                    if ! error=$(validate_domain "$domain" 2>&1); then continue; fi
                    identity=$(expand_identity "$identity")
                    if ! error=$(validate_ssh "$server" "$ssh_port" "$identity" 2>&1); then continue; fi
                    break
                fi
                printf '\n  %s\n  %s [%s]: ' "$(message edit_hint)" "${labels[$selected]}" "${values[$selected]}"
                printf '\033[?25h'
                if ! read -r -e input; then ui_end; exit 130; fi
                printf '\033[?25l'
                if [[ -n $input ]]; then
                    [[ $input != '-' ]] || input=''
                    case $selected in
                        0) server=$input ;; 1) domain=$input ;;
                        2) ssh_port=$input ;; 3) identity=$input ;;
                    esac
                fi
                selected=$(((selected+1)%5))
                error='' ;;
        esac
    done
    ui_end
}

ui_banner() {
    ui_colors
    printf '\n%s%s  TrustTunnel Installer%s\n' "$UI_ACCENT" "$UI_BOLD" "$UI_RESET"
    printf '%s  ────────────────────────────────────────────────────────%s\n' "$UI_DIM" "$UI_RESET"
    printf '  %s  →  %s\n\n' "$server" "$domain"
}

ui_result() {
    local result_dir=$1
    printf '\n%s%s  ✓ %s%s\n\n' "$UI_ACCENT" "$UI_BOLD" "$(message installed)" "$UI_RESET"
    cat "$result_dir/access.txt"
    printf '\n%s%s:%s\n' "$UI_BOLD" "$(message link)" "$UI_RESET"
    cat "$result_dir/connection.txt"
    printf '\n%s\n%s\n' "$(message saved "$result_dir")" "$(message client_check)"
}
