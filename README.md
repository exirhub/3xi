# 3xi

**3x-ui + a multimedia website + an HTTP/2 gRPC gateway.** Combines the DNS/system setup from `xrm-1` with the dedicated Nginx architecture from `XUPDATE`. Both source repositories remain independent.

[راهنمای فارسی](README.fa.md) · [Cloud startup files](cloud-init/README.md) · [Validation](VALIDATION.md) · [Media sources](website/ASSETS.md)

## Choose your installation

| Method | Ready-to-use file | Where to use it |
| --- | --- | --- |
| SSH / terminal | [`install.sh`](install.sh) | Clone this repository, then run the installer |
| One downloaded startup script | [`scripts/bootstrap.sh`](scripts/bootstrap.sh) | Ubuntu/Debian root shell; downloads and verifies the repository |
| Linode / Akamai StackScript | [`stackscript.sh`](stackscript.sh) | Paste the **entire file** into a new StackScript; optional fields are included |
| AWS EC2 / Lightsail | [`aws.sh`](aws.sh) | Shell user-data / launch script on an Ubuntu or Debian image |
| Google Compute Engine | [`providers/gcp-startup.sh`](providers/gcp-startup.sh) | Instance startup script; completed installs are skipped on later boots |
| Vultr | [`providers/vultr-startup.sh`](providers/vultr-startup.sh) | Boot/startup script |
| Hetzner, DigitalOcean, OVH/OpenStack, Oracle, Scaleway, UpCloud | [`cloud-init/3xi.yaml`](cloud-init/3xi.yaml) | Cloud-init user-data on a supported Linux image |
| Azure | [`cloud-init/3xi.yaml`](cloud-init/3xi.yaml) | Custom data on a cloud-init-enabled Ubuntu/Debian image |

Requirements: **Ubuntu 24.04+ or Debian 12+, systemd, amd64 or arm64**, root access, outbound DNS/HTTPS/APT access. The provider must allow TCP **80 and 443** to the origin. Provider security groups/firewalls are configured in the provider console. The preserved XHTTP inbounds need their own ports if you use them.

## Install from a terminal

```bash
git clone https://github.com/exirhub/3xi.git
cd 3xi
sudo bash install.sh
```

No domain, SNI, authority, certificate, private key or Cloudflare token is required for this default mode. A unique origin certificate is generated on the server. Use **Cloudflare SSL/TLS → Full**, enable **Network → gRPC**, and proxy each selected domain to this server.

### Optional trusted certificate

```bash
sudo bash install.sh --domain your-domain.example
```

Replace `your-domain.example` with a domain you control that reaches this server. This selects automatic **Let’s Encrypt HTTP-01** issuance and renewal, suitable for **Full (strict)** for that domain. You may supply an ACME contact email:

```bash
sudo bash install.sh --domain your-domain.example --acme-email admin@your-domain.example
```

HTTP-01 must reach `/.well-known/acme-challenge/` on TCP 80. For initial issuance, use DNS-only temporarily or ensure Cloudflare forwards that HTTP path without an HTTPS redirect, challenge or WAF block. An A/AAAA record pointing elsewhere will prevent issuance. After issuance, enable Orange Cloud and Full (strict). Renewal uses a dedicated Nginx exception on both HTTP and HTTPS and does not stop Nginx.

The domain is optional. When supplied, issuance **must succeed**; the installer does not silently switch to a self-signed certificate. Initial issuance finishes before old installation files are deleted. Existing managed listeners may pause briefly for verification and are restarted if issuance fails. The installer registers an ACME account and accepts the Let’s Encrypt subscriber agreement when this mode is selected; without an email, it registers without a contact address.

### Replace an old installation without backup

```bash
sudo bash install.sh --clean-install
```

Or use a trusted certificate at the same time:

```bash
sudo bash install.sh --clean-install --domain your-domain.example
```

This removes the previous local x-ui and known XUPDATE/3xi/xrm-site gateway installation and uses the bundled database. No old-database backup is created in clean mode. Repository source directories outside the managed installation paths are not removed. Run this from a checkout such as `~/3xi`, not `/opt/3xi` or another directory being removed.

A completed installation run again without `--clean-install` performs health checks; it does not reimport the database or change certificate mode. A fresh install stores a copy of its imported seed under `/var/backups/3xi`; clean mode does not. Packages, DNS, TCP tuning, swap and UFW settings are host configuration and are not rolled back with the application.

## StackScript and cloud-init

**StackScript:** copy [`stackscript.sh`](stackscript.sh) into Linode’s StackScript editor. The fields are:

