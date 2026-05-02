# BookStack RAG

Local Retrieval-Augmented-Generation (RAG) over the Markdown export
produced by the
[`ha-bookstack-sync`](https://github.com/dibi73/ha-bookstack-sync)
integration.

## Stage 1 — v0.2.0

Indexing + retrieval are live. The add-on watches the export folder,
embeds Markdown files locally, stores vectors in an in-container
Qdrant sidecar, and answers `/api/query` with the top-K matching
documents. LLM integration comes in v0.3.0.

## Configuration

| Option | Default | Description |
|---|---|---|
| `bookstack_export_path` | `/config/bookstack_export` | Path inside the container where the Markdown export lives. |
| `embedding_model` | `nomic-ai/nomic-embed-text-v1.5` | sentence-transformers model. Default is pre-baked into the image. |
| `top_k` | `5` | Default number of `/api/query` hits. Range 1-50. |

## Endpoints

- `GET /api/status` — `{status, export_path, markdown_files, indexed}`
- `POST /api/query` — body `{text, top_k?}`, returns ranked hits
- `POST /api/reindex` — manual full reconcile sweep

## Detailed docs

See [`DOCS.md`](DOCS.md).
