# BookStack RAG — Documentation

This page is rendered inside the Home Assistant Add-on UI.

## What this add-on does

It indexes the Markdown export produced by the sister integration
[`ha-bookstack-sync`](https://github.com/dibi73/ha-bookstack-sync) and
makes that documentation queryable in natural language.

The full pipeline (built up across stages):

1. **Watch** `<config>/bookstack_export/*.md` for changes.
2. **Embed** each Markdown file with a local embedding model
   (`nomic-embed-text`, 768-dim) running on CPU.
3. **Store** vectors plus YAML-frontmatter metadata in a local Qdrant
   instance with persistent disk storage.
4. **Query** — user question is embedded, top-k matches retrieved from
   Qdrant, then sent as context to a configurable OpenAI-compatible LLM
   endpoint.
5. **Display** the streamed answer plus links back to the originating
   BookStack pages, in a simple HA-Ingress web UI.

## Current stage

**Stage 0 — v0.1.0.** Only the FastAPI skeleton exists; no embedding, no
LLM, no UI yet. The status endpoint is the smoke test that confirms the
container starts, finds the export folder, and counts files.

## Configuration options (Stage 0)

### `bookstack_export_path`

- **Type**: `str`
- **Default**: `/config/bookstack_export`
- **Description**: Path inside the container where the Markdown export
  produced by the sister integration lives. The default works if you
  haven't customised the integration's export path.

### Future options (placeholder — added in later stages)

- `llm_base_url` — the OpenAI-compatible endpoint
- `llm_api_key` — credentials (stored as `password`, masked in the UI)
- `llm_model` — model name (e.g. `qwen2.5:7b`, `gpt-4o-mini`, …)
- `top_k` — number of context documents to retrieve per query
- `embedding_model` — override of the default `nomic-embed-text`

These will appear in the add-on options dialog as the corresponding
stages ship.

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/status` | Health check + Markdown file count under the configured export path. |

## Permissions

- `map: - config:ro` — the add-on mounts your HA `config/` folder at
  `/config` **read-only**. It cannot modify your Home Assistant config,
  cannot write back to BookStack, and cannot reach the HA Supervisor API.

## Logs

Available in *Settings → Add-ons → BookStack RAG → Log* tab. The add-on
uses `bashio::log.info` for service-level messages and standard Python
logging via uvicorn for request lines.

## Troubleshooting

**"markdown_files": 0** — the configured `bookstack_export_path` doesn't
contain any `.md` files. Check that the sister integration is installed,
configured, and has been triggered at least once
(*Developer Tools → Actions → bookstack_sync.export_markdown*).

**Status `no_export_dir`** — the path doesn't exist inside the container.
Verify the path matches what the integration writes to. The default of
`/config/bookstack_export` corresponds to `<HA-config>/bookstack_export`
on the host.

## Source

Source code, issue tracker, contributing guide:
<https://github.com/dibi73/ha-bookstack-rag-addon>.