| Field | Default | Meaning |
| --- | --- | --- |
| `THREEXI_REF` | `main` | Branch, tag or full commit SHA |
| `THREEXI_DOMAIN` | empty | Empty = local origin certificate; set = Let’s Encrypt |
| `THREEXI_ACME_EMAIL` | empty | Optional ACME contact email |
| `THREEXI_DNS_MODE` | `public` | `public` applies xrm DNS settings; `preserve` keeps provider DNS |
| `THREEXI_CLEAN_INSTALL` | `0` | `1` explicitly deletes a previous installation without backup |

**Cloud-init:** paste the complete [`cloud-init/3xi.yaml`](cloud-init/3xi.yaml) into user-data. Default `runcmd`:

```yaml
runcmd:
  - [bash, /var/lib/3xi-bootstrap/bootstrap.sh, --ref, main]
```

To request a trusted certificate, replace only that final command:

```yaml
runcmd:
  - [bash, /var/lib/3xi-bootstrap/bootstrap.sh, --ref, main, --domain, your-domain.example]
```

To preserve provider DNS instead, use:

```yaml
runcmd:
  - [env, THREEXI_DNS_MODE=preserve, bash, /var/lib/3xi-bootstrap/bootstrap.sh, --ref, main]
```

Append `--clean-install` only when replacement is intended. These are **edits to the supplied full YAML**, not standalone cloud-config documents. The full payload embeds DNS setup and bootstrap code, so DNS repair runs before APT or GitHub downloads. It is below the 16 KiB EC2 user-data limit. SSH users, SSH keys and network interfaces are not rewritten.

For shell user-data / GCP / Vultr, optional settings may be placed after the shebang:

```bash
export THREEXI_DOMAIN=your-domain.example
export THREEXI_ACME_EMAIL=admin@your-domain.example
```

Leave `THREEXI_DOMAIN` absent for the default mode. All startup files share the same installer, seed checksum, retries, lock handling and completed-install guard. See the [cloud startup guide](cloud-init/README.md).

### Downloaded bootstrap

```bash
curl -fL --retry 3 https://raw.githubusercontent.com/exirhub/3xi/main/scripts/bootstrap.sh -o /tmp/3xi-bootstrap.sh
sudo bash /tmp/3xi-bootstrap.sh
```

Optional arguments: `--ref`, `--domain`, `--acme-email`, `--clean-install`. If DNS already prevents the initial `curl`/`git`, use the embedded cloud-init or paste the complete StackScript. A script cannot repair networking before it has been downloaded.

## Open x-ui, the website and client configuration

```bash
sudo x-ui
sudo cat /etc/3xi/access.txt
sudo 3xi doctor
```

`x-ui` is the pinned upstream interactive terminal menu. The **panel URL** is `https://YOUR-PROXIED-DOMAIN` followed by the panel path recorded in `access.txt`. The **website** is the domain root `/`. Existing panel login credentials remain those from the uploaded database.

Export active gRPC clients using whichever domain you choose at the client side:

```bash
sudo 3xi links --sni your-domain.example
```

To use a specific Cloudflare edge address and authority:

```bash
sudo 3xi links --sni your-domain.example --authority your-domain.example --address 188.114.97.6
```

This prints VLESS URLs with the actual UUIDs from the installed database. It does not edit users, the database or the gateway. Changing the text of a domain is insufficient: that domain must exist in your Cloudflare setup, have an edge certificate, be proxied to this origin and have gRPC enabled.

| Client field | Value |
| --- | --- |
| Protocol | VLESS |
| Port | `443` |
| Transport | **gRPC**, not XHTTP |
| TLS | Enabled; normal certificate validation stays enabled at the client |
| SNI / authority | Your selected proxied domain; normally use the same value for both |
| ALPN | `h2` |
| Fingerprint | `chrome` |
| serviceName | `google.internal.analytics.v1.Tracker` |
| Mode | `multi` |
| HTTP gRPC method path | `/google.internal.analytics.v1.Tracker/TunMulti` |

Use the **serviceName**, without a leading slash or `/TunMulti`, in a client’s gRPC service field. A UUID is still required: domain-independent TLS does not disable VLESS authentication.

## What is imported and what changes at runtime

[`x-ui.db`](x-ui.db) is the exact uploaded `51.83.251.103_2026-09-25_053713.db`, **1,003,520 bytes**, verified by [`x-ui.db.sha256`](x-ui.db.sha256). It contains one panel user, eight client records, twelve client/inbound links, six enabled inbounds and one public Host record.

