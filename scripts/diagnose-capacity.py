#!/usr/bin/env python3
"""Bounded, read-only EOF/capacity report. No requests, service changes or DB reads."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time


PROC = Path('/proc')
MAX_LOG_BYTES = 2 * 1024 * 1024
MAX_LOG_LINES = 5000
DIRECTIVES = (
    'worker_processes', 'worker_connections', 'worker_rlimit_nofile',
    'http2_max_concurrent_streams', 'keepalive_timeout', 'keepalive_requests',
    'keepalive_time', 'grpc_connect_timeout', 'grpc_read_timeout',
    'grpc_send_timeout', 'grpc_socket_keepalive', 'client_body_timeout', 'send_timeout',
)
STATES = dict(zip(
    ('01', '02', '03', '04', '05', '06', '07', '08', '09', '0A', '0B', '0C'),
    ('ESTABLISHED', 'SYN_SENT', 'SYN_RECV', 'FIN_WAIT1', 'FIN_WAIT2', 'TIME_WAIT',
     'CLOSE', 'CLOSE_WAIT', 'LAST_ACK', 'LISTEN', 'CLOSING', 'NEW_SYN_RECV'),
))
ERROR_PATTERNS = {
    'worker_connections_exhausted': r'worker_connections are not enough',
    'open_files_exhausted': r'too many open files',
    'address_allocation_failed': r'cannot assign requested address',
    'upstream_refused': r'connect\(\) failed \(111:',
    'upstream_timeout': r'upstream timed out',
    'upstream_closed_early': r'upstream (?:prematurely )?closed',
    'connection_reset': r'connection reset by peer|forcibly closed',
    'http2_goaway': r'\bgoaway\b',
    'http2_rst_stream': r'rst[_ ]stream',
    'grpc_ping_rejected': r'too_many_pings|too many pings|enhance_your_calm',
    'eof': r'\b(?:unexpected )?eof\b',
    'out_of_memory': r'out of memory|oom-kill|oom_kill|killed process',
    'service_reload': r'reloading|reloaded|reconfiguring',
    'service_restart': r'scheduled restart job|main process exited',
}


def read(path, limit=512 * 1024):
    try:
        with Path(path).open('r', errors='replace') as stream:
            return stream.read(limit)
    except OSError:
        return None


def run(args, *, merge_stderr=False):
    try:
        result = subprocess.run(args, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT if merge_stderr else subprocess.PIPE,
                                text=True, errors='replace', timeout=10)
        return result.stdout if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def integer(text):
    return int(text) if text is not None and re.fullmatch(r'\d+', text.strip()) else None


def config_summary(text):
    # Only literal numeric/boolean directives, never paths, domains or headers.
    text = re.sub(r'#[^\n]*', '', text or '')
    found = {}
    for name in DIRECTIVES:
        values = re.findall(r'(?:^|[;{}\n])\s*' + name + r'\s+([^;{}]+);', text)
        found[name] = [v.strip() for v in values if re.fullmatch(r'(?:auto|on|off|\d+[kKmMgGhHsS]?)', v.strip())]
    return found


def port_budget(port_range, reserved):
    try:
        lo, hi = map(int, port_range.split())
        if not 1 <= lo <= hi <= 65535 or reserved is None:
            return None
        excluded = set()
        for part in reserved.strip().split(','):
            if not part:
                continue
            ends = part.split('-')
            first, last = int(ends[0]), int(ends[-1])
            if len(ends) > 2 or not 0 <= first <= last <= 65535:
                return None
            excluded.update(range(max(lo, first), min(hi, last) + 1))
        return {'range': [lo, hi], 'reserved_in_range': len(excluded),
                'candidate_ports_per_source_ip_and_destination': hi - lo + 1 - len(excluded)}
    except (AttributeError, TypeError, ValueError):
        return None


def tcp_counts(lines, backend_port):
    groups = {key: Counter() for key in ('namespace_all_tcp', 'local_443', 'backend_outgoing', 'backend_accepted')}
    for line in lines:
        parts = line.split()
        try:
            local_host, local_port = parts[1].rsplit(':', 1)
            remote_host, remote_port = parts[2].rsplit(':', 1)
            local_port, remote_port = int(local_port, 16), int(remote_port, 16)
            state = STATES[parts[3]]
        except (IndexError, ValueError, KeyError):
            continue
        groups['namespace_all_tcp'][state] += 1
        if local_port == 443:
            groups['local_443'][state] += 1
        if remote_host == '0100007F' and remote_port == backend_port:
            groups['backend_outgoing'][state] += 1
        if local_host == '0100007F' and local_port == backend_port:
            groups['backend_accepted'][state] += 1
    return groups


def sockets(backend_port):
    combined, missing = {}, []
    for name in ('tcp', 'tcp6'):
        try:
            with (PROC / 'net' / name).open() as stream:
                groups = tcp_counts(stream, backend_port)
            for key, counts in groups.items():
                combined.setdefault(key, Counter()).update(counts)
        except OSError:
            missing.append(name)
    return {'counts': combined, 'unavailable_tables': missing,
            'scope': 'current network namespace, all processes; socket sides are separate, not additive'}


def tail_lines(path):
    try:
        with Path(path).open('rb') as stream:
            size = stream.seek(0, 2)
            stream.seek(max(0, size - MAX_LOG_BYTES))
            data = stream.read(MAX_LOG_BYTES)
        if size > MAX_LOG_BYTES:
            data = data.partition(b'\n')[2]  # discard an incomplete first record
        lines = data.decode('utf-8', errors='replace').splitlines()
        return lines[-MAX_LOG_LINES:], size > MAX_LOG_BYTES or len(lines) > MAX_LOG_LINES
    except OSError:
        return None, False


def error_counts(lines):
    counts = Counter()
    for line in lines:
        # Do not let request URL text drive the Nginx error classification.
        message = line.split(', client:', 1)[0]
        for name, pattern in ERROR_PATTERNS.items():
            if re.search(pattern, message, re.I):
                counts[name] += 1
    return dict(counts)


def log_summary(directory, minutes):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=minutes)
    result = {'window_minutes': minutes, 'max_bytes_per_file': MAX_LOG_BYTES,
              'max_lines_per_file': MAX_LOG_LINES, 'rotated_files_read': False}
    for kind in ('access', 'error'):
        lines, truncated = tail_lines(directory / f'nginx-{kind}.log')
        if lines is None:
            result[kind] = {'available': False}
            continue
        statuses, upstream, durations, errors, stamps = Counter(), Counter(), [], [], []
        unreadable = 0
        for line in lines:
            try:
                row = json.loads(line) if kind == 'access' else None
                stamp = (datetime.fromisoformat(row['time']) if row is not None else
                         datetime.strptime(line[:19], '%Y/%m/%d %H:%M:%S').astimezone())
                if stamp.tzinfo is None:
                    raise ValueError('missing timezone')
                if not cutoff <= stamp <= now:
                    continue
                stamps.append(stamp)
                if row is not None:
                    status = str(row.get('status', ''))
                    if re.fullmatch(r'\d{3}', status):
                        statuses[status] += 1
                    for code in re.findall(r'(?<!\d)\d{3}(?!\d)', str(row.get('upstream', ''))):
                        upstream[code] += 1
                    duration = float(row.get('duration', '-1'))
                    if math.isfinite(duration) and duration >= 0:
                        durations.append(duration)
                else:
                    errors.append(line)
            except (TypeError, ValueError, KeyError, AttributeError):
                unreadable += 1
        item = {'available': True, 'tail_truncated': truncated, 'records_in_window': len(stamps),
                'unparsed_records': unreadable,
                'first_utc': min(stamps).astimezone(timezone.utc).isoformat() if stamps else None,
                'last_utc': max(stamps).astimezone(timezone.utc).isoformat() if stamps else None}
        if kind == 'access':
            durations.sort()
            item.update({'http_statuses': statuses, 'upstream_statuses': upstream,
                         'duration_p50_seconds': durations[len(durations) // 2] if durations else None,
                         'duration_p95_seconds': durations[max(0, math.ceil(len(durations) * .95) - 1)] if durations else None,
                         'scope': 'all routes, completed requests only; HTTP 200 does not prove gRPC success'})
        else:
            item['pattern_counts'] = error_counts(errors)
        result[kind] = item
    return result


def units_and_processes():
    units, roots = {}, {}
    properties = ('LoadState', 'ActiveState', 'SubState', 'MainPID', 'NRestarts', 'LimitNOFILE', 'LimitNOFILESoft',
                  'TasksCurrent', 'TasksMax', 'MemoryCurrent', 'MemoryMax', 'CPUQuotaPerSecUSec')
    for unit, role in (('threexi-nginx.service', 'nginx_master'), ('x-ui.service', 'panel')):
        output = run(['systemctl', 'show', unit, '--property=' + ','.join(properties)])
        values = dict(line.split('=', 1) for line in (output or '').splitlines() if '=' in line)
        units[unit] = {k: v for k, v in values.items() if k in properties and re.fullmatch(r'[\w .:/-]{0,80}', v)}
        units[unit]['available'] = bool(units[unit])
        pid = integer(values.get('MainPID'))
        if pid:
            roots[pid] = role
    statuses = {}
    for entry in PROC.iterdir():
        if entry.name.isdigit():
            text = read(entry / 'status', 16384)
            if text:
                statuses[int(entry.name)] = dict(line.split(':', 1) for line in text.splitlines() if ':' in line)
    descendants = dict(roots)
    while True:
        added = {pid: 'child' for pid, status in statuses.items()
                 if pid not in descendants and integer(status.get('PPid')) in descendants}
        if not added:
            break
        descendants.update(added)
    processes = []
    for pid, role in sorted(descendants.items()):
        status = statuses.get(pid, {})
        name = status.get('Name', '').strip()
        if role == 'child':
            role = 'xray' if name.startswith('xray') else ('nginx_worker' if name == 'nginx' else 'child')
        try:
            with os.scandir(PROC / str(pid) / 'fd') as entries:
                fds = sum(1 for _ in entries)
        except OSError:
            fds = None
        limits = read(PROC / str(pid) / 'limits') or ''
        match = re.search(r'^Max open files\s+(\d+|unlimited)\s+(\d+|unlimited)', limits, re.M)
        memory = {}
        for key in ('VmRSS', 'VmSwap', 'Threads'):
            value = status.get(key, '').split()
            memory[key] = integer(value[0]) if value else None
        processes.append({'pid': pid, 'role': role, 'fd_count': fds,
                          'fd_soft_limit': match[1] if match else None,
                          'fd_hard_limit': match[2] if match else None, **memory})
    return {'units': units, 'processes': processes,
            'process_scope': 'systemd MainPIDs and descendants; values can change during collection; VmRSS/VmSwap in KiB'}


def resource_sample():
    stat = (read(PROC / 'stat') or '').splitlines()
    ticks = [int(x) for x in stat[0].split()[1:9]] if stat and stat[0].startswith('cpu ') else []
    net = [0, 0]
    for line in (read(PROC / 'net/dev') or '').splitlines():
        if ':' in line:
            name, data = line.split(':', 1)
            values = data.split()
            if name.strip() != 'lo' and len(values) >= 16:
                net[0] += int(values[0])
                net[1] += int(values[8])
    counters = {}
    wanted = {'Tcp:': ('RetransSegs', 'EstabResets', 'OutRsts'),
              'TcpExt:': ('ListenOverflows', 'ListenDrops', 'TCPBacklogDrop', 'TCPAbortOnMemory')}
    for name in ('snmp', 'netstat'):
        lines = (read(PROC / 'net' / name) or '').splitlines()
        for header, values in zip(lines[::2], lines[1::2]):
            keys, data = header.split(), values.split()
            if keys and data and keys[0] == data[0] and keys[0] in wanted:
                counters.update({k: int(v) for k, v in zip(keys[1:], data[1:]) if k in wanted[keys[0]]})
    return {'monotonic': time.monotonic(), 'ticks': ticks, 'network_bytes': net, 'tcp_counters': counters}


def resource_delta(first, second):
    seconds = second['monotonic'] - first['monotonic']
    ticks = [b - a for a, b in zip(first['ticks'], second['ticks'])]
    total = sum(ticks)
    return {'sample_seconds': round(seconds, 2),
            'host_cpu_busy_percent': round(100 * (total - ticks[3] - ticks[4]) / total, 1) if total > 0 else None,
            'all_non_loopback_rx_mbps': round(8 * max(0, second['network_bytes'][0] - first['network_bytes'][0]) / seconds / 1e6, 3),
            'all_non_loopback_tx_mbps': round(8 * max(0, second['network_bytes'][1] - first['network_bytes'][1]) / seconds / 1e6, 3),
            'tcp_counter_deltas': {key: value - first['tcp_counters'][key] for key, value in second['tcp_counters'].items()
                                   if key in first['tcp_counters']},
            'scope': 'host CPU; network namespace counters for all services; virtual interfaces may double count traffic'}


def report(args):
    first = resource_sample()
    config = read(Path('/etc/3xi/nginx.conf'))
    match = re.search(r'grpc_pass\s+grpc://127\.0\.0\.1:(\d+);', config or '')
    backend = args.backend_port or (int(match[1]) if match else 10001)
    result = {'collected_at_utc': datetime.now(timezone.utc).isoformat(),
              'read_only': True, 'backend_port': backend,
              'backend_port_source': 'argument' if args.backend_port else ('nginx file' if match else 'default; confirm on server'),
              'logical_cpus': os.cpu_count(), 'nginx_config_file_found': config is not None,
              'nginx_directives_on_disk': config_summary(config),
              'runtime': units_and_processes(), 'sockets': sockets(backend)}
    memory = {}
    for line in (read(PROC / 'meminfo') or '').splitlines():
        key, value = line.split(':', 1)
        if key in ('MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'):
            memory[key] = integer(value.split()[0])
    result['memory_KiB'] = memory
    result['ephemeral_ports'] = port_budget(read(PROC / 'sys/net/ipv4/ip_local_port_range'), read(PROC / 'sys/net/ipv4/ip_local_reserved_ports'))
    result['kernel_limits'] = {name: integer(read(PROC / 'sys' / name.replace('.', '/')))
                               for name in ('fs.file-max', 'fs.nr_open', 'net.core.somaxconn',
                                            'net.netfilter.nf_conntrack_count', 'net.netfilter.nf_conntrack_max')}
    result['disk_free_bytes'] = {}
    for directory in ('/var/log', '/etc/x-ui'):
        try:
            result['disk_free_bytes'][directory] = shutil.disk_usage(directory).free
        except OSError:
            result['disk_free_bytes'][directory] = None
    version = re.search(r'nginx/([0-9][0-9A-Za-z.+-]{0,40})', run(['nginx', '-v'], merge_stderr=True) or '')
    result['nginx_version'] = version[1] if version else None
    result['logs'] = log_summary(Path('/var/log/3xi'), args.minutes)
    for label, selectors in (('service_journal', ['-u', 'x-ui.service', '-u', 'threexi-nginx.service']), ('kernel_journal', ['-k'])):
        output = run(['journalctl', *selectors, '--since', f'{args.minutes} minutes ago', '--no-pager', '-o', 'cat', '-n', str(MAX_LOG_LINES)])
        lines = output.splitlines() if output is not None else []
        result[label] = {'available': output is not None, 'bounded_lines': len(lines),
                         'line_limit_reached': len(lines) >= MAX_LOG_LINES, 'pattern_counts': error_counts(lines)}
    remaining = args.sample_seconds - (time.monotonic() - first['monotonic'])
    if remaining > 0:
        time.sleep(remaining)
    result['activity_sample'] = resource_delta(first, resource_sample())
    result['interpretation'] = [
        'This is a diagnostic snapshot, not a load test or a supported-user count.',
        'On-disk directives may differ from the running configuration until a successful reload.',
        'TCP counts cannot measure active HTTP/2 streams or logical connections inside gRPC multiMode.',
        'An empty error sample does not exclude an upstream, CDN or client-side disconnect.',
        'No database, keys, URLs, request bodies, process arguments or raw log messages are printed.',
    ]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--minutes', type=int, default=30, help='Log window, 1-1440 minutes (bounded tail only)')
    parser.add_argument('--sample-seconds', type=int, default=5, help='Minimum activity sample, 1-10 seconds')
    parser.add_argument('--backend-port', type=int, help='Override detected loopback gRPC port')
    args = parser.parse_args()
    if not 1 <= args.minutes <= 1440 or not 1 <= args.sample_seconds <= 10:
        parser.error('minutes must be 1-1440 and sample-seconds 1-10')
    if args.backend_port is not None and not 1 <= args.backend_port <= 65535:
        parser.error('backend-port must be 1-65535')
    if os.geteuid() != 0:
        parser.error('Run with sudo to read process limits and service logs.')
    print(json.dumps(report(args), indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
