# BookStack RAG — Home Assistant Add-on

> Available in: **English** · [Deutsch](README.de.md)

A Home Assistant add-on that indexes the Markdown export produced by the
sister integration
[`ha-bookstack-sync`](https://github.com/dibi73/ha-bookstack-sync) and
makes your smart-home documentation queryable in natural language —
through any OpenAI-compatible LLM endpoint (Ollama, OpenAI, Anthropic via
proxy, …) and a simple web UI for the whole household.

## Status

**Stage 3 — v0.5.0**.

Stage 3 is feature-complete: built-in web UI plus inline source-link
enrichment, non-blocking cold-start (since v0.4.5), multi-arch
pre-built images on ghcr.io (since v0.5.0). Open the add-on panel in
Home Assistant, type a question, read the streamed answer with
clickable links jumping straight back to BookStack (for the doc) or
to the HA frontend (to edit the actual device).

What ships:
- Everything from v0.3.0 (LLM integration, multi-turn chat, SSE
  streaming, conversation persistence).
- **Vanilla SPA web UI** at `/` — single HTML/CSS/JS bundle, no build
  step, mobile-responsive, light/dark theme follows system. Streams
  answers token by token, renders Markdown safely (HTML-escape-first
  before pattern-match).
- **Source-link enrichment**: configure `bookstack_base_url` and
  `homeassistant_base_url`, and each `<doc>` context block in the
  LLM prompt gets a `Sources: [BookStack](...) · [HA Gerät](...)`
  line. The LLM weaves them into its answer; the UI renders them as
  clickable links automatically.

> 64-bit OS required since v0.2.0 (no armv7 / 32-bit Pi OS support —
> PyTorch ships no armv7 wheels).

## How the pieces fit together

```
ha-bookstack-sync (HACS integration, separate repo)
        │
        │  writes Markdown export to <config>/bookstack_export/
        ▼
THIS ADD-ON
        │
        │  watches the export, embeds it locally (nomic-embed-text),
        │  stores vectors in an embedded Qdrant instance,
        │  forwards user queries to a configured OpenAI-compatible LLM
        ▼
Web UI through Home Assistant Ingress
```

## Installation (HACS, recommended)

1. **Settings → Add-ons → Add-on Store → ⋮ (top-right) → Repositories**
2. Paste `https://github.com/dibi73/ha-bookstack-rag-addon` and click **Add**.
3. The "BookStack RAG" add-on now appears in the store. Click **Install**.
4. Configure the export path (default: `/config/bookstack_export`, which
   matches the integration's default).
5. **Start** the add-on. Since v0.5.0 Supervisor pulls a pre-built
   image from `ghcr.io/dibi73/{arch}-bookstack-rag-addon` (~2 min on
   a Pi 4/5 64-bit, faster on x86) instead of building locally. The
   Ingress panel link appears in the HA sidebar; the panel loads
   immediately and the SPA polls `/api/status` for the actual
   readiness phase (embedder load → collection setup → indexing →
   ready, typically 30–60 s on aarch64 from a fresh container).

## Configuration

### Indexing

| Option | Default | Description |
|---|---|---|
| `bookstack_export_path` | `/config/bookstack_export` | Path inside the container where the Markdown export lives. |
| `embedding_model` | `nomic-ai/nomic-embed-text-v1.5` | sentence-transformers model used for embeddings. The default is pre-baked into the image. |
| `top_k` | `5` | Default number of retrieval hits per query. |

### LLM (off by default)

| Option | Description |
|---|---|
| `llm_base_url` | OpenAI-compatible chat-completions endpoint. Empty disables LLM. |
| `llm_api_key` | Bearer token. Stored as a password field. Local Ollama leaves this empty. |
| `llm_model` | Model identifier. Empty disables LLM. |
| `llm_timeout` | Per-request timeout in seconds. Default 60. |
| `max_turns` | Conversation history truncation — last N user/assistant pairs sent to LLM. Default 20. |
| `system_prompt` | Optional override for the built-in bilingual system prompt. |

### Source links (off by default)

| Option | Description |
|---|---|
| `bookstack_base_url` | Public URL of your BookStack instance, e.g. `http://bookstack.lokal:6875`. Used to build `[BookStack](.../link/<page-id>)` links the LLM can cite. |
| `homeassistant_base_url` | Public URL of your HA instance, e.g. `http://homeassistant.local:8123`. Used to build `/config/devices/device/<id>` (etc.) deep-links so the LLM and the UI can offer "edit this device" jumps. |

#### LLM endpoint examples

```yaml
# Ollama on a LAN host (recommended — local, private, free)
llm_base_url: http://192.168.1.100:11434/v1
llm_api_key: ""
llm_model: qwen2.5:7b

# OpenAI
llm_base_url: https://api.openai.com/v1
llm_api_key: sk-...
llm_model: gpt-4o-mini

# Anthropic (their OpenAI-compat layer)
llm_base_url: https://api.anthropic.com/v1
llm_api_key: sk-ant-...
llm_model: claude-haiku-4-5

# Google Gemini (OpenAI-compat endpoint)
llm_base_url: https://generativelanguage.googleapis.com/v1beta/openai
llm_api_key: AIza...
llm_model: gemini-2.0-flash
```

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/status` | `{status, export_path, markdown_files, indexed, llm_configured}` |
| `POST` | `/api/query` | Body: `{text, top_k?, conversation_id?, stream?}`. Returns either a JSON `{query, top_k, hits, conversation_id?, answer?}` or an SSE stream of `hit` / `delta` / `done` events. |
| `POST` | `/api/reindex` | Full reconcile sweep. Returns `{indexed, unchanged, skipped, failed, total}`. |
| `GET` | `/api/conversations` | List of recent chats with title preview + message count. |
| `GET` | `/api/conversations/{id}` | Full message history of one conversation. |
| `DELETE` | `/api/conversations/{id}` | Hard-delete one conversation. |

All endpoints are reachable through the HA Ingress panel.

## Roadmap

- [x] **Stage 0 (v0.1.0)** — skeleton add-on, CI, status endpoint.
- [x] **Stage 1 (v0.2.0)** — file watcher, embedding (nomic-embed-text),
  Qdrant index, `/api/query` returning top-k documents.
- [x] **Stage 2 (v0.3.0)** — LLM integration with multi-turn chat and
  Server-Sent-Events streaming over any OpenAI-compatible endpoint.
- [x] **Stage 3 (v0.4.0)** — Vanilla web UI with streaming Markdown
  rendering, conversation history sidebar, mobile-responsive layout,
  inline source-link citations.
- [ ] **Stage 4+** — HA Conversation platform integration (voice
  control), multi-LLM routing, source re-ranking.

## Non-goals

- **No write-back to HA or BookStack.** This add-on is a read-only
  consumer of the Markdown export. Documentation lives in BookStack
  (managed by the sister integration); the add-on never modifies it.
- **No own LLM server.** You bring your own LLM endpoint (local Ollama,
  cloud API, …). The add-on configures, it doesn't host.
- **No multi-tenant / multi-user system.** One household, one
  installation.

## Hardware & requirements

| Setup | Verdict |
|---|---|
| Raspberry Pi 4 (4 GB, **64-bit OS**) | ✅ embedding works (slow); LLM should be remote |
| Synology / x86 NAS | ✅ embedding fine; small local LLM possible |
| Local PC with GPU | ✅ run Ollama there, point the add-on at it |
| Pi 4 (32-bit OS) or Pi 3 | ❌ since v0.2.0: armv7 is no longer supported (no PyTorch wheels) |
| Pi 4 (2 GB) | ⚠️ marginal — embedding model alone needs ~500 MB |

Minimum RAM for the add-on itself (without LLM): ~1 GB. Supported architectures: **amd64**, **aarch64** (so Pi 4/5 must run a 64-bit OS).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Lint and tests must be green;
new behaviour needs tests.

## Sister project

[`ha-bookstack-sync`](https://github.com/dibi73/ha-bookstack-sync) — the
HACS integration that produces the Markdown export this add-on consumes.
Both projects evolve independently; you need both for the full system.

## License

MIT — see [LICENSE](LICENSE).
