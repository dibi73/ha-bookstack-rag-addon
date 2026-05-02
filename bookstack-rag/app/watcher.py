"""Filesystem watcher that funnels Markdown-export events into the reconcile pipeline.

The watcher itself is a thin wrapper around :mod:`watchdog` that debounces
rapid event bursts (editors often emit several writes per save) and delegates
all real work to :class:`~app.pipeline.Pipeline.reconcile_path`. Tests poke at
the event handler directly without spinning up a real Observer.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

if TYPE_CHECKING:
    from watchdog.events import FileSystemEvent

    from app.pipeline import Pipeline

logger = logging.getLogger(__name__)

DEBOUNCE_SECONDS = 0.5


class _DebouncedHandler(FileSystemEventHandler):
    """Routes filesystem events to the pipeline, debouncing per-path bursts."""

    def __init__(
        self,
        pipeline: Pipeline,
        debounce_seconds: float = DEBOUNCE_SECONDS,
    ) -> None:
        """Bind the handler to a pipeline and a debounce window."""
        self._pipeline = pipeline
        self._debounce_seconds = debounce_seconds
        self._timers: dict[Path, threading.Timer] = {}
        self._lock = threading.Lock()

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(str(event.src_path))
        if path.suffix.lower() != ".md":
            return
        self._schedule(path)
        # On rename events, watchdog also gives us dest_path; reconcile that too.
        dest = getattr(event, "dest_path", None)
        if dest:
            dest_path = Path(str(dest))
            if dest_path.suffix.lower() == ".md":
                self._schedule(dest_path)

    def _schedule(self, path: Path) -> None:
        with self._lock:
            existing = self._timers.pop(path, None)
            if existing is not None:
                existing.cancel()
            timer = threading.Timer(self._debounce_seconds, self._fire, args=[path])
            timer.daemon = True
            self._timers[path] = timer
            timer.start()

    def _fire(self, path: Path) -> None:
        with self._lock:
            self._timers.pop(path, None)
        try:
            outcome = self._pipeline.reconcile_path(path)
        except Exception:
            logger.exception("Watcher reconcile failed for %s", path)
            return
        logger.debug("Watcher reconciled %s → %s", path, outcome.action)


class Watcher:
    """Public watcher API — start/stop the underlying Observer."""

    def __init__(self, pipeline: Pipeline) -> None:
        """Hold the pipeline reference; defer Observer creation to :meth:`start`."""
        self._pipeline = pipeline
        self._observer: Observer | None = None
        self._handler: _DebouncedHandler | None = None

    def start(self) -> None:
        """Start the underlying watchdog Observer if the export path exists."""
        if self._observer is not None:
            return
        if not self._pipeline.export_path.is_dir():
            logger.warning(
                "Watcher start: export path %s does not exist yet — watcher idle",
                self._pipeline.export_path,
            )
            return
        self._handler = _DebouncedHandler(self._pipeline)
        self._observer = Observer()
        self._observer.schedule(
            self._handler,
            str(self._pipeline.export_path),
            recursive=True,
        )
        self._observer.start()
        logger.info("Watcher started on %s", self._pipeline.export_path)

    def stop(self) -> None:
        """Stop the Observer and join its thread."""
        if self._observer is None:
            return
        self._observer.stop()
        self._observer.join(timeout=5)
        self._observer = None
        self._handler = None
        logger.info("Watcher stopped")
