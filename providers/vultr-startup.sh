#!/usr/bin/env bash
# Vultr boot script; Ubuntu or Debian images only.
# Standalone root startup script for Ubuntu 24.04+ / Debian 12+ cloud images.
# Also embedded verbatim in cloud-init/3xi.yaml by render-cloud-init.py.

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


threexi_bootstrap_paths() {
    threexi_root=""
    threexi_log=/var/log/3xi-bootstrap.log
    threexi_state_dir=/var/lib/3xi-bootstrap
    threexi_lock=/run/lock/threexi-bootstrap.lock
    threexi_source_parent=/var/tmp
    threexi_repository=https://github.com/exirhub/3xi.git
}

threexi_bootstrap_preflight() {
    [[ "$EUID" == 0 ]] || { echo "Run this script as root (sudo bash bootstrap.sh)." >&2; return 1; }
    [[ -d /run/systemd/system ]] || { echo "A running systemd server is required." >&2; return 1; }
    . /etc/os-release
    case "${ID:-}" in
        ubuntu) dpkg --compare-versions "${VERSION_ID:-0}" ge 24.04 ;;
        debian) dpkg --compare-versions "${VERSION_ID:-0}" ge 12 ;;
        *) echo "Use Ubuntu 24.04+ or Debian 12+." >&2; return 1 ;;
    esac || { echo "The operating system version is too old." >&2; return 1; }
    case "$(dpkg --print-architecture)" in
        amd64|arm64) ;;
        *) echo "Only amd64 and arm64 are supported." >&2; return 1 ;;
    esac
    command -v flock >/dev/null || { echo "flock (util-linux) is required." >&2; return 1; }
}

threexi_bootstrap_cleanup() {
    local result="$1"
    trap - EXIT
    if [[ -n "${threexi_work:-}" && -d "$threexi_work" ]]; then
        rm -rf -- "$threexi_work"
    fi
    if [[ "$result" != 0 ]]; then
        printf 'THREEXI bootstrap failed during %s (exit %s). See %s.\n' \
            "${threexi_stage:-preflight}" "$result" "$threexi_log" >&2
    fi
    exit "$result"
}

threexi_bootstrap_dependencies() {
    export DEBIAN_FRONTEND=noninteractive
    apt-get -o DPkg::Lock::Timeout=180 -o Acquire::Retries=3 --error-on=any update
    apt-get -o DPkg::Lock::Timeout=180 -o Acquire::Retries=3 install -y \
        --no-install-recommends ca-certificates git curl python3
}

threexi_bootstrap_fetch() {
    local destination="$1" revision="$2" repository="$3" attempt fetched=0
    git init --quiet "$destination"
    git -C "$destination" remote add origin "$repository"
    for attempt in 1 2 3 4 5; do
        printf 'Fetching THREEXI revision %s (%s/5)...\n' "$revision" "$attempt"
        if timeout 180 git -C "$destination" \
            -c http.lowSpeedLimit=1024 -c http.lowSpeedTime=60 \
            fetch --quiet --depth=1 origin "$revision"; then
            fetched=1
            break
        fi
        if [[ "$attempt" != 5 ]]; then
            sleep "$((attempt * 2))"
        fi
    done
    [[ "$fetched" == 1 ]] || { echo "GitHub source download failed." >&2; return 1; }
    git -C "$destination" checkout --quiet --detach FETCH_HEAD
}

