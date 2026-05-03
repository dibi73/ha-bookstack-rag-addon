# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.4] - 2026-05-03

Hotfix on top of v0.4.3: the add-on now boots cleanly (container,
qdrant sidecar, embedder, watcher all up), but on a freshly-installed
instance with hundreds of Markdown files the lifespan hangs in the
synchronous initial reconcile sweep. Each file needs ~1-2 s on
aarch64 CPU, and lifespan blocks `uvicorn` from binding the port —
HA Ingress returns 502 for the entire startup duration.

### Fixed

- `app/main.py`: the initial `pipeline.reconcile_all()` is now
  dispatched as an `asyncio.create_task` running via
  `asyncio.to_thread` so the lifespan yields within seconds. Uvicorn
  binds the port immediately, the Web UI loads, and queries work
  against a partially-populated index that fills in the background.
  The watcher is started **before** the reconcile task, so any
  filesystem events arriving during the sweep are still handled —
  consistency is preserved through the pipeline's hash-based
  idempotency.

### Notes

- 91/91 tests stay green. The lifespan function is not directly
  exercised by the test suite (tests build their own minimal apps);
  the change is pure orchestration.
- Existing `/api/query` and `/api/status` endpoints behave unchanged
  while reconcile is in progress — `markdown_files` reports the on-
  disk count, `indexed` reports the current Qdrant collection size
  (which grows during the sweep). Queries return whatever is already
  in the index.
- On graceful shutdown the background task is cancelled and awaited.

## [0.4.3] - 2026-05-03

Hotfix on top of v0.4.2: the add-on now passes schema validation and
starts uvicorn, but the qdrant sidecar fails to launch with

```
/usr/local/bin/qdrant: error while loading shared libraries:
libunwind-ptrace.so.0: cannot open shared object file
```

We `COPY --from=qdrant_source /qdrant/qdrant ...` only the binary
itself, not its runtime libraries. The upstream `qdrant/qdrant` image
installs `libunwind8` (which contains `libunwind-ptrace.so.0`); our
slim base did not.

### Fixed

- `bookstack-rag/Dockerfile`: add `libunwind8` to the
  `apt-get install` line. The package contains
  `libunwind-ptrace.so.0` plus the rest of the libunwind family that
  qdrant needs for stack-trace generation.

### Changed

- `app/embedder.py`: prefer
  `SentenceTransformer.get_embedding_dimension()` when available
  (newer sentence-transformers releases) and fall back to the
  deprecated `get_sentence_embedding_dimension()` otherwise. Silences
  the runtime FutureWarning we saw next to the qdrant errors.

### Notes

- 91/91 tests stay green. FakeEmbedder is unaffected because it has
  its own `vector_size` implementation that doesn't touch
  sentence-transformers.
- The CI smoke build still does not actually run the container, which
  is why this class of "binary fails to start because of a missing
  shared library" bug slipped through. v0.5.0's plan to publish
  prebuilt images via `home-assistant/builder` will run a real
  container during the publish step and catch this category at CI
  time. Until then, real-host-install testing is the only gate.

## [0.4.2] - 2026-05-03

Hotfix on top of v0.4.1: the v0.4.1 image now builds successfully on real
HA-Supervisor instances (debian + apt-get + PyTorch + model pre-download
complete in ~5-6 min on aarch64), but the add-on refused to **start**
with a schema-validation error:

```
App ... has invalid options: expected a URL. Got {... 'bookstack_base_url': '', 'homeassistant_base_url': ''}
```

### Fixed

- `bookstack-rag/config.yaml` schema: `bookstack_base_url` and
  `homeassistant_base_url` change from `url?` to `str?`. The `?` suffix
  in HA add-on schemas means *„may be omitted from the dict"*, NOT
  *„may be empty"*. An empty string `""` is treated as a present
  value that fails URL-format validation. `str?` accepts both empty
  and any string; the Python runtime in `app/llm.py:build_source_links`
  already validates non-empty before constructing URLs.

### Notes

- No code changes — only the schema annotation. The 91-test suite
  stays green.
- `llm_base_url` was already declared as `str?` (correctly), which is
  why no LLM-empty bug triggered earlier. Same model now applies to
  the source-link URL fields.

## [0.4.1] - 2026-05-02

