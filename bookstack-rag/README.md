# BookStack RAG

Local Retrieval-Augmented-Generation (RAG) over the Markdown export
produced by the
[`ha-bookstack-sync`](https://github.com/dibi73/ha-bookstack-sync)
integration.

> ⏱️ **Erstinstallation dauert 5-15 Minuten** (lokaler Container-Build mit
> PyTorch + Embedding-Modell-Pre-Download). Folgende Updates sind schnell.
> v0.5.0+ wird vorgebaute Images über ghcr.io ausliefern und das
> Erstinstall-Erlebnis auf ~2 Min reduzieren.

## Stage 3 — v0.4.0

Built-in vanilla web UI plus source-link enrichment. Open the add-on
panel in Home Assistant, ask a question, read the streamed answer with
inline links jumping back to BookStack (for the doc) or to the HA
frontend (to edit the device directly).

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

### Source links (off by default)

| Option | Description |
|---|---|
| `bookstack_base_url` | Public BookStack URL. Empty skips BookStack source links. |
| `homeassistant_base_url` | Public Home Assistant URL. Empty skips HA deep-links. |

## Endpoints

- Static UI at `/` (mounted under HA Ingress)
- `GET /api/status` — readiness + counts + `llm_configured` flag
- `POST /api/query` — body `{text, top_k?, conversation_id?, stream?}`
- `POST /api/reindex` — manual reconcile sweep
- `GET /api/conversations` — list summaries
- `GET /api/conversations/{id}` — full history
- `DELETE /api/conversations/{id}` — delete conversation

## Detailed docs

See [`DOCS.md`](DOCS.md).
