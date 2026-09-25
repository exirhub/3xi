#!/usr/bin/env bash
# xrm-1 host behavior: establish a readable, persistent resolver before APT.
threexi_configure_dns() {
    local root="${1:-}" mode="${THREEXI_DNS_MODE:-public}" iface
    case "$mode" in
        preserve) echo "Keeping provider DNS configuration."; return 0 ;;
        public) ;;
        *) echo "THREEXI_DNS_MODE must be public or preserve." >&2; return 2 ;;
    esac
    install -d -m 0755 "$root/etc/systemd/resolved.conf.d"
    cat > "$root/etc/systemd/resolved.conf.d/99-3xi-dns.conf" <<'DNS'
[Resolve]
DNS=1.1.1.1 8.8.8.8
FallbackDNS=9.9.9.9 8.8.4.4
DNS
    chmod 0644 "$root/etc/systemd/resolved.conf.d/99-3xi-dns.conf"
    if [[ -L "$root/etc/resolv.conf" ]]; then rm -- "$root/etc/resolv.conf"; fi
    cat > "$root/etc/resolv.conf" <<'DNS'
nameserver 1.1.1.1
nameserver 8.8.8.8
nameserver 9.9.9.9
options timeout:2 attempts:3
DNS
    chmod 0644 "$root/etc/resolv.conf"
    if [[ -z "$root" ]] && systemctl is-active --quiet systemd-resolved; then
        systemctl restart systemd-resolved
        iface=$(ip -4 route show default | awk 'NR==1 {for(i=1;i<=NF;i++) if($i=="dev") {print $(i+1); exit}}')
        if [[ -n "$iface" ]] && command -v resolvectl >/dev/null 2>&1; then
            resolvectl dns "$iface" 1.1.1.1 8.8.8.8 || true
            resolvectl domain "$iface" '~.' || true
            resolvectl flush-caches || true
        fi
    fi
    echo "Public DNS configured; resolv.conf is readable by the APT sandbox user."
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    set -Eeuo pipefail
    [[ "$EUID" == 0 ]] || { echo "Run with sudo." >&2; exit 1; }
    threexi_configure_dns
fi
