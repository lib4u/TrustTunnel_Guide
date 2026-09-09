#!/usr/bin/env python3
"""Create a single-user configuration; repeated runs preserve credentials/settings."""
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile


def configure(directory, domain, version):
    root = Path(directory)
    state_file = root / ".installer-state.json"
    credentials_file = root / "credentials.toml"
    if state_file.exists():
        state = json.loads(state_file.read_text())
        if state.get("domain") != domain or state.get("version") != version:
            raise ValueError("Domain/version differs from the existing installation. See docs/maintenance.md")
        if not credentials_file.is_file():
            raise ValueError("credentials.toml is missing. Restore the server authentication file before continuing.")
        state.pop("password", None)
    else:
        state = {"domain": domain, "version": version,
                 "username": "tt_" + secrets.token_hex(4)}
        password = secrets.token_urlsafe(32)
        with credentials_file.open("x") as target:
            target.write('[[client]]\n' + f'username = {json.dumps(state["username"])}\n'
                         + f'password = {json.dumps(password)}\n')
    credentials_file.chmod(0o600)

    # Replace legacy metadata without retaining a second copy of the password.
    with tempfile.NamedTemporaryFile(mode="w", dir=root, prefix=".state-", delete=False) as target:
        temporary = Path(target.name)
        json.dump(state, target, indent=2)
        target.write("\n")
    try:
        temporary.replace(state_file)
    finally:
        temporary.unlink(missing_ok=True)

    # Remove only export artifacts written by earlier installer versions.
    legacy = root / "client"
    if legacy.is_dir() and not legacy.is_symlink():
        for name in ("access.txt", "connection.txt", "connection.png", "endpoint.toml"):
            (legacy / name).unlink(missing_ok=True)
        if not any(legacy.iterdir()):
            legacy.rmdir()

    files = {
        "domain": domain + "\n",
        "hosts.toml": ('[[main_hosts]]\n' + f'hostname = "{domain}"\n'
                       + f'cert_chain_path = "/etc/letsencrypt/live/{domain}/fullchain.pem"\n'
                       + f'private_key_path = "/etc/letsencrypt/live/{domain}/privkey.pem"\n'),
        "rules.toml": "# No additional connection filters. Authentication is still required.\n",
    }
    for name, content in files.items():
        path = root / name
        if not path.exists():
            with path.open("x") as target:
                target.write(content)
        path.chmod(0o600)
    return state


if __name__ == "__main__":
    os.umask(0o077)
    try:
        configure(*sys.argv[1:])
    except (ValueError, OSError) as error:
        sys.exit(str(error))
