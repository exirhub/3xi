"""Exercise startup orchestration with local Git and simulated APT/installation."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.root = self.base / "server"
        self.root.mkdir()
        self.repo = self.base / "source"
        self.repo.mkdir()
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.calls = self.base / "apt.jsonl"
        self.install_args = self.base / "install.args"
        (self.bin / "apt-get").write_text('''#!/usr/bin/env python3
import json, os, sys
with open(os.environ["THREEXI_TEST_APT_LOG"], "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
if os.environ.get("THREEXI_TEST_APT_FAIL") in sys.argv[1:]:
    sys.exit(100)
''')
        (self.bin / "apt-get").chmod(0o755)
        (self.bin / "sleep").write_text("#!/bin/sh\nexit 0\n")
        (self.bin / "sleep").chmod(0o755)
        self.git("init", "--quiet", "--initial-branch=main")
        (self.repo / "install.sh").write_text('''#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$@" > "$THREEXI_TEST_INSTALL_ARGS"
if [[ "${THREEXI_TEST_INSTALL_EXIT:-0}" != 0 ]]; then
    exit "$THREEXI_TEST_INSTALL_EXIT"
fi
mkdir -p "$THREEXI_TEST_ROOT/etc/3xi" "$THREEXI_TEST_ROOT/etc/x-ui"
cp "$(dirname "$0")/x-ui.db" "$THREEXI_TEST_ROOT/etc/x-ui/x-ui.db"
printf '{}\\n' > "$THREEXI_TEST_ROOT/etc/3xi/installed.json"
''')
        self.write_seed(b"original synthetic database")
        self.first_commit = self.commit()

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-C", str(self.repo), *args], text=True, stderr=subprocess.PIPE).strip()

    def commit(self):
        self.git("add", ".")
        self.git("-c", "user.name=THREEXI Test", "-c", "user.email=test@example.invalid",
                 "commit", "--quiet", "-m", "synthetic fixture")
        return self.git("rev-parse", "HEAD")

    def write_seed(self, content):
        (self.repo / "x-ui.db").write_bytes(content)
        (self.repo / "x-ui.db.sha256").write_text(
            hashlib.sha256(content).hexdigest() + "  x-ui.db\n")

    def invoke(self, *args, **extra):
        env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                   THREEXI_TEST_ROOT=str(self.root), THREEXI_TEST_REPO=str(self.repo),
                   THREEXI_TEST_APT_LOG=str(self.calls), THREEXI_TEST_INSTALL_ARGS=str(self.install_args))
        env.pop("THREEXI_REF", None)
        env.update(extra)
        # Redirect every server path to the temporary fixture. The bootstrap's
        # real fetch, checksum, lock, cleanup and install ordering still execute.
        driver = '''source "$1"
threexi_bootstrap_preflight() { :; }
threexi_configure_dns() { :; }
threexi_bootstrap_paths() {
    threexi_root="$THREEXI_TEST_ROOT"
    threexi_log="$threexi_root/var/log/bootstrap.log"
    threexi_state_dir="$threexi_root/var/lib/3xi-bootstrap"
    threexi_lock="$threexi_root/run/lock/bootstrap.lock"
    threexi_source_parent="$threexi_root"
    threexi_repository="$THREEXI_TEST_REPO"
}
threexi_bootstrap_main "${@:2}"
'''
        return subprocess.run(["bash", "-c", driver, "bootstrap-test",
                               str(PROJECT / "scripts/bootstrap.sh"), *args],
                              env=env, text=True, capture_output=True, timeout=20)

    def old_database(self, completed=False):
        database = self.root / "etc/x-ui/x-ui.db"
        database.parent.mkdir(parents=True)
        database.write_bytes(b"live data must survive")
        if completed:
            state = self.root / "etc/3xi/installed.json"
            state.parent.mkdir(parents=True)
            state.write_text("{}")
        return database

    def test_fresh_install_fetches_verifies_and_records_commit(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual(len(calls), 2)
        self.assertIn("--error-on=any", calls[0])
        self.assertIn("DPkg::Lock::Timeout=180", calls[0])
        self.assertEqual(self.install_args.read_text().strip(), "")
        self.assertEqual((self.root / "etc/x-ui/x-ui.db").read_bytes(), b"original synthetic database")
        self.assertEqual((self.root / "var/lib/3xi-bootstrap/source-commit.txt").read_text().strip(),
                         self.first_commit)
        self.assertEqual(list(self.root.glob("threexi-src.*")), [])

    def test_repeated_startup_preserves_live_database_without_apt(self):
        database = self.old_database(completed=True)
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("skipped", result.stdout)
        self.assertEqual(database.read_bytes(), b"live data must survive")
        self.assertFalse(self.calls.exists())
        self.assertFalse(self.install_args.exists())

    def test_existing_panel_requires_explicit_clean_flag(self):
        database = self.old_database()
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--clean-install", result.stdout)
        self.assertEqual(database.read_bytes(), b"live data must survive")
        self.assertFalse(self.calls.exists())

    def test_clean_flag_is_forwarded_to_existing_installer(self):
        database = self.old_database(completed=True)
        result = self.invoke("--clean-install")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.install_args.read_text().splitlines(), ["--clean-install"])
        self.assertEqual(database.read_bytes(), b"original synthetic database")

    def test_grpc_and_resource_flags_are_forwarded_without_shell_evaluation(self):
        args=['--grpc-path','/exir.v2.Tunnel/','--grpc-authority','','--grpc-mode','gun',
              '--domain','tls.example.org','--public-address','1.1.1.1',
              '--performance-profile','high','--nginx-logs','off']
        result=self.invoke('--dns-mode','preserve',*args)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(self.install_args.read_text().splitlines(),args)

    def test_invalid_dns_mode_is_rejected_before_packages(self):
        result=self.invoke('--dns-mode','unknown')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(self.calls.exists())

    def test_apt_failures_prevent_install_and_preserve_live_database(self):
        database = self.old_database()
        for phase in ("update", "install"):
            with self.subTest(phase=phase):
                result = self.invoke("--clean-install", THREEXI_TEST_APT_FAIL=phase)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("failed during bootstrap-packages", result.stdout)
                self.assertFalse(self.install_args.exists())
                self.assertEqual(database.read_bytes(), b"live data must survive")

    def test_corrupt_seed_prevents_install(self):
        (self.repo / "x-ui.db").write_bytes(b"does not match checksum")
        self.commit()
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("failed during database-checksum", result.stdout)
        self.assertFalse(self.install_args.exists())
        self.assertEqual(list(self.root.glob("threexi-src.*")), [])

    def test_full_commit_pin_ignores_new_branch_tip(self):
        self.write_seed(b"different newer database")
        self.commit()
        result = self.invoke("--ref", self.first_commit)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / "etc/x-ui/x-ui.db").read_bytes(), b"original synthetic database")
        self.assertEqual((self.root / "var/lib/3xi-bootstrap/source-commit.txt").read_text().strip(),
                         self.first_commit)

    def test_failed_installer_does_not_record_success(self):
        result = self.invoke(THREEXI_TEST_INSTALL_EXIT="23")
        self.assertEqual(result.returncode, 23)
        self.assertIn("failed during installation", result.stdout)
        self.assertNotIn("readiness checks completed", result.stdout)
        self.assertFalse((self.root / "var/lib/3xi-bootstrap/source-commit.txt").exists())
        self.assertEqual(list(self.root.glob("threexi-src.*")), [])

    def test_failed_download_retries_then_stops(self):
        result = self.invoke("--ref", "nonexistent-branch")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout.count("Fetching THREEXI revision"), 5)
        self.assertIn("failed during source-download", result.stdout)
        self.assertFalse(self.install_args.exists())
        self.assertEqual(list(self.root.glob("threexi-src.*")), [])

    def test_concurrent_bootstrap_is_rejected_before_packages(self):
        lock = self.root / "run/lock/bootstrap.lock"
        lock.parent.mkdir(parents=True)
        with lock.open("w") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Another THREEXI bootstrap", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_cloud_config_embeds_current_script_and_fits_user_data_limit(self):
        result = subprocess.run(["python3", str(PROJECT / "scripts/render-cloud-init.py"), "--check"],
                                text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        content = (PROJECT / "cloud-init/3xi.yaml").read_text()
        self.assertTrue(content.startswith("#cloud-config\n"))
        self.assertLessEqual(len(content.encode()), 16 * 1024)
        embedded = content.split("    content: |\n", 1)[1].split("runcmd:\n", 1)[0]
        decoded = "".join(line[6:] + "\n" for line in embedded.splitlines())
        self.assertEqual(decoded, (PROJECT / "scripts/bootstrap.sh").read_text())


if __name__ == "__main__":
    unittest.main()
