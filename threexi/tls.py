"""Generate independent origin TLS keys locally; no domain or API credential is needed."""
from pathlib import Path
from contextlib import contextmanager
import http.server
import socket
import subprocess
import threading
from .core import ConfigError, extract_certificate, run_checked

ACME_ROOT = Path('/var/lib/3xi-acme/www')
ACME_CONFIG = Path('/etc/3xi-acme')


def create_certificate(directory: Path):
    directory.mkdir(parents=True, mode=0o700)
    run_checked(['openssl', 'req', '-x509', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256',
                 '-nodes', '-days', '365', '-subj', '/CN=3xi-origin.local',
                 '-addext', 'subjectAltName=DNS:3xi-origin.local,DNS:localhost,IP:127.0.0.1',
                 '-keyout', str(directory/'origin.key'), '-out', str(directory/'origin.pem')])
    (directory/'origin.key').chmod(0o600)
    (directory/'origin.pem').chmod(0o644)
    return {'mode': 'locally generated self-signed', 'cloudflare_ssl_mode': 'Full', 'validity_days': 365}


def certbot_base():
    return ['certbot', '--config-dir', str(ACME_CONFIG), '--work-dir', '/var/lib/3xi-acme/work',
            '--logs-dir', '/var/log/3xi-acme']


def run_certbot(args):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=420, umask=0o022)
    if result.returncode:
        raise ConfigError('Automatic TLS issuance/renewal failed. See /var/log/3xi-acme/letsencrypt.log. '
                          'Ensure this domain reaches this server on TCP 80 and allow '
                          '/.well-known/acme-challenge/ through CDN, WAF and redirect rules. '
                          'No fallback to a self-signed certificate was performed.')


class ChallengeHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ACME_ROOT), **kwargs)

    def do_GET(self):
        import re
        if not re.fullmatch(r'/\.well-known/acme-challenge/[A-Za-z0-9_-]+', self.path):
            self.send_error(404)
            return
        super().do_GET()

    def do_HEAD(self):
        self.send_error(405)

    def log_message(self, *_):
        pass


@contextmanager
def challenge_server(port=80):
    class DualStackServer(http.server.ThreadingHTTPServer):
        address_family = socket.AF_INET6

        def server_bind(self):
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            super().server_bind()

    try:
        server = DualStackServer(('::', port), ChallengeHandler)
    except OSError as error:
        if error.errno not in (97, 99):
            raise
        server = http.server.ThreadingHTTPServer(('0.0.0.0', port), ChallengeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def load_acme_certificate(domain, destination):
    lineage = ACME_CONFIG/'live'/domain
    pair = {'certificate': (lineage/'fullchain.pem').read_text(), 'key': (lineage/'privkey.pem').read_text()}
    detail = extract_certificate({'tlsSettings': {'certificates': [pair]}}, destination, domain)
    return dict(detail, mode='lets-encrypt', domain=domain, cloudflare_ssl_mode='Full (strict)')


def issue(domain, destination, email=''):
    for path in (ACME_ROOT, ACME_CONFIG, Path('/var/lib/3xi-acme/work'), Path('/var/log/3xi-acme')):
        path.mkdir(parents=True, exist_ok=True)
    for path in (ACME_ROOT.parent, ACME_ROOT):
        path.chmod(0o755)
    args = certbot_base() + ['certonly', '--non-interactive', '--agree-tos', '--webroot',
            '--webroot-path', str(ACME_ROOT), '--preferred-challenges', 'http',
            '--cert-name', domain, '--domain', domain, '--key-type', 'ecdsa', '--keep-until-expiring']
    args += ['--email', email] if email else ['--register-unsafely-without-email']
    with challenge_server():
        run_certbot(args)
    return load_acme_certificate(domain, destination)


def renew_acme(domain, destination):
    run_certbot(certbot_base() + ['renew', '--non-interactive', '--cert-name', domain,
                                '--webroot', '--webroot-path', str(ACME_ROOT)])
    return load_acme_certificate(domain, destination)