threexi_bootstrap_main() {
    set -Eeuo pipefail
    umask 077
    local revision="${THREEXI_REF:-main}" clean_install="${THREEXI_CLEAN_INSTALL:-0}" item commit
    [[ "$clean_install" == 0 || "$clean_install" == 1 ]] || { echo "THREEXI_CLEAN_INSTALL must be 0 or 1." >&2; return 2; }
    local -a install_arguments=()
    [[ "$clean_install" == 0 ]] || install_arguments+=(--clean-install)
    while [[ "$#" -gt 0 ]]; do
        case "$1" in
            --ref)
                [[ "$#" -ge 2 ]] || { echo "--ref requires a branch, tag, or commit." >&2; return 2; }
                revision="$2"
                shift 2
                ;;
            --domain|--acme-email|--grpc-service-name|--grpc-path|--grpc-mode|--public-address|--performance-profile|--nginx-logs)
                [[ "$#" -ge 2 && -n "$2" ]] || { echo "$1 requires a value." >&2; return 2; }
                install_arguments+=("$1" "$2")
                shift 2
                ;;
            --grpc-authority)
                [[ "$#" -ge 2 ]] || { echo "$1 requires a value (empty is allowed)." >&2; return 2; }
                install_arguments+=("$1" "$2")
                shift 2
                ;;
            --dns-mode)
                [[ "$#" -ge 2 && ( "$2" == public || "$2" == preserve ) ]] || {
                    echo "--dns-mode requires public or preserve." >&2; return 2;
                }
                export THREEXI_DNS_MODE="$2"
                shift 2
                ;;
            --clean-install) clean_install=1; install_arguments+=(--clean-install); shift ;;
            --help|-h)
                echo "Usage: sudo bash bootstrap.sh [--ref REF] [--clean-install] [--domain DOMAIN] [--acme-email EMAIL]"
                echo "Options: --grpc-service-name NAME (or --grpc-path /NAME/), --grpc-authority HOST, --grpc-mode multi|gun"
                echo "         --public-address ADDRESS, --dns-mode public|preserve, --performance-profile high|standard, --nginx-logs off|on"
                echo "Fresh installation uses the bundled database. Existing THREEXI is skipped."
                echo "--clean-install deletes the old installation without backup."
                return 0
                ;;
            *) printf 'Unknown argument: %s\n' "$1" >&2; return 2 ;;
        esac
    done
    [[ "$revision" =~ ^[A-Za-z0-9][A-Za-z0-9._/-]*$ ]] || {
        echo "Invalid revision; use a branch, tag, or full commit SHA." >&2
        return 2
    }
    threexi_bootstrap_preflight
    threexi_bootstrap_paths
    mkdir -p -- "$threexi_state_dir" "$(dirname -- "$threexi_lock")" "$(dirname -- "$threexi_log")"
    exec 8>"$threexi_lock"
    flock -n 8 || { echo "Another THREEXI bootstrap is running." >&2; return 1; }
    touch "$threexi_log"
    chmod 0600 "$threexi_log"
    exec > >(tee -a "$threexi_log") 2>&1
    threexi_work=""
    threexi_stage=preflight
    trap 'threexi_bootstrap_cleanup "$?"' EXIT
    printf 'THREEXI bootstrap started at %s\n' "$(date -u +%FT%TZ)"

    if [[ "$clean_install" == 0 && -f "$threexi_root/etc/3xi/installed.json" ]]; then
        echo "Existing THREEXI installation: skipped; no database or code was replaced."
        echo "Check current health with: sudo 3xi doctor"
        return 0
    fi
    for item in /etc/x-ui /usr/local/x-ui /etc/3xi /opt/3xi /var/www/3xi; do
        if [[ "$clean_install" == 0 && ( -e "$threexi_root$item" || -L "$threexi_root$item" ) ]]; then
            printf 'Existing installation: %s. Use --clean-install only to replace it without backup.\n' "$item" >&2
            return 1
        fi
    done

    threexi_stage=dns
    threexi_configure_dns
    threexi_stage=bootstrap-packages
    threexi_bootstrap_dependencies
    threexi_stage=source-download
    threexi_work=$(mktemp -d "$threexi_source_parent/threexi-src.XXXXXXXX")
    threexi_bootstrap_fetch "$threexi_work" "$revision" "$threexi_repository"
    commit=$(git -C "$threexi_work" rev-parse HEAD)
    printf 'Source commit: %s\n' "$commit"
    threexi_stage=database-checksum
    (cd "$threexi_work" && sha256sum --check x-ui.db.sha256)
    threexi_stage=installation
    bash "$threexi_work/install.sh" "${install_arguments[@]}"
    printf '%s\n' "$commit" > "$threexi_state_dir/source-commit.txt"
    echo "THREEXI installation and local readiness checks completed."
    echo "Panel URL: sudo cat /etc/3xi/access.txt"
    echo "After Cloudflare DNS is ready: sudo 3xi doctor --public YOUR-DOMAIN"
    echo "An authenticated client connection must be tested separately."
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    threexi_bootstrap_main "$@"
fi
