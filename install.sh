#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
clean_install=0
for argument in "$@"; do
    [[ "$argument" != "--clean-install" ]] || clean_install=1
done
if [[ "${1:-}" == "--help" ]]; then
    cd "$project_dir"
    exec python3 -m threexi install --help
fi
if [[ "${1:-}" == "--dry-run" ]]; then
    shift
    cd "$project_dir"
    exec python3 -m threexi render "$@"
fi
if [[ "$EUID" -ne 0 ]]; then
    echo "Run with sudo on an Ubuntu 24.04+/Debian 12+ systemd server." >&2
    exit 1
fi
if [[ ! -d /run/systemd/system ]]; then
    echo "A running systemd server is required." >&2
    exit 1
fi
exec 9>/run/lock/threexi-install.lock
flock -n 9 || { echo "Another THREEXI installation is active." >&2; exit 1; }
if [[ "$clean_install" == 0 && -f /etc/3xi/installed.json ]]; then
    exec /usr/local/bin/3xi doctor
fi
for item in /etc/x-ui /usr/local/x-ui /etc/3xi /opt/3xi /var/www/3xi; do
    if [[ "$clean_install" == 0 && ( -e "$item" || -L "$item" ) ]]; then
        echo "Existing installation: $item. Use --clean-install to remove it without backup and install from the bundled database." >&2
        exit 1
    fi
done
. /etc/os-release
case "${ID:-}" in
    ubuntu|debian) ;;
    *) echo "Ubuntu or Debian is required." >&2; exit 1 ;;
esac
nginx_was_present=0
command -v nginx >/dev/null 2>&1 && nginx_was_present=1
if [[ "$clean_install" == 0 && "$nginx_was_present" == 1 ]] && systemctl is-enabled --quiet nginx; then
    echo "An existing enabled Nginx service needs a reviewed migration." >&2
    exit 1
fi
(cd "$project_dir" && sha256sum --check x-ui.db.sha256)
source "$project_dir/scripts/dns.sh"
threexi_configure_dns
source "$project_dir/scripts/install-dependencies.sh"
threexi_install_dependencies
if [[ "$nginx_was_present" == 0 ]]; then
    systemctl disable --now nginx
fi
cd "$project_dir"
exec python3 -m threexi install "$@"
