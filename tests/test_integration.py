"""Preservation and deployment tests against the exact user-supplied seed."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from threexi import deploy, tls
from threexi.core import ConfigError, prepare

ROOT = Path(__file__).resolve().parents[1]


class BundledDatabaseTests(unittest.TestCase):
    def test_client_export_uses_selected_sni_authority_and_real_enabled_users(self):
        from urllib.parse import urlsplit, parse_qs
        from threexi.links import export_links
        links = export_links(ROOT/'x-ui.db', 'client.example.org', 'client.example.org', '188.114.97.6')
        with sqlite3.connect(ROOT/'x-ui.db') as db:
            expected = {r[0] for r in db.execute('SELECT c.uuid FROM clients c JOIN client_inbounds ci ON c.id=ci.client_id WHERE ci.inbound_id=14 AND c.enable=1')}
        self.assertEqual({urlsplit(link).username for link in links}, expected)
        for link in links:
            parsed = urlsplit(link); query = parse_qs(parsed.query)
            self.assertEqual(parsed.hostname, '188.114.97.6')
            self.assertEqual(query['sni'], ['client.example.org'])
            self.assertEqual(query['authority'], ['client.example.org'])
            self.assertEqual(query['serviceName'], ['google.internal.analytics.v1.Tracker'])
            self.assertEqual(query['mode'], ['multi'])

    def test_exact_seed_and_all_unmanaged_records_survive(self):
        source = ROOT/'x-ui.db'
        before = source.read_bytes()
        self.assertEqual(hashlib.sha256(before).hexdigest(), (ROOT/'x-ui.db.sha256').read_text().split()[0])
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'render'
            plan = prepare(source, output, ROOT, certificate_mode='auto')
            self.assertEqual(plan['inbound_id'], 14)
            self.assertEqual(plan['certificate']['cloudflare_ssl_mode'], 'Full')
            with sqlite3.connect(source) as original, sqlite3.connect(output/'x-ui.db') as runtime:
                tables = [r[0] for r in original.execute("SELECT name FROM sqlite_master WHERE type='table'")]
                for table in tables:
                    if table in ('settings','inbounds','sqlite_sequence'):
                        continue
                    self.assertEqual(original.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall(),
                                     runtime.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall(), table)
                self.assertEqual(original.execute('SELECT * FROM inbounds WHERE id!=14 ORDER BY id').fetchall(),
                                 runtime.execute('SELECT * FROM inbounds WHERE id!=14 ORDER BY id').fetchall())
                self.assertEqual(runtime.execute('SELECT count(*) FROM hosts').fetchone()[0], 1)
                cfg = dict(runtime.execute('SELECT key,value FROM settings'))
                self.assertEqual(cfg['webDomain'], '')
                self.assertEqual(cfg['subDomain'], '')
                self.assertEqual(dict(original.execute('SELECT key,value FROM settings'))['xrayTemplateConfig'], cfg['xrayTemplateConfig'])
            text = (output/'nginx.conf').read_text()
            self.assertEqual(plan['performance']['worker_connections'], 65536)
            self.assertFalse(plan['nginx_logging'])
            self.assertIn('worker_connections 65536;', text)
            self.assertIn('worker_rlimit_nofile 262144;', text)
            self.assertIn('http2_max_concurrent_streams 256;', text)
            self.assertIn('error_log /dev/null emerg;', text)
            self.assertIn('    access_log off;', text)
            self.assertIn('server_name _;', text)
            self.assertNotIn('exirhub.site', text)
            self.assertIn('listen 443 ssl default_server;', text)
            self.assertIn('grpc_pass grpc://127.0.0.1:10001;', text)
            self.assertNotIn('google.internal.analytics.v1.Tracker', (output/'var/www/3xi/index.html').read_text())
            self.assertNotIn('PRIVATE KEY', (output/'access.txt').read_text())
            self.assertEqual((output/'etc/3xi/tls/origin.key').stat().st_mode & 0o777, 0o600)
        self.assertEqual(source.read_bytes(), before)

    def test_explicit_domain_selects_trusted_issuance_without_changing_seed(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'render'
            with patch.object(tls, 'run_certbot', side_effect=AssertionError('render must be offline')):
                plan = prepare(ROOT/'x-ui.db', output, ROOT, domain='new.example.org', certificate_mode='auto')
            self.assertEqual(plan['certificate']['mode'], 'lets-encrypt pending')
            with sqlite3.connect(output/'x-ui.db') as db:
                self.assertEqual(db.execute('SELECT sni FROM hosts WHERE inbound_id=14').fetchone()[0], 'new.example.org')

    def test_generated_keys_are_unique_between_servers(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b = Path(temp)/'a',Path(temp)/'b'
            tls.create_certificate(a);tls.create_certificate(b)
            self.assertNotEqual((a/'origin.key').read_bytes(),(b/'origin.key').read_bytes())
            subprocess.run(['openssl','verify','-CAfile',str(a/'origin.pem'),str(a/'origin.pem')],check=True,capture_output=True)


class ResolverTests(unittest.TestCase):
    def test_private_install_umask_does_not_hide_resolver_from_apt(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'etc').mkdir()
            target=root/'old-resolv';target.write_text('old provider DNS\n')
            (root/'etc/resolv.conf').symlink_to(target)
            subprocess.run(['bash','-c','umask 077; source "$1"; threexi_configure_dns "$2"',
                            'test',str(ROOT/'scripts/dns.sh'),str(root)],check=True,capture_output=True,
                            env=dict(os.environ,THREEXI_DNS_MODE='public'))
            self.assertFalse((root/'etc/resolv.conf').is_symlink())
            self.assertEqual((root/'etc/resolv.conf').stat().st_mode & 0o777,0o644)
            self.assertIn('nameserver 1.1.1.1',(root/'etc/resolv.conf').read_text())
            self.assertEqual(target.read_text(),'old provider DNS\n')

    def test_preserve_mode_makes_no_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            subprocess.run(['bash','-c','source "$1"; threexi_configure_dns "$2"',
                            'test',str(ROOT/'scripts/dns.sh'),temp],check=True,capture_output=True,
                            env=dict(os.environ,THREEXI_DNS_MODE='preserve'))
            self.assertEqual(list(Path(temp).iterdir()),[])


class AutomaticTlsTests(unittest.TestCase):
    def test_certificate_failure_is_explicit_and_does_not_fallback(self):
        with patch.object(tls.subprocess,'run',return_value=subprocess.CompletedProcess([],1,b'',b'private')):
            with self.assertRaisesRegex(ConfigError,'No fallback') as error:
                tls.run_certbot(['certbot','certonly'])
            self.assertNotIn('private',str(error.exception))

    def test_previous_service_is_restored_when_issuance_fails(self):
        events=[]
        def running(args,**kwargs):
            return subprocess.CompletedProcess(args,0 if args[-1]=='x-ui.service' else 3,b'',b'')
        with patch.object(deploy.subprocess,'run',side_effect=running), \
             patch.object(deploy,'command',side_effect=lambda args,**kwargs: events.append(args)), \
             patch.object(deploy,'available_ports'):
            with self.assertRaisesRegex(RuntimeError,'ACME unavailable'):
                with deploy.pause_previous_for_acme(True):
                    raise RuntimeError('ACME unavailable')
        self.assertEqual(events,[['systemctl','stop','x-ui.service'],['systemctl','start','x-ui.service']])

    def test_acme_command_uses_webroot_and_optional_email(self):
        from contextlib import nullcontext
        with tempfile.TemporaryDirectory() as temp, patch.object(tls,'ACME_ROOT',Path(temp)/'www'), \
             patch.object(tls,'ACME_CONFIG',Path(temp)/'config'), \
             patch.object(tls.Path,'mkdir'), patch.object(tls.Path,'chmod'), \
             patch.object(tls,'challenge_server',return_value=nullcontext()), \
             patch.object(tls,'load_acme_certificate',return_value={}), \
             patch.object(tls,'run_certbot') as run:
            tls.issue('new.example.org',Path(temp)/'out','admin@example.org')
            args=run.call_args.args[0]
            self.assertIn('--webroot',args)
            self.assertEqual(args[args.index('--domain')+1],'new.example.org')
            self.assertEqual(args[args.index('--email')+1],'admin@example.org')


if __name__ == '__main__':
    unittest.main()
