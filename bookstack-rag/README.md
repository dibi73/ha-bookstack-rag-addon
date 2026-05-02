# BookStack RAG

Local Retrieval-Augmented-Generation (RAG) over the Markdown export
produced by the
[`ha-bookstack-sync`](https://github.com/dibi73/ha-bookstack-sync)
integration.

## Stage 2 — v0.3.0

Indexing + retrieval (v0.2.0) plus LLM-synthesised answers. The add-on
wires an embedded Qdrant sidecar through any OpenAI-compatible
chat-completions endpoint (Ollama, OpenAI, Anthropic, Gemini,
self-hosted vLLM/LM Studio). Multi-turn chat is persisted in SQLite and
answers can stream over Server-Sent Events. Web UI follows in v0.4.0.

## Configuration

### Indexing

| Option | Default | Description |
|---|---|---|
| `bookstack_export_path` | `/config/bookstack_export` | Markdown-export path inside the container. |
| `embedding_model` | `nomic-ai/nomic-embed-text-v1.5` | sentence-transformers model. |
| `top_k` | `5` | Default retrieval hits per query. |

### LLM (off by default)

| Option | Description |
|---|---|
| `llm_base_url` | OpenAI-compatible endpoint. Empty disables LLM. |
| `llm_api_key` | Bearer token (password field). |
| `llm_model` | Model identifier. Empty disables LLM. |
| `llm_timeout` | Per-request timeout in seconds. Default 60. |
| `max_turns` | History truncation — last N user/assistant pairs. Default 20. |
| `system_prompt` | Optional system-prompt override. |

## Endpoints

- `GET /api/status` — readiness + counts + `llm_configured` flag
- `POST /api/query` — body `{text, top_k?, conversation_id?, stream?}`
- `POST /api/reindex` — manual reconcile sweep
- `GET /api/conversations` — list summaries
- `GET /api/conversations/{id}` — full history
- `DELETE /api/conversations/{id}` — delete conversation

## Detailed docs

See [`DOCS.md`](DOCS.md).
