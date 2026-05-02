# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/dibi73/ha-bookstack-rag-addon/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/dibi73/ha-bookstack-rag-addon/releases/tag/v0.1.0
