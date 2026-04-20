"""PID-file lock so only one newsagg instance runs at a time.

Acquire writes our PID to the configured file; if the file already exists
and the PID is live, acquire() raises. Stale PID files (process is gone)
are cleaned up silently so a crashed previous run doesn't block restart.
"""
from __future__ import annotations

import errno
import os
from pathlib import Path


class AlreadyRunning(RuntimeError):
    pass


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError as e:
        return e.errno == errno.EPERM  # running but not ours — still alive


def acquire(pid_path: str | Path) -> None:
    p = Path(pid_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        try:
            old = int(p.read_text().strip())
        except (ValueError, OSError):
            old = 0
        if old and _alive(old) and old != os.getpid():
            raise AlreadyRunning(
                f"another newsagg is already running (pid {old}); "
                f"stop it or remove {p} to override"
            )
        # stale — reclaim
        try:
            p.unlink()
        except OSError:
            pass
    # Atomic-ish create: O_EXCL so two racing starts both can't win.
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        os.write(fd, str(os.getpid()).encode())
    finally:
        os.close(fd)


def release(pid_path: str | Path) -> None:
    """Remove the PID file if it still holds our PID. Silent on mismatch."""
    p = Path(pid_path)
    try:
        owner = int(p.read_text().strip())
    except (OSError, ValueError):
        return
    if owner == os.getpid():
        try:
            p.unlink()
        except OSError:
            pass
