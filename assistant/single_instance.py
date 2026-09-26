"""Single-instance lock (BUILD_PLAN section 3.1).

Windows: named mutex via ``CreateMutexW``. Other OSes (CI): an ``flock``-based
lock file, so the unit tests can run on ubuntu-latest too.
"""

from __future__ import annotations

import sys
from pathlib import Path

from assistant import paths

MUTEX_NAME = "PCAssistant_single_instance"


class SingleInstance:
    """Context manager holding the single-instance lock.

    ``acquired`` is False if another instance already holds it.
    """

    def __init__(self, name: str = MUTEX_NAME, lock_file: Path | None = None) -> None:
        self._name = name
        self._lock_file = lock_file
        self.acquired = False
        self._handle: object | None = None
        self._fd: int | None = None
        self._keepalive: object | None = None

    def acquire(self) -> bool:
        if self._lock_file is not None:
            return self._acquire_file()
        if sys.platform == "win32":
            return self._acquire_windows()
        return self._acquire_file()

    def release(self) -> None:
        if self._handle is not None:
            import ctypes

            ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(self._handle)
            self._handle = None
        if self._fd is not None:
            if sys.platform == "win32":
                import msvcrt

                try:
                    msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                import fcntl

                fcntl.flock(self._fd, fcntl.LOCK_UN)
            keeper = self._keepalive
            self._fd = None
            self._keepalive = None
            close = getattr(keeper, "close", None)
            if close is not None:
                close()  # closes the fd; avoids double-close in the file __del__
        self.acquired = False

    def _acquire_windows(self) -> bool:
        import ctypes

        ERROR_ALREADY_EXISTS = 183
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.CreateMutexW(None, False, self._name)
        if not handle:
            raise ctypes.WinError()
        already = ctypes.get_last_error() == ERROR_ALREADY_EXISTS
        self._handle = handle
        self.acquired = not already
        if already:
            self.release()
        return self.acquired

    def _acquire_file(self) -> bool:
        """Portable file lock: fcntl on POSIX, msvcrt byte-lock on Windows."""
        path = (
            self._lock_file
            if self._lock_file is not None
            else paths.app_data_dir() / "instance.lock"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = open(path, "a+")  # noqa: SIM115 - kept open for the lock lifetime
        try:
            if sys.platform == "win32":
                import msvcrt

                fd.seek(0)
                msvcrt.locking(fd.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fd.close()
            self.acquired = False
            return False
        self._fd = fd.fileno()
        self._keepalive = fd  # prevent GC closing the fd
        self.acquired = True
        return True

    def __enter__(self) -> SingleInstance:
        self.acquire()
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()
