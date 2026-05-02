# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-05-02

Stage 1 — the add-on now actually indexes the BookStack export and
returns relevant documents for natural-language queries. LLM
integration and the web UI follow in v0.3.0 / v0.4.0.

### Added

- `POST /api/query` — embed the user's question with
  `nomic-ai/nomic-embed-text-v1.5` (768-dim, CPU) and return the top-K
  matching documents from the local Qdrant index. Each hit carries
  `title`, `score`, `bookstack_page_id`, and a `content_preview`
  field for surfacing the underlying BookStack page.
- `POST /api/reindex` — manually trigger the same reconcile sweep
  the watcher and the startup scan run. Useful after large bulk edits
  in BookStack where you want to short-circuit the watcher's debounce.
- File watcher on `<config>/bookstack_export/` — `watchdog`-based,
  debounced 500 ms, reuses the same reconcile pipeline as the
  startup scan and `/api/reindex` (HARD RULE §3.7).
- Qdrant sidecar service inside the container (`qdrant/qdrant:v1.17.1`
  binary) supervised by s6-overlay, bound to `localhost:6333`,
  persistence under `/data/qdrant/`. Survives add-on restarts
  without re-indexing.
- Idempotent indexing: SHA-256 of the full Markdown file (frontmatter
  + body) is stored as Qdrant payload, only changed files are
  re-embedded. Soft-delete (tombstoning) on file deletion.
- New configuration options: `embedding_model` (defaults to
  `nomic-ai/nomic-embed-text-v1.5`, pre-baked into the image) and
  `top_k` (default 5, range 1-50).
- `/api/status` now also reports `indexed`: total document count
  in the Qdrant collection.

### Changed

- **Breaking**: armv7 (32-bit ARM) is no longer supported. Stage 1
  pulls in PyTorch transitively via `sentence-transformers`, and
  PyTorch ships no official armv7 wheels. Pi 4 owners on 32-bit
  Raspberry Pi OS need to switch to a 64-bit OS image. Same
  hardware, different OS.
- **Breaking**: container base moved off Home Assistant's published
  `{arch}-base-python:3.12-alpine3.19` and onto the upstream
  `python:3.12-slim-bookworm` (debian/glibc). Reason: PyTorch and
  ONNX Runtime ship no musllinux wheels in 2026, and HA only
  publishes alpine variants of base-python. We bootstrap s6-overlay
  v3 ourselves in the Dockerfile (~10 lines) and drop bashio in
  favour of plain bash + echo-prefixed logs.
- Image is larger (~2-3 GB) due to PyTorch + the pre-baked embedding
  model. Container startup still fast (~5-10 s) because the model
  ships in the image.

### Notes

- The `home-assistant/builder` multi-arch publish workflow is still
  not wired up. Users on first install pay one local container build
  cost (~5-10 minutes on a Pi 4 64-bit, faster on x86); subsequent
  starts are immediate.
- Lint config gains a single ignore: `D213`. It contradicts `D212`
  (already ignored as formatter-incompatible); having both warn
  creates an artificial choice with no real readability impact.

## [0.1.1] - 2026-05-02

Maintenance release — consolidates the five Dependabot bumps that
arrived right after the v0.1.0 initial push.

### Changed

- Bump `fastapi` from 0.115.6 to 0.136.1 (top-level + add-on requirements).
- Bump `uvicorn` from 0.32.1 to 0.46.0 (top-level + add-on requirements).
- Bump `pytest` constraint from `<9` to `<10` (test requirements).
- Bump `docker/build-push-action` from v6 to v7 (CI smoke build).
- Bump `docker/setup-buildx-action` from v3 to v4 (CI smoke build).

### Notes

- All bumps were merged in one consolidated PR rather than five
  individual ones to keep `main` history compact and reduce
  rebase-cascade noise on the open Dependabot PRs.
- No code changes — the 7-test suite stays green against the new
  FastAPI/uvicorn versions.

## [0.1.0] - 2026-05-02

Initial Stage 0 skeleton release.

### Added

- HACS add-on repository scaffolding (`repository.yaml` + `bookstack-rag/`
  subdirectory containing the actual add-on).
- HA add-on manifest (`bookstack-rag/config.yaml`) with one option
  (`bookstack_export_path`, default `/config/bookstack_export`),
  read-only `/config` mount, ingress on port 8000.
- Multi-arch base-image pinning in `bookstack-rag/build.yaml`
  (amd64, aarch64, armv7 — all on
  `ghcr.io/home-assistant/{arch}-base-python:3.12-alpine3.19`).
- s6-overlay v3 long-run service supervising the FastAPI process.
- Minimal FastAPI application with `GET /api/status` returning
  `{status, export_path, markdown_files}` so users can verify the
  add-on can see the export folder produced by the sister integration.
- DE + EN translations for the configuration option.
- 7 unit tests covering the config loader (explicit path, missing file,
  empty option, env-var override) and the status endpoint (empty dir,
  recursive `.md` count, missing dir).
- CI workflows: ruff lint, pytest, smoke amd64 docker build on every
  push and pull request.
- Dependabot configured for pip, github-actions, and docker
  ecosystems on a daily cadence.
- README in EN + DE, slim `CLAUDE.md` pointing at the canonical
  briefing documents, MIT `LICENSE`, `CONTRIBUTING.md`, and standard
  GitHub issue templates (bug + feature request).

### Notes

- This release deliberately does **not** include the
  `home-assistant/builder` multi-arch publishing workflow nor the
  HACS validation action; both come once the build is genuinely
  load-bearing (Stage 1+, when `sentence-transformers` and `qdrant`
  enter the dependency closure).
- Indexing, embedding, RAG and the web UI all land in v0.2.0+.

[Unreleased]: https://github.com/dibi73/ha-bookstack-rag-addon/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/dibi73/ha-bookstack-rag-addon/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/dibi73/ha-bookstack-rag-addon/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/dibi73/ha-bookstack-rag-addon/releases/tag/v0.1.0