Hotfix for the v0.4.0 install path. First-install attempts on real
Home Assistant instances failed with `apt-get: not found` because the
Supervisor's local-build path **ignores `build.yaml`** and injects its
own alpine base image (`ghcr.io/home-assistant/base:latest`) via the
`BUILD_FROM` build-arg. Our Dockerfile assumed `BUILD_FROM` would be
the value pinned in `build.yaml` — it never reaches the Supervisor.

### Fixed

- **Dockerfile hard-codes its base image** as `python:3.12-slim-bookworm`
  instead of consuming `${BUILD_FROM}`. Supervisor's BUILD_FROM
  injection no longer breaks the build, and the GitHub-Actions smoke
  build matches the Supervisor-local-build path bit-for-bit.

### Changed

- `bookstack-rag/config.yaml` — `description:` extended with a hint
  that first install builds locally for 5-15 min so users know what to
  expect before they hit Install.
- `bookstack-rag/DOCS.md` and `bookstack-rag/README.md` — prominent
  ⏱️ warning at the top about first-install duration, disk and RAM
  requirements during the build.
- `bookstack-rag/build.yaml` — left in place but with an explanatory
  comment noting that Supervisor ignores it; only consumed by the
  `home-assistant/builder` action that v0.5.0+ will wire up.
- `.github/workflows/build.yml` — drop the now-redundant
  `BUILD_FROM=python:3.12-slim-bookworm` build-arg.

### Notes

- v0.5.0 is queued as the proper fix: publish multi-arch images to
  `ghcr.io` via `home-assistant/builder` action on each tag, add
  `image:` to `config.yaml`. Supervisor will then pull instead of
  building locally — first install drops from 5-15 min to ~2 min.
- No code or behaviour change. All 91 tests still pass.

## [0.4.0] - 2026-05-02

Stage 3 — the add-on now ships with a built-in single-page web UI plus
the source-link enrichment that lets the LLM cite BookStack pages and
Home Assistant deep-links inline in its answers.

### Added

- **Vanilla SPA web UI** at `/` (mounted at the add-on's ingress
  panel root). Pure HTML/CSS/JS, no build step, no npm. Layout:
  - Composer at the bottom (textarea + Enter to send,
    Shift+Enter for newline).
  - Conversation column with user bubbles, assistant bubbles
    rendered as Markdown, plus a collapsible per-answer hits list
    showing the retrieved documents with score + preview.
  - Sidebar with the chat history (most-recently-updated first,
    per-row delete button), a "+ Neuer Chat" button, and status
    pills showing index size + LLM-configured state.
  - Mobile-responsive: sidebar collapses to an overlay with a
    hamburger toggle when the viewport drops below 720 px.
  - Light / dark themes follow `prefers-color-scheme`.
- **Streaming consumption** in the UI via `fetch` + ReadableStream
  (`EventSource` is GET-only). Each `event: delta` re-renders the
  in-progress assistant bubble; the streaming cursor disappears on
  `event: done`. Source hits arrive on `event: hit` and are
  attached to the bubble's hits panel.
- **Tiny pure-JS Markdown renderer** (~80 lines) with HTML-escape-
  first-then-pattern-match flow. Covers paragraphs, headers,
  fenced code, inline code, bold, italic, links, lists. Links go
  through a safe-href whitelist (`http://`, `https://`, relative).
  The LLM cannot inject `<script>` because everything is escaped
  before any tags are introduced.
- **Source-link enrichment** in the LLM prompt: when both
  `bookstack_base_url` and / or `homeassistant_base_url` are
  configured and the hit's frontmatter carries the matching id
  fields, each `<doc>` block in the prompt gets a trailing
  `Sources: [BookStack](...) · [HA Gerät](...)` line. The LLM is
  instructed to cite those Markdown links sparingly so the user
  can jump to the BookStack page (for context) or to the HA UI
  (to edit the actual device, automation, area, …).
- New configuration options: `bookstack_base_url` (URL, optional)
  and `homeassistant_base_url` (URL, optional).
- `HA_DEEP_LINK_PATTERNS` constant in `app/llm.py` mirrors the
  per-object-kind URL table from Architektur §3 (device, area,
  automation, script, scene, integration, entity, helper).

### Changed

- Default system prompt extended with one paragraph telling the
  LLM how to use the new "Sources" lines.
- `app.main.create_app()` mounts `app/ui/` as static files at `/`
  when the directory exists. The mount is a no-op for tests that
  build their own minimal app.

### Notes

