"""Tests for the watcher event handler.

We do not spin up a real ``Observer`` — that would introduce timing-flakiness
in CI. We poke the inner ``_DebouncedHandler`` directly, advancing the
debounce by waiting briefly. The end-to-end (real Observer + real filesystem
events) path is left to manual smoke-testing.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from app.watcher import _DebouncedHandler
from watchdog.events import (
    DirCreatedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
)


def test_handler_calls_pipeline_on_created_event(tmp_path) -> None:
    pipeline = MagicMock()
    pipeline.reconcile_path = MagicMock()
    handler = _DebouncedHandler(pipeline, debounce_seconds=0.05)

    md = tmp_path / "a.md"
    md.write_text("# A", encoding="utf-8")
    handler.on_any_event(FileCreatedEvent(str(md)))
    time.sleep(0.15)
    pipeline.reconcile_path.assert_called_once()
    assert pipeline.reconcile_path.call_args[0][0] == md


def test_handler_ignores_non_markdown(tmp_path) -> None:
    pipeline = MagicMock()
    pipeline.reconcile_path = MagicMock()
    handler = _DebouncedHandler(pipeline, debounce_seconds=0.05)

    txt = tmp_path / "a.txt"
    txt.write_text("plain", encoding="utf-8")
    handler.on_any_event(FileModifiedEvent(str(txt)))
    time.sleep(0.15)
    pipeline.reconcile_path.assert_not_called()


def test_handler_ignores_directory_events(tmp_path) -> None:
    pipeline = MagicMock()
    pipeline.reconcile_path = MagicMock()
    handler = _DebouncedHandler(pipeline, debounce_seconds=0.05)

    handler.on_any_event(DirCreatedEvent(str(tmp_path)))
    time.sleep(0.15)
    pipeline.reconcile_path.assert_not_called()


def test_debounce_collapses_burst(tmp_path) -> None:
    pipeline = MagicMock()
    pipeline.reconcile_path = MagicMock()
    handler = _DebouncedHandler(pipeline, debounce_seconds=0.1)

    md = tmp_path / "a.md"
    md.write_text("v1", encoding="utf-8")
    for _ in range(5):
        handler.on_any_event(FileModifiedEvent(str(md)))
        time.sleep(0.02)
    time.sleep(0.2)
    assert pipeline.reconcile_path.call_count == 1


def test_handler_reacts_to_delete(tmp_path) -> None:
    pipeline = MagicMock()
    pipeline.reconcile_path = MagicMock()
    handler = _DebouncedHandler(pipeline, debounce_seconds=0.05)

    md = tmp_path / "a.md"
    handler.on_any_event(FileDeletedEvent(str(md)))
    time.sleep(0.15)
    pipeline.reconcile_path.assert_called_once_with(md)


def test_handler_reacts_to_rename(tmp_path) -> None:
    pipeline = MagicMock()
    pipeline.reconcile_path = MagicMock()
    handler = _DebouncedHandler(pipeline, debounce_seconds=0.05)

    src = tmp_path / "old.md"
    dest = tmp_path / "new.md"
    handler.on_any_event(FileMovedEvent(str(src), str(dest)))
    time.sleep(0.15)
    # both source and destination get reconciled
    called_paths = {call.args[0] for call in pipeline.reconcile_path.call_args_list}
    assert src in called_paths
    assert dest in called_paths
