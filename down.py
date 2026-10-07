#!/usr/bin/env python3

import logging
import shutil
import subprocess


SERVICES = ("telemetry-gateway.service", "grafana.service", "loki.service")


def main():
    if shutil.which("systemctl") is None:
        raise RuntimeError("systemctl must already be installed")

    logging.info("Stopping telemetry services")
    subprocess.run(("systemctl", "--user", "stop", *SERVICES), check=True)
    logging.info("Services stopped; data and configuration preserved")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        logging.error("%s", error)
        raise SystemExit(1)
