import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import tarfile
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


configure = module('configure', ROOT / 'lib/configure.py').configure
normalize = module('normalize', ROOT / 'lib/normalize-export.py')
exporter = module('exporter', ROOT / 'lib/export.py')


class InstallerTests(unittest.TestCase):
    def invoke(self, *args):
        return subprocess.run(['bash', str(ROOT / 'install.sh'), *args], stdin=subprocess.DEVNULL,
                              text=True, capture_output=True, timeout=5)

    def test_localized_help_without_email_parameter(self):
        for language, word in [('ru', 'Каталог'), ('en', 'Directory')]:
            result = self.invoke('--lang', language, '--help')
            self.assertEqual(result.returncode, 0)
            self.assertIn(word, result.stdout)
            self.assertNotIn('--email', result.stdout)
        self.assertEqual(self.invoke('--help').returncode, 0)

    def test_rejects_untrusted_arguments_before_ssh(self):
        for args in [('--domain', 'good.test;touch /tmp/tti-injection'),
                     ('--server', 'root@host$(id)'), ('--server', '-oProxyCommand=id'),
                     ('--domain', 'https://good.test'), ('--domain', 'bad..test'),
                     ('--ssh-port', '0'), ('--ssh-port', '65536'), ('--ssh-port', '2x'),
                     ('--identity', '/does/not/exist'), ('--email', 'unused@example.com')]:
            with self.subTest(args=args):
                result = self.invoke('--lang', 'en', '--server', 'root@203.0.113.1', '--domain', 'good.test', *args)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('Connecting to', result.stderr)

    def test_missing_value_and_noninteractive_language(self):
        self.assertIn('Missing value', self.invoke('--lang', 'en', '--domain').stderr)
        self.assertIn('--lang ru', self.invoke().stderr)

    def test_credentials_survive_rerun_and_domain_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            state = configure(directory, 'tt.example.com', '1.1.0')
            path = Path(directory) / 'credentials.toml'
            original = path.read_bytes()
            self.assertEqual(state, configure(directory, 'tt.example.com', '1.1.0'))
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn('password', state)
            with self.assertRaises(ValueError):
                configure(directory, 'other.example.com', '1.1.0')
            self.assertEqual(path.read_bytes(), original)

    def test_legacy_exports_and_duplicate_password_are_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = configure(directory, 'tt.example.com', '1.1.0')
            original = (root / 'credentials.toml').read_bytes()
            state['password'] = 'legacy-password-copy'
            (root / '.installer-state.json').write_text(json.dumps(state))
            legacy = root / 'client'
            legacy.mkdir()
            for name in ('access.txt', 'connection.txt', 'endpoint.toml', 'connection.png'):
                (legacy / name).write_text('legacy export')
            configure(directory, 'tt.example.com', '1.1.0')
            self.assertNotIn('password', json.loads((root / '.installer-state.json').read_text()))
            self.assertEqual((root / 'credentials.toml').read_bytes(), original)
            self.assertFalse(legacy.exists())
            self.assertEqual((root / '.installer-state.json').stat().st_mode & 0o777, 0o600)

    def test_missing_authentication_file_does_not_rotate_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            configure(directory, 'tt.example.com', '1.1.0')
            state = (root / '.installer-state.json').read_bytes()
            (root / 'credentials.toml').unlink()
            with self.assertRaises(ValueError):
                configure(directory, 'tt.example.com', '1.1.0')
            self.assertFalse((root / 'credentials.toml').exists())
            self.assertEqual((root / '.installer-state.json').read_bytes(), state)

    def test_exports_use_memory_and_current_authentication_password(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = configure(directory, 'tt.example.com', '1.1.0')
            (root / 'credentials.toml').write_text(
                '[[client]]\n' + f'username = "{state["username"]}"\npassword = "current-password"\n')
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            link = 'tt://?' + base64.urlsafe_b64encode(b'\x00\x01\x01').decode().rstrip('=')

            def native_export(command, **kwargs):
                if command[0] == 'qrencode':
                    self.assertEqual(kwargs['input'].decode(), normalize.ipv4_link(link) + '\n')
                    return subprocess.CompletedProcess(command, 0, stdout=b'test-png')
                self.assertEqual(command[command.index('-c') + 1], state['username'])
                output = link + '\nQR website hint\n' if command[-1] == 'deeplink' else 'has_ipv6 = true\n'
                return subprocess.CompletedProcess(command, 0, stdout=output)

            with patch.object(exporter.subprocess, 'run', side_effect=native_export):
                files = exporter.connection_files(root, 'en')
            self.assertIn(b'Password: current-password', files['access.txt'])
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, before)
            archive = io.BytesIO()
            exporter.write_archive(files, archive)
            archive.seek(0)
            with tarfile.open(fileobj=archive, mode='r:gz') as package:
                self.assertEqual(set(package.getnames()), set(files))
                for entry in package.getmembers():
                    self.assertTrue(entry.isfile())
                    self.assertEqual(entry.mode, 0o600)
                    self.assertEqual(package.extractfile(entry).read(), files[entry.name])

    def test_deeplink_preserves_unknown_and_long_fields(self):
        # A two-byte length exercises QUIC varints beyond the one-byte range.
        fields = b'\x00\x01\x01\x01\x04host\x05\x04user\x06\x40\x50' + b'x' * 80 + b'\x04\x01\x01\x3f\x02ok'
        link = 'tt://?' + base64.urlsafe_b64encode(fields).decode().rstrip('=')
        normalized = normalize.ipv4_link(link)
        data = base64.urlsafe_b64decode(normalized[6:] + '=' * (-len(normalized[6:]) % 4))
        self.assertEqual(data, fields.replace(b'\x04\x01\x01', b'') + b'\x04\x01\x00')
        self.assertEqual(normalize.ipv4_link(normalized), normalized)

    def test_deeplink_rejects_truncation_and_future_version(self):
        for payload in [b'\x00\x01\x02', b'\x00\x01\x01\x01\x40', b'\x00\x01\x01\x01\x08short']:
            link = 'tt://?' + base64.urlsafe_b64encode(payload).decode().rstrip('=')
            with self.assertRaises(ValueError):
                normalize.ipv4_link(link)

    def test_export_removes_upstream_qr_hint(self):
        with tempfile.TemporaryDirectory() as directory:
            link_path, config_path = Path(directory) / 'link', Path(directory) / 'config'
            link = 'tt://?' + base64.urlsafe_b64encode(b'\x00\x01\x01').decode().rstrip('=')
            link_path.write_text(link + '\n\nTo connect, visit https://example.com/qr\n')
            config_path.write_text('has_ipv6 = true\npassword = "keep-me"\n')
            subprocess.run(['python3', str(ROOT / 'lib/normalize-export.py'), str(link_path), str(config_path)], check=True)
            self.assertEqual(len(link_path.read_text().splitlines()), 1)
            self.assertIn('has_ipv6 = false', config_path.read_text())
            self.assertIn('password = "keep-me"', config_path.read_text())

    def test_tui_language_navigation_and_terminal_restore(self):
        for key, title, quit_key in [(b'1', 'Ваш сервер', b'q'),
                                     (b'\x1b[B\r', 'Your server', b'\x03')]:
            with self.subTest(title=title):
                child, terminal = pty.fork()
                if child == 0:
                    os.environ['TERM'] = 'xterm-256color'
                    os.execvp('bash', ['bash', str(ROOT / 'install.sh')])
                data = bytearray()
                reaped = False
                def until(text):
                    deadline = time.monotonic() + 5
                    while text.encode() not in data:
                        self.assertLess(time.monotonic(), deadline, data.decode(errors='replace'))
                        if select.select([terminal], [], [], 0.1)[0]:
                            data.extend(os.read(terminal, 65536))
                try:
                    until('Choose language')
                    os.write(terminal, key)
                    until(title)
                    self.assertNotIn('Email', data.decode(errors='replace'))
                    os.write(terminal, quit_key)
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        if select.select([terminal], [], [], 0.1)[0]:
                            try:
                                data.extend(os.read(terminal, 65536))
                            except OSError:
                                break
                    _, status = os.waitpid(child, 0)
                    reaped = True
                    self.assertEqual(os.waitstatus_to_exitcode(status), 130)
                    self.assertTrue(data.endswith(b'\x1b[0m\x1b[?25h\x1b[?1049l'), data[-200:])
                finally:
                    if not reaped:
                        os.kill(child, signal.SIGKILL)
                        os.waitpid(child, 0)
                    os.close(terminal)


if __name__ == '__main__':
    unittest.main()
