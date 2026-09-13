ARG BUILD_FROM
FROM $BUILD_FROM

ARG BUILD_ARCH
ARG BOUNCER_VERSION=v0.0.18

# python3 + PyYAML only to merge the generated Cloudflare config with the
# add-on options; the bouncer itself is a static Go binary.
RUN apk add --no-cache ca-certificates curl python3 py3-yaml

# Official release binary for this architecture (same artifacts the upstream
# install script uses). The archive contains one versioned folder.
RUN set -e; \
    case "${BUILD_ARCH}" in \
        amd64)   A=linux-amd64 ;; \
        aarch64) A=linux-arm64 ;; \
        armv7)   A=linux-armv7 ;; \
        armhf)   A=linux-armv6 ;; \
        i386)    A=linux-386 ;; \
        *) echo "unsupported BUILD_ARCH=${BUILD_ARCH}"; exit 1 ;; \
    esac; \
    curl -fsSL "https://github.com/crowdsecurity/cs-cloudflare-worker-bouncer/releases/download/${BOUNCER_VERSION}/crowdsec-cloudflare-worker-bouncer-${A}.tgz" -o /tmp/bouncer.tgz; \
    mkdir -p /tmp/bouncer; tar xzf /tmp/bouncer.tgz -C /tmp/bouncer; \
    BIN="$(find /tmp/bouncer -type f -name crowdsec-cloudflare-worker-bouncer | head -n 1)"; \
    test -n "${BIN}"; \
    install -m 0755 "${BIN}" /usr/local/bin/crowdsec-cloudflare-worker-bouncer; \
    rm -rf /tmp/bouncer /tmp/bouncer.tgz

COPY run.sh /run.sh
COPY merge_config.py /merge_config.py
RUN chmod +x /run.sh

CMD ["/run.sh"]