| Inbound | Runtime behavior |
| --- | --- |
| VLESS gRPC, ID 14 | Loopback `127.0.0.1:10001`, reached through Nginx TLS/HTTP/2 on 443 |
| Five existing XHTTP inbounds | Ports `2082`, `2083`, `2084`, `2087`, `8080` and their existing settings remain as supplied |

The repository seed is never edited. The runtime copy at `/etc/x-ui/x-ui.db` keeps users, client UUIDs, counters, tokens, routing policy and the unrelated inbounds. The managed gRPC backend stays h2c; public TLS metadata is retained. An existing public Host is reused, not duplicated. In explicit-domain mode its SNI/host metadata follows the supplied domain. Panel and subscription listeners move to loopback with TLS terminated by Nginx. The original panel base path remains.

The new frontend does **not** use the unrelated TLS certificate embedded in the XHTTP inbound. That certificate remains part of the original XHTTP configuration. Automatic 3xi certificate rotation applies to the **443 frontend only**.

## Architecture and host behavior

Nginx owns **80/443** in `threexi-nginx.service`, independently from the distro `nginx.service`. Its default virtual host accepts arbitrary SNI/Host values. There is no authority allowlist. The gRPC service path goes through `grpc_pass` to Xray; ordinary requests go to the multimedia website; the existing panel and subscription paths go to 3x-ui on loopback.

The frontend uses ALPN `h2`, streaming timeouts of 3600 seconds, disabled gRPC retry, suitable header buffers, media MIME types, static range requests and cache headers. `http2_max_header_size` is obsolete and is replaced by `large_client_header_buffers`. These settings do not change Cloudflare’s own limits and do not guarantee avoidance of network filtering.

The xrm host profile runs before application cleanup:

| Setting | Default | Override |
| --- | --- | --- |
| DNS | `1.1.1.1`, `8.8.8.8`, `9.9.9.9`; readable `/etc/resolv.conf`, resolved drop-in | `THREEXI_DNS_MODE=preserve` |
| UFW | Disabled, matching xrm-1 | `THREEXI_FIREWALL_MODE=preserve` |
| Swap | Add a 1 GiB `/swapfile` only when no swap is active; do not overwrite an unrelated file | `THREEXI_SWAP=0` |
| TCP | 64 MiB receive/send maxima, backlog 100000, keepalive 60/10/6 | `/etc/sysctl.d/99-3xi-network.conf` |

Example preserving provider DNS and firewall while skipping swap:

```bash
sudo env THREEXI_DNS_MODE=preserve THREEXI_FIREWALL_MODE=preserve THREEXI_SWAP=0 bash install.sh
```

## TLS modes and renewal

| Initial option | Origin certificate | Cloudflare mode | Domain changes |
| --- | --- | --- | --- |
| No `--domain` | Unique ECDSA self-signed certificate generated locally | **Full** | Choose any correctly configured proxied domain at the client |
| `--domain your-domain.example` | Let’s Encrypt certificate for that domain | **Full (strict)** | Strict validation requires a certificate covering the new name |

The client sees Cloudflare’s edge certificate in both modes. Full encrypts the origin connection without authenticating the origin certificate; Strict additionally validates it. Direct browser access to an origin with the self-signed certificate will show a trust warning. No shared frontend private key or Cloudflare API token is bundled or required.

`threexi-tls.timer` checks daily. Locally generated certificates rotate when fewer than 30 days remain. Let’s Encrypt renewals use Certbot’s renewal policy and the same webroot; cert/account state lives under `/etc/3xi-acme`. A validated certificate is copied into `/etc/3xi/tls`, Nginx is checked, and a graceful reload applies it. Failed reloads restore the previous pair. ACME account/certificate state is retained through clean reinstalls to avoid unnecessary reissuance.

```bash
sudo 3xi renew
systemctl list-timers threexi-tls.timer
```

