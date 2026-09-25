"""Resource tuning preserves the running application's configuration and database."""
import json
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from threexi import deploy, performance
from threexi.core import ConfigError, nginx_config


ROOT = Path(__file__).resolve().parents[1]


class ProfileTests(unittest.TestCase):
    def test_rejects_injection_booleans_unknown_fields_and_missing_fd_headroom(self):
        for values in (
            {**performance.profile(), 'h2_streams': '256; worker_processes 99'},
            {**performance.profile(), 'nofile': True},
            {**performance.profile(), 'worker_connections': 262144},
            {**performance.profile(), 'extra': 1},
        ):
            with self.assertRaises(ConfigError):
                performance.validate(values)

    def test_units_match_selected_profile_and_legacy_plans_keep_old_limits(self):
        self.assertEqual(performance.for_plan({}), performance.LEGACY)
        for preset in performance.PROFILES:
            limits = performance.profile(preset)
            units = deploy.unit_files(limits)
            for unit in performance.UNITS:
                self.assertIn(f'LimitNOFILE={limits["nofile"]}\n', units[unit])
            self.assertNotIn('LimitNOFILE', units['threexi-refresh.service'])


class TuneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.gateway = self.root / 'nginx.conf'
        self.state_path = self.root / 'installed.json'
        self.installed = self.root / 'app'
        self.installed.mkdir()
        self.systemd = self.root / 'systemd'
        self.systemd.mkdir()
        for name in ('core.py', 'deploy.py', 'cli.py'):
            (self.installed / name).write_text('# previous installed module\n')
        self.db = self.root / 'x-ui.db'
        self.db.write_bytes(b'active user identities and traffic counters')
        self.state = {'plan': {'route': '/sample.Tracker/', 'backend_port': 10001,
                              'panel_path': '/private-panel/', 'panel_port': 8144,
                              'subscription_paths': [], 'subscription_port': 2096},
                      'modern_nginx': True, 'ipv6': False, 'owned': []}
        self.state_path.write_text(json.dumps(self.state))
        self.gateway.write_text(nginx_config(self.state['plan'], ipv6=False))
        self.before = {p: p.read_bytes() for p in (self.state_path, self.gateway, self.db, *self.installed.iterdir())}
        self.roots = {'x-ui.service': 10, 'threexi-nginx.service': 20}
        self.identities = {10: (1, 100), 20: (1, 200), 11: (10, 101), 21: (20, 201)}
        self.limits = {pid: (65536, 65536) for pid in self.identities}
        self.events = []
        self.fail_test = False
        self.fail_reload = False
        self.deny_pid = None
        self.enter(patch.object(performance, 'GATEWAY', self.gateway))
        self.enter(patch.object(performance, 'INSTALLED', self.installed))
        self.enter(patch.object(performance, 'SYSTEMD', self.systemd))
        self.enter(patch.object(deploy, 'STATE', self.state_path))
        self.enter(patch.object(performance.os, 'geteuid', return_value=0))
        self.enter(patch.object(performance, 'check_kernel'))
        self.enter(patch.object(performance, 'main_pids', side_effect=lambda units: {unit: self.roots[unit] for unit in units}))
        self.enter(patch.object(performance, 'descendants', side_effect=self.descendants))
        self.enter(patch.object(performance, 'process_identity', side_effect=self.identities.get))
        self.enter(patch.object(performance.resource, 'prlimit', side_effect=self.prlimit))
        self.enter(patch.object(performance, 'verify_workers', return_value=1))
        self.enter(patch.object(deploy, 'command', side_effect=self.command))
        self.enter(patch.object(deploy, 'health', return_value={'services': 'active'}))

    def enter(self, context):
        value = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        return value

    def prlimit(self, pid, kind, new=None):
        self.assertEqual(kind, resource.RLIMIT_NOFILE)
        old = self.limits[pid]
        if new is not None:
            if self.deny_pid == pid and new[0] > old[0]:
                raise PermissionError('denied')
            self.limits[pid] = new
        return old

    def descendants(self, roots):
        selected = {pid: self.identities[pid] for pid in roots}
        for pid, identity in self.identities.items():
            if identity[0] in selected:
                selected[pid] = identity
        return selected

    def command(self, args, **kwargs):
        self.events.append(args)
        if args[:2] == ['nginx', '-t']:
            self.assertIn('worker_connections 65536;', Path(args[-1]).read_text())
            if self.fail_test:
                raise ConfigError('nginx test failed')
        elif args[:2] == ['systemctl', 'show']:
            return 'LimitNOFILE=262144\nLimitNOFILESoft=262144\n'
        elif args[:2] == ['systemctl', 'reload'] and self.fail_reload:
            self.fail_reload = False
            raise ConfigError('reload failed')
        elif args not in (['systemctl', 'daemon-reload'], ['systemctl', 'reload', 'threexi-nginx.service'],
                          ['systemctl', 'is-active', '--quiet', 'threexi-nginx.service']):
            if args[:2] != ['nginx', '-t']:
                self.fail(f'Unexpected command: {args}')
        return ''

    def unchanged(self):
        for path, data in self.before.items():
            self.assertEqual(path.read_bytes(), data, str(path))
        self.assertFalse((self.installed / 'performance.py').exists())
        self.assertEqual(list(self.systemd.iterdir()), [])
        self.assertTrue(all(value == (65536, 65536) for value in self.limits.values()))

    def test_live_apply_persists_profile_and_is_idempotent_without_core_restart(self):
        result = performance.tune(ROOT, performance.profile())
        self.assertTrue(result['nginx_reloaded'])
        self.assertFalse(result['xray_restart'])
        self.assertEqual(self.db.read_bytes(), self.before[self.db])
        updated = json.loads(self.state_path.read_text())
        self.assertEqual(updated['plan']['performance'], performance.profile())
        self.assertFalse(updated['plan']['nginx_logging'])
        self.assertEqual(result['nginx_logs'], 'off')
        self.assertEqual(self.gateway.read_text(), nginx_config(updated['plan'], ipv6=False))
        self.assertIn('grpc_read_timeout 3600s;', self.gateway.read_text())
        self.assertIn('grpc_pass grpc://127.0.0.1:10001;', self.gateway.read_text())
        self.assertIn('error_log /dev/null emerg;', self.gateway.read_text())
        self.assertIn('    access_log off;', self.gateway.read_text())
        self.assertNotIn('/var/log/3xi/nginx-', self.gateway.read_text())
        self.assertEqual(updated['plan']['panel_path'], self.state['plan']['panel_path'])
        for name in performance.MODULES:
            self.assertEqual((self.installed / name).read_bytes(), (ROOT / 'threexi' / name).read_bytes())
        self.assertTrue(all(value == (262144, 262144) for value in self.limits.values()))
        before_reload = sum(args[:2] == ['systemctl', 'reload'] for args in self.events)
        again = performance.tune(ROOT, performance.profile())
        self.assertEqual(again['changed_files'], 0)
        self.assertFalse(again['nginx_reloaded'])
        self.assertEqual(sum(args[:2] == ['systemctl', 'reload'] for args in self.events), before_reload)
        self.assertFalse(any('restart' in args or 'stop' in args for args in self.events))

    def test_dry_run_validates_without_persistent_or_live_limit_changes(self):
        result = performance.tune(ROOT, performance.profile(), dry_run=True)
        self.assertTrue(result['dry_run'])
        self.unchanged()

    def test_bad_nginx_candidate_is_rejected_before_mutation(self):
        self.fail_test = True
        with self.assertRaisesRegex(ConfigError, 'nginx test'):
            performance.tune(ROOT, performance.profile())
        self.unchanged()

    def test_reload_failure_restores_files_and_process_limits(self):
        self.fail_reload = True
        with self.assertRaisesRegex(ConfigError, 'reload failed'):
            performance.tune(ROOT, performance.profile())
        self.unchanged()
        self.assertEqual(sum(args[:2] == ['systemctl', 'reload'] for args in self.events), 2)

    def test_partial_live_limit_failure_restores_previously_raised_process(self):
        self.deny_pid = 20
        with self.assertRaisesRegex(ConfigError, 'CAP_SYS_RESOURCE'):
            performance.tune(ROOT, performance.profile())
        self.unchanged()

    def test_manual_route_edit_is_not_overwritten(self):
        self.gateway.write_text(self.gateway.read_text().replace('127.0.0.1:10001', '127.0.0.1:10002'))
        self.before[self.gateway] = self.gateway.read_bytes()
        with self.assertRaisesRegex(ConfigError, 'beyond resource limits'):
            performance.tune(ROOT, performance.profile())
        self.unchanged()

    def test_higher_existing_live_limits_are_preserved(self):
        self.limits[11] = (524288, 1048576)
        performance.tune(ROOT, performance.profile())
        self.assertEqual(self.limits[11], (524288, 1048576))

    def test_logging_can_be_explicitly_reenabled_and_survives_rendering(self):
        performance.tune(ROOT, performance.profile())
        result = performance.tune(ROOT, performance.profile(), nginx_logging=True)
        self.assertEqual(result['nginx_logs'], 'on')
        state = json.loads(self.state_path.read_text())
        self.assertTrue(state['plan']['nginx_logging'])
        self.assertIn('/var/log/3xi/nginx-access.log', self.gateway.read_text())
        self.assertEqual(self.gateway.read_text(), nginx_config(state['plan'], ipv6=False))
        self.assertEqual(self.db.read_bytes(), self.before[self.db])

    def test_nginx_only_hot_update_does_not_touch_xray_limits_or_domain_routes(self):
        original_plan = dict(self.state['plan'])
        # The certificate/domain values remain data in the same installed plan.
        original_plan.update({'domain': 'existing.example.org', 'tls_domain': '',
                              'certificate': {'mode': 'local', 'private_metadata': 'preserved'}})
        self.state['plan'] = original_plan
        self.state_path.write_text(json.dumps(self.state))
        with patch.object(deploy, 'health', side_effect=AssertionError('Nginx-only must not require panel/core health')):
            result = performance.tune(ROOT, performance.profile(), nginx_only=True)
        self.assertEqual(result['scope'], 'nginx')
        self.assertFalse(result['xray_limits_changed'])
        self.assertEqual(self.limits[10], (65536, 65536))
        self.assertEqual(self.limits[11], (65536, 65536))
        self.assertEqual(self.limits[20], (262144, 262144))
        self.assertEqual(self.limits[21], (262144, 262144))
        self.assertFalse((self.systemd / 'x-ui.service.d').exists())
        self.assertEqual(self.db.read_bytes(), self.before[self.db])
        updated = json.loads(self.state_path.read_text())['plan']
        for key, value in original_plan.items():
            self.assertEqual(updated[key], value)
        self.assertFalse(any('x-ui.service' in args for args in self.events))

    def test_later_systemd_override_aborts_and_restores(self):
        with patch.object(performance, 'verify_unit_limits', side_effect=ConfigError('overriding LimitNOFILE')):
            with self.assertRaisesRegex(ConfigError, 'overriding'):
                performance.tune(ROOT, performance.profile())
        self.unchanged()


class LivePrlimitTests(unittest.TestCase):
    def test_live_limit_increase_and_restore_on_our_own_child(self):
        if not hasattr(resource, 'prlimit'):
            self.skipTest('Linux prlimit is required')
        ceiling = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
        hard = 65536 if ceiling == resource.RLIM_INFINITY else min(ceiling, 65536)
        target, initial = hard // 2, hard // 4
        if initial < 64:
            self.skipTest('Test requires at least 256 inherited file descriptors')
        code = f'import resource,sys; resource.setrlimit(resource.RLIMIT_NOFILE,({initial},{hard})); print("ready",flush=True); sys.stdin.read()'
        with subprocess.Popen([sys.executable, '-c', code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) as child:
            try:
                self.assertEqual(child.stdout.readline().strip(), 'ready')
                identity = performance.process_identity(child.pid)
                changed = []
                performance.raise_limits({child.pid: identity}, target, changed)
                self.assertEqual(resource.prlimit(child.pid, resource.RLIMIT_NOFILE), (target, hard))
                self.assertEqual(performance.restore_limits(changed), [])
                self.assertEqual(resource.prlimit(child.pid, resource.RLIMIT_NOFILE), (initial, hard))
            finally:
                child.stdin.close()
                child.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
