"""Trusted benign lease-only probe: substitute a stalled DNS call inside the helper."""
import socket
import sys
from pathlib import Path
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from issue_to_patch_upgrade.http_worker import main


def blocked(*args,**kwargs):
    time.sleep(60)
    raise OSError("unreachable after owned timeout")


if __name__ == "__main__":
    socket.getaddrinfo=blocked
    raise SystemExit(main())

