#!/usr/bin/with-contenv bashio
# CrowdSec Cloudflare Bouncer - Home Assistant add-on entry point
set -e

BIN=/usr/local/bin/crowdsec-cloudflare-worker-bouncer
GENERATED=/data/cf-generated.yaml
CONFIG=/data/bouncer.yaml

# ── options ──────────────────────────────────────────────────────────────────
LAPI_URL="$(bashio::config 'lapi_url')"
LAPI_KEY="$(bashio::config 'lapi_key')"
export LAPI_URL LAPI_KEY
export DEFAULT_ACTION="$(bashio::config 'default_action')"
export CAPTCHA_ENABLED="$(bashio::config 'captcha_enabled')"
export CAPTCHA_MODE="$(bashio::config 'captcha_mode')"
export UPDATE_FREQUENCY="$(bashio::config 'update_frequency')"
export ONLY_LOCAL="$(bashio::config 'only_local_decisions')"
export LOG_LEVEL="$(bashio::config 'log_level')"

# lists: bashio prints one item per line
TOKENS="$(bashio::config 'cloudflare_tokens' | tr '\n' ',' | sed 's/,*$//')"
export ZONES="$(bashio::config 'zones' 2>/dev/null | tr '\n' ',' | sed 's/,*$//')"

if [ -z "${TOKENS}" ]; then
    bashio::log.fatal "cloudflare_tokens ist leer. Einen Cloudflare-API-Token mit den in der Dokumentation genannten Rechten eintragen."
    exit 1
fi
if [ -z "${LAPI_KEY}" ]; then
    bashio::log.fatal "lapi_key ist leer. Im CrowdSec-Addon einen Bouncer-Schluessel erzeugen: cscli bouncers add cloudflare"
    exit 1
fi

# ── optional teardown ────────────────────────────────────────────────────────
if bashio::config.true 'remove_infrastructure'; then
    if [ -f "${CONFIG}" ]; then
        bashio::log.warning "remove_infrastructure ist gesetzt: Worker, Routen und KV-Speicher werden bei Cloudflare entfernt ..."
        "${BIN}" -c "${CONFIG}" -d || bashio::log.error "Entfernen fehlgeschlagen (siehe oben)"
        rm -f "${CONFIG}" "${GENERATED}"
        bashio::log.warning "Fertig. Option remove_infrastructure wieder ausschalten und das Addon neu starten, um den Bouncer erneut einzurichten."
    else
        bashio::log.warning "remove_infrastructure ist gesetzt, aber es gibt keine Konfiguration - nichts zu entfernen."
    fi
    exit 0
fi

# ── discover accounts and zones from the tokens ──────────────────────────────
bashio::log.info "Frage Cloudflare-Konten und -Zonen ab ..."
if ! "${BIN}" -g "${TOKENS}" -o "${GENERATED}" >/tmp/gen.log 2>&1; then
    cat /tmp/gen.log
    bashio::log.fatal "Cloudflare-Abfrage fehlgeschlagen. Token gueltig? Rechte vollstaendig (siehe Dokumentation)?"
    exit 1
fi

# ── merge with the add-on options ────────────────────────────────────────────
python3 /merge_config.py "${GENERATED}" "${CONFIG}"
chmod 600 "${CONFIG}"

bashio::log.info "LAPI: ${LAPI_URL} · Aktion: ${DEFAULT_ACTION} · Captcha: ${CAPTCHA_ENABLED} · Abgleich alle ${UPDATE_FREQUENCY}"
bashio::log.warning "Nach dem ersten Start bei Cloudflare unter Workers & Pages fuer jede Route den Fehlermodus auf 'Fail open' stellen (siehe Dokumentation)."

exec "${BIN}" -c "${CONFIG}"
