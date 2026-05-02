# BookStack RAG — Home Assistant Add-on

> Available in: **English** · [Deutsch](README.de.md)

A Home Assistant add-on that indexes the Markdown export produced by the
sister integration
[`ha-bookstack-sync`](https://github.com/dibi73/ha-bookstack-sync) and
makes your smart-home documentation queryable in natural language —
through any OpenAI-compatible LLM endpoint (Ollama, OpenAI, Anthropic via
proxy, …) and a simple web UI for the whole household.

## Status

**Stage 2 — v0.3.0**.

The add-on now synthesises natural-language answers via any
OpenAI-compatible LLM endpoint (Ollama, OpenAI, Anthropic, Gemini,
self-hosted vLLM/LM Studio). Multi-turn chat is persisted, and
streaming-SSE responses let a future web UI render tokens live.

What ships:
- Everything from v0.2.0 (file watcher, local embedding, Qdrant
  sidecar, `/api/reindex`).
- `POST /api/query` extended with `conversation_id` (multi-turn) and
  `stream: true` (SSE).
- Conversation persistence in SQLite at `/data/conversations.db`.
- New endpoints: `GET/DELETE /api/conversations[/{id}]`.
- LLM is **off by default** — set `llm_base_url` and `llm_model` to
  enable. Without them the add-on stays in v0.2.0 retrieval-only mode.

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
5. **Start** the add-on. The Ingress panel link appears in the HA sidebar.

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
- [ ] **Stage 3 (v0.4.0)** — Web UI: input field, answer display, source
  links back to BookStack pages.
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
