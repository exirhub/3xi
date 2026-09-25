"""Validated resource profiles and an in-place upgrade of managed resource limits."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import resource
import subprocess
import tempfile
import time

from .core import ConfigError


PROFILES = {
    'standard': {'worker_connections': 16384, 'nofile': 131072, 'h2_streams': 128},
    'high': {'worker_connections': 65536, 'nofile': 262144, 'h2_streams': 256},
}
LEGACY = {'worker_connections': 4096, 'nofile': 65536, 'h2_streams': 128}
PROC = Path('/proc')
INSTALLED = Path('/opt/3xi/threexi')
GATEWAY = Path('/etc/3xi/nginx.conf')
SYSTEMD = Path('/etc/systemd/system')
UNITS = ('x-ui.service', 'threexi-nginx.service')
MODULES = ('performance.py', 'core.py', 'deploy.py', 'cli.py')


def validate(values):
    bounds = {'worker_connections': (1024, 262144), 'nofile': (16384, 1048576), 'h2_streams': (16, 1024)}
    if not isinstance(values, dict) or values.keys() != bounds.keys():
        raise ConfigError('Resource settings must contain worker_connections, nofile and h2_streams.')
    for key, (lo, hi) in bounds.items():
        if type(values[key]) is not int or not lo <= values[key] <= hi:
            raise ConfigError(f'{key} must be an integer in {lo}..{hi}.')
    if values['nofile'] < values['worker_connections'] + 1024:
        raise ConfigError('nofile must leave at least 1024 descriptors beyond worker_connections.')
    return dict(values)


def profile(name='high', **overrides):
    if name not in PROFILES:
        raise ConfigError('Resource profile must be standard or high.')
    return validate({**PROFILES[name], **{key: value for key, value in overrides.items() if value is not None}})


def for_plan(plan):
    # Updating code alone must not silently change limits on an older installation.
    return validate(plan.get('performance', LEGACY))


def check_kernel(nofile):
    try:
        maximum = int((PROC / 'sys/fs/nr_open').read_text().strip())
    except (OSError, ValueError) as error:
        raise ConfigError('Cannot read the kernel fs.nr_open ceiling.') from error
    if nofile > maximum:
        raise ConfigError(f'Requested nofile={nofile} exceeds fs.nr_open={maximum}; no limits were changed.')


def process_identity(pid):
    try:
        text = (PROC / str(pid) / 'stat').read_text()
        fields = text[text.rfind(')') + 2:].split()
        return (int(fields[1]), int(fields[19]))  # parent PID, start time
    except (OSError, ValueError, IndexError):
        return None


def descendants(roots):
    identities = {}
    for entry in PROC.iterdir():
        if entry.name.isdigit():
            identity = process_identity(int(entry.name))
            if identity is not None:
                identities[int(entry.name)] = identity
    selected = {pid: identities[pid] for pid in roots if pid in identities}
    while True:
        extra = {pid: identity for pid, identity in identities.items()
                 if pid not in selected and identity[0] in selected}
        if not extra:
            return selected
        selected.update(extra)


def main_pids(units=UNITS):
    from .deploy import command
    roots = {}
    for unit in units:
        text = command(['systemctl', 'show', unit, '--property=ActiveState,MainPID'])
        values = dict(line.split('=', 1) for line in text.splitlines() if '=' in line)
        pid = int(values.get('MainPID', '0'))
        if values.get('ActiveState') != 'active' or pid <= 0 or process_identity(pid) is None:
            raise ConfigError(f'{unit} must be running before applying a live resource profile.')
        roots[unit] = pid
    return roots


def limit_floor(old, requested):
    return tuple(value if value == resource.RLIM_INFINITY else max(value, requested) for value in old)


def raise_limits(processes, nofile, previous):
    # Roots are inserted before descendants: future Xray children inherit the higher ceiling.
    for pid, identity in processes.items():
        if process_identity(pid) != identity:
            continue
        try:
            old = resource.prlimit(pid, resource.RLIMIT_NOFILE)
            wanted = limit_floor(old, nofile)
            if wanted != old:
                resource.prlimit(pid, resource.RLIMIT_NOFILE, wanted)
                previous.append((pid, identity, old))
        except ProcessLookupError:
            continue
        except PermissionError as error:
            raise ConfigError('The OS denied a live FD-limit increase. Run on the host as root with CAP_SYS_RESOURCE; no service restart is attempted.') from error


def restore_limits(previous):
    failures = []
    for pid, identity, old in reversed(previous):
        if process_identity(pid) == identity:
            try:
                resource.prlimit(pid, resource.RLIMIT_NOFILE, old)
            except ProcessLookupError:
                pass
            except OSError:
                failures.append(pid)
    return failures


def verify_unit_limits(nofile, units=UNITS):
    from .deploy import command
    for unit in units:
        text = command(['systemctl', 'show', unit, '--property=LimitNOFILE,LimitNOFILESoft'])
        values = dict(line.split('=', 1) for line in text.splitlines() if '=' in line)
        for key in ('LimitNOFILE', 'LimitNOFILESoft'):
            value = values.get(key, '')
            if value != 'infinity' and (not value.isdigit() or int(value) < nofile):
                raise ConfigError(f'{unit} has an overriding {key} setting below the requested profile.')


def verify_workers(master, before, nofile):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        current = descendants([master])
        new = {pid: identity for pid, identity in current.items() if pid != master and before.get(pid) != identity}
        if new:
            try:
                limits = [resource.prlimit(pid, resource.RLIMIT_NOFILE) for pid in new]
                if all(all(v == resource.RLIM_INFINITY or v >= nofile for v in pair) for pair in limits):
                    return len(new)
            except ProcessLookupError:
                pass
        time.sleep(.2)
    raise ConfigError('Nginx did not start new workers with the requested FD limits after reload.')


def tune(project: Path, values, *, nginx_logging=False, nginx_only=False, dry_run=False):
    from . import deploy
    from .core import nginx_config
    values = validate(values)
    if type(nginx_logging) is not bool:
        raise ConfigError('nginx_logging must be a boolean.')
    units = ('threexi-nginx.service',) if nginx_only else UNITS
    if os.geteuid() != 0:
        raise ConfigError('Applying a resource profile requires root.')
    check_kernel(values['nofile'])
    state = deploy.state_read()
    updated = copy.deepcopy(state)
    updated['plan']['performance'] = values
    updated['plan']['nginx_logging'] = nginx_logging
    old_config = GATEWAY.read_text()
    candidate = old_config
    for key, directive in (('worker_connections', 'worker_connections'), ('nofile', 'worker_rlimit_nofile'),
                           ('h2_streams', 'http2_max_concurrent_streams')):
        candidate, count = re.subn(r'(?m)^(\s*)' + directive + r'\s+\d+;',
                                  lambda match: match[1] + directive + ' ' + str(values[key]) + ';', candidate)
        if count != 1:
            raise ConfigError(f'Expected one managed {directive} directive; review the gateway configuration first.')
    generated = nginx_config(updated['plan'], modern=state['modern_nginx'], ipv6=state['ipv6'])
    for pattern in (r'(?m)^error_log [^\n]+;$', r'(?m)^    access_log [^\n]+;$'):
        wanted = re.search(pattern, generated)[0]
        candidate, count = re.subn(pattern, lambda match: wanted, candidate)
        if count != 1:
            raise ConfigError('Expected one managed global logging directive; review the gateway configuration first.')
    if candidate != generated:
        raise ConfigError('Gateway configuration differs from managed state beyond resource limits. Review local edits before tuning; they were not overwritten.')
    roots = main_pids(units)
    processes = descendants(roots.values())
    if any(pid not in processes for pid in roots.values()):
        raise ConfigError('A service process changed during preparation; retry after it stabilizes.')
    changes = {}
    for name in MODULES:
        path = INSTALLED / name
        if not path.parent.is_dir() or path.is_symlink():
            raise ConfigError('Expected a regular managed installation under /opt/3xi/threexi.')
        text = (project / 'threexi' / name).read_text()
        compile(text, name, 'exec')
        changes[path] = (text, 0o644)
    for unit in units:
        path = SYSTEMD / (unit + '.d') / '90-3xi-performance.conf'
        changes[path] = (f'# Managed by 3xi tune\n[Service]\nLimitNOFILE={values["nofile"]}\n', 0o644)
        if str(path) not in updated['owned']:
            updated['owned'].append(str(path))
    changes[GATEWAY] = (candidate, 0o600)
    changes[deploy.STATE] = (json.dumps(updated, indent=2) + '\n', 0o600)
    # Stage config in its own directory so all absolute certificate paths remain identical.
    with tempfile.NamedTemporaryFile(mode='w', prefix='.nginx-tune-', suffix='.conf', dir=GATEWAY.parent) as preview:
        preview.write(candidate)
        preview.flush()
        deploy.command(['nginx', '-t', '-c', preview.name])
    if dry_run:
        return {'dry_run': True, 'scope': 'nginx' if nginx_only else 'nginx-and-xray',
                'performance': values, 'nginx_logs': 'on' if nginx_logging else 'off', 'nginx_config_test': 'passed',
                'planned_actions': ['raise live FD ceilings', 'persist service drop-ins and resource profile',
                                    'update managed generator/CLI modules', 'gracefully reload Nginx'],
                'xray_restart': False, 'database_changes': False}
    prior_files = {path: (path.read_text(), path.stat().st_mode & 0o777) if path.exists() else None for path in changes}
    changed_paths, made_directories, previous_limits = [], [], []
    reloading = False
    try:
        raise_limits(processes, values['nofile'], previous_limits)
        if main_pids(units) != roots:
            raise ConfigError('A service restarted while changing live limits; retry after it stabilizes.')
        for path, (text, mode) in changes.items():
            if prior_files[path] == (text, mode):
                continue
            if not path.parent.exists():
                path.parent.mkdir(mode=0o755)
                made_directories.append(path.parent)
            deploy.atomic_file(path, text, mode)
            changed_paths.append(path)
        deploy.command(['systemctl', 'daemon-reload'])
        verify_unit_limits(values['nofile'], units)
        new_workers = 0
        if candidate != old_config:
            reloading = True
            deploy.command(['systemctl', 'reload', 'threexi-nginx.service'])
            new_workers = verify_workers(roots['threexi-nginx.service'], processes, values['nofile'])
        # Catch children spawned just before their parent limit changed.
        raise_limits(descendants(roots.values()), values['nofile'], previous_limits)
        if nginx_only:
            deploy.command(['systemctl', 'is-active', '--quiet', 'threexi-nginx.service'])
        else:
            deploy.health(updated['plan'])
        return {'scope': 'nginx' if nginx_only else 'nginx-and-xray',
                'performance': values, 'nginx_logs': 'on' if nginx_logging else 'off', 'nginx_config_test': 'passed',
                'services': 'nginx active' if nginx_only else 'healthy',
                'nginx_reloaded': reloading, 'new_nginx_workers': new_workers,
                'xray_restart': False, 'xray_limits_changed': not nginx_only, 'database_changes': False,
                'changed_files': len(changed_paths),
                'note': 'Connection ceilings increased; bandwidth and 100k-session capacity are not benchmarked.'}
    except BaseException as error:
        failed = []
        for path in reversed(changed_paths):
            try:
                prior = prior_files[path]
                if prior is None:
                    path.unlink(missing_ok=True)
                else:
                    deploy.atomic_file(path, *prior)
            except OSError:
                failed.append('file restore')
        if changed_paths:
            try:
                deploy.command(['systemctl', 'daemon-reload'])
                if reloading:
                    deploy.command(['systemctl', 'reload', 'threexi-nginx.service'])
            except (ConfigError, OSError, subprocess.TimeoutExpired):
                failed.append('service configuration restore')
        if restore_limits(previous_limits):
            failed.append('live FD-limit restore')
        for path in reversed(made_directories):
            try:
                path.rmdir()
            except OSError:
                pass
        if failed:
            raise ConfigError('Resource update failed; restoration was incomplete: ' + ', '.join(sorted(set(failed))) + '. Inspect the server before retrying.') from error
        raise
