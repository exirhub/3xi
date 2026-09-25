# Cloud startup

See the [main installation table and options](../README.md#choose-your-installation) and [فارسی](../README.fa.md). Use Ubuntu 24.04+ or Debian 12+, systemd, amd64/arm64.

| Provider | Complete file | Input |
| --- | --- | --- |
| Linode / Akamai | [stackscript.sh](../stackscript.sh) | StackScript, including optional UDF fields |
| AWS EC2 / Lightsail | [aws.sh](../aws.sh) | Shell user-data / launch script |
| Google Cloud | [gcp-startup.sh](../providers/gcp-startup.sh) | Startup script |
| Vultr | [vultr-startup.sh](../providers/vultr-startup.sh) | Boot script |
| Hetzner, DigitalOcean, OVH, Oracle, Scaleway, UpCloud | [3xi.yaml](3xi.yaml) | Cloud-init user-data |
| Azure | [3xi.yaml](3xi.yaml) | Custom data on a cloud-init-enabled image |
| Other compatible VPS | [bootstrap.sh](../scripts/bootstrap.sh) | Root shell |

Paste the entire file, not just its final command. The cloud-config embeds DNS repair before APT and GitHub and is below 16 KiB. All variants use one bootstrap and skip completed installations on subsequent runs.

## Optional domain

Default: unique locally generated certificate, no domain prompt, Cloudflare **Full**. For Let’s Encrypt and **Full (strict)**, edit the final `runcmd` in the complete YAML:

```yaml
runcmd:
  - [bash, /var/lib/3xi-bootstrap/bootstrap.sh, --ref, main, --domain, your-domain.example]
```

Remove the `--domain` pair for the default. Append `--acme-email, admin@your-domain.example` for an optional contact. Append `--clean-install` only for deliberate replacement without backup. Replace `main` with a commit SHA to pin the revision. HTTP-01 must reach this server on port 80; see the main README for CDN/redirect requirements.

To preserve provider DNS:

```yaml
runcmd:
  - [env, THREEXI_DNS_MODE=preserve, bash, /var/lib/3xi-bootstrap/bootstrap.sh, --ref, main]
```

These fragments replace only `runcmd`; the original `write_files` block is still required.

For StackScript, fill the supplied UDF fields. For other shell startup files, optionally add after the shebang:

```bash
export THREEXI_DOMAIN=your-domain.example
export THREEXI_ACME_EMAIL=admin@your-domain.example
export THREEXI_DNS_MODE=preserve
```

Omit unwanted settings. `THREEXI_CLEAN_INSTALL=1` explicitly deletes a prior installation. `THREEXI_FIREWALL_MODE=preserve` and `THREEXI_SWAP=0` are supported. No client UUID or Cloudflare token is needed in startup variables.

## Logs and maintenance

```bash
sudo cloud-init status --long
sudo tail -n 80 /var/log/3xi-bootstrap.log
sudo cat /var/lib/3xi-bootstrap/source-commit.txt
sudo cat /etc/3xi/access.txt
sudo 3xi doctor
```

Generated from `scripts/bootstrap.sh`. After editing it, run `python3 scripts/render-cloud-init.py`; use `--check` to detect stale provider copies. The default files never activate clean mode or require a domain. SSH users/keys and interface configuration are not rewritten; the xrm host profile is documented in the main README.