- 91 tests (was 76 in v0.3.0). The 15 new tests cover
  `build_source_links` for every `ha_object_kind`, base-URL
  trailing-slash normalisation, prompt-builder source-line
  inclusion, end-to-end URL flow through `/api/query` to the
  FakeLLMClient, plus three static-file-serving smoke tests for
  the SPA bundle.
- Web UI is **not** unit-tested — vanilla JS, manual smoke testing
  is the intentional Stage-3 strategy. Stage 4+ may introduce
  Playwright if the UI grows.
- HA Ingress: all client-side fetch calls use relative URLs
  (`api/query`, `api/conversations/...`) so the SPA works correctly
  whether served at the add-on root or under
  `/api/hassio_ingress/<token>/`.

## [0.3.0] - 2026-05-02

Stage 2 — the add-on now synthesises natural-language answers via a
configurable OpenAI-compatible LLM endpoint. Multi-turn conversations
are persisted in SQLite and the answer can stream over Server-Sent
Events for live token rendering.

### Added

- `LLMClient` (and `FakeLLMClient` for tests) speaking the
  `/v1/chat/completions` dialect supported by OpenAI, Anthropic
  (their 2024 OpenAI-compatibility API), Google Gemini's OpenAI-compat
  endpoint, Ollama, vLLM, LM Studio and most self-hosted servers.
- `POST /api/query` extended:
  - Accepts `conversation_id` to continue a prior chat.
  - Accepts `stream: true` to receive Server-Sent Events instead of
    a single JSON response. The event sequence is `event: hit` per
    retrieval result, then `event: delta` per content chunk, then
    `event: done` carrying the conversation id.
  - Returns `{conversation_id, answer}` alongside the hits when an
    LLM is configured. When no LLM is configured the endpoint stays
    in v0.2.0 retrieval-only mode and returns just the hits — fully
    backwards-compatible.
- `ConversationStore` backed by SQLite at `/data/conversations.db`.
  Schema is auto-created on first start; CASCADE delete on
  conversations cleans up child messages.
- New endpoints:
  - `GET /api/conversations` — list summaries (id, title preview,
    message count, timestamps), most-recently-updated first.
  - `GET /api/conversations/{id}` — full message history.
  - `DELETE /api/conversations/{id}` — hard-delete one conversation.
- `GET /api/status` now also reports `llm_configured: true|false`
  so the upcoming web UI can hide the LLM-only controls when no
  endpoint is set.
- Built-in bilingual (DE/EN) system prompt with prompt-injection
  defence: retrieval hits are wrapped in `<doc>` marker tags so the
  LLM cannot confuse retrieved content with user instructions
  (Anforderungsdokument §6.1).
- Conversation-history truncation: only the last ``max_turns``
  user/assistant pairs reach the LLM, capping context-window growth
  on long chats.
- Six new add-on options: `llm_base_url`, `llm_api_key` (password
  field), `llm_model`, `llm_timeout`, `max_turns`, `system_prompt`.
  All optional; LLM stays disabled until `llm_base_url` and
  `llm_model` are both set (HARD RULE §3.6 — opt-in for cost-/
  privacy-relevant features).

### Changed

- `httpx` is now a runtime dependency (was test-only). Pinned to
  0.28.1 so streaming behaviour cannot regress silently.

### Notes

- 76 tests (was 42 in v0.2.0) covering the new LLM client (via
  httpx MockTransport, no real network calls), conversation store,
  and the new query/conversation endpoints in all three modes
  (retrieval-only, one-shot LLM, streaming SSE).
- Pi 4 (64-bit) impact: each turn adds one SQLite write (sub-ms),
  one embedding pass on the new question (~1 s, same as v0.2.0),
  one LLM call (latency dominated by the remote endpoint). Memory
  stays flat — only the active conversation is in RAM.

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

[Unreleased]: https://github.com/dibi73/ha-bookstack-rag-addon/compare/v0.4.4...HEAD
[0.4.4]: https://github.com/dibi73/ha-bookstack-rag-addon/compare/v0.4.3...v0.4.4
[0.4.3]: https://github.com/dibi73/ha-bookstack-rag-addon/compare/v0.4.2...v0.4.3
[0.4.2]: https://github.com/dibi73/ha-bookstack-rag-addon/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/dibi73/ha-bookstack-rag-addon/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/dibi73/ha-bookstack-rag-addon/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/dibi73/ha-bookstack-rag-addon/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/dibi73/ha-bookstack-rag-addon/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/dibi73/ha-bookstack-rag-addon/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/dibi73/ha-bookstack-rag-addon/releases/tag/v0.1.0
