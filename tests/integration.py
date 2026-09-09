#!/usr/bin/env python3
"""Exercise the public SSH installer against a disposable, isolated VPS fixture."""
import base64
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, **kwargs).stdout.strip()


with tempfile.TemporaryDirectory(prefix='tti-integration-') as directory:
    work = Path(directory)
    container = run('docker', 'run', '-d', '--hostname', 'tt.test', '--privileged', '--cgroupns', 'private',
                    '--tmpfs', '/run', '--tmpfs', '/run/lock', '-p', '127.0.0.1::22', 'trusttunnel-installer-test:local')
    try:
        for _ in range(100):
            ready = subprocess.run(['docker', 'exec', container, 'systemctl', 'is-active', '--quiet', 'ssh'], capture_output=True)
            if ready.returncode == 0:
                break
            time.sleep(0.2)
        else:
            raise RuntimeError('Fixture SSH did not start')

        key = work / 'test key'
        run('ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key))
        run('docker', 'exec', '-i', container, 'sh', '-c',
            'umask 077; mkdir -p /root/.ssh; cat > /root/.ssh/authorized_keys', input=key.with_suffix('.pub').read_text())
        port = run('docker', 'port', container, '22/tcp').rsplit(':', 1)[1]
        host_key = run('docker', 'exec', container, 'cat', '/etc/ssh/ssh_host_ed25519_key.pub').split()
        known = work / 'known_hosts'
        known.write_text(f'[127.0.0.1]:{port} {host_key[0]} {host_key[1]}\n')
        wrappers = work / 'bin'
        wrappers.mkdir()
        ssh = wrappers / 'ssh'
        ssh.write_text('#!/bin/sh\nexec ' + shlex.quote(shutil.which('ssh'))
                       + ' -o StrictHostKeyChecking=yes -o UserKnownHostsFile=' + shlex.quote(str(known)) + ' "$@"\n')
        ssh.chmod(0o755)
        env = {**os.environ, 'PATH': str(wrappers) + os.pathsep + os.environ['PATH']}
        output = work / 'access files'
        email = None
        for language in ('ru', 'en'):
            print(f'Installing over SSH: {language}', flush=True)
            result = subprocess.run(['bash', str(ROOT / 'install.sh'), '--lang', language, '--server', 'root@127.0.0.1',
                                     '--ssh-port', port, '--identity', str(key), '--domain', 'tt.test',
                                     '--output', str(output)],
                                    env=env, capture_output=True, text=True, timeout=600)
            if result.returncode:
                raise RuntimeError(f'Installer failed: {result.stderr[-4000:]}')
            assert 'tt://?' in result.stdout
            assert ('Пароль:' if language == 'ru' else 'Password:') in result.stdout
            generated_email = run('docker', 'exec', container, 'cat', '/etc/letsencrypt/trusttunnel-installer-email')
            assert generated_email.startswith('acme-') and generated_email.endswith('@tt.test')
            if email is not None:
                assert email == generated_email
            email = generated_email
            run('docker', 'exec', container, 'python3', '-c',
                'import json; from pathlib import Path; r=Path("/opt/trusttunnel"); '
                'assert "password" not in json.loads((r/".installer-state.json").read_text()); '
                'assert not (r/"client").exists(); '
                'assert not any(p.name in ("access.txt", "connection.txt", "endpoint.toml", "connection.png") '
                'for p in r.rglob("*"))')
            if language == 'ru':
                # Simulate an older installation before the second run.
                run('docker', 'exec', '-i', container, 'python3', '-', input='''
import json, toml
from pathlib import Path
root = Path('/opt/trusttunnel')
path = root / '.installer-state.json'
state = json.loads(path.read_text())
state['password'] = toml.load(root / 'credentials.toml')['client'][0]['password']
path.write_text(json.dumps(state))
(root / 'client').mkdir()
for name in ('access.txt', 'connection.txt', 'connection.png', 'endpoint.toml'):
    (root / 'client' / name).write_text('legacy export')
''')
        exports = sorted(output.iterdir())
        assert len(exports) == 2
        assert (exports[0] / 'connection.txt').read_bytes() == (exports[1] / 'connection.txt').read_bytes()
        for folder in exports:
            assert folder.stat().st_mode & 0o777 == 0o700
            for file in folder.iterdir():
                assert file.stat().st_mode & 0o777 == 0o600
        print('PASS: SSH upload/run/download, RU/EN output, stable credentials and local permissions', flush=True)
        print('PASS: generated server email persists across installations', flush=True)
        print('PASS: no server export files; legacy copies and duplicate passwords removed', flush=True)
        run('docker', 'cp', str(ROOT / 'tests/smoke.py'), f'{container}:/tmp/smoke.py')
        payload = {file.name: base64.b64encode(file.read_bytes()).decode() for file in exports[0].iterdir()}
        subprocess.run(['docker', 'exec', '-i', container, 'python3', '/tmp/smoke.py'],
                       input=json.dumps(payload), text=True, check=True)
    finally:
        run('docker', 'rm', '-f', container)
