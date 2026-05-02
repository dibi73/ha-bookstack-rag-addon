# BookStack RAG — Documentation

This page is rendered inside the Home Assistant Add-on UI.

## What this add-on does

It indexes the Markdown export produced by the sister integration
[`ha-bookstack-sync`](https://github.com/dibi73/ha-bookstack-sync) and
makes that documentation queryable in natural language.

The full pipeline:

1. **Watch** `<config>/bookstack_export/*.md` for changes (file-system
   events, debounced 500 ms).
2. **Embed** each Markdown file with a local embedding model
   (`nomic-ai/nomic-embed-text-v1.5`, 768 dimensions, CPU-only).
3. **Store** vectors plus YAML-frontmatter metadata in an embedded
   Qdrant sidecar with persistent disk storage at `/data/qdrant/`.
4. **Query** — user question is embedded, top-K matches retrieved
   from Qdrant, returned to the caller. LLM-side answer synthesis
   lands in v0.3.0; until then the add-on returns the documents
   themselves.

## Current stage

**Stage 1 — v0.2.0.** Indexing, retrieval, watcher, manual reindex
are wired up. LLM integration and the web UI are next.

> ⚠️ **v0.2.0 dropped armv7.** PyTorch (transitive via
> `sentence-transformers`) ships no armv7 wheels, so 32-bit Pi OS
> installations are no longer viable. Switch your Pi 4 to a 64-bit OS
> image (same hardware) and re-install the add-on.

## Configuration options

### `bookstack_export_path`

- **Type**: `str`
- **Default**: `/config/bookstack_export`
- **Description**: Path inside the container where the Markdown
  export produced by the sister integration lives.

### `embedding_model`

- **Type**: `str?`
- **Default**: `nomic-ai/nomic-embed-text-v1.5`
- **Description**: sentence-transformers model used to embed
  Markdown content and user queries. The default is pre-downloaded
  into the image — first start is fast. Pointing this at a different
  model triggers a one-time download (~500 MB to several GB
  depending on the model) on first start.

### `top_k`

- **Type**: `int(1,50)?`
- **Default**: `5`
- **Description**: How many matching documents `/api/query` returns
  when the caller does not pass an explicit `top_k` field. Callers
  can always override per-request up to 50.

### Future options (v0.3.0+)

- `llm_base_url`, `llm_api_key`, `llm_model` — point the add-on at an
  OpenAI-compatible chat-completions endpoint (Ollama, OpenAI,
  Anthropic via proxy, …).

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/status` | Health check, Markdown file count, Qdrant document count. |
| `POST` | `/api/query` | Body: `{text: "...", top_k?: 1-50}`. Returns ranked hits. |
| `POST` | `/api/reindex` | Full reconcile sweep. Returns `{indexed, unchanged, skipped, failed, total}`. |

### `/api/query` example

Request:

```json
POST /api/query
{
  "text": "What does the hallway motion sensor do?",
  "top_k": 3
}
```

Response:

```json
{
  "query": "What does the hallway motion sensor do?",
  "top_k": 3,
  "hits": [
    {
      "doc_id": "1234567890",
      "score": 0.842,
      "title": "Bewegungsmelder Gang",
      "content_preview": "## Bewegungsmelder Gang\n\nAqara Motion Sensor P1...",
      "bookstack_page_id": 142
    },
    ...
  ]
}
```

The `bookstack_page_id` lets you build deep-links back to the
originating BookStack page.

## Permissions

- `map: - config:ro` — the add-on mounts your HA `config/` folder at
  `/config` **read-only**. It cannot modify your Home Assistant
  config, cannot write back to BookStack, and cannot reach the HA
  Supervisor API.
- The Qdrant sidecar inside the container is bound to `127.0.0.1`
  only — it is not reachable from outside the add-on container.

## Persistence

- Qdrant collection lives in `/data/qdrant/storage/` (HA-Supervisor
  add-on data volume). Survives restarts, updates, host reboots.
- Idempotency: the SHA-256 of every Markdown file is stored as
  Qdrant payload. Restart-safe — the startup scan only re-embeds
  files whose hash changed.

## Logs

Available in *Settings → Add-ons → BookStack RAG → Log* tab. Two
service streams (qdrant + api) are interleaved with `bashio` info
prefixes for service-level events and standard Python logging via
uvicorn for HTTP request lines.

## Troubleshooting

**`/api/query` returns 503** — the embedder or Qdrant index isn't
ready yet. Wait ~10 s after first start (sentence-transformers loads
the model, Qdrant initialises its on-disk collection), then retry.

**`indexed: 0` after first start with files in the export folder** —
check the log for parse errors. The reconcile pipeline logs every
file it skips or fails on.

**"markdown_files": 0** — the `bookstack_export_path` is empty.
Verify the sister integration is installed and exporting (its
`bookstack_sync.export_markdown` action must be enabled).

**Hash mismatches after a config restore** — if you replace
`/config/bookstack_export/` with a backup that uses different file
encodings (CRLF vs LF), every file's hash changes. Trigger one full
re-index via `POST /api/reindex`; subsequent watcher events stay
incremental.

## Source

Source code, issue tracker, contributing guide:
<https://github.com/dibi73/ha-bookstack-rag-addon>.
