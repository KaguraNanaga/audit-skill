"""Local atomic persistence. No business logic and no network operations."""
import os
from pathlib import Path
import time
import uuid


def replace(source, target, attempts=6):
    """Retry Windows sharing/access errors only, with a bounded 1.55s delay."""
    for attempt in range(attempts):
        try:
            os.replace(source, target)
            return
        except OSError as exc:
            transient = os.name == 'nt' and getattr(exc, 'winerror', None) in {5, 32, 33}
            if not transient or attempt == attempts - 1:
                raise OSError(f'Atomic replace failed after {attempt + 1} attempt(s): {source} -> {target}; '
                              f'close programs holding the target and retry/recover; original error: {exc}') from exc
            time.sleep(0.05 * 2 ** attempt)


def sync_directory(directory):
    # Windows does not provide this POSIX directory-fsync guarantee.
    if os.name == 'nt':
        return False
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return True


def atomic_bytes(path, content, before_replace=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # A short basename avoids overflowing a near-limit destination component.
    tmp = path.parent / ('.write-' + uuid.uuid4().hex + '.tmp')
    try:
        with tmp.open('xb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if before_replace:
            before_replace()
        replace(tmp, path)
        sync_directory(path.parent)
    finally:
        tmp.unlink(missing_ok=True)
