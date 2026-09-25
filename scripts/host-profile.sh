#!/usr/bin/env bash
# System profile carried from xrm-1. Never executed by render or tests on the host.
set -Eeuo pipefail
[[ "$EUID" == 0 ]] || { echo "Run with sudo." >&2; exit 1; }

case "${THREEXI_FIREWALL_MODE:-disable-ufw}" in
    disable-ufw) if command -v ufw >/dev/null 2>&1; then ufw --force disable; fi ;;
    preserve) ;;
    *) echo "THREEXI_FIREWALL_MODE must be disable-ufw or preserve." >&2; exit 2 ;;
esac

install -d -m 0755 /etc/sysctl.d
cat > /etc/sysctl.d/99-3xi-network.conf <<'SYSCTL'
net.core.rmem_max = 67108864
net.core.wmem_max = 67108864
net.core.netdev_max_backlog = 100000
net.ipv4.tcp_keepalive_time = 60
net.ipv4.tcp_keepalive_intvl = 10
net.ipv4.tcp_keepalive_probes = 6
SYSCTL
chmod 0644 /etc/sysctl.d/99-3xi-network.conf
sysctl --load=/etc/sysctl.d/99-3xi-network.conf

case "${THREEXI_SWAP:-1}" in
    0) ;;
    1)
        if [[ -z "$(swapon --show=NAME --noheadings)" ]]; then
            if [[ ! -e /swapfile ]]; then
                dd if=/dev/zero of=/swapfile bs=1M count=1024 status=none
                chmod 0600 /swapfile
                mkswap /swapfile >/dev/null
            elif [[ "$(blkid -s TYPE -o value /swapfile 2>/dev/null || true)" != swap ]]; then
                echo "Existing /swapfile is not a swap file; it was not overwritten." >&2
                exit 1
            fi
            chmod 0600 /swapfile
            swapon /swapfile
            if ! awk '$1=="/swapfile" && $3=="swap" {found=1} END {exit !found}' /etc/fstab; then
                printf '\n/swapfile none swap sw 0 0\n' >> /etc/fstab
            fi
        fi
        ;;
    *) echo "THREEXI_SWAP must be 0 or 1." >&2; exit 2 ;;
esac
