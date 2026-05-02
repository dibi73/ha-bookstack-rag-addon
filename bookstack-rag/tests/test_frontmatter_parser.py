"""Tests for the frontmatter / hash helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.frontmatter_parser import hash_file, parse_markdown_file

if TYPE_CHECKING:
    from pathlib import Path


def test_parse_with_frontmatter(tmp_path: Path) -> None:
    f = tmp_path / "device.md"
    f.write_text(
        "---\n"
        "title: Bewegungsmelder Gang\n"
        "bookstack_page_id: 142\n"
        "ha_object_kind: device\n"
        "---\n"
        "\n"
        "## Bewegungsmelder Gang\n"
        "\n"
        "Aqara Motion Sensor P1.\n",
        encoding="utf-8",
    )
    parsed = parse_markdown_file(f)
    assert parsed.metadata["title"] == "Bewegungsmelder Gang"
    assert parsed.metadata["bookstack_page_id"] == 142
    assert parsed.metadata["ha_object_kind"] == "device"
    assert "Aqara Motion Sensor P1" in parsed.body
    assert len(parsed.content_hash) == 64


def test_parse_without_frontmatter(tmp_path: Path) -> None:
    f = tmp_path / "plain.md"
    f.write_text("# Heading\n\nBody text.\n", encoding="utf-8")
    parsed = parse_markdown_file(f)
    assert parsed.metadata == {}
    assert "Body text" in parsed.body


def test_hash_is_stable_for_same_bytes(tmp_path: Path) -> None:
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    payload = "# Same content\n"
    a.write_text(payload, encoding="utf-8")
    b.write_text(payload, encoding="utf-8")
    assert hash_file(a) == hash_file(b)


def test_hash_changes_when_body_changes(tmp_path: Path) -> None:
    f = tmp_path / "f.md"
    f.write_text("# Original\n", encoding="utf-8")
    h1 = hash_file(f)
    f.write_text("# Modified\n", encoding="utf-8")
    h2 = hash_file(f)
    assert h1 != h2
