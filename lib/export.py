#!/usr/bin/env python3
"""Export connection details through stdout without writing server-side files."""
import argparse
import importlib.util
import io
import json
from pathlib import Path
import resource
import subprocess
import sys
import tarfile

try:
    import tomllib
except ModuleNotFoundError:
    import toml as tomllib

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("normalize_export", Path(__file__).with_name("normalize-export.py"))
normalizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(normalizer)


def connection_files(base, language, username=None, include_qr=True):
    root = Path(base)
    domain = (root / "domain").read_text().strip()
    clients = tomllib.loads((root / "credentials.toml").read_text())["client"]
    if username is None:
        state = root / ".installer-state.json"
        username = json.loads(state.read_text())["username"] if state.exists() else clients[0]["username"]
    user = next((client for client in clients if client["username"] == username), None)
    if user is None:
        raise ValueError("The requested user was not found in credentials.toml")

    command = [str(root / "trusttunnel_endpoint"), "vpn.toml", "hosts.toml", "-c", username,
               "-a", domain + ":443", "--name", domain, "--format"]
    link = subprocess.run(command + ["deeplink"], cwd=root, check=True, capture_output=True,
                          text=True, timeout=30).stdout
    config = subprocess.run(command + ["toml"], cwd=root, check=True, capture_output=True,
                            text=True, timeout=30).stdout
    link, config = normalizer.normalize_exports(link, config)
    labels = ("Домен", "Порт", "Логин", "Пароль") if language == "ru" else ("Domain", "Port", "Username", "Password")
    values = (domain, 443, user["username"], user["password"])
    details = "TrustTunnel\n" + "".join(f"{key}: {value}\n" for key, value in zip(labels, values))
    files = {"access.txt": details.encode(), "connection.txt": link.encode(), "endpoint.toml": config.encode()}
    if include_qr:
        files["connection.png"] = subprocess.run(["qrencode", "-o", "-", "-s", "6"], input=link.encode(),
                                                  check=True, capture_output=True, timeout=30).stdout
    return files


def write_archive(files, output):
    with tarfile.open(fileobj=output, mode="w|gz") as archive:
        for name, content in files.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(content)
            entry.mode = 0o600
            archive.addfile(entry, io.BytesIO(content))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang", choices=("ru", "en"), required=True)
    parser.add_argument("--format", choices=("text", "tar"), default="text")
    parser.add_argument("--username")
    args = parser.parse_args()
    # Export subprocesses must not leave credentials in a crash dump.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    try:
        files = connection_files("/opt/trusttunnel", args.lang, args.username, args.format == "tar")
        if args.format == "tar":
            write_archive(files, sys.stdout.buffer)
        else:
            label = "Ссылка для импорта" if args.lang == "ru" else "Import link"
            sys.stdout.write(files["access.txt"].decode() + "\n" + label + ":\n" + files["connection.txt"].decode())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        prefix = "Не удалось экспортировать доступы" if args.lang == "ru" else "Could not export connection details"
        sys.exit(f"{prefix}: {error}")
