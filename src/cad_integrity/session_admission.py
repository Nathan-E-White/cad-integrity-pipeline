"""Admission shared by computation routes in one parent app."""

from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock


class SessionBusy(RuntimeError):
    """Another computation already owns this browser session."""


class SessionAdmission:
    def __init__(self) -> None:
        self._active: set[str] = set()
        self._lock = Lock()

    @contextmanager
    def admit(self, session_id: str) -> Iterator[None]:
        if not session_id:
            raise ValueError("A browser session is required for computation")
        with self._lock:
            if session_id in self._active:
                raise SessionBusy("This session already has an active computation")
            self._active.add(session_id)
        try:
            yield
        finally:
            with self._lock:
                self._active.remove(session_id)
