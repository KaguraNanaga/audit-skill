"""Kernel writer lock; a separate JSON sidecar is diagnostic, never authoritative."""
from contextlib import contextmanager
from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import sys
import time
import warnings

from .persistence import atomic_bytes


def stamp():
    return datetime.now(timezone.utc).isoformat()


def metadata(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'diagnostic': 'metadata absent or unreadable'}


def write_metadata(path, value):
    try:
        atomic_bytes(path, (json.dumps(value, ensure_ascii=False) + '\n').encode('utf-8'))
    except OSError as exc:
        warnings.warn('Lock acquired; diagnostic sidecar could not be updated: ' + str(exc), RuntimeWarning)


@contextmanager
def lock(project, timeout=5.0, interval=0.05):
    if timeout < 0 or interval <= 0:
        raise ValueError('Lock timeout must be nonnegative and interval positive')
    project = Path(project)
    sidecar = project / '.writer.lock.json'
    # Never unlink the lock file: doing so permits different inodes to be locked.
    fd = os.open(project / '.writer.lock', os.O_RDWR | os.O_CREAT, 0o600)
    stream = os.fdopen(fd, 'r+b', buffering=0)
    acquired = False
    started = time.monotonic()
    try:
        while True:
            try:
                if sys.platform == 'win32':
                    import msvcrt
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError as exc:
                if exc.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                    raise
                if time.monotonic() - started >= timeout:
                    raise ValueError(f'Writer lock timeout after {timeout:g}s; system lock is held. '
                                     f'Diagnostic metadata only: {metadata(sidecar)}') from exc
                time.sleep(min(interval, max(0, timeout - (time.monotonic() - started))))
        previous = metadata(sidecar)
        if previous.get('state') == 'held':
            warnings.warn('System lock acquired; prior writer left residual diagnostic metadata: ' + str(previous), RuntimeWarning)
        owner = dict(pid=os.getpid(), acquired_at=stamp(), state='held')
        write_metadata(sidecar, owner)
        try:
            yield
        finally:
            write_metadata(sidecar, dict(owner, state='released', released_at=stamp()))
    finally:
        try:
            if acquired:
                if sys.platform == 'win32':
                    import msvcrt
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_UN)
        finally:
            stream.close()
