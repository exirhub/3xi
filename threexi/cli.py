from __future__ import annotations
import argparse
import fcntl
import http.client
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from .core import ConfigError, inspect, prepare, public_summary
from . import deploy

def main():
    project = Path(__file__).resolve().parent.parent
    defaults = json.loads((project/"deployment-defaults.json").read_text())
    bundled_db = project/"x-ui.db"
    if not bundled_db.is_file() and (project/"private/x-ui.db").is_file():
        bundled_db = project/"private/x-ui.db"
    p = argparse.ArgumentParser(prog="3xi")
    commands = p.add_subparsers(dest="action", required=True)
    for name in ("inspect", "render", "install"):
        sub = commands.add_parser(name)
        sub.add_argument("--db", type=Path, default=bundled_db)
        sub.add_argument("--domain", default=os.environ.get("THREEXI_DOMAIN", defaults.get("domain", "")), help="Optional domain for automatic Let’s Encrypt; omit for domain-independent origin TLS")
        sub.add_argument("--public-address", default=defaults.get("public_address", ""))
        sub.add_argument("--backend-port", type=int, default=defaults.get("backend_port", 10001))
        if name == "render":
            sub.add_argument("--output", type=Path, required=True)
            sub.add_argument("--legacy-nginx", action="store_true")
        if name == "install":
            sub.add_argument("--acme-email", default=os.environ.get("THREEXI_ACME_EMAIL", ""), help="Optional ACME contact email")
            sub.add_argument("--archive", type=Path, help="Offline verified 3x-ui release archive")
            sub.add_argument("--clean-install", action="store_true",
                             help="Remove the previous x-ui/THREEXI installation without backup")
    doc = commands.add_parser("doctor")
    doc.add_argument("--public", metavar="DOMAIN", default=False, help="Probe any client domain without storing it")
    commands.add_parser("renew")
    links = commands.add_parser("links", help="Export VLESS URLs for a client-selected domain")
    links.add_argument("--sni", required=True)
    links.add_argument("--authority", default="")
    links.add_argument("--address", default="", help="Optional Cloudflare edge address; defaults to SNI")
    links.add_argument("--db", type=Path, default=Path('/etc/x-ui/x-ui.db'))
    commands.add_parser("refresh")
    commands.add_parser("rollback")
    args = p.parse_args()
    os.umask(0o077)
    try:
        if args.action in ("install", "refresh", "rollback", "renew") and os.geteuid() == 0:
            operation_lock = open("/run/lock/threexi-operation.lock", "a")
            try:
                fcntl.flock(operation_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ConfigError("Another THREEXI operation is active.") from error
        if args.action == "links":
            from .links import export_links
            print('\n'.join(export_links(args.db, args.sni, args.authority, args.address)))
            return 0
        if args.action in ("inspect", "render", "install"):
            kw = dict(domain=args.domain, advertised=args.public_address, backend_port=args.backend_port)
            if args.action == "inspect":
                result = public_summary(inspect(args.db, **kw))
            elif args.action == "render":
                result = public_summary(prepare(args.db, args.output, project,
                                               modern=not args.legacy_nginx, certificate_mode="auto", **kw))
            else:
                result = deploy.install(project, args.db, offline=args.archive,
                                        clean_install=args.clean_install, acme_email=args.acme_email, **kw)
        elif args.action == "doctor":
            result = deploy.health(deploy.state_read()["plan"], public=args.public)
        elif args.action == "renew":
            result = deploy.renew_certificate()
        elif args.action == "refresh":
            result = deploy.refresh()
        else:
            result = deploy.rollback()
        print(json.dumps(result, indent=2))
        return 0
    except (ConfigError, OSError, ValueError, KeyError, sqlite3.Error,
            http.client.HTTPException, subprocess.TimeoutExpired) as error:
        if isinstance(error, ConfigError):
            message = str(error)
        else:
            message = f"{type(error).__name__}: operation failed; no secret-bearing detail was printed."
        print("THREEXI: "+message, file=sys.stderr)
        return 1
