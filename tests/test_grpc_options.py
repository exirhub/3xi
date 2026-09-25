"""Installer overrides must reach the core, gateway and links without replacing identities."""
import contextlib
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from threexi import cli, deploy
from threexi.core import ConfigError, inspect, prepare
from threexi.links import export_links

ROOT = Path(__file__).resolve().parents[1]


class GrpcOptionsTests(unittest.TestCase):
    def test_custom_values_reach_core_gateway_host_and_links(self):
        source = ROOT/'x-ui.db'
        before = source.read_bytes()
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)/'render'
            plan = prepare(source, out, ROOT, certificate_mode='auto',
                           grpc_service_name='/exir.v2.Tunnel/', grpc_authority='edge.example.org',
                           grpc_mode='gun', advertised='1.1.1.1', domain='tls.example.org')
            self.assertEqual(plan['route'], '/exir.v2.Tunnel/')
            self.assertIn('location ^~ /exir.v2.Tunnel/', (out/'nginx.conf').read_text())
            core = json.loads((out/'core-validation.json').read_text())
            inbound = next(x for x in core['inbounds'] if x.get('tag') == plan['tag'])
            grpc = inbound['streamSettings']['grpcSettings']
            self.assertEqual((grpc['serviceName'], grpc['authority'], grpc['multiMode']),
                             ('exir.v2.Tunnel', 'edge.example.org', False))
            with sqlite3.connect(source) as seed, sqlite3.connect(out/'x-ui.db') as db:
                for table in ('clients','users','client_inbounds','client_traffics','api_tokens'):
                    self.assertEqual(seed.execute(f'SELECT * FROM {table} ORDER BY 1').fetchall(),
                                     db.execute(f'SELECT * FROM {table} ORDER BY 1').fetchall())
                self.assertEqual(db.execute('SELECT address,sni,host_header,path FROM hosts WHERE inbound_id=14').fetchone(),
                                 ('1.1.1.1', 'tls.example.org', 'edge.example.org', ''))
                self.assertEqual(seed.execute('SELECT * FROM inbounds WHERE id!=14 ORDER BY id').fetchall(),
                                 db.execute('SELECT * FROM inbounds WHERE id!=14 ORDER BY id').fetchall())
            for link in export_links(out/'x-ui.db', 'tls.example.org', 'edge.example.org'):
                q = parse_qs(urlsplit(link).query)
                self.assertEqual(q['serviceName'], ['exir.v2.Tunnel'])
                self.assertEqual(q['authority'], ['edge.example.org'])
                self.assertEqual(q['mode'], ['gun'])
        self.assertEqual(source.read_bytes(), before)

    def test_empty_authority_explicitly_clears_only_host_override(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)/'render'
            prepare(ROOT/'x-ui.db', out, ROOT, certificate_mode='auto', grpc_authority='')
            with sqlite3.connect(out/'x-ui.db') as db:
                self.assertEqual(db.execute('SELECT host_header FROM hosts WHERE inbound_id=14').fetchone()[0], '')
                stream=json.loads(db.execute('SELECT stream_settings FROM inbounds WHERE id=14').fetchone()[0])
                self.assertEqual(stream['grpcSettings']['authority'], '')
            self.assertIn('server_name _;', (out/'nginx.conf').read_text())
            self.assertNotIn('exirhub.site', (out/'nginx.conf').read_text())

    def test_bad_paths_hosts_modes_and_reserved_routes_fail_before_render(self):
        for opts in ({'grpc_service_name': 'x; return 200;'}, {'grpc_service_name':'../x'},
                     {'grpc_service_name':'/name/Tun'}, {'grpc_service_name':'assets'},
                     {'grpc_service_name':'.well-known'}, {'grpc_authority':'x\nmalicious'},
                     {'grpc_authority':'https://example.org'}, {'grpc_mode':'wrong'}):
            with self.subTest(opts=opts), tempfile.TemporaryDirectory() as temp:
                out=Path(temp)/'render'
                with self.assertRaises(ConfigError):
                    prepare(ROOT/'x-ui.db', out, ROOT, certificate_mode='auto', **opts)
                self.assertFalse(out.exists())

    def test_cli_flags_override_environment_and_path_alias_is_supported(self):
        argv=['3xi','inspect','--grpc-path','/chosen.Tunnel/','--grpc-authority','','--grpc-mode','gun']
        with patch.dict(os.environ, {'THREEXI_GRPC_SERVICE_NAME':'env.Tunnel','THREEXI_GRPC_AUTHORITY':'env.example.org'}), \
                patch('sys.argv',argv), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.main(),0)
        plan=json.loads(output.getvalue())
        self.assertEqual(plan['route'],'/chosen.Tunnel/')
        self.assertEqual(plan['grpc_authority_override'],'')
        self.assertFalse(plan['multi_mode'])

    def test_default_selection_keeps_source_values(self):
        plan=inspect(ROOT/'x-ui.db')
        self.assertEqual(plan['route'],'/google.internal.analytics.v1.Tracker/')
        self.assertIsNone(plan['grpc_authority_override'])
        self.assertTrue(plan['multi_mode'])
        self.assertFalse(plan['public_address_override'])

    def test_link_command_uses_installed_authority_but_allows_explicit_sni(self):
        for extra,expected in (([], 'installed.example.org'), (['--authority',''], ''),
                               (['--authority','override.example.org'],'override.example.org')):
            with tempfile.TemporaryDirectory() as temp:
                state=Path(temp)/'installed.json'
                state.write_text(json.dumps({'plan':{'grpc_authority_override':'installed.example.org'}}))
                with patch.object(deploy,'STATE',state), patch('sys.argv',['3xi','links','--sni','client.example.org',*extra]), \
                        patch('threexi.links.export_links',return_value=[]) as export, contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(cli.main(),0)
                self.assertEqual(export.call_args.args[2],expected)
