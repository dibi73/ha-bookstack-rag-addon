# BookStack RAG

Ask questions about your smart home in plain language and get answers
straight from your own documentation — no cloud service required.

This add-on indexes the Markdown export produced by the sister
integration
[`ha-bookstack-sync`](https://github.com/dibi73/ha-bookstack-sync)
(a local mirror of your BookStack wiki) and makes it searchable
through a built-in chat UI. Search itself runs fully offline; handing
the retrieved context to an LLM for a written-out answer is optional
and off by default.

**Requirements**: `ha-bookstack-sync` must already be exporting to
`<config>/bookstack_export/`. 64-bit OS (Pi 4/5 need a 64-bit image),
~3 GB free disk space for the add-on image, ~2 GB free RAM at runtime.

## Getting started

1. Install and configure [`ha-bookstack-sync`](https://github.com/dibi73/ha-bookstack-sync)
   first, if you haven't already, so it's exporting your BookStack
   docs to Markdown.
2. Install and start this add-on.
3. Open *Settings → Add-ons → BookStack RAG → Open Web UI* and ask a
   question. Answers can link back to the source BookStack page or the
   matching Home Assistant device/automation page.
4. Optional: set an LLM endpoint under the add-on's "LLM" configuration
   options to get synthesised answers instead of raw search hits.

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
