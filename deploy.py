#!/usr/bin/env python3

import logging
import os
import pwd
import secrets
import shutil
import subprocess
from pathlib import Path


BUNDLE_DIR = Path(__file__).resolve().parent
PASSWORD_SECRETS = {
    user: f"telemetry-loki-{user}-password-hash" for user in ("otel", "admin")
}


def run(*args, capture=False, **kwargs):
    result = subprocess.run(
        args, check=True, text=True,
        stdout=subprocess.PIPE if capture else None, **kwargs,
    )
    return result.stdout.strip() if capture else ""


def main():
    unit_dir = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "containers/systemd"
    config_dir = unit_dir / "config"
    runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")
    socket_dir = runtime_dir / "host-sockets"
    quadlets = sorted((BUNDLE_DIR / "quadlets").iterdir())

    logging.info("Checking dependencies and installation targets")
    for command in ("caddy", "podman", "setfacl", "systemctl"):
        if shutil.which(command) is None:
            raise RuntimeError(f"{command} must already be installed")
    try:
        pwd.getpwnam("caddy")
    except KeyError as error:
        raise RuntimeError("the caddy OS user must already exist") from error
    for field, expected, message in (
        ("Security.Rootless", "true", "Run as your ordinary user with rootless Podman"),
        ("CgroupsVersion", "v2", "Quadlet requires cgroup v2"),
    ):
        if run("podman", "info", "--format", "{{.Host." + field + "}}", capture=True) != expected:
            raise RuntimeError(message)
    for target in [config_dir, *(unit_dir / source.name for source in quadlets)]:
        if target.exists() or target.is_symlink():
            raise RuntimeError(f"Refusing to overwrite {target}")
    for name in PASSWORD_SECRETS.values():
        status = subprocess.run(("podman", "secret", "exists", name), check=False).returncode
        if status == 0:
            raise RuntimeError(f"Refusing to overwrite Podman secret {name}")
        if status != 1:
            raise RuntimeError(f"Unable to inspect Podman secret {name}")
    if not runtime_dir.is_dir():
        raise RuntimeError(f"Runtime directory does not exist: {runtime_dir}")

    logging.info("Preparing socket permissions and installing configuration")
    socket_dir.mkdir(parents=True, exist_ok=True)
    socket_dir.chmod(0o700)
    run("setfacl", "--modify", "user:caddy:--x", str(runtime_dir))
    run("setfacl", "--modify", "user:caddy:--x", "--modify", "default:user:caddy:rw-", str(socket_dir))
    unit_dir.mkdir(parents=True, exist_ok=True)
    unit_dir.chmod(0o700)
    shutil.copytree(BUNDLE_DIR / "config", config_dir)

    logging.info("Creating Loki password secrets")
    passwords = {}
    for user, name in PASSWORD_SECRETS.items():
        passwords[user] = secrets.token_urlsafe(32)
        password_hash = run("caddy", "hash-password", "--plaintext", passwords[user], capture=True)
        run("podman", "secret", "create", name, "-", input=password_hash, capture=True)

    for source in quadlets:
        target = unit_dir / source.name
        shutil.copyfile(source, target)
        target.chmod(0o600)
    logging.info("Reloading systemd and starting services")
    run("systemctl", "--user", "daemon-reload")
    run("systemctl", "--user", "cat", "loki.service", "telemetry-gateway.service", "grafana.service", capture=True)
    run("systemctl", "--user", "start", "telemetry-gateway.service")

    logging.info("Deployment completed")
    for label, filename in (
        ("Grafana", "grafana.sock"),
        ("Loki ingestion", "loki-ingest.sock"),
        ("Loki administration", "loki-admin.sock"),
    ):
        print(f"{label} socket: {socket_dir / filename}")
    for label, user in (("Loki ingestion", "otel"), ("Loki administration", "admin")):
        print(f"{label} credentials: username={user} password={passwords[user]}")
    print("Point the external Caddy routes at the Unix sockets shown above.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        logging.error("%s", error)
        raise SystemExit(1)
