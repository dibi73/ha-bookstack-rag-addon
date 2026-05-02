# BookStack RAG

Local Retrieval-Augmented-Generation (RAG) over the Markdown export
produced by the
[`ha-bookstack-sync`](https://github.com/dibi73/ha-bookstack-sync)
integration. Ask your BookStack-documented smart home in natural language;
get answers from a configurable OpenAI-compatible LLM endpoint.

## Stage 0 — v0.1.0

This release ships only the skeleton: a FastAPI server that confirms it
can see the export folder and counts the Markdown files in it. Indexing,
embedding, RAG and the web UI come in v0.2.0+.

## Configuration

| Option | Default | Description |
|---|---|---|
| `bookstack_export_path` | `/config/bookstack_export` | Path inside the container where the Markdown export lives. |

## Endpoints

- `GET /api/status` — `{"status": "ok", "export_path": "...", "markdown_files": N}`

Reachable through the HA Ingress panel.

## Detailed docs

See [`DOCS.md`](DOCS.md).
