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
    bashio::log.fatal "lapi_key ist leer. Bouncer-Schluessel erzeugen: docker exec app_424ccef4_crowdsec cscli -c /config/.storage/crowdsec/config/config.yaml bouncers add cloudflare-bouncer"
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

# ── wait for the CrowdSec LAPI ───────────────────────────────────────────────
# At host boot the add-ons start together. Before the CrowdSec add-on is up,
# its hostname does not even resolve; the bouncer then fails its first
# decision pull, tears down its Worker and KV at Cloudflare on the way out and
# exits - leaving the zones without any protection until someone restarts it.
# So nothing touches Cloudflare before the LAPI answers with our key.
LAPI_BASE="${LAPI_URL%/}"
wait_for_lapi() {
    local waited=0 code
    while true; do
        code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
                  -H "X-Api-Key: ${LAPI_KEY}" "${LAPI_BASE}/v1/decisions?ip=127.0.0.1" || true)"
        case "${code}" in
            200)
                if [ "${waited}" -gt 0 ]; then
                    bashio::log.info "CrowdSec-LAPI erreichbar (nach ${waited} s)."
                fi
                return 0 ;;
            401|403)
                bashio::log.fatal "Die LAPI lehnt lapi_key ab (HTTP ${code}). Schluessel mit 'cscli -c /config/.storage/crowdsec/config/config.yaml bouncers add ...' neu erzeugen."
                return 2 ;;
        esac
        if [ $((waited % 30)) -eq 0 ]; then
            bashio::log.info "Warte auf CrowdSec-LAPI ${LAPI_BASE} (HTTP ${code:-000}) - laeuft das CrowdSec-Addon?"
        fi
        sleep 5
        waited=$((waited + 5))
    done
}

if ! wait_for_lapi; then
    exit 1
fi

# ── discover accounts and zones from the tokens ──────────────────────────────
# Right after boot DNS or the uplink can still be settling: retry a few times
# before calling the token broken.
bashio::log.info "Frage Cloudflare-Konten und -Zonen ab ..."
attempt=1
until "${BIN}" -g "${TOKENS}" -o "${GENERATED}" >/tmp/gen.log 2>&1; do
    if [ "${attempt}" -ge 6 ]; then
        cat /tmp/gen.log
        bashio::log.fatal "Cloudflare-Abfrage fehlgeschlagen. Token gueltig? Rechte vollstaendig (siehe Dokumentation)?"
        exit 1
    fi
    bashio::log.warning "Cloudflare-Abfrage fehlgeschlagen (Versuch ${attempt}/6), neuer Versuch in 20 s ..."
    attempt=$((attempt + 1))
    sleep 20
done

# ── merge with the add-on options ────────────────────────────────────────────
python3 /merge_config.py "${GENERATED}" "${CONFIG}"
chmod 600 "${CONFIG}"

bashio::log.info "LAPI: ${LAPI_URL} · Aktion: ${DEFAULT_ACTION} · Captcha: ${CAPTCHA_ENABLED} · Abgleich alle ${UPDATE_FREQUENCY}"
bashio::log.warning "Nach dem ersten Start bei Cloudflare unter Workers & Pages fuer jede Route den Fehlermodus auf 'Fail open' stellen (siehe Dokumentation)."

# ── run, and bring the bouncer back if it dies ───────────────────────────────
# A restarted or updated CrowdSec add-on makes the bouncer exit the same way
# as at boot. Instead of ending the add-on (and the protection with it), wait
# for the LAPI again and redeploy, backing off up to 5 minutes. The Supervisor
# stopping the add-on still ends everything: the signal goes to the bouncer.
child=""
stop() {
    bashio::log.info "Stoppe den Bouncer ..."
    if [ -n "${child}" ]; then
        kill -TERM "${child}" 2>/dev/null || true
        wait "${child}" 2>/dev/null || true
    fi
    exit 0
}
trap stop TERM INT

backoff=10
while true; do
    started=$(date +%s)
    "${BIN}" -c "${CONFIG}" &
    child=$!
    set +e
    wait "${child}"
    rc=$?
    set -e
    child=""
    if [ $(( $(date +%s) - started )) -ge 600 ]; then
        backoff=10                      # it ran for a while: this is a new incident
    fi
    bashio::log.warning "Bouncer beendet (Code ${rc}). Neuer Start in ${backoff} s, sobald die LAPI antwortet ..."
    sleep "${backoff}" &
    wait $! || true
    backoff=$(( backoff * 2 > 300 ? 300 : backoff * 2 ))
    if ! wait_for_lapi; then
        exit 1
    fi
done
