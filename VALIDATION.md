# Validation record

Validated locally on 2026-09-25. This records executed checks, not a claim of production deployment.

## Executed

- **8 additional capacity-diagnostic tests passed.** They check source-port reservations, separate TCP socket sides, actual child-process FD limits, missing-service reporting, bounded log windows, error classification and omission of private URLs/raw messages. The read-only collector also ran locally without installed 3xi services. These checks are not a production load test.
- **13 resource-profile tests passed.** They cover in-place application and repeat application, profile persistence, disabled/re-enabled Nginx logs, preservation of routes/database/higher live limits, validation failures before changes, rollback after partial FD changes or failed Nginx reload, and effective systemd override rejection. The Nginx-only hot-update test also verifies that domain/certificate metadata and Xray's running limits/service are preserved. A real Linux `prlimit` increase/restore was exercised on a child process created only for the test, within the workspace's existing hard limit. Applying the full profile to a real systemd/Nginx/Xray server remains a destination-side check. The complete Python suite now has **69 passing tests**.
- **48 Python tests passed.** Coverage includes staged import, exact source-byte preservation, all unrelated inbound/table preservation, existing Host reuse, optional-domain metadata, independent origin keys, explicit ACME failures, restoration of prior services after simulated issuance failure, readable DNS under a private umask, clean removal boundaries, port conflicts, APT failure ordering, retry/locking, bootstrap idempotence and client URL export.
- **Real Chromium interaction tests passed.** Actual MP3 playback and seek, H.264/AAC video loading, pause coordination, source release on film close, collection filters, bookmark persistence, keyboard gallery navigation, journal dialogs, reduced motion, mobile navigation and no horizontal overflow at 320/390/768/1440 px. No browser exceptions or failing HTTP responses. No MP3/MP4 downloads before interaction.
- Desktop and mobile screenshots were inspected; image aspect ratios and small-screen navigation/layout were corrected.
- Shell syntax passed for the installer, helper scripts, provider scripts and pinned upstream menu. Browser JavaScript syntax passed.
- Generated startup files match the canonical bootstrap; cloud-config is **9,567 bytes**, below 16 KiB. The embedded script is checked against the standalone file.
- `ffprobe` validated all three MP4 files: **16 seconds, 1280×720, H.264 + AAC**. All three MP3 files decode as MP3 and report approximately **64.044 seconds**, including encoder padding.
- Real user database passed SQLite integrity checks. Its exact SHA-256 is `56df4e93a5eb532fe872760f21b1e323157c996c6c9c9376e80f3f5a63c96336`; size **1,003,520 bytes**. The runtime migration leaves the five XHTTP inbounds, user/client/counter/token tables and Xray routing template unchanged. The repository seed remains byte-for-byte unchanged.
- Both default and explicit-domain configurations rendered locally without changing system services or the source database.

## Checks performed by installation on the destination

The installer verifies the pinned 3x-ui archive and terminal-menu SHA-256, tests the staged Xray configuration with the actual downloaded core, and runs `nginx -t` before removing an old application. With a supplied domain, real ACME issuance also completes before deleting old application files. It then checks each required service, the locally pinned TLS certificate, negotiated ALPN h2, backend HTTP/2 SETTINGS, website and panel responses, and the actual panel-generated Xray configuration.

## Not executed in this workspace

- A fresh privileged install on a real Ubuntu/Debian systemd VM, across either CPU architecture or every listed provider.
- Live Let’s Encrypt issuance/renewal for a user-controlled domain. The invocation, staging and failure paths are tested; DNS/ACME/provider reachability remains a deployment dependency.
- Actual destination Nginx/Xray binary validation here; those binaries are checked by the installer on the server.
- An authenticated VLESS session through the user's Cloudflare zone and client network. `3xi doctor --public DOMAIN` checks a public HTTPS endpoint; it does not establish authenticated VLESS end-to-end success.
- A concurrent-load/soak test, including the requested 100,000-connection workload. Current defaults are not a capacity guarantee; see [the capacity review](docs/CAPACITY.md). The diagnostic snapshot does not establish capacity or an EOF root cause.

The site and timeout settings do not guarantee immunity to Cloudflare rules, congestion, network filtering or DPI. The final deployment must be tested from the intended client network.

## Reproduce

```bash
python3 -m unittest discover -s tests -v
python3 scripts/render-cloud-init.py --check
for script in install.sh scripts/*.sh stackscript.sh aws.sh providers/*.sh vendor/3x-ui/x-ui.sh; do bash -n "$script"; done
node --check website/assets/site.js
node tests/browser.cjs
```

Browser tests require Playwright and an installed Chromium; `THREEXI_CHROMIUM_PATH` optionally selects an existing browser binary. They serve only the static site in a temporary local HTTP server. DNS/systemd/APT destructive paths in unit tests use temporary fixtures or mocks, never the workstation's actual configuration.
