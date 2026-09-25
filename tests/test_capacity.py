"""Capacity diagnostics must distinguish socket sides and incomplete evidence."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('capacity', Path(__file__).parents[1] / 'scripts/diagnose-capacity.py')
capacity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capacity)


class CapacityTests(unittest.TestCase):
    def test_source_port_budget_accounts_for_reserved_and_overlapping_ranges(self):
        self.assertEqual(capacity.port_budget('32768 60999', '')['candidate_ports_per_source_ip_and_destination'], 28232)
        budget = capacity.port_budget('40000 40010', '80,40000-40002,40001-40003,40010-40020')
        self.assertEqual(budget['candidate_ports_per_source_ip_and_destination'], 6)
        self.assertIsNone(capacity.port_budget('1 999999999', ''))
        self.assertIsNone(capacity.port_budget('32768 60999', None))

    def test_socket_counts_separate_frontend_and_both_backend_sides(self):
        rows = [
            '0: 0100007F:C350 0100007F:2711 01',
            '1: 0100007F:2711 0100007F:C350 01',
            '2: 00000000:2711 00000000:0000 0A',
            '3: 00000000:01BB 00000000:0000 0A',
            '4: 0100007F:01BB 0200007F:C351 01',
            '5: 0100007F:C353 0200007F:2711 01',
            '6: 0100007F:C354 0100007F:2711 06',
            'sl local_address rem_address st',
        ]
        counts = capacity.tcp_counts(rows, 10001)
        self.assertEqual(counts['local_443'], {'LISTEN': 1, 'ESTABLISHED': 1})
        self.assertEqual(counts['backend_outgoing'], {'ESTABLISHED': 1, 'TIME_WAIT': 1})
        self.assertEqual(counts['backend_accepted'], {'ESTABLISHED': 1})
        self.assertEqual(counts['namespace_all_tcp']['ESTABLISHED'], 4)

    def test_configuration_summary_does_not_dump_management_paths_or_comments(self):
        text = '''# worker_connections 999999;
events { worker_connections 4096; }
http { keepalive_timeout 75s; location /secret-panel/ { proxy_pass http://secret-domain; } }
worker_processes auto;
grpc_read_timeout $private_value;
'''
        result = capacity.config_summary(text)
        self.assertEqual(result['worker_connections'], ['4096'])
        self.assertEqual(result['worker_processes'], ['auto'])
        self.assertEqual(result['grpc_read_timeout'], [])
        self.assertNotIn('secret', json.dumps(result))

    def test_log_window_and_finite_durations_do_not_claim_grpc_success(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            now = datetime.now(timezone.utc)
            rows = [
                {'time': now.isoformat(), 'status': '200', 'upstream': '200', 'duration': '5.0', 'path': 'PRIVATE'},
                {'time': now.isoformat(), 'status': '499', 'upstream': '-', 'duration': 'NaN'},
                {'time': (now - timedelta(hours=2)).isoformat(), 'status': '504', 'duration': '3600'},
                {'time': (now + timedelta(hours=2)).isoformat(), 'status': '502', 'duration': '10'},
            ]
            (directory / 'nginx-access.log').write_text('\n'.join(map(json.dumps, rows)) + '\nbroken PRIVATE\n')
            (directory / 'nginx-error.log').write_text(now.astimezone().strftime('%Y/%m/%d %H:%M:%S') +
                ' [error] upstream prematurely closed connection, client: PRIVATE, request: PRIVATE\n')
            result = capacity.log_summary(directory, 30)
            self.assertEqual(result['access']['http_statuses'], {'200': 1, '499': 1})
            self.assertEqual(result['access']['duration_p95_seconds'], 5)
            self.assertIn('HTTP 200 does not prove gRPC success', result['access']['scope'])
            self.assertEqual(result['error']['pattern_counts'], {'upstream_closed_early': 1})
            self.assertNotIn('PRIVATE', json.dumps(result, allow_nan=False))

    def test_tail_is_bounded_and_missing_log_is_not_empty_success(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'log'
            path.write_text('A' * 100 + '\nnew 1\nnew 2\nnew 3\n')
            with patch.object(capacity, 'MAX_LOG_BYTES', 25), patch.object(capacity, 'MAX_LOG_LINES', 2):
                lines, truncated = capacity.tail_lines(path)
            self.assertEqual(lines, ['new 2', 'new 3'])
            self.assertTrue(truncated)
            result = capacity.log_summary(Path(temp), 30)
            self.assertFalse(result['access']['available'])
            self.assertNotIn('http_statuses', result['access'])

    def test_error_labels_distinguish_capacity_from_resets_without_raw_messages(self):
        counts = capacity.error_counts([
            '[alert] 4096 worker_connections are not enough',
            '[crit] connect() failed (99: Cannot assign requested address) while connecting to upstream',
            '[error] recv() failed (104: Connection reset by peer), client: PRIVATE',
            '[error] ordinary message, client: PRIVATE, request: GET /too_many_pings',
            'gRPC GOAWAY: ENHANCE_YOUR_CALM too_many_pings',
            'transport closed: unexpected EOF',
        ])
        self.assertEqual(counts['worker_connections_exhausted'], 1)
        self.assertEqual(counts['address_allocation_failed'], 1)
        self.assertEqual(counts['grpc_ping_rejected'], 1)
        self.assertEqual(counts['connection_reset'], 1)
        self.assertEqual(counts['eof'], 1)
        self.assertNotIn('PRIVATE', json.dumps(counts))

    def test_descendants_report_actual_core_fd_limits_not_shell_ulimit(self):
        with tempfile.TemporaryDirectory() as temp:
            proc = Path(temp)
            for pid, parent, name in ((10, 1, 'nginx'), (11, 10, 'nginx'), (20, 1, 'x-ui'), (21, 20, 'xray-linux-amd')):
                node = proc / str(pid)
                (node / 'fd').mkdir(parents=True)
                (node / 'fd/0').touch()
                (node / 'fd/1').touch()
                (node / 'status').write_text(f'Name:\t{name}\nPPid:\t{parent}\nVmRSS:\t4096 kB\nThreads:\t2\n')
                (node / 'limits').write_text('Max open files            65536                65536                files\n')
            def systemctl(args):
                self.assertEqual(args[:2], ['systemctl', 'show'])
                return 'MainPID=' + ('10' if args[2] == 'threexi-nginx.service' else '20') + '\nActiveState=active\n'
            with patch.object(capacity, 'PROC', proc), patch.object(capacity, 'run', side_effect=systemctl):
                result = capacity.units_and_processes()
            core = next(item for item in result['processes'] if item['role'] == 'xray')
            self.assertEqual(core['pid'], 21)
            self.assertEqual(core['fd_soft_limit'], '65536')
            self.assertEqual(core['fd_count'], 2)
            self.assertEqual(len(result['processes']), 4)

    def test_missing_service_properties_are_explicitly_unavailable(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(capacity, 'PROC', Path(temp)), patch.object(capacity, 'run', return_value='unrecognized output\n'):
                result = capacity.units_and_processes()
            self.assertFalse(result['units']['x-ui.service']['available'])
            self.assertFalse(result['units']['threexi-nginx.service']['available'])
            self.assertEqual(result['processes'], [])


if __name__ == '__main__':
    unittest.main()