Use `3xi renew` for the managed frontend; keep the panel’s internal certificate fields empty. Domainless installations do not contact an ACME provider. See [Cloudflare Full](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full/), [Full (strict)](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/), [gRPC requirements](https://developers.cloudflare.com/network/grpc-connections/), and [Certbot HTTP-01](https://eff-certbot.readthedocs.io/en/stable/using.html#webroot).

## Website: 3xi Atlas

The site ships with three original digital landscapes, three 16-second H.264/AAC motion studies, three 64-second original ambient compositions, a reading journal, keyboard-accessible image dialogs, saved collections, a persistent music player and responsive mobile navigation. Images, video, music, CSS and JavaScript are all served locally. No build step is needed on the server.

Media playback starts after user interaction. Favorites and preferences stay in the browser. There is no fake analytics generator or background visitor simulation. Source prompts, generation notes and reproduction commands are in [`website/ASSETS.md`](website/ASSETS.md).

## Increase gRPC connection capacity

For an update that changes **only Nginx**, use the [hot-update block at the end of this README](#hot-update-nginx-only).

New installations use the **high** resource profile. Apply it to an existing installation from the updated repository checkout:

```bash
git pull --ff-only
sudo python3 -m threexi tune --profile high --nginx-logs off
```

| Setting | Older installations | Standard | High (new default) |
| --- | --- | --- | --- |
| Nginx `worker_connections`, per worker | 4096 | 16384 | **65536** |
| Nginx worker/service and Xray service `nofile` | 65536 | 131072 | **262144** |
| HTTP/2 concurrent streams, per frontend connection | 128 | 128 | **256** |
| Nginx runtime file logs | Enabled | Off by default | **Off by default** |

The command validates the candidate with `nginx -t`, raises live FD limits on the service processes and their children, persists systemd drop-ins and the selected profile, upgrades the managed generator/CLI modules in `/opt/3xi`, and gracefully reloads Nginx. It does not restart Xray or reimport the database. The route refresh timer preserves the profile. A repeated application does not reload unchanged Nginx configuration.

Logging defaults to `--nginx-logs off`: `access_log off;` and `error_log /dev/null emerg;`. Routine requests produce no access-log records and Nginx runtime errors do not go to a log file. `error_log off;` is deliberately not used because `off` would be interpreted as a filename. The logging choice persists across route refresh and reboot. `--nginx-logs on` explicitly restores diagnostic file logging. Previously draining workers can finish under their old configuration; `nginx -t` and systemd status messages remain available.

Use `--dry-run` to preview. After the first application, `sudo 3xi tune --profile high` is also available. For smaller machines use `--profile standard`; numeric overrides are `--worker-connections`, `--nofile` and `--h2-streams`. Raising limits consumes additional memory under load. Live FD limits that are already higher are not lowered; selecting a smaller profile changes future service/worker limits, not all existing processes immediately.

The operation shares the installer/refresh lock, checks `fs.nr_open`, refuses unrelated manual gateway edits and verifies effective systemd limits/new workers. Failed applications restore the previous files and changed live limits; an incomplete restoration is reported explicitly. The host must permit live limit changes (`CAP_SYS_RESOURCE` when raising a hard limit). Services are not automatically restarted as a fallback.

For new installations the optional selector is `sudo bash install.sh --performance-profile standard`; omitted means `high`, also for the cloud startup scripts. Logs default to off for both profiles; `--nginx-logs on` opts in. Merely pulling the repository or rerunning the completed installer does not tune an existing installation: run the command above.

**Concurrency is not bandwidth.** There is no configured Nginx 20 MB/s rate cap. A ceiling increase alone does not promise 40–70 MB/s. If these units are bytes per second, 20 MB/s is 160 Mbit/s and 40–70 MB/s is 320–560 Mbit/s before overhead. The hardware, provider link, traffic mix and CDN path still determine throughput. No timeouts, Xray transport settings, routes or certificates are changed by tuning.

## EOF and high concurrency

**Even the high profile is not validated for 100,000 concurrent connections.** Older installations retain their earlier limits until explicitly tuned. The single loopback TCP backend still has a source-port budget. `netdev_max_backlog=100000` is a packet queue, not connection capacity. Users, TCP sockets and gRPC streams are different quantities.

Run this from the repository checkout during the problem; it reads runtime limits, resource usage, socket counts and recent errors without restarting services or changing the database:

```bash
git pull --ff-only
sudo python3 scripts/diagnose-capacity.py
```

Send the report together with the exact client error, timestamp/timezone and client/core version. No reinstall is needed. See [capacity limits, EOF interpretation and the 100k test plan](docs/CAPACITY.md). An EOF alone does not prove Nginx saturation; larger timeouts do not override Cloudflare's connection lifecycle.

## Operations and troubleshooting

```bash
sudo 3xi doctor
sudo 3xi doctor --public your-domain.example
sudo bash scripts/diagnose.sh
sudo nginx -t -c /etc/3xi/nginx.conf
sudo systemctl status x-ui threexi-nginx --no-pager
sudo journalctl -u x-ui -u threexi-nginx -n 80 --no-pager
sudo ss -lntp '( sport = :80 or sport = :443 or sport = :10001 )'
```

| Symptom | Check |
| --- | --- |
| APT `Temporary failure resolving` | DNS reachability; `sudo -u _apt getent ahosts security.ubuntu.com`; `/etc/resolv.conf` must be readable (`0644`). `scripts/dns.sh` reapplies the default profile. If public resolvers are blocked by the provider, use provider DNS and `THREEXI_DNS_MODE=preserve`. |
| Distro `nginx.service` cannot bind 80 | Check `threexi-nginx.service`; it is the expected port owner. Manage the dedicated unit, not two Nginx masters. |
| Cloudflare 526 | Domainless certificate requires **Full**; Strict needs a valid certificate covering the requested hostname. |
| Cloudflare 521/525 | Check origin IP, TCP 443, provider firewall, dedicated Nginx, and TLS negotiation. Longer timeouts cannot fix a refused TCP connection. |
| gRPC 403 | Enable gRPC in the zone; inspect Cloudflare request/security events for rule actions. |
| Client preface/reset error | Check client SNI, authority, ALPN `h2`, TLS and gRPC serviceName, then compare local and public health. The message alone does not prove rate limiting or DPI. |
| ACME failed | Check `/var/log/3xi-acme/letsencrypt.log`, all A/AAAA records, port 80, redirects and the challenge path. Existing app files are kept until issuance succeeds. |

Bootstrap logs: `/var/log/3xi-bootstrap.log`, `/var/log/cloud-init-output.log`. Source revision: `/var/lib/3xi-bootstrap/source-commit.txt`. Application state: `/etc/3xi/installed.json`.

`3xi refresh` and its timer validate supported gRPC route changes. Keep the managed inbound on loopback `10001` with transport `grpc` and security `none`. Panel path/port or internal TLS changes need a matching gateway change and are not silently guessed.

## Development and validation

```bash
python3 -m unittest discover -s tests -v
python3 scripts/render-cloud-init.py --check
for script in install.sh scripts/*.sh stackscript.sh aws.sh providers/*.sh; do bash -n "$script"; done
node --check website/assets/site.js
python3 -m threexi render --output /tmp/3xi-preview
```

`render` writes into a new directory without installing packages, touching services or editing the seed. Explicit-domain rendering uses a temporary local certificate; real ACME issuance happens during installation. The installer validates the pinned panel archive hash, Xray configuration and Nginx configuration before deleting an old application.

For browser tests, install Playwright and Chromium, then run `node tests/browser.cjs`. Set `THREEXI_CHROMIUM_PATH` only when using a separate Chromium binary. See [`VALIDATION.md`](VALIDATION.md) for measured results and live-deployment limits.

The panel and terminal menu are pinned to **3x-ui v3.8.5**, amd64/arm64, with checksums in [`upstream.lock.json`](upstream.lock.json). Attribution and upstream license: [`THIRD_PARTY.md`](THIRD_PARTY.md).

## Hot update: Nginx only

Run the block below on an **already installed 3xi server**. It works after cloud-init/StackScript installation too, without a local Git checkout or package installation. It downloads the current project into a private temporary directory and applies only Nginx connection/FD/HTTP2 limits and logging settings:

- `worker_connections 65536` per worker; `worker_rlimit_nofile 262144`; Nginx service `LimitNOFILE=262144`.
- `http2_max_concurrent_streams 256`; access logging off; error output to `/dev/null` at `emerg` level.
- Existing domains, SNI/authority, certificates, ports, gRPC route, panel settings, users and traffic statistics are preserved. The Xray service and its live FD limits are not changed or restarted.

The updater preserves these values in the managed generator/state so the refresh timer cannot undo them. It validates with `nginx -t`, raises Nginx's live limits, then gracefully reloads Nginx. It restores previous settings if application fails. It neither runs `install.sh` nor imports `x-ui.db`.

```bash
sudo bash <<'BASH'
set -Eeuo pipefail
if [[ ! -f /etc/3xi/installed.json ]]; then
    echo "An existing 3xi installation is required." >&2
    exit 1
fi
update_dir="$(mktemp -d /var/tmp/3xi-nginx-update.XXXXXX)"
trap 'rm -rf -- "$update_dir"' EXIT
curl -fL --retry 5 --retry-delay 2 --connect-timeout 15 --max-time 180 \
    https://codeload.github.com/exirhub/3xi/tar.gz/refs/heads/main \
    -o "$update_dir/source.tar.gz"
mkdir "$update_dir/source"
tar -xzf "$update_dir/source.tar.gz" --strip-components=1 --no-same-owner -C "$update_dir/source"
bash "$update_dir/source/scripts/hot-update-nginx.sh"
BASH
```

If you already have the checkout, the equivalent command is `git pull --ff-only && sudo bash scripts/hot-update-nginx.sh`. Add `--dry-run` to the script invocation to validate/preview without applying it. These are concurrency limits; no fixed 40–70 MB/s throughput or 100,000-session capacity is claimed.
